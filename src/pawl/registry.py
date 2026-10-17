"""CSV registry of honest negatives. Append-only, one row per escalation."""

from __future__ import annotations

import csv
from pathlib import Path

COLUMNS = ["recorded_at", "test_id", "message", "status"]


def registry_path(root: Path) -> Path:
    return root / ".pawl" / "registry.csv"


def append_negative(root: Path, recorded_at: str, test_id: str, message: str) -> None:
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow(
            {
                "recorded_at": recorded_at,
                "test_id": test_id,
                "message": message,
                "status": "open",
            }
        )


def read_rows(root: Path) -> list[dict[str, str]]:
    path = registry_path(root)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))
