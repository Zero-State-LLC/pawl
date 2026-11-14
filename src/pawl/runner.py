"""Run commands with timeouts. A timeout or a missing executable is an error, never a pass."""

from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pawl.errors import PawlError

MAX_OUTPUT_BYTES = 8388608
TERMINATE_GRACE_SECONDS = 5.0
POSIX = os.name == "posix"


@dataclass(frozen=True)
class ExecutionLimits:
    max_output_bytes: int = MAX_OUTPUT_BYTES
    terminate_grace_seconds: float = TERMINATE_GRACE_SECONDS

    max_report_bytes: int = 16777216
    max_test_records: int = 200000
    max_parse_depth: int = 128

    def validate(self) -> None:
        if (
            any(
                type(v) is not int or not low <= v <= high
                for v, low, high in (
                    (self.max_report_bytes, 65536, 268435456),
                    (self.max_test_records, 1, 1000000),
                    (self.max_parse_depth, 8, 256),
                )
            )
            or type(self.max_output_bytes) is not int
            or not 65536 <= self.max_output_bytes <= 67108864
            or type(self.terminate_grace_seconds) not in (int, float)
            or not 0 <= self.terminate_grace_seconds <= 30
        ):
            raise ExecutionError("INVALID_EXECUTION_POLICY", "invalid output or cleanup limit")


class ExecutionError(PawlError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _stop(proc: subprocess.Popen[bytes], grace: float) -> None:
    """Terminate the session's group and reap the direct child within a bound."""
    errors: list[str] = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        except OSError:
            errors.append("could not signal child process group")
        try:
            proc.wait(timeout=grace if sig == signal.SIGTERM else 1.0)
        except subprocess.TimeoutExpired:
            if sig == signal.SIGKILL:
                errors.append("direct child did not exit after kill")
    if errors:
        raise ExecutionError("TERMINATION_UNCERTAIN", "; ".join(errors))


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
        text = "\n".join(self.output.strip().splitlines()[-lines:])
        return text if len(text) <= 4096 else "[earlier output omitted]\n" + text[-4096:]


def run(
    argv: Sequence[str],
    cwd: Path,
    timeout: float,
    env: Mapping[str, str] | None = None,
    *,
    limits: ExecutionLimits = ExecutionLimits(),
) -> Completed:
    """Run ``argv`` in ``cwd``. Raises PawlError on timeout or a missing executable."""
    if not POSIX:
        raise ExecutionError("UNSUPPORTED_PLATFORM", "bounded process groups require POSIX")
    limits.validate()
    try:
        valid_timeout = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        raise ExecutionError("INVALID_EXECUTION_POLICY", "invalid command timeout")
    max_output_bytes = limits.max_output_bytes
    merged = dict(os.environ)
    if env:
        merged.update(env)
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            list(argv),
            cwd=cwd,
            env=merged,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            bufsize=0,
        )
    except FileNotFoundError as exc:
        raise PawlError(f"command not found: {argv[0]} ({exc})") from exc
    except OSError as exc:
        raise ExecutionError("RUN_START_FAILED", "could not start command") from exc
    assert proc.stdout is not None and proc.stderr is not None
    streams = (proc.stdout, proc.stderr)
    buffers = (bytearray(), bytearray())
    total = 0
    deadline = start + timeout
    try:
        with selectors.DefaultSelector() as selector:
            for index, stream in enumerate(streams):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, index)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ExecutionError("RUN_TIMEOUT", f"command timed out after {timeout:g}s")
                for key, _ in selector.select(min(remaining, 0.1)):
                    data = os.read(key.fd, min(65536, max_output_bytes - total + 1))
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(data)
                    if total > max_output_bytes:
                        raise ExecutionError(
                            "OUTPUT_LIMIT", "combined stdout/stderr exceeded byte limit"
                        )
                    buffers[key.data].extend(data)
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as exc:
                raise ExecutionError(
                    "RUN_TIMEOUT", f"command timed out after {timeout:g}s"
                ) from exc
    except KeyboardInterrupt as exc:
        raise ExecutionError("RUN_INTERRUPTED", "command interrupted; cleanup required") from exc
    except OSError as exc:
        raise ExecutionError("RUN_IO_FAILED", "could not collect command output") from exc
    finally:
        try:
            _stop(proc, limits.terminate_grace_seconds)
        finally:
            for stream in streams:
                stream.close()
    return Completed(
        argv=tuple(argv),
        returncode=proc.returncode,
        stdout=buffers[0].decode("utf-8", errors="replace"),
        stderr=buffers[1].decode("utf-8", errors="replace"),
        seconds=time.monotonic() - start,
    )
