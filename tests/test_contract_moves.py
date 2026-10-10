"""Contract coverage for intact contract moves: ``SPEC_AUTHORITY_MOVED``."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.cli import main

DURATIONS = (
    "def parse_duration(text):\n"
    '    """Parse a duration.\n'
    "\n"
    "    pawl: contract\n"
    '    "1h1s" is 3601 seconds.\n'
    '    """\n'
    "    return 3601\n"
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    payload = dict(files)
    payload["tests/test_ok.py"] = "def test_ok():\n    assert True\n"
    for rel, text in payload.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    config = (
        '[[suite]]\nname="unit"\nadapter="pytest"\n'
        f'command=[{json.dumps(sys.executable)}, "-B", "-m", "pytest", "tests", "-q"]\n'
    )
    (repo / "pawl.toml").write_text(config, encoding="utf-8")
    assert main(["--root", str(repo), "update"]) == 0
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "freeze the base")
    git(repo, "checkout", "-qb", "agent")
    return repo


def test_intact_spec_move_reports_info(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path, {"specs/a.md": "# Requirement\n"})
    git(repo, "mv", "specs/a.md", "specs/b.md")
    commit(repo, "move the spec intact")
    args = ["--root", str(repo)]
    assert main([*args, "guard", "--base", "main"]) == 0
    capsys.readouterr()
    assert main([*args, "guard", "--base", "main", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    codes = [finding["rule"] for finding in report["findings"]]
    assert "SPEC_AUTHORITY_CHANGED" not in codes
    moves = [f for f in report["findings"] if f["rule"] == "SPEC_AUTHORITY_MOVED"]
    assert len(moves) == 1
    finding = moves[0]
    assert set(finding) >= {"rule", "severity", "path", "message"}
    assert finding["severity"] == "info"
    assert finding["path"] == "specs/b.md"


def test_moved_and_edited_spec_blocks(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"specs/a.md": "# Requirement\n"})
    git(repo, "mv", "specs/a.md", "specs/b.md")
    (repo / "specs/b.md").write_text("# Requirement\n\nChanged.\n", encoding="utf-8")
    commit(repo, "move and edit the spec")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 1


def test_spec_moved_out_of_protected_paths_blocks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {"specs/a.md": "# Requirement\n"})
    (repo / "notes").mkdir()
    git(repo, "mv", "specs/a.md", "notes/a.md")
    commit(repo, "move the spec out of protected paths")
    capsys.readouterr()
    assert main(["--root", str(repo), "guard", "--base", "main", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    messages = [f["message"] for f in report["findings"] if f["rule"] == "SPEC_AUTHORITY_CHANGED"]
    assert any("moved out of protected paths" in m for m in messages)


def test_moved_marked_function_reports_info(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {"durations.py": DURATIONS})
    git(repo, "mv", "durations.py", "other.py")
    (repo / "durations.py").write_text("x = 1\n", encoding="utf-8")
    commit(repo, "move the marked function intact")
    args = ["--root", str(repo)]
    assert main([*args, "guard", "--base", "main"]) == 0
    capsys.readouterr()
    assert main([*args, "guard", "--base", "main", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    moves = [f for f in report["findings"] if f["rule"] == "SPEC_AUTHORITY_MOVED"]
    assert any("parse_duration" in f["message"] for f in moves)


def test_registered_move_is_warned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path, {"specs/a.md": "# Requirement\n"})
    git(repo, "checkout", "-q", "main")
    assert main(["--root", str(repo), "contracts", "update"]) == 0
    commit(repo, "record the contract registry")
    git(repo, "checkout", "-qB", "agent")
    git(repo, "mv", "specs/a.md", "specs/b.md")
    commit(repo, "move the registered spec intact")
    capsys.readouterr()
    assert main(["--root", str(repo), "guard", "--base", "main", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    moves = [f for f in report["findings"] if f["rule"] == "SPEC_AUTHORITY_MOVED"]
    assert moves
    assert any(f["severity"] == "warn" for f in moves)
    assert any("contracts update" in f["message"] for f in moves)
