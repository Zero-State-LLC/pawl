"""A tiny library used to demonstrate Pawl."""

from __future__ import annotations


def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return a - b."""
    return a - b


def mean(values: list[float]) -> float:
    """Return the arithmetic mean. An empty list has mean 0.0."""
    return sum(values) / len(values)


def clamp(value: int, low: int, high: int) -> int:
    """Clamp value into [low, high]."""
    return max(low, min(value, high))


def is_prime(n: int) -> bool:
    """Return True if n is prime."""
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True
