"""Rerun the P0-expanded corpus without rewriting historical benchmark receipts.

python -m benchmarks.p0_validation --output /tmp/pawl-p0.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from benchmarks import effectiveness, report
from benchmarks.corpus import ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    # Bind the executed code and demo inputs even for an uncommitted candidate.
    paths = [
        *ROOT.joinpath("src/pawl").glob("*.py"),
        ROOT / "benchmarks/corpus.py",
        ROOT / "benchmarks/effectiveness.py",
        ROOT / "benchmarks/p0_validation.py",
        ROOT / "benchmarks/abraxas_ratchet.sh.tmpl",
        *ROOT.joinpath("examples/demo").rglob("*.py"),
        ROOT / "examples/demo/pawl.toml",
        ROOT / "examples/demo/pawl.baseline.json",
    ]
    hashes = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    started = datetime.now(UTC).isoformat()
    machine = report.machine()
    results = effectiveness.run_all(args.workers)
    errors = [f"{r.scenario}/{r.base}: {r.error}" for r in results if r.error]
    unexpected = [
        f"{r.scenario}/{r.base}"
        for r in results
        if not r.error and r.caught["pawl_ci"] != (r.label == "bad" and not r.known_miss)
    ]
    # Detect changes during execution rather than silently mixing code versions.
    if any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h for p, h in hashes.items()):
        errors.append("source inputs changed during the run")
    data = {
        "schema": "pawl.p0.effectiveness.v1",
        "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "source_head": head,
        "source_files_sha256": hashes,
        "source_binding": "HEAD is context; file hashes bind executed working-tree inputs",
        "machine": machine,
        "results": [asdict(r) for r in results],
        "scores": {base: effectiveness.score(results, base) for base in ("debt", "clean")},
        "errors": errors,
        "unexpected_pawl_ci_outcomes": unexpected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scores": data["scores"], "errors": errors, "unexpected": unexpected}))
    return int(bool(errors or unexpected))


if __name__ == "__main__":
    raise SystemExit(main())
