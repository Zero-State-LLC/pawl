"""Untrusted report limits, descriptor safety, and CLI fail-closed outcomes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from benchmarks.corpus import REPORT_BOUND_SCENARIOS

from pawl.adapters import parse_cargo, parse_go_json, parse_jest_json, parse_junit
from pawl.baseline import Baseline, SuiteBaseline
from pawl.cli import main
from pawl.errors import ParseError
from pawl.evidence import ReportError, load_json, read_report
from pawl.runner import ExecutionLimits

LIMITS = ExecutionLimits(max_report_bytes=65536, max_test_records=2, max_parse_depth=8)


@pytest.mark.parametrize("name,label,xml,code", REPORT_BOUND_SCENARIOS)
def test_report_cli(tmp_path: Path, name: str, label: str, xml: str, code: str | None) -> None:
    script = f"from pathlib import Path; Path('report.xml').write_text({xml!r})"
    (tmp_path / "pawl.toml").write_text(
        '[execution]\nmax_test_records=2\n[[suite]]\nname="fixture"\nadapter="junit"\n'
        'junit_path="report.xml"\ncommand=' + json.dumps([sys.executable, "-c", script]) + "\n"
    )
    (tmp_path / "pawl.baseline.json").write_text(
        Baseline(suites={"fixture": SuiteBaseline(collected=1, collected_ids=["ok"])}).dumps()
    )
    assert main(["--root", str(tmp_path), "check", "--json"]) == (2 if label == "bad" else 0)
    report = json.loads((tmp_path / ".pawl/last-report.json").read_text())
    if code:
        assert report["error_code"] == code


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "parent_symlink"])
def test_unsafe_files(tmp_path: Path, kind: str) -> None:
    target = tmp_path / "target"
    target.write_text("{}")
    report = tmp_path / "report"
    if kind == "symlink":
        report.symlink_to(target)
    elif kind == "hardlink":
        os.link(target, report)
    elif kind == "fifo":
        os.mkfifo(report)
    else:
        directory = tmp_path / "real"
        directory.mkdir()
        (directory / "report").write_text("{}")
        (tmp_path / "link").symlink_to(directory, target_is_directory=True)
        report = tmp_path / "link/report"
    with pytest.raises(ParseError):
        read_report(report, LIMITS)


def test_exact_byte_boundary(tmp_path: Path) -> None:
    path = tmp_path / "report"
    path.write_bytes(b" " * 65536)
    assert len(read_report(path, LIMITS)) == 65536
    path.write_bytes(b" " * 65537)
    with pytest.raises(ReportError, match="REPORT_LIMIT"):
        read_report(path, LIMITS)


@pytest.mark.parametrize("text", ["[" * 9 + "0" + "]" * 9, '{"a":NaN}', '{"a":'])
def test_invalid_json(text: str) -> None:
    with pytest.raises(ParseError):
        load_json(text, LIMITS)


def test_json_string_braces_are_not_depth() -> None:
    text = json.dumps({"a": '["' * 100})
    assert load_json(text, LIMITS) == {"a": '["' * 100}


def test_xml_depth_and_utf16_dtd(tmp_path: Path) -> None:
    path = tmp_path / "report"
    path.write_bytes('<!DOCTYPE testsuite [<!ENTITY x "ok">]><testsuite/>'.encode("utf-16"))
    with pytest.raises(ParseError, match="DTD"):
        parse_junit(path, limits=LIMITS)
    path.write_text("<testsuite>" + "<x>" * 8 + "</x>" * 8 + "</testsuite>")
    with pytest.raises(ReportError, match="PARSE_LIMIT"):
        parse_junit(path, limits=LIMITS)


@pytest.mark.parametrize("adapter", ["jest", "go", "cargo"])
def test_duplicate_records_count_before_dedup(tmp_path: Path, adapter: str) -> None:
    with pytest.raises(ReportError, match="REPORT_LIMIT"):
        if adapter == "jest":
            parse_jest_json(
                {
                    "testResults": [
                        {"assertionResults": [{"title": "same", "status": "passed"}] * 3}
                    ]
                },
                tmp_path,
                limits=LIMITS,
            )
        elif adapter == "go":
            parse_go_json('{"Action":"pass","Test":"same"}\n' * 3, limits=LIMITS)
        else:
            parse_cargo("test same ... ok\n" * 3, limits=LIMITS)


@pytest.mark.parametrize("value", [True, -1, "0", 0.5])
def test_jest_invalid_counter(tmp_path: Path, value: object) -> None:
    with pytest.raises(ParseError):
        parse_jest_json({"testResults": [], "numFailedTests": value}, tmp_path)


def test_file_swap_during_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "report"
    path.write_text("{}")
    replacement = tmp_path / "replacement"
    replacement.write_text("{}")
    real_open = os.open

    def swap(file: str, flags: int, *, dir_fd: int | None = None) -> int:
        if file == "report":
            replacement.replace(path)
        return real_open(file, flags, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swap)
    with pytest.raises(ParseError, match="changed while opening"):
        read_report(path, LIMITS)


def test_file_growth_during_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "report"
    path.write_bytes(b"x" * 65536)
    real_read = os.read
    first = True

    def grow(fd: int, size: int) -> bytes:
        nonlocal first
        data = real_read(fd, size)
        if first:
            first = False
            with path.open("ab") as stream:
                stream.write(b"x")
        return data

    monkeypatch.setattr(os, "read", grow)
    with pytest.raises(ReportError, match="REPORT_LIMIT"):
        read_report(path, LIMITS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_report_bytes", True),
        ("max_report_bytes", 65535),
        ("max_test_records", 0),
        ("max_test_records", 1000001),
        ("max_parse_depth", 7),
        ("max_parse_depth", 257),
    ],
)
def test_invalid_report_policy(field: str, value: int) -> None:
    from pawl.runner import ExecutionError

    with pytest.raises(ExecutionError):
        ExecutionLimits(**{field: value}).validate()
