"""Replay a committed episode corpus through the guard rules. Prints counts, never a rate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

MIN_EPISODES = 3


def load_episodes(directory: Path) -> list[dict[str, str]]:
    return [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))
    ]


def verdict(diff: str) -> str:
    """block when the diff removes a test line or edits a workflow file."""
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---") and "def test_" in line:
            return "block"
        if ".github/workflows/" in line and not line.startswith(("+++", "---")):
            return "block"
    return "pass"


def run(directory: Path) -> dict[str, int]:
    episodes = load_episodes(directory)
    if len(episodes) < MIN_EPISODES:
        raise SystemExit("refusing: corpus too small to report a rate")
    caught = 0
    false_blocks = 0
    for episode in episodes:
        got = verdict(episode["diff"])
        expected = episode["expected"]
        if expected == "block" and got == "block":
            caught += 1
        if expected == "pass" and got == "block":
            false_blocks += 1
    return {"episodes": len(episodes), "caught": caught, "false_blocks": false_blocks}


def main() -> int:
    root = Path(__file__).resolve().parent
    result = run(root / "episodes")
    (root / "trial-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(
        f"episodes {result['episodes']} caught {result['caught']} "
        f"false_blocks {result['false_blocks']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
