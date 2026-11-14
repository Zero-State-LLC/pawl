"""Explicit child-environment policy. This is not a filesystem or process sandbox."""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from pawl.errors import PawlError

RESERVED = frozenset({"HOME", "TMPDIR", "TMP", "TEMP", "PAWL_TEST_ORDER"})
INTERNAL = frozenset({"PYTHONPATH", "PAWL_TEST_ORDER"})
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


class EnvironmentPolicyError(PawlError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def validate_policy(mode: str, names: tuple[str, ...]) -> None:
    if type(mode) is not str or mode not in ("inherit", "minimal"):
        raise EnvironmentPolicyError("INVALID_EXECUTION_POLICY", "invalid environment mode")
    if (
        not isinstance(names, tuple)
        or len(names) > 256
        or any(
            not isinstance(name, str)
            or len(name) > 256
            or not NAME.fullmatch(name)
            or name in RESERVED
            for name in names
        )
        or len(set(names)) != len(names)
    ):
        raise EnvironmentPolicyError("INVALID_EXECUTION_POLICY", "invalid pass_env names")


def policy_summary(mode: str, names: tuple[str, ...]) -> dict[str, object]:
    return {
        "mode": mode,
        "pass_env": list(names),
        "sandbox": False,
        "disclosure": (
            "Child commands inherit the launcher environment."
            if mode == "inherit"
            else "Minimal child environment; host access is not isolated."
        ),
    }


@contextmanager
def command_environment(
    mode: str,
    names: tuple[str, ...],
    overrides: Mapping[str, str] | None,
) -> Iterator[dict[str, str]]:
    validate_policy(mode, names)
    if mode == "inherit":
        env = dict(os.environ)
        env.update(overrides or {})
        yield env
        return
    if overrides and any(name not in INTERNAL and name not in names for name in overrides):
        raise EnvironmentPolicyError("INVALID_EXECUTION_POLICY", "unapproved environment override")
    try:
        temporary = tempfile.TemporaryDirectory(prefix="pawl-env-")
    except OSError as exc:
        raise EnvironmentPolicyError(
            "ENV_SETUP_FAILED", "cannot create command environment"
        ) from exc
    try:
        root = Path(temporary.name)
        home, tmp = root / "home", root / "tmp"
        try:
            home.mkdir(mode=0o700)
            tmp.mkdir(mode=0o700)
        except OSError as exc:
            raise EnvironmentPolicyError(
                "ENV_SETUP_FAILED", "cannot prepare command directories"
            ) from exc
        env = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C", "LC_ALL": "C"}
        env.update({name: os.environ[name] for name in names if name in os.environ})
        env.update(overrides or {})
        env.update({"HOME": str(home), "TMPDIR": str(tmp), "TMP": str(tmp), "TEMP": str(tmp)})
        yield env
    finally:
        try:
            temporary.cleanup()
        except OSError as exc:
            raise EnvironmentPolicyError(
                "ENV_CLEANUP_FAILED", "cannot remove command environment"
            ) from exc
