from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, edit, git

from pawl.check import report_path
from pawl.cli import main
from pawl.config import load_config
from pawl.errors import PawlError
from pawl.replay_migration import REGISTRY, digest, replace_block, resolve_migration

TEST_FILE = "tests/test_calc.py"
BEFORE = "    assert add(2, 3) == 5\n"
AFTER = "    assert add(2, 3) == 6\n"


def proposal(repo: Path) -> dict:
    report_path(repo)
    cfg = repo / "pawl.toml"
    cfg.write_text(
        cfg.read_text() + '\n[guard]\napprovers = ["reviewer"]\nrefuse_pr_author = true\n'
    )
    commit(repo, "trusted independent approval policy")
    git(repo, "branch", "-f", "main", "HEAD")
    base = git(repo, "rev-parse", "main").strip()
    before = (repo / TEST_FILE).read_text()
    edit(repo / TEST_FILE, BEFORE, AFTER)
    edit(repo / "calc/__init__.py", "return a + b", "return 6 if (a, b) == (2, 3) else a + b")
    data = {
        "schema_version": 1,
        "base_sha": base,
        "entries": [
            {
                "path": TEST_FILE,
                "function": "test_add",
                "before_sha256": digest(before),
                "after_sha256": digest((repo / TEST_FILE).read_text()),
                "reason": "Fixture: reviewed addition contract changes for this input",
                "replacements": [{"before": BEFORE, "after": AFTER}],
            }
        ],
    }
    (repo / REGISTRY).write_text(json.dumps(data))
    commit(repo, "candidate assertion migration")
    return data


def event(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **changes: object) -> None:
    payload = {
        "action": "labeled",
        "sender": {"login": "reviewer", "type": "User"},
        "label": {"name": "pawl-approved"},
        "pull_request": {
            "number": 12,
            "user": {"login": "author"},
            "head": {"sha": git(repo, "rev-parse", "HEAD").strip()},
            "labels": [{"name": "pawl-approved"}],
        },
    }
    payload.update(changes)
    path = tmp_path / "provider-event.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_RUN_ID", "1234")


def guard(repo: Path) -> tuple[int, dict]:
    rc = main(["--root", str(repo), "guard", "--base", "main", "--ci", "--replay", "--json"])
    return rc, json.loads((repo / ".pawl/last-guard.json").read_text())


def test_exact_approved_migration_replays_new_contract(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposal(demo_repo)
    event(demo_repo, tmp_path, monkeypatch)
    rc, report = guard(demo_repo)
    assert rc == 0
    assert {f["rule"] for f in report["findings"]} >= {"REPLAY_MIGRATION_APPLIED", "REPLAY_PASSED"}
    assert main(["--root", str(demo_repo), "check", "--ci", "--trusted-ref", "main"]) == 0


def test_other_assertions_in_same_file_still_block(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = proposal(demo_repo)
    edit(demo_repo / "calc/__init__.py", "return a - b", "return a + b")
    edit(demo_repo / TEST_FILE, "assert subtract(5, 3) == 2", "assert subtract(5, 3) == 8")
    data["entries"][0]["after_sha256"] = digest((demo_repo / TEST_FILE).read_text())
    (demo_repo / REGISTRY).write_text(json.dumps(data))
    commit(demo_repo, "unrelated regression hidden in candidate tests")
    event(demo_repo, tmp_path, monkeypatch)
    rc, report = guard(demo_repo)
    assert rc == 1
    assert any(
        f["rule"] == "TESTS_WEAKENED_REPLAY"
        and f["severity"] == "block"
        and "tests/test_calc.py::test_subtract" in f["ids"]
        for f in report["findings"]
    )


def test_replacement_assertion_failure_is_not_waived(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposal(demo_repo)
    edit(demo_repo / "calc/__init__.py", "return 6 if (a, b) == (2, 3) else a + b", "return a + b")
    commit(demo_repo, "contract implementation missing")
    event(demo_repo, tmp_path, monkeypatch)
    rc, report = guard(demo_repo)
    assert rc == 1
    assert any(
        f["rule"] == "TESTS_WEAKENED_REPLAY" and "tests/test_calc.py::test_add" in f["ids"]
        for f in report["findings"]
    )


@pytest.mark.parametrize(
    "kind",
    [
        "no-event",
        "author",
        "bot",
        "stale",
        "unknown-author",
        "synchronize",
        "malformed-label-list",
        "malformed-label-name",
        "malformed-author",
    ],
)
def test_invalid_approval_cannot_activate(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    proposal(demo_repo)
    event(demo_repo, tmp_path, monkeypatch)
    path = tmp_path / "provider-event.json"
    payload = json.loads(path.read_text())
    if kind == "no-event":
        monkeypatch.delenv("GITHUB_EVENT_PATH")
    elif kind == "author":
        payload["pull_request"]["user"]["login"] = "reviewer"
    elif kind == "bot":
        payload["sender"]["type"] = "Bot"
    elif kind == "stale":
        payload["pull_request"]["head"]["sha"] = "0" * 40
    elif kind == "unknown-author":
        payload["pull_request"].pop("user")
    elif kind == "synchronize":
        payload["action"] = "synchronize"
    elif kind == "malformed-label-list":
        payload["pull_request"]["labels"] = 1
    elif kind == "malformed-label-name":
        payload["pull_request"]["labels"] = [{"name": {"unexpected": "object"}}]
    else:
        payload["pull_request"]["user"]["login"] = {"unexpected": "object"}
    path.write_text(json.dumps(payload))
    assert guard(demo_repo)[0] == 2


@pytest.mark.parametrize(
    "kind",
    [
        "base",
        "before-hash",
        "after-hash",
        "duplicate",
        "unknown-field",
        "bool-version",
        "missing-assert",
        "foreign-test",
    ],
)
def test_invalid_manifest_cannot_activate(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    data = proposal(demo_repo)
    entry = data["entries"][0]
    if kind == "base":
        data["base_sha"] = "0" * 40
    elif kind == "before-hash":
        entry["before_sha256"] = "0" * 64
    elif kind == "after-hash":
        entry["after_sha256"] = "0" * 64
    elif kind == "duplicate":
        data["entries"].append(entry)
    elif kind == "unknown-field":
        data["skip_tests"] = True
    elif kind == "bool-version":
        data["schema_version"] = True
    elif kind == "missing-assert":
        entry["replacements"][0]["after"] = "    pass\n"
    else:
        entry["function"] = "test_never_existed"
    (demo_repo / REGISTRY).write_text(json.dumps(data))
    commit(demo_repo, "malformed proposal")
    event(demo_repo, tmp_path, monkeypatch)
    assert guard(demo_repo)[0] == 2


def test_dirty_candidate_rejected(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proposal(demo_repo)
    event(demo_repo, tmp_path, monkeypatch)
    (demo_repo / "unreviewed.py").write_text("print('not approved')\n")
    assert guard(demo_repo)[0] == 2


def test_manual_flag_cannot_activate(demo_repo: Path) -> None:
    proposal(demo_repo)
    assert (
        main(["--root", str(demo_repo), "guard", "--base", "main", "--replay", "--approved"]) == 2
    )


def test_replay_is_mandatory(demo_repo: Path) -> None:
    proposal(demo_repo)
    with pytest.raises(PawlError, match="requires --replay"):
        resolve_migration(
            load_config(demo_repo), git(demo_repo, "rev-parse", "main").strip(), replay=False
        )


def test_consumed_manifest_is_history_not_standing_exemption(demo_repo: Path) -> None:
    proposal(demo_repo)
    git(demo_repo, "branch", "-f", "main", "HEAD")
    base = git(demo_repo, "rev-parse", "main").strip()
    assert resolve_migration(load_config(demo_repo), base, replay=True) is None


def test_candidate_policy_cannot_create_its_own_authority(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = demo_repo / "pawl.toml"
    cfg.write_text(
        cfg.read_text() + '\n[guard]\napprovers = ["reviewer"]\nrefuse_pr_author = true\n'
    )
    (demo_repo / REGISTRY).write_text("{}")
    commit(demo_repo, "untrusted candidate policy")
    event(demo_repo, tmp_path, monkeypatch)
    rc, report = guard(demo_repo)
    assert rc == 2
    assert "trusted policy" in report["error"]


def test_bad_encoding_is_a_closed_error(demo_repo: Path) -> None:
    (demo_repo / REGISTRY).write_bytes(b"\xff")
    rc, report = guard(demo_repo)
    assert rc == 2
    assert "REPLAY_MIGRATION_INVALID" in report["error"]
    assert report["error_code"] == "REPLAY_MIGRATION_INVALID"


def test_assignment_retirement_preserves_other_assertions() -> None:
    before = "    assert run() == 0\n    wf = read_workflow()\n    assert wf == expected\n"
    after = "    assert run() == 2\n    assert not workflow_exists()\n"
    source = "def test_setup():\n" + before + "    assert hashes_are_valid()\n"
    candidate = source.replace(before, after)
    assert replace_block(source, candidate, "test_setup", before, after) == candidate


def test_overlay_keeps_imports_prefix_and_suffix() -> None:
    source = "import os\n\ndef test_one():\n    setup()\n    assert old()\n    cleanup()\n"
    candidate = source.replace("    assert old()\n", "    assert new()\n")
    assert (
        replace_block(source, candidate, "test_one", "    assert old()\n", "    assert new()\n")
        == candidate
    )


@pytest.mark.parametrize(
    "after", ["    return\n", "assert new()\n", "    assert new(); bypass()\n"]
)
def test_overlay_cannot_escape_assertion_span(after: str) -> None:
    source = "def test_one():\n    assert old()\n"
    with pytest.raises(PawlError):
        replace_block(
            source, "def test_one():\n    assert new()\n", "test_one", "    assert old()\n", after
        )
