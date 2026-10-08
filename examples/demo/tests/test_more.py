import pytest
from calc import clamp, is_prime


@pytest.mark.parametrize(("value", "expected"), [(-5, 0), (5, 5), (50, 10)])
def test_clamp(value, expected):
    assert clamp(value, 0, 10) == expected


def test_is_prime_small():
    assert [n for n in range(10) if is_prime(n)] == [2, 3, 5, 7]


def test_is_prime_large():
    assert is_prime(7919)
    assert not is_prime(7917)
