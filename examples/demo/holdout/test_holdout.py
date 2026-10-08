"""Held-out checks. In real use this suite lives outside the agent's workspace."""

from calc import add, clamp, subtract


def test_add_other_inputs():
    assert add(10, 32) == 42
    assert add(0, 0) == 0


def test_subtract_other_inputs():
    assert subtract(10, 4) == 6


def test_clamp_bounds():
    assert clamp(0, 0, 10) == 0
    assert clamp(10, 0, 10) == 10
