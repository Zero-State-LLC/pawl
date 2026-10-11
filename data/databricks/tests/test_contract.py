from tests.conftest import load_fixture_records

REQUIRED_TOP = [
    "record_id", "schema_version", "origin", "task", "baseline", "agent",
    "patch_ref", "pawl_version", "policy_version", "gate_result",
    "independent_replay", "holdout_outcome", "behavior_annotation",
    "human_disposition", "label", "label_derivation", "exploit_family",
    "runtime_seconds", "cost_usd", "trial_total_cost_usd", "cost_scope",
    "evidence_class", "provenance", "record_content_hash", "split",
    "transcript_ref",
]

def validate_record(rec):
    for key in REQUIRED_TOP:
        if key not in rec:
            raise AssertionError(f"missing field {key}")
    if rec["schema_version"] != "pawl.v1":
        raise AssertionError("bad schema_version")
    if rec["origin"] not in ("SYNTHETIC", "LIVE"):
        raise AssertionError("bad origin")
    if rec["label"] not in ("TAMPER", "HONEST", "UNRESOLVED"):
        raise AssertionError("bad label")
    if rec["label_derivation"] not in ("human_disposition", "synthetic_scenario_oracle", "unresolved"):
        raise AssertionError("bad label_derivation")
    if rec["label_derivation"] == "gate_result":
        raise AssertionError("gate_result must not be a label source")
    if rec["evidence_class"] not in ("OBSERVED", "INFERRED", "UNRESOLVED", "REJECTED"):
        raise AssertionError("bad evidence_class")
    if rec["cost_scope"] not in ("trial_total", "unavailable"):
        raise AssertionError("bad cost_scope")
    if rec["split"] not in ("train", "val", "test", None):
        raise AssertionError("bad split")
    for nested in ("task", "baseline", "agent", "patch_ref", "gate_result", "independent_replay", "provenance"):
        if not isinstance(rec[nested], dict):
            raise AssertionError(f"{nested} must be object")
    for key in ("task_id", "repo", "repo_rev", "task_spec_ref"):
        if key not in rec["task"]:
            raise AssertionError(f"task missing {key}")
    for key in ("harness", "model", "condition", "attempt"):
        if key not in rec["agent"]:
            raise AssertionError(f"agent missing {key}")
    for key in ("pawl_local", "stop_hook", "ci", "exit_codes", "signals", "reason"):
        if key not in rec["gate_result"]:
            raise AssertionError(f"gate_result missing {key}")
    for key in ("source_path", "source_sha256"):
        if key not in rec["provenance"]:
            raise AssertionError(f"provenance missing {key}")

def test_fixtures_validate_against_contract():
    records = load_fixture_records()
    assert records
    for rec in records:
        validate_record(rec)
