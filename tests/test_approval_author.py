"""The pull request author may be refused as approver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.config import parse_config
from pawl.errors import ConfigError
from pawl.trust import label_approval


def _event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **payload: object) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def _labeled(
    sha: str,
    *,
    author: str,
    sender: dict | None = None,  # type: ignore[type-arg]
    number: int = 7,
    label: str = "pawl-approved",
) -> dict:  # type: ignore[type-arg]
    payload: dict = {  # type: ignore[type-arg]
        "action": "labeled",
        "label": {"name": label},
        "pull_request": {
            "number": number,
            "labels": [{"name": label}],
            "head": {"sha": sha},
            "user": {"login": author},
        },
    }
    if sender is not None:
        payload["sender"] = sender
    return payload


def _head(repo: Path) -> str:
    return git(repo, "rev-parse", "HEAD").strip()


def _tamper(repo: Path) -> None:
    (repo / "tests" / "test_more.py").unlink()
    commit(repo, "delete a test file")


def test_author_cannot_self_approve(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        **_labeled(sha, author="danny", sender={"login": "danny", "type": "User"}),
    )
    approval, note = label_approval("pawl-approved", demo_repo, refuse_pr_author=True)
    assert approval is None
    assert note is not None and "author" in note


def test_author_allowed_when_option_off(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        **_labeled(sha, author="danny", sender={"login": "danny", "type": "User"}),
    )
    approval, note = label_approval("pawl-approved", demo_repo, refuse_pr_author=False)
    assert approval is not None
    assert note is None


def test_other_human_can_approve(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tamper(demo_repo)
    sha = _head(demo_repo)
    _event(
        tmp_path,
        monkeypatch,
        **_labeled(sha, author="danny", sender={"login": "mallory", "type": "User"}),
    )
    approval, note = label_approval("pawl-approved", demo_repo, refuse_pr_author=True)
    assert approval is not None
    assert note is None


def test_config_rejects_non_bool_refuse_pr_author() -> None:
    with pytest.raises(ConfigError):
        parse_config('[guard]\nrefuse_pr_author = "yes"\n', Path("."))
