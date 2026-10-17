"""Append-only scorecard trend. One JSON object per line, never rewritten."""

from __future__ import annotations

import json
from pathlib import Path

TREND_NAME = "trend.jsonl"


def trend_path(root: Path) -> Path:
    return root / ".pawl" / TREND_NAME


def append(root: Path, record: dict[str, object]) -> None:
    path = trend_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def read(root: Path) -> list[dict[str, object]]:
    path = trend_path(root)
    if not path.is_file():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out
