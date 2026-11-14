"""Bounded authenticated observations and no inferred CI readiness."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from benchmarks.corpus import GITHUB_DOCTOR_CLEAN_POLICY, GITHUB_DOCTOR_SCENARIOS

from pawl import github_doctor as github
from pawl.doctor import diagnose

TOKEN = "synthetic-token-not-a-real-credential"
BRANCH = {"name": "main", "commit": {"sha": "a" * 40}}
POLICY = GITHUB_DOCTOR_CLEAN_POLICY


class Reply:
    def __init__(
        self, status: int = 200, body: bytes = b"{}", headers: dict[str, str] | None = None
    ):
        self.status = status
        self.body = body
        self.headers = headers or {}

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name, default)

    def read1(self, size: int) -> bytes:
        data, self.body = self.body[:size], self.body[size:]
        return data


def transport(monkeypatch: pytest.MonkeyPatch, reply: Reply) -> list[Any]:
    calls: list[Any] = []

    class Connection:
        def __init__(self, host, **kwargs):
            calls.append((host, kwargs))

        def request(self, method, path, *, headers):
            calls.append((method, path, headers))

        def getresponse(self):
            return reply

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(github.http.client, "HTTPSConnection", Connection)
    return calls


@pytest.mark.parametrize("name,status", GITHUB_DOCTOR_SCENARIOS)
def test_denial_and_redirect_never_become_evidence(
    monkeypatch: pytest.MonkeyPatch, name: str, status: int
) -> None:
    calls = transport(
        monkeypatch, Reply(status, TOKEN.encode(), {"Location": "https://evil.invalid"})
    )
    result = github.fetch("/repos/o/r/branches/main", TOKEN)
    assert result.problem and result.data is None
    assert TOKEN not in result.problem
    assert calls[0][0] == "api.github.com"
    assert len([call for call in calls if isinstance(call, tuple) and call[0] == "GET"]) == 1
    assert calls[-1] == "closed"


@pytest.mark.parametrize(
    "body",
    [
        b"{",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b"\xff",
        b"[" * 65 + b"0" + b"]" * 65,
        b"x" * (github.LIMIT + 1),
    ],
    ids=[
        "invalid-json",
        "duplicate-key",
        "nonfinite-json",
        "invalid-utf8",
        "deep-json",
        "oversized-body",
    ],
)
def test_malformed_oversized_and_deep_bodies(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    transport(monkeypatch, Reply(body=body))
    result = github.fetch("/repos/o/r/branches/main", TOKEN)
    assert result.problem and result.data is None


def test_transport_valid_body_is_bounded_and_get_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = transport(
        monkeypatch, Reply(body=b'{"ok":true}', headers={"Link": '<https://evil>; rel="next"'})
    )
    result = github.fetch("/repos/o/r/rules/branches/main", TOKEN)
    assert result.data == {"ok": True} and result.paginated
    assert calls[1][0] == "GET"
    assert calls[1][2]["Authorization"] == "Bearer " + TOKEN
    assert calls[1][2]["Accept-Encoding"] == "identity"


def test_network_exception_never_echoes_token(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            raise OSError(TOKEN)

        def close(self):
            pass

    monkeypatch.setattr(github.http.client, "HTTPSConnection", Connection)
    result = github.fetch("/repos/o/r/branches/main", TOKEN)
    assert result.problem and TOKEN not in result.problem


def responses(
    monkeypatch: pytest.MonkeyPatch,
    policy: dict[str, Any] | None = None,
    rules: github.Response | None = None,
    branch: dict[str, Any] | None = None,
) -> list[str]:
    monkeypatch.setenv("GH_TOKEN", TOKEN)
    paths: list[str] = []

    def fetch(path, token):
        assert token == TOKEN
        paths.append(path)
        if "/protection" in path:
            return github.Response(copy.deepcopy(policy if policy is not None else POLICY))
        if "/rules/" in path:
            return rules if rules is not None else github.Response([])
        return github.Response(branch if branch is not None else BRANCH)

    monkeypatch.setattr(github, "fetch", fetch)
    return paths


def statuses() -> dict[str, str]:
    return {o.id: o.status for o in github.inspect_github("owner/repo", "main", "pawl", 123)}


def test_strong_classic_policy_verifies_only_supported_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = responses(monkeypatch)
    result = statuses()
    assert result["ci.last_push_review"] == result["ci.current_base_checks"] == "pass"
    assert (
        result["ci.independent_review"]
        == result["ci.code_owner_review"]
        == result["ci.release_controls"]
        == "unknown"
    )
    assert len(paths) == 3


@pytest.mark.parametrize(
    "change",
    [
        "admin_bypass",
        "review_bypass",
        "missing_bypass",
        "bool_count",
        "wrong_app",
        "missing_expectation",
    ],
)
def test_incomplete_or_weak_binding_never_passes(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    policy = copy.deepcopy(POLICY)
    if change == "admin_bypass":
        policy["enforce_admins"]["enabled"] = False
    elif change == "review_bypass":
        policy["required_pull_request_reviews"]["bypass_pull_request_allowances"]["users"] = [
            {"login": "bypass"}
        ]
    elif change == "missing_bypass":
        del policy["required_pull_request_reviews"]["bypass_pull_request_allowances"]
    elif change == "bool_count":
        policy["required_pull_request_reviews"]["required_approving_review_count"] = True
    elif change == "wrong_app":
        policy["required_status_checks"]["checks"][0]["app_id"] = 456
    responses(monkeypatch, policy)
    observed = github.inspect_github(
        "owner/repo", "main", None if change == "missing_expectation" else "pawl", 123
    )
    result = {o.id: o.status for o in observed}
    if change in ("bool_count",):
        assert result["ci.last_push_review"] == "unknown"
    else:
        assert result["ci.current_base_checks"] == "unknown"


@pytest.mark.parametrize(
    "rules,expected",
    [
        (github.Response([]), "fail"),
        (github.Response([{"type": "pull_request"}]), "unknown"),
        (github.Response([], paginated=True), "unknown"),
        (github.Response(problem="HTTP 403"), "unknown"),
    ],
)
def test_ruleset_alternatives_and_missing_pages_prevent_false_failure(
    monkeypatch: pytest.MonkeyPatch,
    rules: github.Response,
    expected: str,
) -> None:
    policy = copy.deepcopy(POLICY)
    policy["required_pull_request_reviews"]["require_last_push_approval"] = False
    policy["required_status_checks"]["strict"] = False
    responses(monkeypatch, policy, rules)
    result = statuses()
    assert result["ci.last_push_review"] == result["ci.current_base_checks"] == expected


@pytest.mark.parametrize(
    "repository,branch",
    [(None, None), ("https://evil/x", "main"), ("o/r", "x\r\nHost:evil"), ("o/..", "main")],
)
def test_explicit_target_required_before_credentials_or_network(
    monkeypatch: pytest.MonkeyPatch,
    repository: str | None,
    branch: str | None,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("network should not be reached")

    monkeypatch.setattr(github, "fetch", forbidden)
    result = github.inspect_github(repository, branch, None, None)
    assert all(o.status == "unknown" for o in result)


def test_missing_credentials_do_not_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert all(o.status == "unknown" for o in github.inspect_github("o/r", "main", None, None))


def test_mismatched_branch_stops_before_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = responses(monkeypatch, branch={"name": "other", "commit": {"sha": "a" * 40}})
    assert statuses()["github.branch"] == "unknown"
    assert len(paths) == 1


def test_online_integration_cannot_claim_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_doctor import project

    project(tmp_path)
    workflow = tmp_path / ".github/workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("name: example")
    responses(monkeypatch)
    report = diagnose(
        tmp_path,
        online=True,
        repository="owner/repo",
        branch="main",
        expected_check="pawl",
        expected_app_id=123,
    ).to_json()
    assert (
        report["scope"] == "online-ci"
        and report["readiness"] == "unknown"
        and report["exit_code"] == 2
    )
    assert TOKEN not in json.dumps(report)


def test_deadline_and_encoding_errors_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    transport(monkeypatch, Reply(headers={"Content-Encoding": "gzip"}))
    assert github.fetch("/repos/o/r/branches/main", TOKEN).problem
    transport(monkeypatch, Reply())
    times = iter([0, 16])
    monkeypatch.setattr(github.time, "monotonic", lambda: next(times))
    assert "deadline" in github.fetch("/repos/o/r/branches/main", TOKEN).problem


@pytest.mark.parametrize("token", ["", "bad\r\nheader", "bad token", "x" * 8193])
def test_invalid_credentials_never_create_connection(
    monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("connection attempted")

    monkeypatch.setattr(github.http.client, "HTTPSConnection", forbidden)
    assert github.fetch("/repos/o/r/branches/main", token).problem


def test_offline_never_uses_online_target_or_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_doctor import project

    project(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("offline request attempted")

    monkeypatch.setenv("GH_TOKEN", TOKEN)
    monkeypatch.setattr(github, "fetch", forbidden)
    assert diagnose(tmp_path, repository="owner/repo", branch="main").to_json()["exit_code"] == 0


def test_malformed_policy_shape_is_not_a_successful_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses(monkeypatch, policy={})
    result = statuses()
    assert result["github.branch_protection"] == "unknown"
    assert all(value == "unknown" for key, value in result.items() if key.startswith("ci."))


def test_online_cli_wires_explicit_target_and_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tests.test_doctor import project, snapshot

    from pawl.cli import main

    project(tmp_path)
    workflow = tmp_path / ".github/workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("name: example")
    paths = responses(monkeypatch)
    before = snapshot(tmp_path)
    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "doctor",
                "--online",
                "--repository",
                "owner/repo",
                "--branch",
                "main",
                "--expected-check",
                "pawl",
                "--expected-app-id",
                "123",
                "--json",
            ]
        )
        == 2
    )
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == "online-ci"
    assert len(paths) == 3
    assert TOKEN not in json.dumps(report)
    assert snapshot(tmp_path) == before
