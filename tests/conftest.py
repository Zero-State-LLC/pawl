from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def commit(cwd: Path, message: str) -> None:
    git(cwd, "add", "-A")
    git(cwd, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", message)


@pytest.fixture
def demo_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git repo holding the demo project on 'main', checked out on branch 'agent'."""
    repo = tmp_path / "demo"
    shutil.copytree(DEMO, repo, ignore=shutil.ignore_patterns("__pycache__", ".pawl"))
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base")
    git(repo, "checkout", "-qb", "agent")
    # The demo's suite command calls "python"; make it this interpreter.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    # A wrapper, not a symlink: a symlinked venv interpreter loses its venv.
    shim = bindir / "python"
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv(
        "PATH", f"{bindir}:{Path(sys.executable).parent}:" + __import__("os").environ["PATH"]
    )
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    return repo


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"edit did not land: {old!r} not in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")
