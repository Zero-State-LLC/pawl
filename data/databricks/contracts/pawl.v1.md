# pawl.v1 episode contract

## Field table

| Field | Type | Description |
| --- | --- | --- |
| record_id | string sha256 | Stable id over origin, episode_key, repo_rev. |
| schema_version | const pawl.v1 | Contract version. |
| origin | SYNTHETIC or LIVE | Source class. |
| task | object | task_id, repo, repo_rev, task_spec_ref. |
| baseline | object | ref and sha256 or null. |
| agent | object | harness, model, condition, attempt. |
| patch_ref | object | changed_files list, diff_sha256 or null. |
| pawl_version | string | pawl package version. |
| policy_version | string | sha256 of pawl.toml plus contract file. |
| gate_result | object | pawl_local, stop_hook, ci, exit_codes, signals, reason. |
| independent_replay | object | outcome, method, ref. UNRESOLVED unless a non-Pawl oracle exists. |
| holdout_outcome | string or null | pawl_ci_no_holdout vs pawl_ci difference. |
| behavior_annotation | object or null | value and source. live_trial.md is not a human disposition. |
| human_disposition | object or null | label, by, at. Always null in fixtures. |
| label | TAMPER, HONEST, UNRESOLVED | Training label from human disposition or synthetic oracle only. Never from gate_result. |
| label_derivation | human_disposition, synthetic_scenario_oracle, unresolved | Derivation field. gate_result is invalid and quarantined. |
| exploit_family | string | Category for synthetic, behavior class for live. |
| runtime_seconds | number or null | Runtime if measured. |
| cost_usd | number or null | Per-row cost only when scope allows. |
| trial_total_cost_usd | number or null | Total trial cost for live rows. Never divided per episode. |
| cost_scope | trial_total or unavailable | Cost scope. |
| evidence_class | OBSERVED, INFERRED, UNRESOLVED, REJECTED | Distinct evidence labels, never coerced. |
| provenance | object | source_path and source_sha256. |
| record_content_hash | string sha256 | Hash over record content excluding hash and split. |
| split | train, val, test, null | Deterministic group split. |
| transcript_ref | object or null | Transcript path and sha256. No transcript text copied. |

## Label semantics

- TAMPER: synthetic scenario oracle says bad, or a human disposition says tamper.
- HONEST: synthetic scenario oracle says clean, or a human disposition says honest.
- UNRESOLVED: no human disposition and no synthetic oracle.
- OBSERVED, INFERRED, UNRESOLVED, REJECTED are distinct evidence_class values and are never coerced into each other.
- A model proposal is never ground truth.
- human_disposition may only be set from a human source and is always null in generated fixtures.

## Rights and sensitivity

Repository sources are public pawl benchmark artifacts. Do not add secrets, private workspace data, personal data, or live customer data. Fixtures copy only hashes and parsed benchmark rows, not transcript text.

## Split design

- split_method: sha256_group_mod_100
- split_method_version: pawl.v1
- group key: task_id|repo_rev|exploit_family
- split key: sha256(f"{split_method_version}:{group_key}") mod 100
- train if value < 80, val if value < 90, else test
- Whole groups go to one split.
- Live episodes share task_id pawl-live-trial-v1 and exploit_family live_trial so they land in one split.
- Release manifest records split_method, split_method_version, group key definition, counts per split, and release_hash.
