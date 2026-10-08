from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, edit

from pawl.baseline import Baseline, SuiteBaseline
from pawl.config import load_config
from pawl.guard import (
    _test_config_view,
    baseline_changes,
    glob_match,
    run_guard,
    shadowed_tests,
    split_diff,
)


def _loosen_baseline(repo: Path) -> None:
    path = repo / "pawl.baseline.json"
    data = json.loads(path.read_text())
    suite = data["suites"]["tests"]
    suite["failing_ids"] = sorted([*suite["failing_ids"], "tests/test_calc.py::test_add"])
    suite["failures"] = len(suite["failing_ids"])
    path.write_text(json.dumps(data, indent=2) + "\n")


def rules(report) -> list[str]:  # type: ignore[no-untyped-def]
    return sorted({f.rule for f in report.findings if f.severity == "block"})


def test_glob_match() -> None:
    assert glob_match("conftest.py", "**/conftest.py")
    assert glob_match("a/b/conftest.py", "**/conftest.py")
    assert glob_match("tests/x/y.py", "tests/**")
    assert glob_match("src/a.test.ts", "**/*.test.[jt]s")
    assert not glob_match("src/app.py", "tests/**")


def test_split_diff() -> None:
    removed, added = split_diff("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n+more\n")
    assert removed == ["old"] and added == ["new", "more"]


def test_shadowed_tests() -> None:
    src = "def test_a():\n    pass\n\nclass TestK:\n    def test_b(self): pass\n    def test_b(self): pass\n\ndef test_a():\n    pass\n"
    assert sorted(shadowed_tests(src)) == ["TestK.test_b", "test_a"]
    assert shadowed_tests("def broken(:\n") == []


def test_baseline_changes() -> None:
    a = Baseline(
        suites={"t": SuiteBaseline(failing_ids=["x"], collected=2, collected_ids=["x", "y"])},
        metrics={"lint": {"value": 3, "direction": "down"}},
    )
    b = Baseline(
        suites={"t": SuiteBaseline(failing_ids=[], collected=2, collected_ids=["x", "y"])},
        metrics={"lint": {"value": 2, "direction": "down"}},
    )
    loosened, tightened = baseline_changes(a.dumps(), b.dumps())
    assert loosened == [] and len(tightened) == 2
    loosened, _ = baseline_changes(b.dumps(), a.dumps())
    assert any("failing IDs added" in x for x in loosened)
    assert any("lint" in x for x in loosened)
    assert baseline_changes(a.dumps(), None)[0] == ["baseline file deleted"]


def test_test_config_view() -> None:
    a = '[project]\nname="x"\n[tool.pytest.ini_options]\naddopts="-q"\n'
    b = a.replace('"-q"', '"-q --deselect tests/test_a.py::test_x"')
    c = a.replace('name="x"', 'name="y"')
    assert _test_config_view("pyproject.toml", a) != _test_config_view("pyproject.toml", b)
    assert _test_config_view("pyproject.toml", a) == _test_config_view("pyproject.toml", c)
    pj = json.dumps({"scripts": {"test": "jest"}, "dependencies": {}})
    pj2 = json.dumps({"scripts": {"test": "jest --passWithNoTests"}, "dependencies": {}})
    assert _test_config_view("package.json", pj) != _test_config_view("package.json", pj2)


def test_clean_change_passes(demo_repo: Path) -> None:
    edit(
        demo_repo / "tests" / "test_more.py",
        "def test_is_prime_large",
        "def test_is_prime_two():\n    assert is_prime(2)\n\n\ndef test_is_prime_large",
    )
    report = run_guard(load_config(demo_repo), "main")
    assert report.status == "pass", report.to_json()


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda r: (r / "tests" / "test_more.py").unlink(), "TEST_DELETED"),
        (
            lambda r: edit(
                r / "tests" / "test_calc.py",
                "def test_add():",
                "@pytest.mark.skip\ndef test_add():",
            ),
            "SKIP_ADDED",
        ),
        (
            lambda r: edit(
                r / "tests" / "test_calc.py", "assert add(2, 3) == 5", "assert add(2, 3)"
            ),
            "TEST_MODIFIED",
        ),
        (
            lambda r: (r / "conftest.py").write_text(
                "def pytest_runtest_makereport(item, call):\n    pass\n"
            ),
            "PROTECTED_CHANGED",
        ),
        (
            lambda r: edit(
                r / "calc" / "__init__.py",
                '"""Return a + b."""',
                '"""Return a + b."""\n    import os\n    if "PYTEST_CURRENT_TEST" in os.environ:\n        return 5',
            ),
            "SUSPICIOUS_CODE",
        ),
        (
            lambda r: edit(
                r / "pyproject.toml",
                'addopts = "--strict-markers"',
                'addopts = "--strict-markers --deselect tests/test_calc.py::test_add"',
            ),
            "TEST_CONFIG_CHANGED",
        ),
        (lambda r: _loosen_baseline(r), "BASELINE_LOOSENED"),
        (
            lambda r: edit(
                r / "tests" / "test_calc.py",
                "def test_mean():",
                "def test_add():\n    assert True\n\n\ndef test_mean():",
            ),
            "TEST_SHADOWED",
        ),
    ],
)
def test_tamper_is_flagged(demo_repo: Path, mutate, expected: str) -> None:  # type: ignore[no-untyped-def]
    mutate(demo_repo)
    report = run_guard(load_config(demo_repo), "main")
    assert expected in rules(report), report.to_json()
    assert report.status == "fail"


def test_approval_label_downgrades_blocks(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (demo_repo / "tests" / "test_more.py").unlink()
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"labels": [{"name": "pawl-approved"}]}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    report = run_guard(load_config(demo_repo), "main")
    assert report.status == "pass"
    assert report.approved
    assert any(f.severity == "approved" for f in report.findings)


def test_escalation_blocks_until_resolved(demo_repo: Path) -> None:
    from pawl.cli import main

    assert (
        main(
            ["--root", str(demo_repo), "escalate", "test_x contradicts the spec", "--test", "t::x"]
        )
        == 0
    )
    report = run_guard(load_config(demo_repo), "main")
    assert "ESCALATION_OPEN" in rules(report)


@pytest.mark.slow
def test_replay_catches_weakened_assertion(demo_repo: Path) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a + b", "return a * b")
    edit(demo_repo / "tests" / "test_calc.py", "assert add(2, 3) == 5", "assert add(2, 3) == 6")
    edit(
        demo_repo / "tests" / "test_calc.py", "assert add(-2, -3) == -5", "assert add(-2, -3) == 6"
    )
    commit(demo_repo, "agent change")
    report = run_guard(load_config(demo_repo), "main", replay=True)
    replay = [f for f in report.findings if f.rule == "TESTS_WEAKENED_REPLAY"]
    assert replay, report.to_json()
    assert "tests/test_calc.py::test_add" in replay[0].ids


def test_debt_log_is_append_only(demo_repo: Path) -> None:
    log = demo_repo / "PAWL_DEBT.md"
    text = log.read_text()
    assert "recorded 1 failing" in text
    log.write_text(text.replace("recorded 1 failing", "recorded 0 failing"))
    report = run_guard(load_config(demo_repo), "main")
    assert "DEBT_LOG_REWRITTEN" in rules(report)


def test_agent_cannot_close_an_escalation(demo_repo: Path) -> None:
    from pawl.cli import main

    assert main(["--root", str(demo_repo), "escalate", "spec conflict"]) == 0
    commit(demo_repo, "escalate")
    from tests.conftest import git

    git(demo_repo, "checkout", "-q", "main")
    git(demo_repo, "merge", "-q", "--ff-only", "agent")
    git(demo_repo, "checkout", "-q", "agent")
    path = demo_repo / ".pawl" / "ESCALATIONS.md"
    path.write_text(path.read_text().replace(" open\n", " resolved\n"))
    report = run_guard(load_config(demo_repo), "main")
    assert "ESCALATION_RESOLVED" in rules(report)
