from __future__ import annotations

import json
from pathlib import Path

from pawl.config import parse_config
from pawl.hooks import protect_decision, protect_output, stop_output

CFG = parse_config('[[suite]]\nname="t"\nadapter="pytest"\ncommand="x"', Path("/repo"))


def test_protect_blocks_baseline_and_conftest_edits() -> None:
    for payload in (
        {"tool_name": "Edit", "tool_input": {"file_path": "/repo/pawl.baseline.json"}},
        {"tool_name": "write_file", "tool_input": {"path": "tests/conftest.py"}},
        {
            "tool_name": "apply_patch",
            "tool_input": {"command": ["apply_patch", "*** Update File: pawl.toml\n"]},
        },
        {"tool_name": "Bash", "tool_input": {"command": "sed -i s/1/9/ pawl.baseline.json"}},
        {"tool_name": "Bash", "tool_input": {"command": "pawl update --loosen --reason x"}},
        {"file_path": "/repo/.github/workflows/ci.yml"},
        {"tool_name": "Write", "tool_input": {"file_path": "./.github/workflows/x.yml"}},
    ):
        assert protect_decision(CFG, payload), payload


def test_protect_allows_normal_work() -> None:
    for payload in (
        {"tool_name": "Edit", "tool_input": {"file_path": "/repo/src/app.py"}},
        {"tool_name": "Bash", "tool_input": {"command": "cat pawl.baseline.json"}},
        {"tool_name": "Bash", "tool_input": {"command": "pawl check"}},
        {},
    ):
        assert protect_decision(CFG, payload) is None, payload


def test_output_shapes() -> None:
    assert stop_output("claude", None) == "{}"
    assert json.loads(stop_output("codex", "red"))["decision"] == "block"
    assert json.loads(stop_output("cursor", "red"))["followup_message"] == "red"
    assert protect_output("claude", "no")[2] == 2
    out, _, code = protect_output("codex", "no")
    assert code == 0 and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert json.loads(protect_output("cursor", "no")[0])["permission"] == "deny"
