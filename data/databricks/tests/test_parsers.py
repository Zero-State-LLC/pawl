import json

import pytest

from pawl_core.parsers import parse_hook_log_line, parse_json_report

def synthetic_hook_line():
    return json.dumps({
        "v": 1,
        "ts": "2025-01-01T00:00:00Z",
        "pawl": "0.0.0",
        "harness": "synthetic_harness",
        "hook": "stop",
        "event": "synthetic_event",
        "session": "s1",
        "turn": 1,
        "agent": "a1",
        "tool": "bash",
        "tool_use_id": "t1",
        "model": "synthetic_model",
        "paths": ["a.py"],
        "decision": "allow",
        "reason": "synthetic",
    })

def synthetic_report():
    return {
        "schema_version": "pawl.report.v1",
        "tool": "pawl",
        "version": "0.0.0",
        "kind": "check",
        "status": "synthetic",
        "exit_code": 0,
        "generated_at": "2025-01-01T00:00:00Z",
        "config_source": "synthetic",
        "notes": "synthetic",
        "approval": None,
    }

def test_parse_hook_log_line():
    obj = parse_hook_log_line(synthetic_hook_line())
    assert obj["decision"] == "allow"

def test_parse_hook_log_rejects_bad_decision():
    line = json.loads(synthetic_hook_line())
    line["decision"] = "maybe"
    with pytest.raises(ValueError):
        parse_hook_log_line(json.dumps(line))

def test_parse_json_report():
    obj = parse_json_report(synthetic_report())
    assert obj["exit_code"] == 0

def test_parse_json_report_rejects_bad_exit_code():
    obj = synthetic_report()
    obj["exit_code"] = 99
    with pytest.raises(ValueError):
        parse_json_report(obj)
