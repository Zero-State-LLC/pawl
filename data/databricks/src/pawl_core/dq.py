from .records import EVIDENCE_CLASSES, LABELS

REQUIRED_TOP = [
    "record_id",
    "schema_version",
    "origin",
    "task",
    "baseline",
    "agent",
    "patch_ref",
    "pawl_version",
    "policy_version",
    "gate_result",
    "independent_replay",
    "holdout_outcome",
    "behavior_annotation",
    "human_disposition",
    "label",
    "label_derivation",
    "exploit_family",
    "runtime_seconds",
    "cost_usd",
    "trial_total_cost_usd",
    "cost_scope",
    "evidence_class",
    "provenance",
    "record_content_hash",
    "split",
    "transcript_ref",
]

VALID_DERIVATIONS = ("human_disposition", "synthetic_scenario_oracle", "unresolved")


def dq_check(record: dict) -> list:
    codes = []
    for key in REQUIRED_TOP:
        if key not in record:
            codes.append(f"DQ_MISSING_FIELD:{key}")
    if record.get("schema_version") != "pawl.v1":
        codes.append("DQ_BAD_SCHEMA_VERSION")
    if record.get("origin") not in ("SYNTHETIC", "LIVE"):
        codes.append("DQ_BAD_ORIGIN")
    if record.get("label") not in LABELS:
        codes.append("DQ_BAD_LABEL")
    if record.get("label_derivation") not in VALID_DERIVATIONS:
        codes.append("DQ_BAD_LABEL_DERIVATION")
    if record.get("label_derivation") == "gate_result":
        codes.append("DQ_GATE_LABEL_DERIVATION")
    if record.get("evidence_class") not in EVIDENCE_CLASSES:
        codes.append("DQ_BAD_EVIDENCE_CLASS")
    human = record.get("human_disposition")
    if human is not None:
        if not isinstance(human, dict):
            codes.append("DQ_HUMAN_DISPOSITION_NOT_OBJECT")
        else:
            by = human.get("by", "")
            if not isinstance(by, str) or not by.startswith("human:"):
                codes.append("DQ_HUMAN_LABEL_SOURCE_NOT_HUMAN")
            source = human.get("source", "")
            if isinstance(source, str) and source.lower() in ("model", "llm", "assistant"):
                codes.append("DQ_MODEL_IN_HUMAN_FIELD")
    return codes
