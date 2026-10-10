from __future__ import annotations

import json
from pathlib import Path

from pawl.config import parse_config
from pawl.hooks import protect_decision, provenance, record

CFG = parse_config('[[suite]]\nname="t"\nadapter="pytest"\ncommand="x"', Path("/repo"))


def test_claude_provenance_omits_payload_content() -> None:
    d = provenance(
        "claude",
        "PreToolUse",
        {
            "session_id": "s1",
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_use_id": "tu1",
            "tool_input": {"file_path": "src/x.py", "content": "SECRET"},
        },
        None,
        None,
    )
    assert d["harness"] == "claude"
    assert d["event"] == "PreToolUse"
    assert d["session"] == "s1"
    assert d["tool"] == "Write"
    assert d["tool_use_id"] == "tu1"
    assert d["paths"] == ["src/x.py"]
    assert "SECRET" not in json.dumps(d)


def test_codex_provenance_omits_payload_content() -> None:
    d = provenance(
        "codex",
        "PreToolUse",
        {"turn_id": "t1", "tool_input": {"command": "echo hi > pawl.toml"}},
        None,
        None,
    )
    assert d["turn"] == "t1"
    assert "echo hi" not in json.dumps(d)


def test_cursor_provenance_session_and_turn() -> None:
    d = provenance(
        "cursor",
        "PreToolUse",
        {"conversation_id": "c1", "generation_id": "g1"},
        None,
        None,
    )
    assert d["session"] == "c1"
    assert d["turn"] == "g1"


def test_provenance_invalid_session_is_none() -> None:
    d = provenance(
        "claude",
        "PreToolUse",
        {"session_id": 5, "hook_event_name": "PreToolUse", "tool_name": "Write"},
        None,
        None,
    )
    assert d["session"] is None


def test_provenance_reason_truncated() -> None:
    d = provenance("claude", "PreToolUse", {}, None, "x" * 900)
    assert len(d["reason"]) == 500


def test_record_appends_json_lines_and_never_raises(tmp_path: Path) -> None:
    entry = provenance("claude", "PreToolUse", {"session_id": "s1"}, None, None)
    record(tmp_path, entry)
    record(tmp_path, entry)
    lines = (tmp_path / ".pawl" / "hook-log.jsonl").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)
    bad = tmp_path / "file"
    bad.write_text("x")
    record(bad / "sub", entry)


def test_protect_blocks_spec_contracts_and_adr_writes() -> None:
    for path in ("specs/001/spec.md", "pawl.contracts.json", "docs/adr/0002.md"):
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}}
        assert protect_decision(CFG, payload), payload
    allowed = {"tool_name": "Write", "tool_input": {"file_path": "src/app.py"}}
    assert protect_decision(CFG, allowed) is None
