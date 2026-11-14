"""Small git helpers. All reads; Pawl never commits or pushes."""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from pawl.errors import PawlError


def git(root: Path, *args: str, check: bool = True) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            errors="surrogateescape",
            check=False,
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


def toplevel(root: Path) -> Path:
    """The repository's top-level directory. Paths in git refs and diffs are relative to it."""
    return Path(git(root, "rev-parse", "--show-toplevel").strip()).resolve()


def prefix(root: Path) -> str:
    """``root`` relative to the top level, with a trailing slash ("" at the top level)."""
    return git(root, "rev-parse", "--show-prefix").strip()


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
    out = git(root, "diff", "--name-status", "-z", "--no-renames", base, "--")
    changes: list[tuple[str, str]] = []
    fields = out.split("\0")
    if fields[-1] != "" or (len(fields) - 1) % 2:
        raise PawlError("malformed NUL-delimited Git change inventory")
    for index in range(0, len(fields) - 1, 2):
        status, path = fields[index : index + 2]
        if status not in ("A", "M", "D", "T") or not path:
            raise PawlError("unsupported Git change status or empty path")
        safe_path(root, path)
        changes.append(("M" if status == "T" else status, path))
    for path in git(root, "ls-files", "-z", "--others", "--exclude-standard").split("\0"):
        if path:
            safe_path(root, path)
            changes.append(("A", path))
    return changes


def diff_text(root: Path, base: str, path: str) -> str:
    return git(root, "--literal-pathspecs", "diff", "--no-renames", "-U0", base, "--", path)


def safe_path(root: Path, path: str) -> Path:
    """Resolve a Git path without following candidate links or escaping the tree."""
    try:
        path.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise PawlError("Git path is not valid UTF-8") from exc
    parts = PurePosixPath(path)
    if not path or parts.is_absolute() or ".." in parts.parts:
        raise PawlError(f"unsafe repository path: {path!r}")
    current = root.resolve()
    for part in parts.parts:
        current /= part
        if current.is_symlink():
            raise PawlError(f"refusing linked candidate path: {path!r}")
    if not current.resolve().is_relative_to(root.resolve()):
        raise PawlError(f"repository path escapes root: {path!r}")
    return current
