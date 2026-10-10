"""P0 attack/clean fixtures exercise real subprocesses and CLI exit contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from benchmarks.corpus import P0_PYTEST_EXITS, P0_REPORT_SCENARIOS

from pawl.adapters import run_suite
from pawl.baseline import Baseline, SuiteBaseline
from pawl.cli import main
from pawl.config import SuiteConfig
from pawl.errors import ParseError

CASES = P0_REPORT_SCENARIOS


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_junit_attack_and_clean_fixtures(tmp_path: Path, case: dict[str, object]) -> None:
    code = (
        "from pathlib import Path; "
        f"Path('report.xml').write_text({case['xml']!r}); "
        f"raise SystemExit({case['exit']})"
    )
    suite = SuiteConfig("fixture", "junit", (sys.executable, "-c", code), junit_path="report.xml")
    if case["error"]:
        with pytest.raises(ParseError, match=str(case["error"])):
            run_suite(suite, tmp_path)
    else:
        result = run_suite(suite, tmp_path)
        assert result.exit_code == case["exit"]
        assert result.outcomes


def test_stale_report_is_removed_and_cli_returns_error(tmp_path: Path) -> None:
    (tmp_path / "pawl.toml").write_text(
        '[[suite]]\nname="fixture"\nadapter="junit"\njunit_path="report.xml"\n'
        f'command=[{json.dumps(sys.executable)}, "-c", "pass"]\n',
        encoding="utf-8",
    )
    (tmp_path / "pawl.baseline.json").write_text(
        Baseline(suites={"fixture": SuiteBaseline(collected=1, collected_ids=["ok"])}).dumps(),
        encoding="utf-8",
    )
    (tmp_path / "report.xml").write_text('<testsuite><testcase name="ok"/></testsuite>')
    assert main(["--root", str(tmp_path), "check"]) == 2
    report = json.loads((tmp_path / ".pawl/last-report.json").read_text())
    assert report["status"] == "error"
    assert "not written" in report["error"]
    assert not (tmp_path / "report.xml").exists()


@pytest.mark.parametrize("exit_code", P0_PYTEST_EXITS)
def test_pytest_abnormal_exit_cannot_launder_a_passing_report(
    tmp_path: Path, exit_code: int
) -> None:
    xml = '<testsuite><testcase file="tests/test_a.py" name="test_a"/></testsuite>'
    code = (
        "import sys; from pathlib import Path; "
        "p=next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--junitxml=')); "
        f"Path(p).write_text({xml!r}); raise SystemExit({exit_code})"
    )
    suite = SuiteConfig("fixture", "pytest", (sys.executable, "-c", code))
    with pytest.raises(ParseError, match="pytest exited"):
        run_suite(suite, tmp_path)


def test_real_pytest_no_collection_remains_measurable(tmp_path: Path) -> None:
    suite = SuiteConfig("fixture", "pytest", (sys.executable, "-m", "pytest", "-q"))
    result = run_suite(suite, tmp_path)
    assert result.exit_code == 5
    assert result.outcomes == {}
