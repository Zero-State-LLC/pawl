"""Display-only escaping must preserve identity and verdict evidence."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from benchmarks.corpus import DIAGNOSTIC_SCENARIOS

from pawl.baseline import Baseline, SuiteBaseline
from pawl.cli import _emit, main
from pawl.display import terminal
from pawl.render import check_markdown, guard_markdown


@pytest.mark.parametrize("name,label,text", DIAGNOSTIC_SCENARIOS)
def test_report_fields(name: str, label: str, text: str) -> None:
    data = {
        "status": "fail",
        "error": text,
        "notes": [text],
        "problems": [{"code": "REGRESSION", "subject": text, "message": text, "ids": [text]}],
        "isolation": {text: {text: "failed"}},
    }
    before = copy.deepcopy(data)
    result = check_markdown(data)
    assert data == before
    assert result.startswith("### Pawl check: FAIL")
    assert "(failed)" in result
    for char in ("\x1b", "\r", "\x08", "\u202e", "\u2066"):
        assert char not in result
    assert "<img" not in result
    assert "\n# PASS" not in result
    if label == "clean":
        assert "café.py" in result and "雪" in result
    guard = guard_markdown(
        {
            "status": "fail",
            "base": text,
            "findings": [{"rule": "RULE", "severity": "block", "path": text, "message": text}],
        }
    )
    assert "\x1b" not in guard and "<img" not in guard


@pytest.mark.parametrize(
    "char", ["\0", "\t", "\r", "\x1b", "\x7f", "\x9b", "\u2028", "\u202e", "\ud800"]
)
def test_terminal_controls(char: str, capsys: pytest.CaptureFixture[str]) -> None:
    _emit("error: " + char + "\nnext line")
    out = capsys.readouterr().out
    assert char not in out
    assert "\nnext line\n" in out
    assert terminal("ordinary café 雪") == "ordinary café 雪"


def test_json_protocol_remains_lossless(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {"id": "name\x1b\r\n\u202e雪"}
    _emit(json.dumps(raw))
    assert json.loads(capsys.readouterr().out) == raw


def test_cli_failure_diagnostic_and_raw_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = "print('bad\\x1b[2J\\rPASS'); raise SystemExit(7)"
    (tmp_path / "pawl.toml").write_text(
        '[[suite]]\nname="fixture"\nadapter="pytest"\ncommand='
        + json.dumps([sys.executable, "-c", script])
        + "\n"
    )
    (tmp_path / "pawl.baseline.json").write_text(
        Baseline(suites={"fixture": SuiteBaseline(collected=1, collected_ids=["ok"])}).dumps()
    )
    assert main(["--root", str(tmp_path), "check"]) == 2
    displayed = capsys.readouterr().out
    assert "\x1b" not in displayed and "\r" not in displayed
    assert "Pawl check: ERROR" in displayed
    report = json.loads((tmp_path / ".pawl/last-report.json").read_text())
    assert "\x1b" in report["error"]
    assert report["status"] == "error"


def test_literal_escape_and_control_keep_distinct_verdicts() -> None:
    from pawl.display import markdown

    actual = "test\x1b"
    literal = r"test\x1b"
    assert markdown(actual) != markdown(literal)
    rendered = check_markdown(
        {
            "status": "fail",
            "problems": [
                {
                    "code": "REGRESSION",
                    "subject": "unit",
                    "message": "failed",
                    "ids": [actual, literal],
                }
            ],
            "isolation": {"unit": {actual: "failed", literal: "passed"}},
        }
    )
    assert f"`{markdown(actual)}` (failed)" in rendered
    assert f"`{markdown(literal)}` (passed)" in rendered
