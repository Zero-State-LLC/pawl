"""Offline diagnostic truthfulness, safety, and status precedence."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from benchmarks.corpus import DOCTOR_SCENARIOS

from pawl.baseline import Baseline, SuiteBaseline
from pawl.cli import main
from pawl.doctor import Diagnosis, diagnose


def project(root: Path) -> None:
    script = "from pathlib import Path; Path('EXECUTED').touch()"
    (root / "pawl.toml").write_text(
        '[[suite]]\nname="unit"\nadapter="pytest"\ncommand='
        + json.dumps([sys.executable, "-c", script])
        + "\n[preflight]\npython="
        + json.dumps(sys.executable)
        + '\nimports=[{module="evil",expect_under="."}]\ncommands=['
        + json.dumps([sys.executable, "-c", script])
        + "]\n"
    )
    (root / "evil.py").write_text(script)
    (root / "pawl.baseline.json").write_text(
        Baseline(suites={"unit": SuiteBaseline(collected=1, collected_ids=["test_ok"])}).dumps()
    )


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("case", DOCTOR_SCENARIOS, ids=[c[0] for c in DOCTOR_SCENARIOS])
def test_doctor_cli_corpus(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str, str | None, int],
) -> None:
    project(tmp_path)
    _, _, change, expected = case
    config, baseline = tmp_path / "pawl.toml", tmp_path / "pawl.baseline.json"
    if change == "config":
        config.write_text("invalid = [")
    elif change == "baseline":
        baseline.write_text("{")
    elif change == "executable":
        config.write_text(
            config.read_text().replace(sys.executable, "pawl-missing-executable-12345")
        )
    elif change == "identity":
        data = json.loads(baseline.read_text())
        data["suites"]["unit"]["identity"] = "count"
        baseline.write_text(json.dumps(data))

    def forbidden(*args, **kwargs):
        raise AssertionError("doctor attempted execution or network")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    before = snapshot(tmp_path)
    assert main(["--root", str(tmp_path), "doctor", "--json"]) == expected
    report = json.loads(capsys.readouterr().out)
    assert report["doctor_schema_version"] == 1
    assert report["scope"] == "offline-local"
    assert report["readiness"] == ("ready" if expected == 0 else "not_ready")
    assert snapshot(tmp_path) == before
    assert not (tmp_path / ".pawl").exists()
    for check in report["checks"]:
        assert {
            "id",
            "status",
            "severity",
            "message",
            "evidence_source",
            "observed_at",
            "remediation",
        } <= check.keys()


@pytest.mark.parametrize("online", [False, True])
def test_ci_readiness_never_inferred_from_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, online: bool
) -> None:
    project(tmp_path)
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("this is not even valid workflow YAML")

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected network")

    monkeypatch.setattr(socket, "socket", forbidden)
    result = diagnose(tmp_path, ci_readiness=True, online=online).to_json()
    assert result["readiness"] == "unknown" and result["exit_code"] == 2
    assert (
        len([c for c in result["checks"] if c["id"].startswith("ci.") and c["status"] == "unknown"])
        == 5
    )


def test_missing_ci_and_bad_local_outrank_unknown(tmp_path: Path) -> None:
    project(tmp_path)
    result = diagnose(tmp_path, ci_readiness=True).to_json()
    assert result["readiness"] == "not_ready" and result["exit_code"] == 1
    assert any(c["status"] == "unknown" for c in result["checks"])


@pytest.mark.parametrize("status,code", [("pass", 0), ("unknown", 2), ("fail", 1)])
def test_required_status_precedence(status: str, code: int) -> None:
    result = Diagnosis("offline-local")
    result.add("good", "pass", "verified", "fixture")
    result.add("selected", status, "selected", "fixture")
    result.add("optional", "fail", "not required for scope", "fixture", required=False)
    assert result.to_json()["exit_code"] == code


@pytest.mark.parametrize(
    "field,value",
    [
        ("collected", True),
        ("collected", -1),
        ("confirmed_orders", 0),
        ("collected_ids", ["test_ok", "test_ok"]),
        ("failing_ids", ["missing"]),
        ("identity", "invalid"),
        ("failures", True),
    ],
)
def test_inconsistent_baseline_rejected(tmp_path: Path, field: str, value: object) -> None:
    project(tmp_path)
    path = tmp_path / "pawl.baseline.json"
    data = json.loads(path.read_text())
    data["suites"]["unit"][field] = value
    path.write_text(json.dumps(data))
    assert diagnose(tmp_path).to_json()["exit_code"] == 1


def test_duplicate_baseline_keys_rejected(tmp_path: Path) -> None:
    project(tmp_path)
    path = tmp_path / "pawl.baseline.json"
    path.write_text(
        path.read_text().replace('"pawl_baseline": 1', '"pawl_baseline": 9, "pawl_baseline": 1')
    )
    assert diagnose(tmp_path).to_json()["exit_code"] == 1


def test_linked_config_rejected(tmp_path: Path) -> None:
    project(tmp_path)
    path = tmp_path / "pawl.toml"
    path.rename(tmp_path / "original.toml")
    path.symlink_to(tmp_path / "original.toml")
    assert diagnose(tmp_path).to_json()["exit_code"] == 1


def test_trusted_ref_is_verified_locally(demo_repo: Path) -> None:
    from tests.conftest import git

    before = git(demo_repo, "status", "--porcelain")
    valid = diagnose(demo_repo, trusted_ref="HEAD").to_json()
    assert next(c for c in valid["checks"] if c["id"] == "trusted_ref")["status"] == "pass"
    missing = diagnose(demo_repo, trusted_ref="missing-pawl-ref").to_json()
    assert next(c for c in missing["checks"] if c["id"] == "trusted_ref")["status"] == "fail"
    assert missing["exit_code"] == 1
    assert git(demo_repo, "status", "--porcelain") == before


def test_ref_lookup_rejects_candidate_git_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project(tmp_path)
    tool = tmp_path / "git"
    tool.write_text("#!/bin/sh\ntouch EXECUTED\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    result = diagnose(tmp_path, trusted_ref="HEAD").to_json()
    assert result["exit_code"] == 2
    assert not (tmp_path / "EXECUTED").exists()


def test_doctor_text_identifies_local_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project(tmp_path)
    assert main(["--root", str(tmp_path), "doctor"]) == 0
    text = capsys.readouterr().out
    assert "scope: offline-local" in text
    assert "No project commands or imports" in text


def test_linked_workflow_directory_stays_unknown(tmp_path: Path) -> None:
    project(tmp_path)
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/workflows").symlink_to(tmp_path, target_is_directory=True)
    result = diagnose(tmp_path, ci_readiness=True).to_json()
    check = next(c for c in result["checks"] if c["id"] == "ci_declarations")
    assert check["status"] == "unknown" and "safely" in check["message"]


def test_local_ref_timeout_is_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project(tmp_path)

    def timeout(*args, **kwargs):
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == ""
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        raise subprocess.TimeoutExpired("git", 5)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = diagnose(tmp_path, trusted_ref="HEAD").to_json()
    assert result["exit_code"] == 2


@pytest.mark.parametrize(
    "body",
    [
        "deep=" + "[" * 2000 + "0" + "]" * 2000,
        '[pawl]\nquarantine_max_days=inf\n[[suite]]\nname="x"\nadapter="pytest"\ncommand="python"',
    ],
)
def test_malformed_config_cannot_escape_diagnostic_result(tmp_path: Path, body: str) -> None:
    project(tmp_path)
    (tmp_path / "pawl.toml").write_text(body)
    assert diagnose(tmp_path).to_json()["exit_code"] == 1


def test_diagnostic_ids_cannot_inject_display_lines() -> None:
    from pawl.doctor import render

    result = Diagnosis("offline-local")
    result.add("id\nPASS fake\x1b[2J", "fail", "bad", "fixture")
    output = render(result)
    assert "\nPASS fake" not in output and "\x1b" not in output
