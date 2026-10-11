import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "pawl.v1"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def row_count(path: Path) -> int | None:
    if path.suffix == ".jsonl" and path.exists():
        return sum(1 for _ in path.open("r", encoding="utf-8"))
    if path.name == "results.json" and path.exists():
        data = json.loads(path.read_text())
        return len(data.get("effectiveness", []))
    if path.name == "live_trial.md" and path.exists():
        return sum(1 for line in path.read_text().splitlines() if line.strip().startswith("|") and "---" not in line)
    return None

def source_entries():
    entries = []
    candidates = [
        REPO_ROOT / "benchmarks" / "results.json",
        REPO_ROOT / "benchmarks" / "live_trial.md",
    ]
    transcript_dir = REPO_ROOT / "benchmarks" / "live_transcripts"
    if transcript_dir.exists():
        candidates.extend(sorted(transcript_dir.glob("*.json")))
    fixture_dir = BUNDLE_ROOT / "fixtures"
    if fixture_dir.exists():
        candidates.extend(sorted(fixture_dir.glob("*.jsonl")))
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        entries.append({
            "path": str(rel),
            "sha256": sha256_file(path),
            "row_count": row_count(path),
        })
    return entries

def main():
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle": "zs_pawl_episodes",
        "sources": source_entries(),
    }
    out = BUNDLE_ROOT / "bundle" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
