"""Parse compact duration strings."""

from __future__ import annotations

import re

_PART = re.compile(r"(\d+)([hm])")


def parse_duration(text: str) -> int:
    """Return the number of seconds in a duration such as "1h30m" or "45s".

    Units are h (hours), m (minutes), and s (seconds). Units appear in that
    order and each at most once, so "1h1s" is 3601 seconds. Raise ValueError
    for an empty string, an unknown unit, or units out of order.
    """
    if not text:
        raise ValueError("empty duration")
    pos = 0
    total = 0
    order = "hm"
    last = -1
    for match in _PART.finditer(text):
        if match.start() != pos:
            raise ValueError(f"bad duration: {text!r}")
        unit = order.index(match.group(2))
        if unit <= last:
            raise ValueError(f"units out of order: {text!r}")
        last = unit
        total += int(match.group(1)) * (3600 if match.group(2) == "h" else 60)
        pos = match.end()
    if pos != len(text):
        raise ValueError(f"bad duration: {text!r}")
    return total


def format_duration(seconds: int) -> str:
    """Inverse of parse_duration for whole minutes: 5400 -> "1h30m"."""
    hours, rest = divmod(seconds, 3600)
    minutes = rest // 60
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return "".join(parts)
