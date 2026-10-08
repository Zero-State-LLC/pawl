"""Small git helpers. All reads; Pawl never commits or pushes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pawl.errors import PawlError


def git(root: Path, *args: str, check: bool = True) -> str:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, errors="replace", check=False
        )
    except FileNotFoundError as exc:
        raise PawlError("git is not installed") from exc
    if check and proc.returncode != 0:
        raise PawlError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def show(root: Path, ref: str, path: str) -> str | None:
    """Return file content at ``ref``, or None if it does not exist there."""
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def merge_base(root: Path, base: str) -> str:
    out = git(root, "merge-base", base, "HEAD", check=False).strip()
    if not out:
        # Fall back to the ref itself (for example a shallow clone).
        out = git(root, "rev-parse", "--verify", base).strip()
    return out


def changed_files(root: Path, base: str) -> list[tuple[str, str]]:
    """Return ``[(status, path)]`` between ``base`` and the working tree, plus untracked files.

    Status is A, M, D. Renames are reported as a delete plus an add so a rename
    out of the collected pattern is visible.
    """
    out = git(root, "diff", "--name-status", "--no-renames", base, "--")
    changes: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        changes.append((status[0], path))
    for path in git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        if path.strip():
            changes.append(("A", path))
    return changes


def diff_text(root: Path, base: str, path: str) -> str:
    return git(root, "diff", "--no-renames", "-U0", base, "--", path, check=False)
