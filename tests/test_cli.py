from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import commit, edit

from pawl.cli import main


def run(repo: Path, *args: str) -> int:
    return main(["--root", str(repo), *args])


def test_check_passes_on_clean_tree(demo_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(demo_repo, "check", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "pass"
    assert (demo_repo / ".pawl" / "last-report.json").is_file()


def test_check_catches_regression_with_isolation(
    demo_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    assert run(demo_repo, "check", "--json") == 1
    data = json.loads(capsys.readouterr().out)
    assert [p["code"] for p in data["problems"]] == ["NEW_FAILURE"]
    assert data["isolation"]["tests"]["tests/test_calc.py::test_subtract"] == "reproduces"


def test_check_catches_collection_error(
    demo_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(demo_repo / "tests" / "test_more.py", "from calc import", "from calc import missing_name,")
    assert run(demo_repo, "check", "--json") == 1
    codes = {p["code"] for p in json.loads(capsys.readouterr().out)["problems"]}
    assert {"NEW_FAILURE", "MISSING_TESTS", "COLLECTION_DROP"} <= codes


def test_wrong_interpreter_fails_preflight(
    demo_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = tmp_path / "stale" / "calc"
    stale.mkdir(parents=True)
    (stale / "__init__.py").write_text("")
    monkeypatch.setenv("PYTHONSAFEPATH", "1")
    monkeypatch.setenv("PYTHONPATH", str(stale.parent))
    assert run(demo_repo, "check") == 3


def test_update_refuses_loosening_then_logs_it(demo_repo: Path) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    assert run(demo_repo, "update") == 1
    assert run(demo_repo, "update", "--loosen") == 1
    assert run(demo_repo, "update", "--loosen", "--reason", "upstream change") == 0
    assert "Reason: upstream change" in (demo_repo / "PAWL_DEBT.md").read_text()
    assert run(demo_repo, "check") == 0


def test_update_tightens_freely(demo_repo: Path) -> None:
    edit(
        demo_repo / "calc" / "__init__.py",
        "    return sum(values) / len(values)",
        "    return sum(values) / len(values) if values else 0.0",
    )
    assert run(demo_repo, "check", "--lock") == 1  # stale: the debt is fixed
    assert run(demo_repo, "update") == 0
    data = json.loads((demo_repo / "pawl.baseline.json").read_text())
    assert data["suites"]["tests"]["failing_ids"] == []
    assert run(demo_repo, "check", "--lock") == 0


def test_trusted_ref_ignores_head_baseline_edit(demo_repo: Path) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    assert run(demo_repo, "update", "--loosen", "--reason", "agent cheat") == 0
    commit(demo_repo, "agent loosens baseline")
    assert run(demo_repo, "check") == 0  # head baseline alone is fooled
    assert run(demo_repo, "check", "--trusted-ref", "main") == 1
    assert run(demo_repo, "check", "--trusted-ref", "main", "--approved") == 0


def test_guard_cli_and_report(demo_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (demo_repo / "tests" / "test_more.py").unlink()
    assert run(demo_repo, "guard", "--base", "main") == 1
    assert run(demo_repo, "guard", "--base", "main", "--approved") == 0
    capsys.readouterr()
    assert run(demo_repo, "report", "--format", "json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["reports"][-1]["kind"] == "guard"


def test_guard_bad_ref_fails_closed(demo_repo: Path) -> None:
    assert run(demo_repo, "guard", "--base", "no-such-ref") == 2


def test_init_detects_pytest(demo_repo: Path) -> None:
    (demo_repo / "pawl.toml").unlink()
    (demo_repo / "pawl.baseline.json").unlink()
    assert run(demo_repo, "init", "--github") == 0
    assert 'adapter = "pytest"' in (demo_repo / "pawl.toml").read_text()
    assert (demo_repo / ".github" / "workflows" / "pawl.yml").is_file()
    assert run(demo_repo, "check") == 0
    assert run(demo_repo, "init") == 2  # refuses to overwrite


def test_quarantine_and_escalate(demo_repo: Path) -> None:
    assert (
        run(
            demo_repo,
            "quarantine",
            "tests/test_calc.py::test_add",
            "--suite",
            "tests",
            "--reason",
            "flaky",
            "--days",
            "90",
        )
        == 0
    )
    q = json.loads((demo_repo / "pawl.baseline.json").read_text())["quarantine"]
    assert len(q) == 1
    assert run(demo_repo, "escalate", "conflict", "--test", "x") == 0
    assert "open" in (demo_repo / ".pawl" / "ESCALATIONS.md").read_text()


def test_mutate_reports_survivors(demo_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    edit(demo_repo / "calc" / "__init__.py", "return a + b", "return a + b + 0")
    assert run(demo_repo, "mutate", "--base", "main", "--json", "--max", "3") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mutants"] >= 1


def test_stop_hook_blocks_until_green(
    demo_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert run(demo_repo, "hook", "stop", "--format", "codex") == 0
    assert json.loads(capsys.readouterr().out) == {}
    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert run(demo_repo, "hook", "stop", "--format", "codex", "--base", "main") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "block" and "NEW_FAILURE" in out["reason"]


def test_protect_hook(
    demo_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(demo_repo / "pawl.baseline.json")},
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    assert run(demo_repo, "hook", "protect") == 2
    assert "protected" in capsys.readouterr().err


def test_stop_hook_gives_up_after_max_blocks(
    demo_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    payload = json.dumps({"session_id": "s1", "cwd": str(demo_repo)})
    outs = []
    for _ in range(3):
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert main(["hook", "stop", "--format", "codex", "--max-blocks", "2"]) == 0
        outs.append(json.loads(capsys.readouterr().out))
    assert [o.get("decision") for o in outs] == ["block", "block", None]


def test_stop_hook_uses_trusted_base(
    demo_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    edit(demo_repo / "calc" / "__init__.py", "return a - b", "return a + b")
    assert run(demo_repo, "update", "--loosen", "--reason", "agent cheat") == 0
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    assert run(demo_repo, "hook", "stop", "--format", "codex", "--base", "main") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "block"
    assert "NEW_FAILURE" in out["reason"] and "BASELINE_LOOSENED" in out["reason"]
