"""python -m benchmarks run [--only effectiveness|performance] [--runs N] [--sizes 100,5000]"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from benchmarks import effectiveness, performance, report

RESULTS = Path(__file__).resolve().parent / "results.json"


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m benchmarks")
    p.add_argument("command", choices=["run"])
    p.add_argument("--only", choices=["effectiveness", "performance"])
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--sizes", default="100,5000")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    data = json.loads(RESULTS.read_text()) if RESULTS.is_file() else {}
    if args.only in (None, "effectiveness"):
        print("effectiveness: running the corpus ...", flush=True)
        data["effectiveness"] = [asdict(r) for r in effectiveness.run_all(args.workers)]
    if args.only in (None, "performance"):
        sizes = tuple(int(s) for s in args.sizes.split(","))
        print(f"performance: sizes {sizes}, {args.runs} runs each ...", flush=True)
        data["performance"] = performance.run_all(sizes, args.runs)
    RESULTS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    results = [effectiveness.Result(**r) for r in data.get("effectiveness", [])] or None
    live_path = Path(__file__).resolve().parent / "live_trial.md"
    live = live_path.read_text(encoding="utf-8") if live_path.is_file() else ""
    path = report.write(results, data.get("performance"), live)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
