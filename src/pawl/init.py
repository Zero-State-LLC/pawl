"""``pawl init``: detect the runner and write a starter config."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

from pawl.errors import ConfigError

TEMPLATES = {
    # pytest command is filled in render_config with sys.executable so init
    # works on hosts that only ship ``python3``.
    "pytest": ("pytest", ""),
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
python = {python}
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
        # Absolute path of the interpreter that ran ``pawl init``. Avoids the
        # ``python`` vs ``python3`` PATH trap on Debian/Ubuntu and macOS.
        command = f'[{json.dumps(sys.executable)}, "-m", "pytest", "-q"]'
        found = python_package(root)
        if found:
            preflight = PREFLIGHT_TEMPLATE.format(
                python=json.dumps(sys.executable),
                module=found[0],
                under=found[1],
            )
    return CONFIG_TEMPLATE.format(adapter=name, command=command, preflight=preflight)


PYPI_JSON = "https://pypi.org/pypi/pawl-gate/{version}/json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def is_sha256(value: str) -> bool:
    return bool(_SHA256.match(value))


def pypi_hashes(version: str, timeout: float = 10.0) -> tuple[str, str]:
    """Return (wheel sha256, sdist sha256) of a pawl-gate release on PyPI.

    Raises ConfigError when PyPI cannot be reached or the release is incomplete,
    so the caller can fall back to placeholders that make pip fail closed.
    """
    url = PYPI_JSON.format(version=version)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
            data = json.load(resp)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"could not read {url}: {exc}") from exc
    found: dict[str, str] = {}
    for entry in data.get("urls", []) if isinstance(data, dict) else []:
        kind = entry.get("packagetype")
        digest = (entry.get("digests") or {}).get("sha256", "")
        if kind in ("bdist_wheel", "sdist") and is_sha256(digest) and kind not in found:
            found[kind] = digest
    if set(found) != {"bdist_wheel", "sdist"}:
        raise ConfigError(f"pawl-gate {version} on PyPI has no wheel and sdist hashes")
    return found["bdist_wheel"], found["sdist"]
