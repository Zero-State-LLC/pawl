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
    p.add_argument(
        "command",
        choices=["run", "report"],
        help="run: measure and write; report: re-render BENCHMARKS.md from saved results",
    )
    p.add_argument("--only", choices=["effectiveness", "performance"])
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--sizes", default="100,5000,20000")
    p.add_argument("--workers", type=int, default=4)
    args = p.parse_args()
    data = json.loads(RESULTS.read_text()) if RESULTS.is_file() else {}
    if args.command == "run":
        data["machine"] = report.machine()  # load and commit at the start of the run
    if args.command == "run" and args.only in (None, "effectiveness"):
        print("effectiveness: running the corpus ...", flush=True)
        data["effectiveness"] = [asdict(r) for r in effectiveness.run_all(args.workers)]
    if args.command == "run" and args.only in (None, "performance"):
        sizes = tuple(int(s) for s in args.sizes.split(","))
        print(f"performance: sizes {sizes}, {args.runs} runs each ...", flush=True)
        data["performance"] = performance.run_all(sizes, args.runs)
    RESULTS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    results = [effectiveness.Result(**r) for r in data.get("effectiveness", [])] or None
    live_path = Path(__file__).resolve().parent / "live_trial.md"
    live = live_path.read_text(encoding="utf-8") if live_path.is_file() else ""
    notes_path = live_path.with_name("live_trial_notes.md")
    if live and notes_path.is_file():
        live += "\n" + notes_path.read_text(encoding="utf-8")
    path = report.write(results, data.get("performance"), live, data.get("machine"))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
