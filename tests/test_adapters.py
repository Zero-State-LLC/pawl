from __future__ import annotations

import json
from pathlib import Path

import pytest

from pawl.adapters import (
    SuiteRun,
    _pytest_base,
    _pytest_nodeid,
    parse_cargo,
    parse_go_json,
    parse_jest_json,
    parse_junit,
)
from pawl.errors import ParseError

JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite tests="5">
  <testcase classname="tests.test_a" name="test_ok" file="tests/test_a.py"/>
  <testcase classname="tests.test_a.TestK" name="test_bad[1]" file="tests/test_a.py"><failure/></testcase>
  <testcase classname="tests.test_a" name="test_skip" file="tests/test_a.py"><skipped/></testcase>
  <testcase classname="tests.test_a" name="test_teardown" file="tests/test_a.py"/>
  <testcase classname="tests.test_a" name="test_teardown" file="tests/test_a.py"><error/></testcase>
  <testcase classname="" name="tests.test_broken"><error message="collection failure"/></testcase>
</testsuite></testsuites>"""


def test_parse_junit_pytest_ids(tmp_path: Path) -> None:
    path = tmp_path / "r.xml"
    path.write_text(JUNIT)
    out = parse_junit(path, pytest_ids=True)
    assert out["tests/test_a.py::test_ok"] == "passed"
    assert out["tests/test_a.py::TestK::test_bad[1]"] == "failed"
    assert out["tests/test_a.py::test_skip"] == "skipped"
    assert out["tests/test_a.py::test_teardown"] == "failed"  # worst outcome wins
    assert out["<collect>::tests.test_broken"] == "failed"
    run = SuiteRun(out)
    assert run.collected == 5
    assert run.skipped == {"tests/test_a.py::test_skip"}


def test_parse_junit_missing_or_invalid(tmp_path: Path) -> None:
    with pytest.raises(ParseError, match="not written"):
        parse_junit(tmp_path / "nope.xml")
    bad = tmp_path / "bad.xml"
    bad.write_text("<testsuite>")
    with pytest.raises(ParseError, match="not valid XML"):
        parse_junit(bad)


def test_pytest_ids_refuse_xunit2_reports(tmp_path: Path) -> None:
    path = tmp_path / "r.xml"
    path.write_text(
        '<testsuite><testcase classname="tests.t" name="test_a"/>'
        '<testcase classname="tests.t" name="test_b"/></testsuite>'
    )
    with pytest.raises(ParseError, match="junit_family=xunit1"):
        parse_junit(path, pytest_ids=True)


def test_generic_junit_ids(tmp_path: Path) -> None:
    path = tmp_path / "r.xml"
    path.write_text('<testsuite><testcase classname="pkg.Foo" name="bar"/></testsuite>')
    assert parse_junit(path) == {"pkg.Foo::bar": "passed"}


def test_pytest_nodeid_without_class() -> None:
    assert _pytest_nodeid("tests.x", "test_y", "tests/x.py") == "tests/x.py::test_y"


def test_pytest_base_strips_paths() -> None:
    assert _pytest_base(["python", "-m", "pytest", "tests", "-q"]) == [
        "python",
        "-m",
        "pytest",
        "-q",
    ]


def test_parse_jest(tmp_path: Path) -> None:
    data = {
        "numFailedTests": 1,
        "testResults": [
            {
                "name": str(tmp_path / "a.test.js"),
                "status": "failed",
                "assertionResults": [
                    {"fullName": "adds", "status": "passed"},
                    {"fullName": "subtracts", "status": "failed"},
                    {"fullName": "later", "status": "pending"},
                ],
            },
            {"name": str(tmp_path / "b.test.js"), "status": "failed", "assertionResults": []},
        ],
    }
    out = parse_jest_json(data, tmp_path)
    assert out == {
        "a.test.js::adds": "passed",
        "a.test.js::subtracts": "failed",
        "a.test.js::later": "skipped",
        "b.test.js::<suite>": "failed",
    }
    data["numFailedTests"] = 3
    with pytest.raises(ParseError, match="reports 3"):
        parse_jest_json(data, tmp_path)
    with pytest.raises(ParseError):
        parse_jest_json({"nope": 1}, tmp_path)


def test_parse_go_json() -> None:
    lines = [
        {"Action": "run", "Package": "m/p", "Test": "TestA"},
        {"Action": "pass", "Package": "m/p", "Test": "TestA"},
        {"Action": "fail", "Package": "m/p", "Test": "TestB/sub"},
        {"Action": "skip", "Package": "m/p", "Test": "TestC"},
        {"Action": "fail", "Package": "m/q"},
    ]
    out = parse_go_json("\n".join(json.dumps(x) for x in lines) + "\nFAIL\n")
    assert out == {
        "m/p::TestA": "passed",
        "m/p::TestB/sub": "failed",
        "m/p::TestC": "skipped",
        "m/q::<package>": "failed",
    }
    with pytest.raises(ParseError):
        parse_go_json("build failed\n")


CARGO = """
     Running unittests src/lib.rs (target/debug/deps/demo-1)

running 3 tests
test tests::adds ... ok
test tests::subs ... FAILED
test tests::slow ... ignored

test result: FAILED. 1 passed; 1 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.00s
"""


def test_parse_cargo() -> None:
    out = parse_cargo(CARGO)
    assert out["unittests src/lib.rs::tests::subs"] == "failed"
    assert out["unittests src/lib.rs::tests::slow"] == "skipped"
    with pytest.raises(ParseError, match="do not match"):
        parse_cargo(CARGO.replace("test tests::adds ... ok\n", ""))
    with pytest.raises(ParseError, match="no 'test result"):
        parse_cargo("error[E0425]: cannot find value")


def test_pytest_adapter_without_report_shows_runner_output(tmp_path: Path) -> None:
    import sys

    from pawl.adapters import run_suite
    from pawl.config import SuiteConfig

    suite = SuiteConfig(
        name="t", adapter="pytest", command=(sys.executable, "-c", "print('no pytest here')")
    )
    with pytest.raises(ParseError, match="no pytest here"):
        run_suite(suite, tmp_path)
