import hashlib
import json

SCHEMA_VERSION = "pawl.v1"
LABELS = ("TAMPER", "HONEST", "UNRESOLVED")
EVIDENCE_CLASSES = ("OBSERVED", "INFERRED", "UNRESOLVED", "REJECTED")


def stable_id(origin: str, episode_key: str, repo_rev: str) -> str:
    raw = f"pawl:v1:{origin}:{episode_key}:{repo_rev}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def content_hash(record: dict) -> str:
    data = {k: v for k, v in record.items() if k not in ("record_content_hash", "split")}
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
