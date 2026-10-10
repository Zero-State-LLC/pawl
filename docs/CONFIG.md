# Configuration reference

`pawl.toml` lives at the Pawl root: the repository root, or a subdirectory
passed with `--root`. With `--trusted-ref` or `--base`, the base config is
read from the same path (`pkg/pawl.toml` for `--root pkg`), and paths in
`baseline`, `debt_log`, `protected`, and `tests` are relative to the Pawl
root. Repository-wide paths such as `.github/workflows/**` also match from the
repository root. Unknown keys are errors.

## `[pawl]`

| Key | Default | Meaning |
| --- | --- | --- |
| `baseline` | `"pawl.baseline.json"` | Baseline path |
| `debt_log` | `"PAWL_DEBT.md"` | Append-only log of baseline changes |
| `lock_in_ci` | `true` | In CI, a baseline failure that now passes is `STALE_BASELINE` |
| `quarantine_max_days` | `30` | Longest allowed quarantine. Enforced whenever a baseline is read: an expiry further out than this from today is an error (`check`, `update`) or a guard block |

## `[[suite]]` (one or more)

| Key | Default | Meaning |
| --- | --- | --- |
| `name` | required | Suite name, used in the baseline |
| `adapter` | required | `pytest`, `jest`, `vitest`, `go`, `cargo`, or `junit` |
| `command` | required | List of strings, or one string split like a shell |
| `identity` | `"ids"` | `"ids"` tracks each test; `"count"` only counts failures and tests |
| `check_orders` | `1` | Orders run by `pawl check`. `pawl update` uses 2 for pytest or when `order_args` is set |
| `order_args` | `[]` | Extra argument lists, one per extra order, for adapters other than pytest (for example `[["-shuffle=on"]]` for Go) |
| `isolate_max` | `10` | Failed tests re-run alone for the annotation (pytest and Go) |
| `timeout` | `3600` | Seconds |
| `junit_path` | none | Required for `adapter = "junit"`: where the runner writes JUnit XML |
| `ci_only` | `false` | Run only in CI (`--ci` or `CI=true`). Use for holdouts and slow suites |
| `cwd` | `"."` | Working directory relative to the root |

Adapter notes:

- `pytest`: Pawl adds `--junitxml`, `-o junit_family=xunit1`, `--rootdir`, and
  `-p no:cacheprovider`. Extra orders (reverse, then seeded random) come from a
  small plugin Pawl loads only for those runs; `order_args` is not needed.
- `jest`, `vitest`: Pawl adds `--json` and `--outputFile` (Jest) or
  `--reporter=json` (Vitest).
- `go`: Pawl adds `-json`. For a second order set
  `order_args = [["-shuffle=on"]]`.
- `cargo`: parsed from `cargo test` output and reconciled with the summary.
- `junit`: any runner that writes JUnit XML to `junit_path`.

## `[[metric]]` (optional)

| Key | Meaning |
| --- | --- |
| `name` | Metric name |
| `command` | Command to run |
| `direction` | `"down"` (lower is better) or `"up"` |
| `extract` | `count-lines`, `count-regex:<re>`, `regex:<re with one group>`, or `json:<dotted.path>` (append `.length()` to count a list) |
| `ok_exit_codes` | Exit codes that mean the command ran. Default `[0]`. Any other exit code is an error (exit 2), never a value |
| `cwd` | Working directory relative to the root. Default `"."` |
| `tolerance` | Differences up to this amount count as unchanged: no `METRIC_REGRESSION`, no `STALE_BASELINE`, and `pawl update` keeps the recorded value. Default `0` |
| `timeout`, `ci_only` | As for suites |

The metric fails closed:

- The command must exit with one of `ok_exit_codes`. A linter that exits
  non-zero when it finds problems needs `ok_exit_codes = [0, 1]` or its own
  "exit zero" flag (for example `ruff check --exit-zero`). A crash or a
  configuration error usually exits with another code and stops the gate.
- `regex:` and `json:` are errors when nothing matches.
- `count-lines` and `count-regex:` read output with no matching lines as 0.
  That is why the exit code check matters: without it, a crashed tool reads
  as "0 findings", which looks like an improvement.

## `[preflight]` (optional)

| Key | Meaning |
| --- | --- |
| `python` | Interpreter to probe (default `python`) |
| `imports` | List of `{ module = "...", expect_under = "..." }`: the module must import from under that path |
| `commands` | Commands that must exit 0 before tests run |

## `[guard]` (optional)

| Key | Default | Meaning |
| --- | --- | --- |
| `protected` | see below | Glob patterns for gate files (replaces the default) |
| `extra_protected` | `[]` | Added to the default list |
| `tests` | see below | Glob patterns for test files |
| `approval_label` | `"pawl-approved"` | PR label that marks a gate change as human-approved |
| `approvers` | `[]` | GitHub logins allowed to approve with the label; empty means any human sender. Read from the trusted base config only |
| `refuse_pr_author` | `false` | Refuse an approval label applied by the pull request author. Read from the trusted base config only |
| `fail_on_suspicious` | `false` | Turn suspicious-code warnings into blocks |

Default protected: `pawl.toml`, `pawl.baseline.json`, `.github/workflows/**`,
`.github/CODEOWNERS`, `CODEOWNERS`, `**/conftest.py`, `pytest.ini`, `tox.ini`,
`**/sitecustomize.py`, `**/usercustomize.py`, `**/*.pth`, `.pawl/hooks/**`.

Default tests: `tests/**`, `test/**`, `**/test_*.py`, `**/*_test.py`,
`**/*_test.go`, `**/*.test.[jt]s(x)`, `**/*.spec.[jt]s(x)`, `**/__tests__/**`.

## Exit codes

See [JSON.md](JSON.md) for the full machine-readable contract.

| Code | Meaning |
| --- | --- |
| 0 | Pass |
| 1 | Regression or tampering found |
| 2 | Could not measure (fail closed) |
| 3 | Preflight failed: fix the environment |
