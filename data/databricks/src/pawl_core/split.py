import hashlib

SPLIT_METHOD = "sha256_group_mod_100"
SPLIT_METHOD_VERSION = "pawl.v1"


def group_key(record: dict) -> str:
    task = record.get("task", {})
    return f"{task.get('task_id')}|{task.get('repo_rev')}|{record.get('exploit_family')}"


def split_value(group_key_str: str) -> int:
    raw = f"{SPLIT_METHOD_VERSION}:{group_key_str}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest(), 16) % 100


def assign_split(value: int) -> str:
    if value < 80:
        return "train"
    if value < 90:
        return "val"
    return "test"


def split_for_record(record: dict) -> str:
    return assign_split(split_value(group_key(record)))


def assert_no_group_crosses(records: list) -> None:
    seen = {}
    for rec in records:
        key = group_key(rec)
        split = rec.get("split") or split_for_record(rec)
        if key in seen and seen[key] != split:
            raise ValueError(f"group crosses splits: {key} -> {seen[key]} and {split}")
        seen[key] = split
