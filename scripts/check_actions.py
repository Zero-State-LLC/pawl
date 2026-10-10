#!/usr/bin/env python3
"""Fail if any workflow `uses:` reference is unpinned or off the allow-list.

Scans every `.github/workflows/*.yml` and `integrations/github/*.yml` file. A
reference is acceptable when it is a local action (`./...`) or when its
`owner/repo` is in ALLOWED and its ref is a full 40-hex commit SHA. Tags,
branches, and abbreviated SHAs fail. Problems print as `file:line: reason`.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from pathlib import Path

ALLOWED = frozenset(
    {
        "actions/checkout",
        "actions/upload-artifact",
        "actions/download-artifact",
        "actions/setup-python",
        "astral-sh/setup-uv",
        "astral-sh/attest-action",
    }
)

WORKFLOW_DIRS = (Path(".github/workflows"), Path("integrations/github"))
USES_RE = re.compile(r"uses:\s*(\S+)")
SHA_RE = re.compile(r"[0-9a-f]{40}")


def references() -> Iterator[tuple[str, int, str]]:
    """Yield (path, line number, reference) for every `uses:` line."""
    for directory in WORKFLOW_DIRS:
        for path in sorted(directory.glob("*.yml")):
            lines = path.read_text(encoding="utf-8").splitlines()
            for number, line in enumerate(lines, start=1):
                if line.lstrip().startswith("#"):
                    continue
                match = USES_RE.search(line)
                if match is not None:
                    yield str(path), number, match.group(1)


def problem(reference: str) -> str | None:
    """Describe why a reference is rejected, or None when it is acceptable."""
    if reference.startswith("./"):
        return None
    name, _, pin = reference.partition("@")
    if SHA_RE.fullmatch(pin) is None:
        return f"not pinned to a 40-hex commit SHA: {reference}"
    if name not in ALLOWED:
        return f"not in the allow-list: {name}"
    return None


def main() -> int:
    """Check every workflow reference; return 0 when all of them pass."""
    total = 0
    failures = 0
    for path, number, reference in references():
        total += 1
        message = problem(reference)
        if message is not None:
            print(f"{path}:{number}: {message}")
            failures += 1
    if failures:
        return 1
    print(f"actions: {total} references pinned and allowed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
