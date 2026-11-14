"""Validate target runtimes and commit generated setup files with rollback."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from dataclasses import replace
from pathlib import Path

from pawl.config import Config
from pawl.errors import PawlError, PreflightError
from pawl.gitutil import safe_path
from pawl.runner import run


def verify_runner(config: Config) -> tuple[Config, list[str]]:
    suite = config.suites[0]
    executable = suite.command[0]
    search = str(config.root / executable) if "/" in executable else executable
    resolved = shutil.which(search)
    if resolved is None:
        raise PreflightError(f"target runner not found: {executable!r}")
    if suite.adapter == "pytest":
        argv = [resolved, "-c", "import pytest, sys; print(sys.executable)"]
    elif suite.adapter in ("jest", "vitest"):
        argv = [resolved, "--no-install", suite.adapter, "--version"]
    elif suite.adapter == "go":
        argv = [resolved, "version"]
    else:
        argv = [resolved, "--version"]
    try:
        result = run(argv, config.root, 15)
    except PawlError as exc:
        raise PreflightError(f"target runner unavailable: {executable!r}: {exc}") from exc
    if result.returncode:
        raise PreflightError(f"target runner unavailable: {executable!r}: {result.tail()}")
    note = f"target runner: {executable!r} resolves to {resolved!r}"
    if Path(executable).is_absolute():
        note += " (explicit absolute override is nonportable)"
    runtime = replace(suite, command=(resolved, *suite.command[1:]))
    preflight = (
        replace(config.preflight, python=resolved)
        if suite.adapter == "pytest"
        else config.preflight
    )
    return replace(config, suites=(runtime,), preflight=preflight), [note]


def validate_targets(root: Path, names: list[str], *, force: bool, append: str) -> None:
    for name in names:
        path = safe_path(root, name)
        if path.exists():
            mode = path.stat()
            if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1:
                raise PawlError(f"setup destination is not an independent regular file: {name!r}")
            if not force and name != append:
                raise PawlError(f"{name} exists; use --force to overwrite")


def commit_files(root: Path, files: dict[str, bytes], *, force: bool, append: str) -> None:
    """Stage on the target filesystem; restore original bytes/modes on write failure.

    This handles ordinary filesystem errors, not process kill or power loss.
    Test commands execute with the user's privileges; their own side effects
    are outside the generated-file transaction.
    """
    validate_targets(root, list(files), force=force, append=append)
    created_dirs: list[Path] = []
    committed: list[str] = []
    originals: dict[str, tuple[bytes, int] | None] = {}
    with tempfile.TemporaryDirectory(prefix=".pawl-init-", dir=root) as temp:
        stage = Path(temp)
        for index, (name, content) in enumerate(files.items()):
            target = safe_path(root, name)
            original = (
                (target.read_bytes(), stat.S_IMODE(target.stat().st_mode))
                if target.exists()
                else None
            )
            originals[name] = original
            staged = stage / str(index)
            staged.write_bytes(content)
            staged.chmod(original[1] if original else 0o644)
            if original:
                backup = stage / f"backup-{index}"
                backup.write_bytes(original[0])
                backup.chmod(original[1])
        (stage / "journal.json").write_text(json.dumps(list(files)), encoding="utf-8")
        try:
            for index, name in enumerate(files):
                target = safe_path(root, name)
                missing = []
                parent = target.parent
                while parent != root and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for directory in reversed(missing):
                    directory.mkdir()
                    created_dirs.append(directory)
                os.replace(stage / str(index), target)
                committed.append(name)
        except (OSError, PawlError) as exc:
            errors = []
            for name in reversed(committed):
                target = root / name
                original = originals[name]
                try:
                    if original is None:
                        target.unlink()
                    else:
                        # Use a separate primitive so a failed replace can still recover.
                        target.write_bytes(original[0])
                        target.chmod(original[1])
                except OSError as rollback:
                    errors.append(f"{name}: {rollback}")
            for directory in reversed(created_dirs):
                try:
                    directory.rmdir()
                except OSError as rollback:
                    errors.append(f"{directory}: {rollback}")
            detail = "; rollback incomplete: " + "; ".join(errors) if errors else "; rolled back"
            raise PawlError(f"setup commit failed: {exc}{detail}") from exc
