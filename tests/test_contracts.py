"""Contract coverage for ``pawl.contracts``: docstring scanning and guard blocks."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.cli import main
from pawl.contracts import contract_docstrings

DURATIONS = (
    "def parse_duration(text):\n"
    '    """Parse a duration.\n'
    "\n"
    "    pawl: contract\n"
    '    "1h1s" is 3601 seconds.\n'
    '    """\n'
    "    return 3601\n"
)

PLAIN = 'def parse_duration(text):\n    """Parse a duration."""\n    return 3601\n'

MARKED_SOURCE = (
    '"""Module prose.\n'
    "\n"
    "pawl: contract\n"
    '"""\n'
    "def f():\n"
    '    """pawl: contract\n'
    "    Contract body.\n"
    '    """\n'
    "def g():\n"
    '    """plain prose"""\n'
    "class C:\n"
    "    def m(self):\n"
    '        """pawl: contract"""\n'
    "    def n(self):\n"
    '        """plain"""\n'
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


def test_contract_docstrings() -> None:
    found = contract_docstrings(MARKED_SOURCE)
    assert set(found) == {"<module>", "f", "C.m"}
    assert contract_docstrings("def (") == {}


def test_marked_docstring_rewrite_blocks(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    repo = _repo(tmp_path, {"durations.py": DURATIONS})
    (repo / "durations.py").write_text(
        DURATIONS.replace("3601 seconds", "3660 seconds"), encoding="utf-8"
    )
    commit(repo, "rewrite the normative docstring only")
    args = ["--root", str(repo)]
    assert main([*args, "guard", "--ci", "--base", "main"]) == 1
    capsys.readouterr()
    main([*args, "guard", "--base", "main", "--json"])
    report = json.loads(capsys.readouterr().out)
    codes = [finding["rule"] for finding in report["findings"]]
    assert "SPEC_AUTHORITY_CHANGED" in codes
    assert main([*args, "guard", "--base", "main", "--approved"]) == 0


def test_unmarked_docstring_edit_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"durations.py": PLAIN})
    (repo / "durations.py").write_text(
        PLAIN.replace("Parse a duration.", "Parse a duration from text."), encoding="utf-8"
    )
    commit(repo, "edit unmarked prose")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 0


def test_spec_file_edit_blocks(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"specs/req.md": "# Requirement\n"})
    (repo / "specs/req.md").write_text("# Requirement\n\nChanged.\n", encoding="utf-8")
    commit(repo, "edit the spec")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 1


def test_readme_edit_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"README.md": "# Project\n"})
    (repo / "README.md").write_text("# Project\n\nMore.\n", encoding="utf-8")
    commit(repo, "edit the readme")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 0


def test_registered_file_hash_mismatch_blocks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path, {"data/rules.txt": "v1\n"})
    registry = {
        "pawl_contracts": 1,
        "files": {"data/rules.txt": hashlib.sha256(b"v1\n").hexdigest()},
        "docstrings": {},
    }
    git(repo, "checkout", "-q", "main")
    (repo / "pawl.contracts.json").write_text(json.dumps(registry), encoding="utf-8")
    commit(repo, "record the contract registry")
    git(repo, "checkout", "-qB", "agent")
    (repo / "data/rules.txt").write_text("v2\n", encoding="utf-8")
    commit(repo, "edit the registered contract")
    capsys.readouterr()
    assert main(["--root", str(repo), "guard", "--base", "main", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    rules = {(f["rule"], f["message"]) for f in report["findings"]}
    assert rules == {("SPEC_AUTHORITY_CHANGED", "registered contract hash mismatch")}


def test_contracts_update_writes_registry(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"specs/req.md": "# Requirement\n"})
    assert main(["--root", str(repo), "contracts", "update"]) == 0
    data = json.loads((repo / "pawl.contracts.json").read_text(encoding="utf-8"))
    assert "specs/req.md" in data["files"]


def test_malformed_registry_exits_2(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"specs/req.md": "# Requirement\n"})
    git(repo, "checkout", "-q", "main")
    (repo / "pawl.contracts.json").write_text("{", encoding="utf-8")
    commit(repo, "corrupt the registry")
    git(repo, "checkout", "-qB", "agent")
    (repo / "specs/req.md").write_text("# Requirement\n\nChanged.\n", encoding="utf-8")
    commit(repo, "edit the spec")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 2
