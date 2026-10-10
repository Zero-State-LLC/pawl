"""Approval provenance: who approved, from where, and for which run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.cli import main
from pawl.trust import label_approval, resolve


def _event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **payload: object) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def _labeled(
    sha: str,
    *,
    sender: dict | None = None,  # type: ignore[type-arg]
    number: int = 7,
    label: str = "pawl-approved",
) -> dict:  # type: ignore[type-arg]
    payload: dict = {  # type: ignore[type-arg]
        "action": "labeled",
        "label": {"name": label},
        "pull_request": {"number": number, "labels": [{"name": label}], "head": {"sha": sha}},
    }
    if sender is not None:
        payload["sender"] = sender
    return payload


def _head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def _tamper(repo: Path) -> None:
    (repo / "tests" / "test_more.py").unlink()
    commit(repo, "delete a test file")


def _approvers(path: Path, *names: str) -> None:
    entry = "approvers = [" + ", ".join(f'"{name}"' for name in names) + "]"
    text = path.read_text()
    if "[guard]" in text:
        path.write_text(text.replace("[guard]", f"[guard]\n{entry}", 1))
    else:
        path.write_text(text + f"\n[guard]\n{entry}\n")


def test_provenance_is_recorded_and_reported(
    demo_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(tmp_path, monkeypatch, **_labeled(sha, sender={"login": "danny", "type": "User"}))
    approval, note = label_approval("pawl-approved", demo_repo)
    assert note is None
    assert approval is not None
    assert approval.provenance() == {
        "source": "label",
        "label": "pawl-approved",
        "sha": sha,
        "actor": "danny",
        "actor_type": "User",
        "event": "pull_request",
        "action": "labeled",
        "run_id": "42",
        "pr": 7,
    }
    capsys.readouterr()
    assert main(["--root", str(demo_repo), "guard", "--base", "main", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["approval_provenance"]["actor"] == "danny"
    assert report["approval"] == {"source": "label", "label": "pawl-approved", "sha": sha}


def test_missing_sender_is_never_inferred(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    _event(tmp_path, monkeypatch, **_labeled(_head(demo_repo)))
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None
    assert note is not None and "never inferred" in note


def test_bot_sender_never_approves(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        **_labeled(_head(demo_repo), sender={"login": "github-actions[bot]", "type": "Bot"}),
    )
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None
    assert note is not None and "bot" in note


def test_approvers_must_come_from_the_trusted_base(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(demo_repo, "checkout", "-q", "main")
    _approvers(demo_repo / "pawl.toml", "danny")
    commit(demo_repo, "trust danny as an approver")
    git(demo_repo, "checkout", "-qB", "agent")
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(tmp_path, monkeypatch, **_labeled(sha, sender={"login": "mallory", "type": "User"}))
    approval, note = label_approval("pawl-approved", demo_repo, ("danny",))
    assert approval is None
    assert note is not None and "not in guard.approvers" in note
    assert resolve(demo_repo, "main").approval is None
    assert main(["--root", str(demo_repo), "guard", "--base", "main"]) == 1
    _event(tmp_path, monkeypatch, **_labeled(sha, sender={"login": "danny", "type": "User"}))
    assert resolve(demo_repo, "main").approval is not None
    assert main(["--root", str(demo_repo), "guard", "--base", "main"]) == 0


def test_head_config_cannot_add_an_approver(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(demo_repo, "checkout", "-q", "main")
    _approvers(demo_repo / "pawl.toml", "danny")
    commit(demo_repo, "trust danny as an approver")
    git(demo_repo, "checkout", "-qB", "agent")
    cfg = demo_repo / "pawl.toml"
    cfg.write_text(cfg.read_text().replace('approvers = ["danny"]', 'approvers = ["mallory"]'))
    commit(demo_repo, "trust mallory as an approver")
    _tamper(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        **_labeled(_head(demo_repo), sender={"login": "mallory", "type": "User"}),
    )
    approval, _ = label_approval("pawl-approved", demo_repo, ("danny",))
    assert approval is None
    assert main(["--root", str(demo_repo), "guard", "--base", "main"]) == 1


def test_label_removal_is_recorded_as_revocation(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        action="unlabeled",
        sender={"login": "danny", "type": "User"},
        label={"name": "pawl-approved"},
        pull_request={"number": 7, "labels": [], "head": {"sha": _head(demo_repo)}},
    )
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None
    assert note is not None and "revoked" in note
