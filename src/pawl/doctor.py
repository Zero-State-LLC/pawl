"""Read-only static diagnostics. Local readiness is not CI or runtime qualification."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pawl.baseline import Baseline, parse_baseline
from pawl.config import CONFIG_NAME, Config, parse_config
from pawl.display import terminal
from pawl.errors import PawlError
from pawl.evidence import load_json, read_report
from pawl.gitutil import safe_path
from pawl.runner import ExecutionLimits

LIMITS = ExecutionLimits(max_report_bytes=1048576, max_parse_depth=64)
REMOTE_CONTROLS = (
    "independent_review",
    "code_owner_review",
    "last_push_review",
    "current_base_checks",
    "release_controls",
)


@dataclass
class Diagnostic:
    id: str
    status: str
    severity: str
    message: str
    evidence_source: str
    observed_at: str
    remediation: str
    required: bool


@dataclass
class Diagnosis:
    scope: str
    observed_at: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    )
    checks: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        id: str,
        status: str,
        message: str,
        source: str,
        remediation: str = "",
        *,
        required: bool = True,
    ) -> None:
        self.checks.append(
            Diagnostic(
                id,
                status,
                "error" if required else "warning",
                message,
                source,
                self.observed_at,
                remediation,
                required,
            )
        )

    def to_json(self) -> dict[str, Any]:
        statuses = {check.status for check in self.checks if check.required}
        readiness = (
            "not_ready" if "fail" in statuses else "unknown" if "unknown" in statuses else "ready"
        )
        return {
            "doctor_schema_version": 1,
            "kind": "doctor",
            "scope": self.scope,
            "generated_at": self.observed_at,
            "readiness": readiness,
            "exit_code": {"ready": 0, "not_ready": 1, "unknown": 2}[readiness],
            "checks": [asdict(check) for check in self.checks],
            "limitation": "Static diagnostics only. No project commands or imports were executed.",
        }


def _text(path: Path) -> str:
    return read_report(path, LIMITS).decode("utf-8")


def _baseline(text: str) -> Baseline:
    load_json(text, LIMITS)

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate baseline object key")
            out[key] = value
        return out

    raw = json.loads(text, object_pairs_hook=unique)
    if not isinstance(raw, dict) or type(raw.get("pawl_baseline")) is not int:
        raise ValueError("invalid baseline schema")
    for section in ("suites", "metrics"):
        if not isinstance(raw.get(section, {}), dict):
            raise ValueError(f"baseline {section} must be an object")
    for suite in raw.get("suites", {}).values():
        if not isinstance(suite, dict):
            raise ValueError("baseline suite must be an object")
        for key, default in (("collected", 0), ("confirmed_orders", 1)):
            value = suite.get(key, default)
            if type(value) is not int or value < (1 if key == "confirmed_orders" else 0):
                raise ValueError(f"invalid baseline {key}")
        for key in ("failing_ids", "collected_ids", "skipped_ids"):
            ids = suite.get(key, [])
            if (
                not isinstance(ids, list)
                or any(not isinstance(i, str) or not i for i in ids)
                or len(set(ids)) != len(ids)
            ):
                raise ValueError(f"invalid or duplicate {key}")
        failures = suite.get("failures", len(suite.get("failing_ids", [])))
        if type(failures) is not int or failures < 0:
            raise ValueError("invalid baseline failures")
        if suite.get("identity", "ids") not in ("ids", "count"):
            raise ValueError("invalid baseline identity mode")
        failing, skipped = set(suite.get("failing_ids", [])), set(suite.get("skipped_ids", []))
        if failing & skipped or len(failing | skipped) > suite.get("collected", 0):
            raise ValueError("inconsistent failing/skipped identities")
        if suite.get("identity", "ids") == "ids" and not (failing | skipped) <= set(
            suite.get("collected_ids", [])
        ):
            raise ValueError("baseline outcomes reference uncollected IDs")
    for metric in raw.get("metrics", {}).values():
        if not isinstance(metric, dict) or type(metric.get("value")) not in (int, float):
            raise ValueError("invalid baseline metric value")
        if not math.isfinite(metric["value"]):
            raise ValueError("nonfinite baseline metric")
    return parse_baseline(text)


def _compatibility(config: Config, baseline: Baseline) -> None:
    if {s.name for s in config.suites} != set(baseline.suites):
        raise ValueError("configured suites and baseline suites differ")
    if {m.name for m in config.metrics} != set(baseline.metrics):
        raise ValueError("configured metrics and baseline metrics differ")
    for suite in config.suites:
        if suite.identity != baseline.suites[suite.name].identity:
            raise ValueError("configured identity mode differs from baseline")
    for metric in config.metrics:
        if metric.direction != baseline.metrics[metric.name]["direction"]:
            raise ValueError("configured metric direction differs from baseline")
    for item in baseline.quarantine:
        if item.suite not in baseline.suites:
            raise ValueError("quarantine references an unconfigured suite")


def _executables(result: Diagnosis, config: Config) -> None:
    commands = [(f"suite.{s.name}", s.cwd, s.command) for s in config.suites]
    commands += [(f"metric.{m.name}", m.cwd, m.command) for m in config.metrics]
    commands += [
        (f"preflight.{i}", ".", command) for i, command in enumerate(config.preflight.commands)
    ]
    if config.preflight.imports:
        commands.append(("preflight.python", ".", (config.preflight.python,)))
    for label, cwd, argv in commands:
        try:
            directory = safe_path(config.root, cwd)
            if not directory.is_dir():
                raise ValueError("working directory does not exist")
            executable = argv[0]
            resolved = (
                str((directory / executable).absolute())
                if "/" in executable
                else shutil.which(executable)
            )
            if not resolved or not Path(resolved).is_file() or not os.access(resolved, os.X_OK):
                raise ValueError("executable cannot be resolved as an executable file")
            result.add(
                "executable." + label,
                "pass",
                "Executable resolves; it was not run or authenticated.",
                label,
            )
        except (PawlError, OSError, ValueError):
            result.add(
                "executable." + label,
                "fail",
                "Working directory or executable is missing or unsafe.",
                label,
                "Install the target toolchain or correct the command/cwd.",
            )


def _trusted_ref(result: Diagnosis, root: Path, ref: str | None) -> None:
    if ref is None:
        result.add(
            "trusted_ref",
            "not_applicable",
            "No ref requested; worktree configuration inspected.",
            "arguments",
            required=False,
        )
        return
    executable = shutil.which("git")
    if (
        not executable
        or Path(executable).absolute().is_relative_to(root)
        or Path(executable).resolve().is_relative_to(root)
    ):
        result.add(
            "trusted_ref",
            "unknown",
            "Trusted launcher Git executable unavailable.",
            "launcher PATH",
            "Install Git outside the candidate checkout.",
        )
        return
    env = {
        "PATH": os.environ.get("PATH", os.defpath),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_NO_LAZY_FETCH": "1",
    }
    try:
        done = subprocess.run(
            [
                executable,
                "--no-pager",
                "-c",
                "core.fsmonitor=false",
                "rev-parse",
                "--verify",
                "--end-of-options",
                ref + "^{commit}",
            ],
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        if done.returncode or not re.fullmatch(rb"[0-9a-f]{40,64}\n?", done.stdout):
            result.add(
                "trusted_ref",
                "fail",
                "Requested commit ref is not available locally.",
                "local Git object database",
                "Fetch the intended ref outside doctor and retry.",
            )
        else:
            result.add(
                "trusted_ref",
                "pass",
                "Requested commit ref resolves locally: " + done.stdout.decode().strip(),
                "local Git object database",
            )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        result.add(
            "trusted_ref",
            "unknown",
            "Local Git ref verification could not complete.",
            "local Git",
            "Repair Git availability and retry.",
        )


def _workflow_state(root: Path) -> str:
    try:
        path = safe_path(root, ".github/workflows")
        with os.scandir(path) as entries:
            found = False
            for index, entry in enumerate(entries):
                if index >= 4096:
                    return "limit"
                if entry.name.endswith((".yml", ".yaml")):
                    if not entry.is_file(follow_symlinks=False):
                        return "unsafe"
                    found = True
            return "present" if found else "absent"
    except FileNotFoundError:
        return "absent"
    except (PawlError, OSError):
        return "unsafe"


def diagnose(
    root: Path,
    *,
    ci_readiness: bool = False,
    online: bool = False,
    trusted_ref: str | None = None,
    repository: str | None = None,
    branch: str | None = None,
    expected_check: str | None = None,
    expected_app_id: int | None = None,
) -> Diagnosis:
    root = root.resolve()
    ci = ci_readiness or online
    result = Diagnosis("online-ci" if online else "offline-ci" if ci else "offline-local")
    config: Config | None = None
    try:
        config = parse_config(_text(root / CONFIG_NAME), root)
        result.add("config", "pass", "Worktree configuration parses.", CONFIG_NAME)
    except (
        PawlError,
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        RecursionError,
        OverflowError,
    ) as exc:
        result.add(
            "config",
            "fail",
            f"Configuration is missing, unsafe or invalid: {str(exc)[:512]}",
            CONFIG_NAME,
            "Repair configuration; doctor will not rewrite it.",
        )
    if config is not None:
        try:
            baseline = _baseline(_text(safe_path(root, config.baseline)))
            _compatibility(config, baseline)
            result.add(
                "baseline",
                "pass",
                "Baseline structure and configured identities agree.",
                config.baseline,
            )
        except (PawlError, OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
            result.add(
                "baseline",
                "fail",
                f"Baseline is missing, unsafe or incompatible: {str(exc)[:512]}",
                config.baseline,
                "Review the baseline and configuration; do not reset history.",
            )
        _executables(result, config)
        result.add(
            "execution_boundary",
            "pass" if os.name == "posix" else "fail",
            f"Configured environment: {config.execution.environment}; not a sandbox. "
            "POSIX runner platform available."
            if os.name == "posix"
            else "Native Windows is not qualified.",
            "runtime and worktree configuration",
            "" if os.name == "posix" else "Use a qualified POSIX host.",
        )
    else:
        result.add(
            "dependent_checks",
            "unknown",
            "Baseline and executable checks require valid config.",
            CONFIG_NAME,
            "Repair configuration and retry.",
        )
    _trusted_ref(result, root, trusted_ref)
    state = _workflow_state(root)
    result.add(
        "ci_declarations",
        "unknown" if state != "absent" else ("fail" if ci else "not_applicable"),
        {
            "present": "Workflow declarations found; semantics and enforcement are unverified.",
            "absent": "No GitHub workflow declarations found.",
            "unsafe": "Workflow declarations could not be safely inspected.",
            "limit": "Workflow directory exceeds the inspection limit.",
        }[state],
        ".github/workflows",
        "Validate the workflow implementation and required-check binding independently.",
        required=ci,
    )
    if online:
        from pawl.github_doctor import inspect_github

        for observation in inspect_github(repository, branch, expected_check, expected_app_id):
            result.add(
                observation.id,
                observation.status,
                observation.message,
                observation.source,
                "Review missing evidence; doctor does not change settings."
                if observation.status != "pass"
                else "",
            )
    elif ci:
        for control in REMOTE_CONTROLS:
            result.add(
                "ci." + control,
                "unknown",
                "Remote settings cannot be verified offline.",
                "remote settings not observed",
                "Obtain fresh authenticated provider evidence.",
            )
    return result


def render(result: Diagnosis) -> str:
    data = result.to_json()
    lines = [
        f"Pawl doctor: {data['readiness'].upper()} (scope: {data['scope']})",
        data["limitation"],
    ]
    for check in result.checks:
        lines.append(f"{check.status.upper()} {terminal(check.id)}: {terminal(check.message)}")
        if check.remediation:
            lines.append("  Next: " + terminal(check.remediation))
    return "\n".join(lines) + "\n"
