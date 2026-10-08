from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, git

from pawl.errors import ConfigError
from pawl.trust import resolve


def _label_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"labels": [{"name": label}]}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))


def test_no_ref_trusts_the_working_tree(demo_repo: Path) -> None:
    gate = resolve(demo_repo, None)
    assert gate.config.source == "pawl.toml" and gate.baseline is not None
    assert gate.notes == [] and gate.approval is None


def test_ref_uses_base_config_and_stricter_baseline(demo_repo: Path) -> None:
    gate = resolve(demo_repo, "main")
    assert gate.config.source == "main:pawl.toml"
    assert gate.notes == ["gate definition from main; stricter of base and head baselines"]


def test_flag_approval_uses_head(demo_repo: Path) -> None:
    gate = resolve(demo_repo, "main", approved=True)
    assert gate.config.source == "pawl.toml"
    assert gate.approval is not None and gate.approval.source == "flag"


def test_label_approval_check_uses_head_guard_keeps_base_rules(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _label_event(tmp_path, monkeypatch, "pawl-approved")
    check_gate = resolve(demo_repo, "main")
    assert check_gate.config.source == "pawl.toml"
    assert check_gate.approval is not None and check_gate.approval.label == "pawl-approved"
    guard_gate = resolve(demo_repo, "main", need_baseline=False)
    assert guard_gate.config.source == "main:pawl.toml"
    assert guard_gate.approval is not None


def test_label_name_comes_from_the_base(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (demo_repo / "pawl.toml").write_text(
        (demo_repo / "pawl.toml").read_text() + '\n[guard]\napproval_label = "lgtm"\n'
    )
    commit(demo_repo, "rename the label on the branch")
    _label_event(tmp_path, monkeypatch, "lgtm")
    assert resolve(demo_repo, "main").approval is None


def test_missing_base_baseline_is_an_error(demo_repo: Path) -> None:
    saved = (demo_repo / "pawl.baseline.json").read_text()
    git(demo_repo, "checkout", "-q", "main")
    git(demo_repo, "rm", "-q", "pawl.baseline.json")
    commit(demo_repo, "drop baseline on main")
    git(demo_repo, "checkout", "-q", "agent")
    git(demo_repo, "rebase", "-q", "main")
    (demo_repo / "pawl.baseline.json").write_text(saved)
    with pytest.raises(ConfigError, match=r"but no pawl\.baseline\.json"):
        resolve(demo_repo, "main")


def test_bootstrap_is_explicit(demo_repo: Path) -> None:
    git(demo_repo, "checkout", "-q", "--orphan", "empty")
    git(demo_repo, "rm", "-rq", "--cached", ".")
    (demo_repo / "seed.txt").write_text("x\n")
    git(demo_repo, "add", "seed.txt")
    git(demo_repo, "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "empty base")
    git(demo_repo, "branch", "-f", "nopawl")
    with pytest.raises(ConfigError, match=r"no pawl\.toml"):
        resolve(demo_repo, "nopawl")
    gate = resolve(demo_repo, "nopawl", bootstrap=True)
    assert gate.notes[0].startswith("bootstrap:")


def test_bootstrap_label_name_is_not_taken_from_the_head(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no base config the head config is untrusted, including its label name."""
    empty_tree = git(demo_repo, "hash-object", "-t", "tree", "/dev/null").strip()
    root_commit = git(
        demo_repo, "-c", "user.email=t@e", "-c", "user.name=t", "commit-tree", empty_tree, "-m", "x"
    ).strip()
    git(demo_repo, "branch", "-f", "nopawl", root_commit)
    (demo_repo / "pawl.toml").write_text(
        (demo_repo / "pawl.toml").read_text() + '\n[guard]\napproval_label = "documentation"\n'
    )
    commit(demo_repo, "pick a label the agent can apply")
    _label_event(tmp_path, monkeypatch, "documentation")
    with pytest.raises(ConfigError, match=r"no pawl\.toml"):
        resolve(demo_repo, "nopawl")
    _label_event(tmp_path, monkeypatch, "pawl-approved")
    assert resolve(demo_repo, "nopawl").approval is not None
