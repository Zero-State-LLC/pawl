"""Regression tests for bugs reproduced in the 2026-10-08 architecture review.

Each test here fails on pawl 0.1.1 (main 8fcac25) and passes with the fix. They
only use the command-line entry point, so they run unchanged against 0.1.1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.cli import main

LINT = "import product\nfor i in range(product.N):\n    print('WARN finding', i)\n"


def _repo(tmp_path: Path, extract: str, extra: str = "") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lint.py").write_text(LINT, encoding="utf-8")
    (repo / "product.py").write_text("N = 3\n", encoding="utf-8")
    (repo / "pawl.toml").write_text(
        "[[metric]]\n"
        'name = "lint_findings"\n'
        f'command = [{json.dumps(sys.executable)}, "-B", "lint.py"]\n'
        'direction = "down"\n'
        f"extract = {json.dumps(extract)}\n" + extra,
        encoding="utf-8",
    )
    assert main(["--root", str(repo), "update"]) == 0
    return repo


@pytest.mark.parametrize("extract", ["count-regex:WARN", "count-lines"])
def test_crashed_metric_command_is_an_error_not_zero(tmp_path: Path, extract: str) -> None:
    repo = _repo(tmp_path, extract)
    (repo / "product.py").write_text("N = 50\nraise RuntimeError('boom')\n", encoding="utf-8")
    # On 0.1.1 this was exit 0 ("improved to 0 from 3"). It must fail closed.
    assert main(["--root", str(repo), "check"]) == 2
    report = json.loads((repo / ".pawl" / "last-report.json").read_text())
    assert report["status"] == "error"
    assert "exited 1" in report["error"]
    # And the crash must not be recordable as a tightening.
    assert main(["--root", str(repo), "update"]) == 2
    baseline = json.loads((repo / "pawl.baseline.json").read_text())
    assert baseline["metrics"]["lint_findings"]["value"] == 3


def test_real_regression_still_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "count-regex:WARN")
    (repo / "product.py").write_text("N = 50  # more findings\n", encoding="utf-8")
    assert main(["--root", str(repo), "check"]) == 1


TESTS_AB = "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"


def _pytest_project(where: Path) -> None:
    (where / "tests").mkdir(parents=True)
    (where / "tests" / "test_ab.py").write_text(TESTS_AB, encoding="utf-8")
    (where / "pawl.toml").write_text(
        "[[suite]]\n"
        'name = "tests"\n'
        'adapter = "pytest"\n'
        f'command = [{json.dumps(sys.executable)}, "-m", "pytest", "-q"]\n',
        encoding="utf-8",
    )
    assert main(["--root", str(where), "update"]) == 0


def _break_test_b_and_hide_it(where: Path) -> None:
    """Break test_b and add it to the head baseline's known failures."""
    (where / "tests" / "test_ab.py").write_text(
        TESTS_AB.replace("def test_b():\n    assert True", "def test_b():\n    assert False"),
        encoding="utf-8",
    )
    path = where / "pawl.baseline.json"
    data = json.loads(path.read_text())
    suite = data["suites"]["tests"]
    suite["failing_ids"] = ["tests/test_ab.py::test_b"]
    suite["failures"] = 1
    path.write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)


@pytest.mark.usefixtures("clean_env")
def test_subdirectory_root_uses_the_base_gate(tmp_path: Path) -> None:
    """F2: with pawl.toml in pkg/, the trusted ref was looked up at the top level,
    missed, and the head config and baseline were used ("bootstrap")."""
    repo = tmp_path / "mono"
    pkg = repo / "pkg"
    pkg.mkdir(parents=True)
    _pytest_project(pkg)
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base")
    git(repo, "checkout", "-qb", "agent")
    _break_test_b_and_hide_it(pkg)
    commit(repo, "break test_b and add it to the head baseline")
    root = ["--root", str(pkg)]
    assert main([*root, "check", "--trusted-ref", "main"]) == 1
    report = json.loads((pkg / ".pawl" / "last-report.json").read_text())
    assert report["config_source"] == "main:pkg/pawl.toml"
    assert "NEW_FAILURE" in [p["code"] for p in report["problems"]]
    assert main([*root, "guard", "--base", "main"]) == 1
    guard = json.loads((pkg / ".pawl" / "last-guard.json").read_text())
    blocks = {f["rule"] for f in guard["findings"] if f["severity"] == "block"}
    assert {"BASELINE_LOOSENED", "TEST_MODIFIED"} <= blocks


@pytest.mark.usefixtures("clean_env")
def test_trusted_ref_without_a_config_is_refused(tmp_path: Path) -> None:
    """F2: a trusted ref with no pawl.toml silently fell back to the head config."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base without pawl")
    git(repo, "checkout", "-qb", "agent")
    _pytest_project(repo)
    commit(repo, "add pawl")
    assert main(["--root", str(repo), "check", "--trusted-ref", "main"]) == 2
    report = json.loads((repo / ".pawl" / "last-report.json").read_text())
    assert "no pawl.toml" in report["error"]
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 2
    # The explicit escape hatch for the change that adds Pawl.
    assert main(["--root", str(repo), "check", "--trusted-ref", "main", "--bootstrap"]) == 0


def _quarantined_repo(tmp_path: Path) -> Path:
    """A repo on branch 'agent' whose main has a 7-day quarantine for test_b."""
    repo = tmp_path / "q"
    repo.mkdir()
    _pytest_project(repo)
    (repo / "tests" / "test_ab.py").write_text(
        TESTS_AB.replace("def test_b():\n    assert True", "def test_b():\n    assert False"),
        encoding="utf-8",
    )
    reason = ["--reason", "flaky", "--days", "7", "--suite", "tests"]
    assert main(["--root", str(repo), "quarantine", "tests/test_ab.py::test_b", *reason]) == 0
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base with a quarantine")
    git(repo, "checkout", "-qb", "agent")
    return repo


def _edit_quarantine(repo: Path, **fields: str) -> None:
    path = repo / "pawl.baseline.json"
    data = json.loads(path.read_text())
    data["quarantine"][0].update(fields)
    path.write_text(json.dumps(data, indent=2) + "\n")


@pytest.mark.usefixtures("clean_env")
def test_quarantine_extension_is_flagged(tmp_path: Path) -> None:
    """F3: extending a quarantine expiry in the baseline produced no guard finding."""
    repo = _quarantined_repo(tmp_path)
    _edit_quarantine(repo, expires="2099-12-31", reason="forever")
    commit(repo, "extend the quarantine")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 1
    guard = json.loads((repo / ".pawl" / "last-guard.json").read_text())
    blocks = {f["rule"] for f in guard["findings"] if f["severity"] == "block"}
    assert {"BASELINE_LOOSENED", "PROTECTED_CHANGED"} <= blocks
    # A hand-written expiry past quarantine_max_days is refused when the baseline is read.
    assert main(["--root", str(repo), "check"]) == 2
    report = json.loads((repo / ".pawl" / "last-report.json").read_text())
    assert "quarantine_max_days" in report["error"]


@pytest.mark.usefixtures("clean_env")
def test_quarantine_reason_change_is_flagged(tmp_path: Path) -> None:
    """F3: quarantine entries were compared by test ID only."""
    repo = _quarantined_repo(tmp_path)
    _edit_quarantine(repo, reason="rewritten")
    commit(repo, "rewrite the reason")
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 1


@pytest.mark.usefixtures("clean_env")
def test_label_left_on_the_pr_does_not_approve_later_pushes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F5: the label was read from the event's label list, so a label left on
    the pull request approved every later push."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _pytest_project(repo)
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "base")
    git(repo, "checkout", "-qb", "agent")
    _break_test_b_and_hide_it(repo)
    commit(repo, "pushed after the label was applied")
    event = tmp_path / "event.json"
    head = git(repo, "rev-parse", "HEAD").strip()
    labels = [{"name": "pawl-approved"}]
    payload = {"action": "synchronize", "pull_request": {"labels": labels, "head": {"sha": head}}}
    event.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert main(["--root", str(repo), "guard", "--base", "main"]) == 1
    assert main(["--root", str(repo), "check", "--trusted-ref", "main"]) == 1


@pytest.mark.usefixtures("clean_env")
def test_report_exit_status_reflects_a_failed_check(tmp_path: Path) -> None:
    """'pawl report' exited 0 even when the last check failed; there was no way
    to gate on it. 'report --exit-status' now exits with the worst result."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _pytest_project(repo)
    (repo / "tests" / "test_ab.py").write_text(
        TESTS_AB.replace("def test_b():\n    assert True", "def test_b():\n    assert False"),
        encoding="utf-8",
    )
    assert main(["--root", str(repo), "check"]) == 1
    assert main(["--root", str(repo), "report", "--exit-status"]) == 1
    assert main(["--root", str(repo), "report"]) == 0  # the renderer default is unchanged


def _protect(repo: Path, payload: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> int:
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return main(["--root", str(repo), "hook", "protect", "--format", "claude"])


def test_protect_hook_sees_through_dotdot_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The protect hook compared the path as typed, so 'tests/../pawl.toml' or a
    symlink to the baseline slipped past it. It now checks the resolved path."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "pawl.toml").write_text(
        '[[suite]]\nname = "t"\nadapter = "pytest"\ncommand = ["true"]\n', encoding="utf-8"
    )
    (repo / "pawl.baseline.json").write_text("{}\n", encoding="utf-8")
    (repo / "notes.txt").symlink_to("pawl.baseline.json")
    (repo / "gate").symlink_to(".", target_is_directory=True)
    # Sanity: an ordinary file is allowed, the plain path is blocked.
    allowed = {"tool_name": "Write", "tool_input": {"file_path": "tests/test_x.py"}}
    assert _protect(repo, allowed, monkeypatch) == 0
    plain = {"tool_name": "Write", "tool_input": {"file_path": "pawl.toml"}}
    assert _protect(repo, plain, monkeypatch) == 2
    for path in (
        "tests/../pawl.toml",
        str(repo / "tests" / ".." / "pawl.baseline.json"),
        "notes.txt",
        str(repo / "notes.txt"),
        "gate/pawl.toml",
    ):
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}, "cwd": str(repo)}
        assert _protect(repo, payload, monkeypatch) == 2, path
