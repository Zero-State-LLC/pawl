"""Load and validate ``pawl.toml``."""

from __future__ import annotations

import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pawl.errors import ConfigError

CONFIG_NAME = "pawl.toml"
ADAPTERS = ("pytest", "junit", "jest", "vitest", "go", "cargo")
IDENTITY_MODES = ("ids", "count")
DIRECTIONS = ("down", "up")

DEFAULT_PROTECTED = (
    "pawl.toml",
    "pawl.baseline.json",
    ".github/workflows/**",
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "**/conftest.py",
    "pytest.ini",
    "tox.ini",
    "**/sitecustomize.py",
    "**/usercustomize.py",
    "**/*.pth",
    ".pawl/hooks/**",
)

DEFAULT_TESTS = (
    "tests/**",
    "test/**",
    "**/test_*.py",
    "**/*_test.py",
    "**/*_test.go",
    "**/*.test.[jt]s",
    "**/*.test.[jt]sx",
    "**/*.spec.[jt]s",
    "**/*.spec.[jt]sx",
    "**/__tests__/**",
)


@dataclass(frozen=True)
class SuiteConfig:
    """One test suite whose failures and collection are ratcheted."""

    name: str
    adapter: str
    command: tuple[str, ...]
    identity: str = "ids"
    isolate_max: int = 10
    timeout: float = 3600.0
    junit_path: str | None = None
    ci_only: bool = False
    check_orders: int = 1
    order_args: tuple[tuple[str, ...], ...] = ()
    cwd: str = "."


@dataclass(frozen=True)
class MetricConfig:
    """A numeric metric (lint count, type errors, coverage) with a direction."""

    name: str
    command: tuple[str, ...]
    direction: str
    extract: str
    timeout: float = 1800.0
    ci_only: bool = False
    ok_exit_codes: tuple[int, ...] = (0,)
    cwd: str = "."
    tolerance: float = 0.0


@dataclass(frozen=True)
class ImportCheck:
    """Preflight: ``module`` must resolve under ``expect_under``."""

    module: str
    expect_under: str


@dataclass(frozen=True)
class PreflightConfig:
    """Checks that run before any suite. Any failure stops the gate."""

    python: str = "python"
    imports: tuple[ImportCheck, ...] = ()
    commands: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class GuardConfig:
    """Tamper guard settings."""

    protected: tuple[str, ...] = DEFAULT_PROTECTED
    tests: tuple[str, ...] = DEFAULT_TESTS
    approval_label: str = "pawl-approved"
    fail_on_suspicious: bool = False


@dataclass(frozen=True)
class Config:
    """The whole gate definition."""

    root: Path
    baseline: str = "pawl.baseline.json"
    debt_log: str = "PAWL_DEBT.md"
    lock_in_ci: bool = True
    quarantine_max_days: int = 30
    suites: tuple[SuiteConfig, ...] = ()
    metrics: tuple[MetricConfig, ...] = ()
    preflight: PreflightConfig = field(default_factory=PreflightConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    source: str = CONFIG_NAME

    @property
    def baseline_path(self) -> Path:
        return self.root / self.baseline

    @property
    def debt_log_path(self) -> Path:
        return self.root / self.debt_log


def _command(value: Any, where: str) -> tuple[str, ...]:
    if isinstance(value, str):
        parts = shlex.split(value)
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        parts = list(value)
    else:
        raise ConfigError(f"{where}: command must be a string or a list of strings")
    if not parts:
        raise ConfigError(f"{where}: command is empty")
    return tuple(parts)


def _str(table: dict[str, Any], key: str, where: str, default: str | None = None) -> str:
    value = table.get(key, default)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where}: '{key}' must be a non-empty string")
    return value


def _check_keys(table: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {', '.join(unknown)}")


def _parse_suite(raw: Any, index: int) -> SuiteConfig:
    where = f"suite[{index}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: must be a table")
    _check_keys(
        raw,
        {
            "name",
            "adapter",
            "command",
            "identity",
            "isolate_max",
            "timeout",
            "junit_path",
            "ci_only",
            "check_orders",
            "order_args",
            "cwd",
        },
        where,
    )
    name = _str(raw, "name", where)
    adapter = _str(raw, "adapter", where)
    if adapter not in ADAPTERS:
        raise ConfigError(f"{where}: adapter must be one of {', '.join(ADAPTERS)}")
    identity = _str(raw, "identity", where, "ids")
    if identity not in IDENTITY_MODES:
        raise ConfigError(f"{where}: identity must be 'ids' or 'count'")
    junit_path = raw.get("junit_path")
    if adapter == "junit" and not isinstance(junit_path, str):
        raise ConfigError(f"{where}: the junit adapter needs 'junit_path'")
    order_args_raw = raw.get("order_args", [])
    if not isinstance(order_args_raw, list):
        raise ConfigError(f"{where}: order_args must be a list of commands")
    check_orders = int(raw.get("check_orders", 1))
    if check_orders < 1:
        raise ConfigError(f"{where}: check_orders must be at least 1")
    return SuiteConfig(
        name=name,
        adapter=adapter,
        command=_command(raw.get("command"), where),
        identity=identity,
        isolate_max=int(raw.get("isolate_max", 10)),
        timeout=float(raw.get("timeout", 3600)),
        junit_path=junit_path if isinstance(junit_path, str) else None,
        ci_only=bool(raw.get("ci_only", False)),
        check_orders=check_orders,
        order_args=tuple(_command(a, f"{where}.order_args") for a in order_args_raw),
        cwd=str(raw.get("cwd", ".")),
    )


def _parse_metric(raw: Any, index: int) -> MetricConfig:
    where = f"metric[{index}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: must be a table")
    _check_keys(
        raw,
        {
            "name",
            "command",
            "direction",
            "extract",
            "timeout",
            "ci_only",
            "ok_exit_codes",
            "cwd",
            "tolerance",
        },
        where,
    )
    direction = _str(raw, "direction", where)
    if direction not in DIRECTIONS:
        raise ConfigError(f"{where}: direction must be 'down' or 'up'")
    extract = _str(raw, "extract", where)
    if not extract.startswith(("regex:", "count-regex:", "json:", "count-lines")):
        raise ConfigError(
            f"{where}: extract must start with regex:, count-regex:, json: or be count-lines"
        )
    return MetricConfig(
        name=_str(raw, "name", where),
        command=_command(raw.get("command"), where),
        direction=direction,
        extract=extract,
        timeout=float(raw.get("timeout", 1800)),
        ci_only=bool(raw.get("ci_only", False)),
        ok_exit_codes=_exit_codes(raw.get("ok_exit_codes", [0]), where),
        cwd=_str(raw, "cwd", where, "."),
        tolerance=_tolerance(raw.get("tolerance", 0), where),
    )


def _exit_codes(value: Any, where: str) -> tuple[int, ...]:
    """Exit codes that mean the metric command ran. Any other code is an error."""
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    ):
        raise ConfigError(f"{where}: ok_exit_codes must be a non-empty list of integers")
    return tuple(value)


def _tolerance(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{where}: tolerance must be a number >= 0")
    return float(value)


def _parse_preflight(raw: Any) -> PreflightConfig:
    if raw is None:
        return PreflightConfig()
    if not isinstance(raw, dict):
        raise ConfigError("preflight: must be a table")
    _check_keys(raw, {"python", "imports", "commands"}, "preflight")
    imports: list[ImportCheck] = []
    for i, item in enumerate(raw.get("imports", [])):
        if not isinstance(item, dict):
            raise ConfigError(f"preflight.imports[{i}]: must be a table")
        imports.append(
            ImportCheck(
                module=_str(item, "module", f"preflight.imports[{i}]"),
                expect_under=_str(item, "expect_under", f"preflight.imports[{i}]", "."),
            )
        )
    commands = tuple(
        _command(c, f"preflight.commands[{i}]") for i, c in enumerate(raw.get("commands", []))
    )
    return PreflightConfig(
        python=_str(raw, "python", "preflight", "python"),
        imports=tuple(imports),
        commands=commands,
    )


def _parse_guard(raw: Any) -> GuardConfig:
    if raw is None:
        return GuardConfig()
    if not isinstance(raw, dict):
        raise ConfigError("guard: must be a table")
    _check_keys(
        raw,
        {"protected", "extra_protected", "tests", "approval_label", "fail_on_suspicious"},
        "guard",
    )
    protected = tuple(raw.get("protected", DEFAULT_PROTECTED)) + tuple(
        raw.get("extra_protected", [])
    )
    return GuardConfig(
        protected=protected,
        tests=tuple(raw.get("tests", DEFAULT_TESTS)),
        approval_label=str(raw.get("approval_label", "pawl-approved")),
        fail_on_suspicious=bool(raw.get("fail_on_suspicious", False)),
    )


def parse_config(text: str, root: Path, source: str = CONFIG_NAME) -> Config:
    """Parse config text. Raises ConfigError on any problem (fail closed)."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{source}: invalid TOML: {exc}") from exc
    _check_keys(data, {"pawl", "suite", "metric", "preflight", "guard"}, source)
    top = data.get("pawl", {})
    if not isinstance(top, dict):
        raise ConfigError("[pawl] must be a table")
    _check_keys(top, {"baseline", "debt_log", "lock_in_ci", "quarantine_max_days"}, "[pawl]")
    suites = tuple(_parse_suite(s, i) for i, s in enumerate(data.get("suite", [])))
    metrics = tuple(_parse_metric(m, i) for i, m in enumerate(data.get("metric", [])))
    names = [s.name for s in suites] + [m.name for m in metrics]
    if len(names) != len(set(names)):
        raise ConfigError("suite and metric names must be unique")
    if not names:
        raise ConfigError(f"{source}: define at least one [[suite]] or [[metric]]")
    return Config(
        root=root,
        baseline=str(top.get("baseline", "pawl.baseline.json")),
        debt_log=str(top.get("debt_log", "PAWL_DEBT.md")),
        lock_in_ci=bool(top.get("lock_in_ci", True)),
        quarantine_max_days=int(top.get("quarantine_max_days", 30)),
        suites=suites,
        metrics=metrics,
        preflight=_parse_preflight(data.get("preflight")),
        guard=_parse_guard(data.get("guard")),
        source=source,
    )


def load_config(root: Path, path: Path | None = None) -> Config:
    """Load ``pawl.toml`` from ``root`` (or an explicit path)."""
    cfg_path = path or root / CONFIG_NAME
    if not cfg_path.is_file():
        raise ConfigError(f"no {CONFIG_NAME} at {cfg_path}; run 'pawl init'")
    return parse_config(cfg_path.read_text(encoding="utf-8"), root, str(cfg_path.name))
