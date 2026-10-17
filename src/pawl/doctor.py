"""Read-only audit of a pawl installation. Never writes."""

from __future__ import annotations

from pathlib import Path

SKIP_DIR_NAMES = {".venv", "venv", "node_modules", "site-packages", "__pycache__", "dist", "build"}


def findings(root: Path) -> list[str]:
    out: list[str] = []
    if not (root / "pawl.toml").is_file():
        out.append("no pawl.toml in this directory")
    if not (root / "pawl.baseline.json").is_file():
        out.append("no pawl.baseline.json")
    if any(part in SKIP_DIR_NAMES for part in root.resolve().parts):
        out.append("root is inside a virtualenv or site-packages")
    scanned = [
        p
        for p in root.rglob("*.py")
        if p.is_file() and not any(part in SKIP_DIR_NAMES for part in p.parts)
    ]
    out.append(f"scannable python files: {len(scanned)}")
    return out
