"""Read-only scan of workflow files for floating action tags."""

from __future__ import annotations

import re
from pathlib import Path

FLOATING = re.compile(r"uses:\s*\S+@v\d+")


def workflow_findings(text: str) -> list[str]:
    if FLOATING.search(text):
        return ["action pinned by floating tag, not commit SHA"]
    return []


def scan(root: Path) -> list[str]:
    out: list[str] = []
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return out
    for path in sorted(workflows.glob("*.yml")):
        for finding in workflow_findings(path.read_text(encoding="utf-8")):
            out.append(f"{path.relative_to(root)}: {finding}")
    return out
