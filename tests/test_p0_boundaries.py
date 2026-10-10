"""Bounded trust probes. Known limits are assertions, not claims of isolation.

All files and credential markers are synthetic and task-local. No real token,
host persistence, network access, or privileged environment is exercised.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from tests.conftest import commit

from pawl.adapters import parse_junit, run_suite
from pawl.cli import main
from pawl.config import SuiteConfig, load_config
from pawl.errors import ParseError
from pawl.guard import run_guard


def test_candidate_runner_inherits_environment_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = "synthetic-p0-marker"
    monkeypatch.setenv("GH_TOKEN", marker)
    code = (
        "import os; from pathlib import Path; "
        "Path('report.xml').write_text('<testsuite><testcase name=\"'"
        "+os.environ['GH_TOKEN']+'\"/></testsuite>')"
    )
    suite = SuiteConfig("probe", "junit", (sys.executable, "-c", code), junit_path="report.xml")
    assert run_suite(suite, tmp_path).outcomes == {marker: "passed"}


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_linked_report_is_a_known_same_user_limit(tmp_path: Path, link_kind: str) -> None:
    """Linked reports are rejected (was a known accept; now fail closed)."""
    source = tmp_path / "synthetic.xml"
    source.write_text('<testsuite><testcase name="forged"/></testsuite>')
    report = tmp_path / "report.xml"
    if link_kind == "symlink":
        report.symlink_to(source)
    else:
        os.link(source, report)
    with pytest.raises(ParseError, match=r"must not be a hard link|not a symlink"):
        parse_junit(report)


def test_report_identity_is_data_not_a_shell_command(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(
        '<testsuite><testcase name="../../outside; touch sentinel $(touch sentinel)"/></testsuite>'
    )
    assert list(parse_junit(report)) == ["../../outside; touch sentinel $(touch sentinel)"]
    assert not (tmp_path / "sentinel").exists()


def test_generated_workflow_is_protected(demo_repo: Path) -> None:
    workflow = demo_repo / ".github/workflows/generated.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: synthetic\n")
    commit(demo_repo, "add a generated workflow")
    report = run_guard(load_config(demo_repo), "main")
    assert report.status == "fail"
    assert any(f.rule == "PROTECTED_CHANGED" for f in report.findings)


def test_missing_comparison_ref_is_an_error(demo_repo: Path) -> None:
    assert main(["--root", str(demo_repo), "guard", "--base", "missing-p0-ref"]) == 2


def test_replay_cleans_up_its_temporary_worktree(demo_repo: Path) -> None:
    from tests.conftest import git

    path = demo_repo / "tests/test_calc.py"
    # Add a harmless comment to an existing assertion, requiring a replay.
    source = path.read_text()
    path.write_text(source.replace("assert add(2, 3) == 5", "assert add(2, 3) == 5  # unchanged"))
    commit(demo_repo, "synthetic test edit")
    before = git(demo_repo, "worktree", "list", "--porcelain")
    run_guard(load_config(demo_repo), "main", replay=True)
    assert git(demo_repo, "worktree", "list", "--porcelain") == before
