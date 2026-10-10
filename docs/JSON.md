# JSON reports and exit codes

Pawl's machine-readable contract. Agents, CI scripts, and PR bots can rely on
everything on this page within one `schema_version`. Fields may be added within
a version; removing a field, renaming a code, or changing a meaning bumps
`schema_version`.

## Exit codes

| Code | Meaning | Commands |
| --- | --- | --- |
| 0 | Pass | all |
| 1 | Regression or tampering found, or an update refused | `check`, `guard`, `update`, `report --exit-status`, `mutate --min-score` |
| 2 | Could not measure or could not establish the gate (fail closed) | all |
| 3 | Preflight failed: fix the environment, not the baseline | `check`, `update`, `init` |

`pawl report` exits 0 by default because it is a renderer (the workflow uses
it to post a comment even when the gate is red). `pawl report --exit-status`
exits with the worst `exit_code` of the reports it read (3 > 2 > 1 > 0).
Both forms exit 2 when there is no report to render. `pawl hook stop` and `pawl hook protect` follow
each harness's own protocol, not this table.

## Common fields

Every JSON document has:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | int | `1` for this document |
| `tool` | string | `"pawl"` |
| `version` | string | Pawl version |
| `kind` | string | `check`, `guard`, `update`, `report`, or `mutate` |
| `status` | string | `pass`, `fail`, or `error` (`update` also: `written`, `unchanged`, `refused`) |
| `exit_code` | int | The exit code the command returned |

`check` and `guard` also have `generated_at` (UTC, ISO 8601), `config_source`
(where the gate definition came from, for example `origin/main:pawl.toml`),
`notes` (list of strings), and `approval` (`null`, or `{"source": "label" |
"flag", "label": "...", "sha": "<commit>"}`).

## `pawl check --json` (also `.pawl/last-report.json`)

| Field | Meaning |
| --- | --- |
| `error` | Error text when `status` is `error`, else `""` |
| `problems` | List of `{code, subject, message, ids, ids_total}`; `ids` holds at most 25 entries |
| `suites` | Per-suite summary: `name`, `failures`, `baseline_failures`, `collected`, `baseline_collected`, `orders` |
| `metrics` | Per-metric: `name`, `value`, `baseline`, `direction` |
| `isolation` | `{suite: {test_id: verdict}}` for new failures re-run alone |
| `next_steps` | Plain-language steps for the agent |

Problem codes (stable):

`NEW_FAILURE`, `MISSING_TESTS`, `NEWLY_SKIPPED`, `COLLECTION_DROP`,
`ORDER_DEPENDENT_FAILURE`, `STALE_BASELINE`, `METRIC_REGRESSION`,
`NOT_IN_BASELINE`, `SUITE_REMOVED`.

## `pawl guard --json` (also `.pawl/last-guard.json`)

| Field | Meaning |
| --- | --- |
| `base` | The base ref and merge base |
| `approved` | Boolean: a human approval applies to this commit |
| `error` | Present when `status` is `error` |
| `findings` | List of `{rule, severity, path, message, ids}`; severity is `block`, `warn`, `info`, or `approved` |

Finding rules (stable):

`PROTECTED_CHANGED`, `SPEC_AUTHORITY_CHANGED`, `BASELINE_LOOSENED`,
`BASELINE_TIGHTENED`, `DEBT_LOG_REWRITTEN`, `DEBT_LOG_CHANGED`,
`TEST_DELETED`, `TEST_MODIFIED`, `SKIP_ADDED`, `TEST_SHADOWED`,
`HOOK_TAMPER`, `TEST_CONFIG_CHANGED`, `SUSPICIOUS_CODE`,
`ESCALATION_OPEN`, `ESCALATION_RESOLVED`,
`TESTS_WEAKENED_REPLAY`, `REPLAY_PASSED`, `REPLAY_SKIPPED`.

## `pawl update --json`

| Field | Meaning |
| --- | --- |
| `status` | `written`, `unchanged`, `refused`, or `error` |
| `loosened`, `tightened` | Lists of change descriptions |
| `order_dependent` | `{suite: [test_id, ...]}` |
| `message`, `error` | Human-readable text |

## `pawl report --format json`

`{schema_version, tool, version, kind: "report", status, exit_code,
worst_exit_code, reports}`, where `reports` holds the last check and guard
documents as written. `status` and `worst_exit_code` describe the worst of
those reports; `exit_code` is what this command returned (0 without
`--exit-status`).

A guard that cannot establish the gate still writes a full guard document:
`status` `error`, `error` set, `approved` false, `approval` null,
`config_source` empty, and no findings.
