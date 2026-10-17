import json

from pawl.trend import append, read


def test_append_is_additive(tmp_path):
    append(tmp_path, {"kind": "check", "n": 1})
    append(tmp_path, {"kind": "check", "n": 2})
    assert [row["n"] for row in read(tmp_path)] == [1, 2]
    assert (tmp_path / ".pawl" / "trend.jsonl").read_text().count("\n") == 2


def test_read_missing_is_empty(tmp_path):
    assert read(tmp_path) == []
    assert json.dumps({"a": 1})
