from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, edit, git

from pawl.cli import main
from pawl.config import load_config
from pawl.errors import PawlError
from pawl.gitutil import changed_files, diff_text
from pawl.guard import replay_base_tests, run_guard
from pawl.test_changes import classify
from pawl.trust import label_approval

ORIGINAL = "import math\n\ndef test_a():\n    assert 2 + 2 == 4\n"


@pytest.mark.parametrize(
    "candidate",
    [
        ORIGINAL.replace("    assert", "    return\n    assert"),
        ORIGINAL.replace("def test_a", "@wrapper\ndef test_a"),
        ORIGINAL + "\ntest_a = lambda: None\n",
        ORIGINAL.replace("import math", "import math\nmath.sqrt = lambda x: 0"),
        ORIGINAL + "\ndef replacement():\n    pass\n",
        ORIGINAL.replace("    assert", "    global state\n    assert"),
        ORIGINAL + "    assert callback()\n",
    ],
    ids=["return", "decorator", "rebind", "module-mutation", "helper", "global", "assert-call"],
)
def test_execution_additions_need_review(candidate: str) -> None:
    assert classify(ORIGINAL, candidate, "tests/test_a.py").review_required


@pytest.mark.parametrize(
    "candidate",
    [
        ORIGINAL + "    assert 1 < 2\n",
        ORIGINAL + "\ndef test_b():\n    assert math.sqrt(4) == 2\n",
        ORIGINAL.replace("    assert", "    # explanation\n    assert"),
    ],
    ids=["terminal-assert", "independent-test", "comment"],
)
def test_bounded_additions_stay_clean(candidate: str) -> None:
    assert not classify(ORIGINAL, candidate, "tests/test_a.py").review_required


def test_malformed_python_is_unmeasurable() -> None:
    with pytest.raises(PawlError, match="cannot classify"):
        classify(ORIGINAL, "def broken(:", "tests/test_a.py")


def test_non_python_edits_are_conservative() -> None:
    result = classify("test('a', fn)", "test('a', fn)\nsetup()", "test/a.test.js")
    assert result.review_required and result.full_replay


def test_additive_early_return_fails_real_ci_replay(demo_repo: Path) -> None:
    edit(demo_repo / "calc/__init__.py", "return a - b", "return a + b")
    for path, name in (
        ("tests/test_calc.py", "test_subtract"),
        ("holdout/test_holdout.py", "test_subtract_other_inputs"),
    ):
        edit(demo_repo / path, f"def {name}():\n", f"def {name}():\n    return\n")
    commit(demo_repo, "synthetic additive test weakening")
    root = ["--root", str(demo_repo)]
    # Test IDs still pass: the guard must independently protect execution.
    assert main([*root, "check", "--ci", "--trusted-ref", "main"]) == 0
    assert main([*root, "guard", "--ci", "--replay", "--base", "main"]) == 1
    result = json.loads((demo_repo / ".pawl/last-guard.json").read_text())
    codes = {f["rule"] for f in result["findings"]}
    assert {"TEST_EXECUTION_CHANGED", "TESTS_WEAKENED_REPLAY"} <= codes
    approved = run_guard(load_config(demo_repo), "main", approved=True, replay=True, ci=True)
    assert approved.status == "fail"
    assert any(
        f.rule == "TESTS_WEAKENED_REPLAY" and f.severity == "block" for f in approved.findings
    )


def test_terminal_assert_addition_replays_cleanly(demo_repo: Path) -> None:
    edit(
        demo_repo / "tests/test_calc.py",
        "assert subtract(5, 3) == 2",
        "assert subtract(5, 3) == 2\n    assert 2 < 3",
    )
    report = run_guard(load_config(demo_repo), "main", replay=True)
    assert report.status == "pass", report.to_json()
    assert any(f.rule == "REPLAY_PASSED" for f in report.findings)


def test_shared_fixture_is_removed_for_original_replay(demo_repo: Path) -> None:
    (demo_repo / "conftest.py").write_text("raise RuntimeError('candidate fixture')\n")
    report = run_guard(load_config(demo_repo), "main", replay=True)
    assert any(f.rule == "PROTECTED_CHANGED" for f in report.findings)
    assert any(f.rule == "REPLAY_PASSED" and "full suite" in f.message for f in report.findings)


def test_missing_replay_baseline_is_error(demo_repo: Path) -> None:
    config = load_config(demo_repo)
    (demo_repo / config.baseline).unlink()
    commit(demo_repo, "synthetic baseline absent")
    with pytest.raises(PawlError, match="REPLAY_UNAVAILABLE"):
        replay_base_tests(config, "HEAD", ["tests/test_calc.py"], ci=True)


@pytest.mark.parametrize(
    "name",
    ["snow-☃.txt", "has space.txt", "tab\tname.txt", "line\nname.txt", ":(glob)*.txt"],
    ids=["unicode", "space", "tab", "newline", "pathspec"],
)
def test_git_inventory_and_diff_keep_literal_paths(demo_repo: Path, name: str) -> None:
    path = demo_repo / name
    path.write_text("old\n")
    commit(demo_repo, "synthetic path")
    path.write_text("new\n")
    assert ("M", name) in changed_files(demo_repo, "HEAD")
    assert "+new" in diff_text(demo_repo, "HEAD", name)


def test_candidate_symlink_is_not_followed(demo_repo: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("secret_synthetic_marker\n")
    (demo_repo / "tests/test_escape.py").symlink_to(outside)
    with pytest.raises(PawlError, match="linked candidate path"):
        changed_files(demo_repo, "main")


@pytest.mark.parametrize("command", ["check", "guard"])
def test_ci_manual_approval_is_rejected(demo_repo: Path, command: str) -> None:
    args = ["--root", str(demo_repo), command, "--ci", "--approved"]
    if command == "guard":
        args += ["--base", "main"]
    assert main(args) == 2


def test_malformed_actor_never_approves(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"action": "labeled", "sender": "not-an-actor", "label": {}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert label_approval("pawl-approved", demo_repo)[0] is None
    event.write_text(
        json.dumps(
            {
                "action": "labeled",
                "sender": {"login": "unknown"},
                "label": {"name": "pawl-approved"},
                "pull_request": {
                    "labels": [{"name": "pawl-approved"}],
                    "head": {"sha": git(demo_repo, "rev-parse", "HEAD").strip()},
                },
            }
        )
    )
    assert label_approval("pawl-approved", demo_repo)[0] is None
