# New feature: seconds support. These fail until it is implemented.
from durations import parse_duration


def test_seconds_only():
    assert parse_duration("45s") == 45


def test_minutes_and_seconds():
    assert parse_duration("1m5s") == 65


def test_all_units():
    assert parse_duration("2h0m1s") == 7201


def test_hours_and_seconds():
    assert parse_duration("1h1s") == 3660
