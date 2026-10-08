import pytest
from durations import format_duration, parse_duration


def test_hours():
    assert parse_duration("1h") == 3600


def test_minutes():
    assert parse_duration("30m") == 1800


def test_hours_and_minutes():
    assert parse_duration("1h30m") == 5400


@pytest.mark.parametrize("bad", ["", "5x", "30m1h", "1h 30m"])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


def test_format_round_trip():
    assert format_duration(parse_duration("2h15m")) == "2h15m"
