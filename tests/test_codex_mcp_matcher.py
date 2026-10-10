"""Tests that the Codex PreToolUse matcher covers MCP tools and the hook denies them."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from pawl.cli import main

HOOKS_JSON = Path(__file__).resolve().parents[1] / "integrations" / "codex" / "hooks.json"


def _protect_matcher() -> str:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    for group in data["hooks"]["PreToolUse"]:
        if any("hook protect" in h["command"] for h in group["hooks"]):
            return str(group["matcher"])
    raise AssertionError("no PreToolUse group running 'hook protect'")


def test_matcher_covers_mcp_and_shell() -> None:
    matcher = _protect_matcher()
    for name in ("mcp__filesystem__write_file", "mcp__fs__edit_file", "apply_patch", "Bash"):
        assert re.search(matcher, name), name


def _payload(cwd: Path, tool_input: dict[str, object]) -> str:
    return json.dumps(
        {
            "cwd": str(cwd),
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__filesystem__write_file",
            "tool_input": tool_input,
        }
    )


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payload: str,
) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    return main(["hook", "protect", "--format", "codex"])


def test_mcp_write_to_protected_path_is_denied(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run(monkeypatch, capsys, _payload(demo_repo, {"path": "pawl.toml", "content": "x"}))
    out = capsys.readouterr().out
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"


def test_mcp_write_to_new_path_is_allowed(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _run(monkeypatch, capsys, _payload(demo_repo, {"path": "calc/new.py"}))
    out = capsys.readouterr().out
    assert code == 0
    assert out.strip() == ""


def test_mcp_write_to_absolute_protected_path_is_denied(
    demo_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _payload(demo_repo, {"path": str(demo_repo / "pawl.baseline.json")})
    code = _run(monkeypatch, capsys, payload)
    out = capsys.readouterr().out
    assert code == 0
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    assert decision == "deny"
