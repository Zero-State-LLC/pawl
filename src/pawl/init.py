"""``pawl init``: detect the runner and write a starter config."""

from __future__ import annotations

import json
from pathlib import Path

from pawl.errors import ConfigError

TEMPLATES = {
    "pytest": ("pytest", '["python", "-m", "pytest", "-q"]'),
    "jest": ("jest", '["npx", "jest"]'),
    "vitest": ("vitest", '["npx", "vitest", "run"]'),
    "go": ("go", '["go", "test", "./..."]'),
    "cargo": ("cargo", '["cargo", "test"]'),
}

CONFIG_TEMPLATE = """# Pawl gate definition. Code can only move forward.
# Changes to this file, the baseline, and conftest files need human approval.
# Reference: https://github.com/Zero-State-LLC/pawl/blob/main/docs/CONFIG.md

[pawl]
baseline = "pawl.baseline.json"
debt_log = "PAWL_DEBT.md"
lock_in_ci = true            # in CI, fixed failures must be recorded in the same change

[[suite]]
name = "tests"
adapter = "{adapter}"
command = {command}          # run exactly what CI runs: CI should call 'pawl check'
identity = "ids"             # track which tests fail, not only how many
{preflight}"""

PREFLIGHT_TEMPLATE = """
[preflight]
python = "python"
imports = [{{ module = "{module}", expect_under = "{under}" }}]
"""


def detect(root: Path) -> str:
    """Return the adapter name for the project in ``root``."""
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "vitest" in deps:
            return "vitest"
        if "jest" in deps:
            return "jest"
    if (root / "go.mod").is_file():
        return "go"
    if (root / "Cargo.toml").is_file():
        return "cargo"
    py_markers = ("pyproject.toml", "pytest.ini", "setup.cfg", "setup.py", "conftest.py", "tox.ini")
    if any((root / m).is_file() for m in py_markers) or (root / "tests").is_dir():
        return "pytest"
    raise ConfigError("could not detect a test runner; pass --runner")


def python_package(root: Path) -> tuple[str, str] | None:
    """Find the main import package for the preflight check, if obvious."""
    for base in (root / "src", root):
        if not base.is_dir():
            continue
        pkgs = sorted(
            p.name
            for p in base.iterdir()
            if p.is_dir()
            and (p / "__init__.py").is_file()
            and p.name not in ("tests", "test", "docs")
        )
        if len(pkgs) == 1:
            return pkgs[0], str(base.relative_to(root)) if base != root else "."
    return None


def render_config(root: Path, adapter: str) -> str:
    name, command = TEMPLATES[adapter]
    preflight = ""
    if adapter == "pytest":
        found = python_package(root)
        if found:
            preflight = PREFLIGHT_TEMPLATE.format(module=found[0], under=found[1])
    return CONFIG_TEMPLATE.format(adapter=name, command=command, preflight=preflight)
