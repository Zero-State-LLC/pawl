import json
from pathlib import Path

import pytest

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BUNDLE_ROOT.parents[1]
FIXTURE_PATH = BUNDLE_ROOT / "fixtures" / "episodes.jsonl"
MANIFEST_PATH = BUNDLE_ROOT / "bundle" / "manifest.json"

@pytest.fixture
def synthetic_record():
    return {
        "record_id": "a" * 64,
        "schema_version": "pawl.v1",
        "origin": "SYNTHETIC",
        "task": {
            "task_id": "t1",
            "repo": "Zero-State-LLC/pawl",
            "repo_rev": "rev1",
            "task_spec_ref": "benchmarks/corpus.py",
        },
        "baseline": {"ref": None, "sha256": None},
        "agent": {"harness": "scripted", "model": None, "condition": "debt", "attempt": 1},
        "patch_ref": {"changed_files": [], "diff_sha256": None},
        "pawl_version": "0.0.0",
        "policy_version": "unavailable",
        "gate_result": {
            "pawl_local": False,
            "stop_hook": False,
            "ci": False,
            "exit_codes": {},
            "signals": [],
            "reason": None,
        },
        "independent_replay": {"outcome": "bad", "method": "scenario_oracle_plus_plain_pytest", "ref": "benchmarks/corpus.py"},
        "holdout_outcome": None,
        "behavior_annotation": None,
        "human_disposition": None,
        "label": "TAMPER",
        "label_derivation": "synthetic_scenario_oracle",
        "exploit_family": "cat",
        "runtime_seconds": None,
        "cost_usd": None,
        "trial_total_cost_usd": None,
        "cost_scope": "unavailable",
        "evidence_class": "INFERRED",
        "provenance": {"source_path": "benchmarks/results.json", "source_sha256": "b" * 64},
        "record_content_hash": "c" * 64,
        "split": None,
        "transcript_ref": None,
    }

def load_fixture_records():
    if not FIXTURE_PATH.exists():
        pytest.skip("fixtures absent; run python scripts/build_fixtures.py")
    records = []
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))
    return records
