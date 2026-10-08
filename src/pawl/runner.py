"""Run commands with timeouts. A timeout or a missing executable is an error, never a pass."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pawl.errors import PawlError


@dataclass(frozen=True)
class Completed:
    """Result of one command."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    seconds: float

    @property
    def output(self) -> str:
        return self.stdout + ("\n" if self.stdout and self.stderr else "") + self.stderr

    def tail(self, lines: int = 15) -> str:
        return "\n".join(self.output.strip().splitlines()[-lines:])


def run(
    argv: Sequence[str],
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None = None,
) -> Completed:
    """Run ``argv`` in ``cwd``. Raises PawlError on timeout or a missing executable."""
    import time

    merged = dict(os.environ)
    if env:
        merged.update(env)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            env=merged,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise PawlError(f"command not found: {argv[0]} ({exc})") from exc
    except subprocess.TimeoutExpired as exc:
        raise PawlError(f"command timed out after {timeout:.0f}s: {' '.join(argv)}") from exc
    return Completed(
        argv=tuple(argv),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        seconds=time.monotonic() - start,
    )
