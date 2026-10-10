"""Harness hooks: a stop/done check and a protected-path write blocker.

The harness hook is a fast early check. It is not the authority: an agent with
a shell can disable local hooks. CI with a required check is the authority.

The hook log written here (``.pawl/hook-log.jsonl``) is local evidence, not
authority: it is best-effort, agent-writable, and may be missing or tampered
with. It records provenance only, never tool input, commands or transcripts.
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pawl
from pawl import contracts
from pawl.config import Config
from pawl.guard import matches_any

STOP_FORMATS = ("claude", "codex", "hermes", "cursor")
HOOK_LOG = ".pawl/hook-log.jsonl"
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


def _candidates(root: Path, path: str, cwd: object) -> list[str]:
    """Root-relative spellings of a written path, as typed and as resolved.

    Resolving collapses '..' and follows symlinks, so 'tests/../pawl.toml' or a
    symlink that points at the baseline is checked as the file it really writes.
    """
    real_root = root.resolve()
    raw = path.removeprefix("./")
    out = [raw[len(str(real_root)) + 1 :] if raw.startswith(f"{real_root}/") else raw]
    base = Path(cwd) if isinstance(cwd, str) and cwd else root
    target = Path(path) if Path(path).is_absolute() else base / path
    try:
        resolved = target.resolve()
    except (OSError, RuntimeError):  # a symlink loop: check what we have
        return out
    with contextlib.suppress(ValueError):
        out.append(resolved.relative_to(real_root).as_posix())
    return out


def protect_decision(config: Config, payload: dict[str, Any]) -> str | None:
    """Return a block reason if the tool call would write a protected path."""
    paths, command = _paths_from_payload(payload)
    for rel in (r for p in paths for r in _candidates(config.root, p, payload.get("cwd"))):
        if matches_any(rel, config.guard.protected) or rel in (config.baseline,):
            return (
                f"Pawl: {rel} is a protected gate file. Agents may not edit the baseline, "
                "the gate config, or conftest files. Fix the code instead, or run "
                "'pawl escalate \"<why>\"' and stop."
            )
        if matches_any(rel, config.guard.contracts) or rel == contracts.REGISTRY:
            return (
                f"Pawl: {rel} is a protected contract (spec, ADR or contract fixture). "
                "Changing it needs a human approval bound to the commit. Stop and run "
                "'pawl escalate \"<why>\"'."
            )
    if command:
        if HUMAN_ONLY.search(command):
            return "Pawl: loosening the baseline or quarantining tests is for humans only."
        protected_literals = [
            config.baseline,
            "pawl.toml",
            "conftest.py",
            ".github/workflows",
            contracts.REGISTRY,
        ]
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


def _str_field(payload: dict[str, Any], *keys: str) -> str | None:
    """First string value among ``keys``; anything non-string becomes None."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def provenance(
    fmt: str,
    hook: str,
    payload: dict[str, Any],
    decision: str,
    reason: str | None,
) -> dict[str, Any]:
    """A harness-neutral provenance record for one hook decision.

    Only scalar fields are copied from the payload. Tool input, commands and
    transcript paths are deliberately excluded: they may hold secrets.
    """
    paths = sorted({p for p in _paths_from_payload(payload)[0] if p})
    return {
        "v": 1,
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pawl": pawl.__version__,
        "harness": fmt,
        "hook": hook,
        "event": _str_field(payload, "hook_event_name", "hookEventName"),
        "session": _str_field(payload, "session_id", "conversation_id"),
        "turn": _str_field(payload, "turn_id", "generation_id", "prompt_id"),
        "agent": _str_field(payload, "agent_id", "agent_type"),
        "tool": _str_field(payload, "tool_name", "toolName"),
        "tool_use_id": _str_field(payload, "tool_use_id"),
        "model": _str_field(payload, "model"),
        "paths": paths,
        "decision": decision,
        "reason": reason[:500] if reason else None,
    }


def record(root: Path, entry: dict[str, Any]) -> None:
    """Append one JSON line to the local hook log. Best effort, never raises."""
    target = root / HOOK_LOG
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        return
