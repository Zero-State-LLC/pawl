# zs_pawl_episodes v0.1 (dev), dataset card

- Workspace https://dbc-275599e8-47be.cloud.databricks.com (AWS us-west-2), catalog `workspace`, schema `pawl_dev`. Dev only, not shared. Built 2026-10-10 19:37 PT.
- Source: `fixtures/episodes.jsonl` (sha256 prefix 7a18a404bf61), built by `scripts/build_fixtures.py` from pawl@286e0c0: `benchmarks/results.json` (62 SYNTHETIC scenario rows) and `benchmarks/live_trial.md` (12 LIVE episodes). Uploaded to `/Volumes/workspace/pawl_dev/landing/episodes/`.

| table | rows |
|---|---:|
| raw_episode | 74 |
| validated_episode | 74 |
| quarantine_episode | 0 |
| curated_episode | 74 |

- Labels: SYNTHETIC TAMPER 45 and HONEST 17 come from the scenario oracle. All 12 LIVE episodes are UNRESOLVED because no human dispositions exist. Pawl's gate verdict is never the label, and DQ quarantines any label derived from the gate.
- Split, grouped by (task_id, repo_rev, exploit_family): train 66, val 2, test 6. All 12 LIVE episodes share one task, so they all land in train. Do not report LIVE results as held out.
- Cost: the live trial total was $0.1147 (scope: whole trial). Per-episode cost is not computed.
- Lineage: `_source_file` and `_ingested_at` on raw rows, plus `provenance.source_path` and `source_sha256` per record. All loads are MERGE on `record_id`.

## Sample queries
```sql
SELECT origin, label, split, count(*) FROM workspace.pawl_dev.validated_episode GROUP BY ALL;
SELECT reasons, count(*) FROM workspace.pawl_dev.quarantine_episode GROUP BY 1;
SELECT record_id, get_json_object(payload,'$.exploit_family') fam, get_json_object(payload,'$.gate_result.ci') ci
FROM workspace.pawl_dev.curated_episode LIMIT 10;
```
