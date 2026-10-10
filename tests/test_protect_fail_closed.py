import io
import json
from pathlib import Path
from typing import cast

import pytest

from pawl.cli import main

BROKEN = "this is = not [ toml"


def _payload(cwd: Path, file_path: str) -> dict[str, object]:
    return {
        "cwd": str(cwd),
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
    }


def _run(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    fmt: str,
) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return main(["hook", "protect", "--format", fmt])


def _last_log(demo_repo: Path) -> dict[str, object]:
    log = demo_repo / ".pawl" / "hook-log.jsonl"
    lines = log.read_text().splitlines()
    return cast("dict[str, object]", json.loads(lines[-1]))


@pytest.fixture(autouse=True)
def _clear_ci_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("CI", "GITHUB_ACTIONS", "CLAUDECODE", "CODEX"):
        monkeypatch.delenv(name, raising=False)


def test_claude_fails_closed(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (demo_repo / "pawl.toml").write_text(BROKEN)
    code = _run(monkeypatch, _payload(demo_repo, "src/app.py"), "claude")
    captured = capsys.readouterr()
    assert code == 2
    assert "fail closed" in captured.err
    assert _last_log(demo_repo)["decision"] == "error"


def test_codex_fails_closed(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (demo_repo / "pawl.toml").write_text(BROKEN)
    code = _run(monkeypatch, _payload(demo_repo, "src/app.py"), "codex")
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_cursor_fails_closed(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (demo_repo / "pawl.toml").write_text(BROKEN)
    code = _run(monkeypatch, _payload(demo_repo, "src/app.py"), "cursor")
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data["permission"] == "deny"


def test_config_found_by_walking_up(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _payload(demo_repo / "calc", "calc/new.py")
    code = _run(monkeypatch, payload, "claude")
    assert code == 0
