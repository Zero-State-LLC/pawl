"""The approval label is bound to the commit it was applied at."""

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


def _labeled(sha: str, label: str = "pawl-approved", applied: str | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "action": "labeled",
        "label": {"name": applied or label},
        "pull_request": {"labels": [{"name": label}], "head": {"sha": sha}},
    }


def _head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def _tamper(repo: Path) -> None:
    (repo / "tests" / "test_more.py").unlink()
    commit(repo, "delete a test file")


def test_label_applied_at_this_commit_approves(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(tmp_path, monkeypatch, **_labeled(sha))
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is not None and approval.sha == sha and note is None
    assert main(["--root", str(demo_repo), "guard", "--base", "main"]) == 0
    guard = json.loads((demo_repo / ".pawl" / "last-guard.json").read_text())
    assert guard["approval"] == {"source": "label", "label": "pawl-approved", "sha": sha}
    assert any(sha[:12] in n for n in guard["notes"])


def test_label_does_not_approve_a_later_push(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    labeled_at = _head(demo_repo)
    (demo_repo / "later.txt").write_text("pushed after the label\n")
    commit(demo_repo, "later push")
    _event(tmp_path, monkeypatch, **_labeled(labeled_at))
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None and note is not None and labeled_at[:12] in note
    _event(
        tmp_path,
        monkeypatch,
        action="synchronize",
        pull_request={"labels": [{"name": "pawl-approved"}], "head": {"sha": _head(demo_repo)}},
    )
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None and note is not None and "synchronize" in note
    assert main(["--root", str(demo_repo), "guard", "--base", "main"]) == 1


def test_other_label_event_does_not_approve(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _event(tmp_path, monkeypatch, **_labeled(_head(demo_repo), applied="documentation"))
    approval, note = label_approval("pawl-approved", demo_repo)
    assert approval is None and note is not None


def test_no_label_no_note(demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _event(tmp_path, monkeypatch, action="opened", pull_request={"labels": []})
    assert label_approval("pawl-approved", demo_repo) == (None, None)
    monkeypatch.delenv("GITHUB_EVENT_PATH")
    assert label_approval("pawl-approved", demo_repo) == (None, None)


def test_pull_request_merge_commit_checkout(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In CI the checkout is the PR merge commit; its second parent is the PR head."""
    _tamper(demo_repo)
    pr_head = _head(demo_repo)
    git(demo_repo, "checkout", "-q", "main")
    git(demo_repo, "checkout", "-qb", "merge")
    git(demo_repo, "-c", "user.email=t@e", "-c", "user.name=t", "merge", "-q", "--no-ff", "agent")
    _event(tmp_path, monkeypatch, **_labeled(pr_head))
    approval, _ = label_approval("pawl-approved", demo_repo)
    assert approval is not None and approval.sha == pr_head


def test_flag_approval_records_head(demo_repo: Path) -> None:
    gate = resolve(demo_repo, "main", approved=True)
    assert gate.approval is not None
    assert gate.approval.source == "flag" and gate.approval.sha == _head(demo_repo)
    assert main(["--root", str(demo_repo), "check", "--trusted-ref", "main", "--approved"]) == 0
    report = json.loads((demo_repo / ".pawl" / "last-report.json").read_text())
    assert report["approval"]["sha"] == _head(demo_repo)
