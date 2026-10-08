"""Harness hooks: a stop/done check and a protected-path write blocker.

The harness hook is a fast early check. It is not the authority: an agent with
a shell can disable local hooks. CI with a required check is the authority.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

from pawl.config import Config
from pawl.guard import matches_any

STOP_FORMATS = ("claude", "codex", "hermes", "cursor")
WRITE_TOKENS = re.compile(
    r"((?<![\d&])>(?!&)|\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btruncate\b|\bgit\s+(checkout|restore|rm)\b|"
    r"\bperl\s+-p?i|open\([^)]*['\"][wa]|write_text|\bchmod\b|\bln\b)"
)
HUMAN_ONLY = re.compile(r"\bpawl\s+(update\s+.*--loosen|quarantine|init\s+.*--force)")


def read_stdin_json() -> dict[str, Any]:
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def stop_output(fmt: str, reason: str | None) -> str:
    """JSON a harness expects from a stop hook. ``None`` means allow the stop."""
    if reason is None:
        return "{}"
    if fmt == "cursor":
        return json.dumps({"followup_message": reason})
    return json.dumps({"decision": "block", "reason": reason})


def _paths_from_payload(payload: dict[str, Any]) -> tuple[list[str], str]:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    paths: list[str] = []
    command = ""
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path", "target_file", "filePath"):
            value = tool_input.get(key)
            if isinstance(value, str):
                paths.append(value)
        for edit in tool_input.get("edits", []) or []:
            if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
                paths.append(edit["file_path"])
        cmd = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("input") or ""
        command = "\n".join(map(str, cmd)) if isinstance(cmd, list) else str(cmd)
    if isinstance(payload.get("file_path"), str):
        paths.append(payload["file_path"])
    if isinstance(payload.get("command"), str):
        command = command or payload["command"]
    for m in re.finditer(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", command, flags=re.MULTILINE):
        paths.append(m.group(1).strip())
    return paths, command


def protect_decision(config: Config, payload: dict[str, Any]) -> str | None:
    """Return a block reason if the tool call would write a protected path."""
    paths, command = _paths_from_payload(payload)
    root = str(config.root.resolve())
    for p in paths:
        rel = p[len(root) + 1 :] if p.startswith(root + "/") else p.removeprefix("./")
        if matches_any(rel, config.guard.protected) or rel in (config.baseline,):
            return (
                f"Pawl: {rel} is a protected gate file. Agents may not edit the baseline, "
                "the gate config, or conftest files. Fix the code instead, or run "
                "'pawl escalate \"<why>\"' and stop."
            )
    if command:
        if HUMAN_ONLY.search(command):
            return "Pawl: loosening the baseline or quarantining tests is for humans only."
        protected_literals = [config.baseline, "pawl.toml", "conftest.py", ".github/workflows"]
        if any(lit in command for lit in protected_literals) and WRITE_TOKENS.search(command):
            return "Pawl: this command appears to modify a protected gate file. Blocked."
    return None


def protect_output(fmt: str, reason: str) -> tuple[str, str, int]:
    """Return (stdout, stderr, exit code) to block a tool call in each harness."""
    if fmt == "codex":
        body = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
        return json.dumps(body), "", 0
    if fmt == "cursor":
        return (
            json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason}),
            "",
            0,
        )
    return "", reason, 2  # Claude Code and Hermes: exit 2 blocks, stderr is the reason
