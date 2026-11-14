"""Escape display text without changing machine-readable evidence or identities."""

from __future__ import annotations

import unicodedata
from typing import Any


def terminal(text: str, *, layout: bool = False) -> str:
    """Make controls visible; only the outer renderer may supply layout newlines."""
    out: list[str] = []
    for char in text:
        if layout and char == "\n":
            out.append(char)
        elif unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp"):
            value = ord(char)
            out.append(f"\\x{value:02x}" if value <= 255 else f"\\u{value:04x}")
        else:
            out.append(char)
    return "".join(out)


def markdown(value: str) -> str:
    """Keep a field on one line and prevent it from creating Markdown structure."""
    return "".join(
        f"&#{ord(char)};" if char in "&<>`|[]!*#\\" else char
        for char in terminal(value.replace("\\", "\\\\"))
    )


def display_tree(value: Any) -> Any:
    """Copy report fields for rendering; never mutate the underlying evidence."""
    if isinstance(value, str):
        return markdown(value)
    if isinstance(value, list):
        return [display_tree(item) for item in value]
    if isinstance(value, dict):
        return {display_tree(key): display_tree(item) for key, item in value.items()}
    return value
