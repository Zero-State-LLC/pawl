"""The JSON and exit-code contract (docs/JSON.md)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from pawl.cli import main
from pawl.contract import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _codes(pattern: str) -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "src" / "pawl").glob("*.py"):
        found |= set(re.findall(pattern, path.read_text(encoding="utf-8")))
    return found


def test_docs_list_every_problem_code_and_finding_rule() -> None:
    doc = (ROOT / "docs" / "JSON.md").read_text(encoding="utf-8")
    codes = _codes(r'Problem\(\s*"([A-Z_]+)"') | _codes(r'Finding\(\s*"([A-Z_]+)"')
    assert codes, "no codes found; the pattern is stale"
    missing = sorted(c for c in codes if f"`{c}`" not in doc)
    assert missing == []


def _json(capsys: pytest.CaptureFixture[str]) -> dict:  # type: ignore[type-arg]
    return json.loads(capsys.readouterr().out)


def test_check_and_guard_json_carry_the_contract(
    demo_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = ["--root", str(demo_repo)]
    assert main([*root, "check", "--json"]) == 0
    check = _json(capsys)
    assert check["schema_version"] == SCHEMA_VERSION and check["exit_code"] == 0
    assert check["kind"] == "check" and check["approval"] is None
    (demo_repo / "tests" / "test_more.py").unlink()
    assert main([*root, "guard", "--base", "main", "--json"]) == 1
    guard = _json(capsys)
    assert guard["schema_version"] == SCHEMA_VERSION and guard["exit_code"] == 1
    assert main([*root, "guard", "--base", "no-such-ref", "--json"]) == 2
    error = _json(capsys)
    assert error["schema_version"] == SCHEMA_VERSION and error["exit_code"] == 2
    assert error["version"]


def test_update_json(demo_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = ["--root", str(demo_repo)]
    assert main([*root, "update", "--json"]) == 0
    data = _json(capsys)
    assert data["kind"] == "update" and data["status"] in ("unchanged", "written")
    assert data["schema_version"] == SCHEMA_VERSION and data["exit_code"] == 0
    (demo_repo / "tests" / "test_more.py").unlink()
    assert main([*root, "update", "--json"]) == 1
    data = _json(capsys)
    assert data["status"] == "refused" and data["loosened"]
    (demo_repo / "pawl.toml").write_text("not toml [")
    assert main([*root, "update", "--json"]) == 2
    data = _json(capsys)
    assert data["status"] == "error" and data["error"]


def test_report_exit_status(demo_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = ["--root", str(demo_repo)]
    assert main([*root, "report", "--exit-status"]) == 2  # no report yet
    assert main([*root, "check"]) == 0
    assert main([*root, "report", "--exit-status"]) == 0
    capsys.readouterr()
    assert main([*root, "report", "--format", "json"]) == 0
    data = _json(capsys)
    assert data["kind"] == "report" and data["exit_code"] == 0


def test_guard_error_document_has_the_full_guard_shape(
    demo_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = ["--root", str(demo_repo)]
    assert main([*root, "guard", "--base", "main", "--json"]) == 0
    ok = _json(capsys)
    assert main([*root, "guard", "--base", "no-such-ref", "--json"]) == 2
    error = _json(capsys)
    assert set(ok) <= set(error)
    assert error["approved"] is False and error["approval"] is None
    assert error["config_source"] == "" and error["findings"] == []


def test_report_envelope_exit_code_is_what_the_command_returned(
    demo_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = ["--root", str(demo_repo)]
    (demo_repo / "tests" / "test_more.py").unlink()
    assert main([*root, "guard", "--base", "main"]) == 1
    capsys.readouterr()
    assert main([*root, "report", "--format", "json"]) == 0
    data = _json(capsys)
    assert data["status"] == "fail" and data["worst_exit_code"] == 1 and data["exit_code"] == 0
    assert main([*root, "report", "--format", "json", "--exit-status"]) == 1
    data = _json(capsys)
    assert data["exit_code"] == 1 and data["worst_exit_code"] == 1
