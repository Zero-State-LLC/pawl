import json

HOOK_KEYS = (
    "v",
    "ts",
    "pawl",
    "harness",
    "hook",
    "event",
    "session",
    "turn",
    "agent",
    "tool",
    "tool_use_id",
    "model",
    "paths",
    "decision",
    "reason",
)
HOOK_DECISIONS = ("allow", "block", "error", "budget")
REPORT_KEYS = (
    "schema_version",
    "tool",
    "version",
    "kind",
    "status",
    "exit_code",
    "generated_at",
    "config_source",
    "notes",
    "approval",
)
REPORT_KINDS = ("check", "guard", "update", "report", "mutate")
REPORT_EXIT_CODES = (0, 1, 2, 3)


def parse_hook_log_line(line: str) -> dict:
    obj = json.loads(line)
    missing = [k for k in HOOK_KEYS if k not in obj]
    if missing:
        raise ValueError(f"missing hook keys: {missing}")
    if obj["decision"] not in HOOK_DECISIONS:
        raise ValueError(f"bad decision: {obj['decision']}")
    return obj


def parse_hook_log_lines(lines: list) -> list:
    return [parse_hook_log_line(line) for line in lines if line.strip()]


def parse_json_report(obj: dict) -> dict:
    missing = [k for k in REPORT_KEYS if k not in obj]
    if missing:
        raise ValueError(f"missing report keys: {missing}")
    if obj["kind"] not in REPORT_KINDS:
        raise ValueError(f"bad kind: {obj['kind']}")
    if obj["exit_code"] not in REPORT_EXIT_CODES:
        raise ValueError(f"bad exit_code: {obj['exit_code']}")
    return obj
