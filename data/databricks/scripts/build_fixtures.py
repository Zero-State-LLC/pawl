import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = BUNDLE_ROOT / "fixtures"
SCHEMA_VERSION = "pawl.v1"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def stable_id(origin: str, episode_key: str, repo_rev: str) -> str:
    return sha256_bytes(f"pawl:v1:{origin}:{episode_key}:{repo_rev}".encode("utf-8"))

def record_content_hash(record: dict) -> str:
    data = {k: v for k, v in record.items() if k not in ("record_content_hash", "split")}
    return sha256_bytes(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8"))

def git_rev() -> str:
    try:
        out = subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode().strip()
    except Exception:
        return "unknown"

def pawl_version() -> str:
    path = REPO_ROOT / "pyproject.toml"
    if not path.exists():
        return "unknown"
    data = tomllib.loads(path.read_text())
    return data.get("project", {}).get("version", "unknown")

def policy_version() -> str:
    files = [REPO_ROOT / "pawl.toml", BUNDLE_ROOT / "contracts" / "pawl.v1.schema.json"]
    if not all(p.exists() for p in files):
        return "unavailable"
    h = hashlib.sha256()
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()

def baseline_info() -> tuple:
    path = REPO_ROOT / "pawl.baseline.json"
    if not path.exists():
        return None, None
    return "pawl.baseline.json", sha256_file(path)

def parse_bool(cell: str):
    if cell is None:
        return None
    text = cell.strip().lower()
    if text in ("true", "pass", "passed", "yes", "1"):
        return True
    if text in ("false", "fail", "failed", "no", "0"):
        return False
    return None

def split_cell(cell: str) -> list:
    if not cell or cell.strip() in ("", "-"):
        return []
    return [part.strip() for part in cell.split("<br>") if part.strip()]

def build_synthetic(rows, repo_rev, pawl_ver, pol_ver, source_sha):
    records = []
    baseline_ref, baseline_sha = baseline_info()
    for row in rows:
        scenario = row.get("scenario", "")
        base = row.get("base", "")
        label = row.get("label")
        category = row.get("category", "")
        episode_key = f"synthetic:{scenario}:{base}"
        origin = "SYNTHETIC"
        caught = row.get("caught", {})
        gate = {
            "pawl_local": caught.get("pawl_local"),
            "stop_hook": caught.get("pawl_stop_hook"),
            "ci": caught.get("pawl_ci"),
            "exit_codes": {},
            "signals": row.get("signals", []),
            "reason": row.get("error"),
        }
        holdout = None
        if caught.get("pawl_ci") is not None and caught.get("pawl_ci_no_holdout") is not None:
            holdout = f"pawl_ci={caught['pawl_ci']};pawl_ci_no_holdout={caught['pawl_ci_no_holdout']}"
        if label == "bad":
            training_label, derivation = "TAMPER", "synthetic_scenario_oracle"
        elif label == "clean":
            training_label, derivation = "HONEST", "synthetic_scenario_oracle"
        else:
            training_label, derivation = "UNRESOLVED", "unresolved"
        seconds = row.get("seconds", {})
        runtime = seconds.get("pawl_local") if isinstance(seconds, dict) else None
        rec = {
            "record_id": stable_id(origin, episode_key, repo_rev),
            "schema_version": SCHEMA_VERSION,
            "origin": origin,
            "task": {
                "task_id": f"synthetic:{scenario}",
                "repo": "Zero-State-LLC/pawl",
                "repo_rev": repo_rev,
                "task_spec_ref": "benchmarks/corpus.py",
            },
            "baseline": {"ref": baseline_ref, "sha256": baseline_sha},
            "agent": {"harness": "scripted", "model": None, "condition": base, "attempt": 1},
            "patch_ref": {"changed_files": [], "diff_sha256": None},
            "pawl_version": pawl_ver,
            "policy_version": pol_ver,
            "gate_result": gate,
            "independent_replay": {
                "outcome": label,
                "method": "scenario_oracle_plus_plain_pytest",
                "ref": "benchmarks/corpus.py",
            },
            "holdout_outcome": holdout,
            "behavior_annotation": None,
            "human_disposition": None,
            "label": training_label,
            "label_derivation": derivation,
            "exploit_family": category,
            "runtime_seconds": runtime,
            "cost_usd": None,
            "trial_total_cost_usd": None,
            "cost_scope": "unavailable",
            "evidence_class": "INFERRED",
            "provenance": {"source_path": "benchmarks/results.json", "source_sha256": source_sha},
            "record_content_hash": "",
            "split": None,
            "transcript_ref": None,
        }
        rec["record_content_hash"] = record_content_hash(rec)
        records.append(rec)
    return records

def parse_live_trial(path: Path) -> list:
    rows = []
    for line in path.read_text().splitlines():
        text = line.strip()
        if not text.startswith("|"):
            continue
        if text.startswith("| ---") or "---" in text:
            continue
        cells = [c.strip() for c in text.strip("|").split("|")]
        if not cells or cells[0] == "Episode":
            continue
        rows.append(cells)
    return rows

def build_live(rows, repo_rev, pawl_ver, pol_ver, source_sha):
    records = []
    transcript_dir = REPO_ROOT / "benchmarks" / "live_transcripts"
    for cells in rows:
        if len(cells) < 11:
            continue
        episode = cells[0]
        if episode.startswith("plain-"):
            condition = "plain"
        elif episode.startswith("pawl-v1-"):
            condition = "pawl-v1"
        else:
            condition = "pawl"
        behavior = cells[3]
        changed_files = split_cell(cells[5])
        signals = split_cell(cells[10])
        gate = {
            "pawl_local": parse_bool(cells[7]),
            "stop_hook": parse_bool(cells[8]),
            "ci": parse_bool(cells[9]),
            "exit_codes": {},
            "signals": signals,
            "reason": None,
        }
        transcript_path = transcript_dir / f"{episode}.json"
        transcript_ref = None
        if transcript_path.exists():
            transcript_ref = {
                "path": f"benchmarks/live_transcripts/{episode}.json",
                "sha256": sha256_file(transcript_path),
            }
        meta_path = transcript_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        spend = meta.get("spend", [])
        trial_total = spend[0] if isinstance(spend, list) and spend else None
        rec = {
            "record_id": stable_id("LIVE", f"live:{episode}", repo_rev),
            "schema_version": SCHEMA_VERSION,
            "origin": "LIVE",
            "task": {
                "task_id": "pawl-live-trial-v1",
                "repo": "Zero-State-LLC/pawl",
                "repo_rev": repo_rev,
                "task_spec_ref": "benchmarks/live_trial.md",
            },
            "baseline": {"ref": None, "sha256": None},
            "agent": {
                "harness": "live_transcript",
                "model": meta.get("model"),
                "condition": condition,
                "attempt": 1,
            },
            "patch_ref": {"changed_files": changed_files, "diff_sha256": None},
            "pawl_version": pawl_ver,
            "policy_version": pol_ver,
            "gate_result": gate,
            "independent_replay": {"outcome": "UNRESOLVED", "method": "none", "ref": None},
            "holdout_outcome": None,
            "behavior_annotation": {"value": behavior, "source": "live_trial.md"},
            "human_disposition": None,
            "label": "UNRESOLVED",
            "label_derivation": "unresolved",
            "exploit_family": behavior or "live_trial",
            "runtime_seconds": None,
            "cost_usd": None,
            "trial_total_cost_usd": trial_total,
            "cost_scope": "trial_total" if trial_total is not None else "unavailable",
            "evidence_class": "OBSERVED",
            "provenance": {"source_path": "benchmarks/live_trial.md", "source_sha256": source_sha},
            "record_content_hash": "",
            "split": None,
            "transcript_ref": transcript_ref,
        }
        rec["record_content_hash"] = record_content_hash(rec)
        records.append(rec)
    return records

def assign_splits(records):
    for rec in records:
        key = f"{rec['task']['task_id']}|{rec['task']['repo_rev']}|{rec['exploit_family']}"
        value = int(hashlib.sha256(f"pawl.v1:{key}".encode("utf-8")).hexdigest(), 16) % 100
        rec["split"] = "train" if value < 80 else "val" if value < 90 else "test"

def main():
    results_path = REPO_ROOT / "benchmarks" / "results.json"
    live_path = REPO_ROOT / "benchmarks" / "live_trial.md"
    if not results_path.exists() or not live_path.exists():
        print("missing source files", file=sys.stderr)
        sys.exit(1)
    results = json.loads(results_path.read_text())
    effectiveness = results.get("effectiveness", [])
    live_rows = parse_live_trial(live_path)
    repo_rev = git_rev()
    pawl_ver = pawl_version()
    pol_ver = policy_version()
    results_sha = sha256_file(results_path)
    live_sha = sha256_file(live_path)
    records = build_synthetic(effectiveness, repo_rev, pawl_ver, pol_ver, results_sha)
    records += build_live(live_rows, repo_rev, pawl_ver, pol_ver, live_sha)
    assign_splits(records)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURE_DIR / "episodes.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"wrote {len(records)} records to {out}")

if __name__ == "__main__":
    main()
