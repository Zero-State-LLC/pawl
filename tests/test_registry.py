from pawl.registry import append_negative, read_rows


def test_comma_in_message_round_trips(tmp_path):
    append_negative(tmp_path, "2026-10-17T00:00:00Z", "tests/t.py::test_a", "a, b")
    append_negative(tmp_path, "2026-10-17T00:01:00Z", "", "second")
    rows = read_rows(tmp_path)
    assert len(rows) == 2
    assert rows[0]["message"] == "a, b"
    assert rows[0]["status"] == "open"
    assert (
        (tmp_path / ".pawl" / "registry.csv").read_text().splitlines()[0].startswith("recorded_at")
    )
