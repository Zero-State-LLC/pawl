# PAWL-005 contracts

Normative companion to [spec.md](spec.md). All interfaces below are proposed.
Existing report fields retain their meaning; new fields are additive unless
the versioning rule below explicitly applies.

## Verdict contract

| Exit | Existing status | Meaning |
| --- | --- | --- |
| 0 | pass | All required evidence valid; no unapproved blocking findings |
| 1 | fail | Measured regression or unauthorized policy/test change |
| 2 | error | Cannot establish required policy, measurement, replay, or evidence |
| 3 | error | Target environment failed preflight |

If multiple conditions exist, retain all bounded findings but use precedence
3 before execution, then 2 for incomplete evidence, then 1, then 0. A known
block must not hide incomplete measurement. Check/guard combination is a
workflow result, not permission to replace either independent command.

Existing codes remain. Add `TEST_EXECUTION_CHANGED` for executable additions
that require review. Errors use additive machine-readable `error_code` values:
`REPLAY_UNAVAILABLE`, `OUTPUT_LIMIT`, `REPORT_LIMIT`, `PARSE_LIMIT`,
`RUN_TIMEOUT`, `TERMINATION_UNCERTAIN`, `UNSUPPORTED_IDENTITY`,
`UNSAFE_PATH`, and `APPROVAL_UNVERIFIED`.
Unknown codes must be rendered, not discarded as success.

## Report fields

Retain `schema_version: 1`, `kind`, `status`, `exit_code`, `problems/findings`,
`notes`, and current scorecard fields. New optional fields:

```json
{
  "execution": {
    "mode": "inherited",
    "isolation_verified": false,
    "outcome_authenticity": "candidate-produced"
  },
  "replay": {
    "required": true,
    "completed": true,
    "scope": "full",
    "reason": "fixture-or-module-change",
    "files_total": 2,
    "seconds": 1.25
  },
  "evidence": {
    "run_id": "example-only",
    "candidate_sha": "example-only",
    "trusted_sha": "example-only",
    "policy_sha256": "example-only"
  }
}
```

The sample identifiers are placeholders, never valid receipts. `completed`
means all required replay measurements parsed and compared. An empty plan is
`required: false`, not an executed replay. Do not include hidden-test content,
raw environment values, credentials, or report payloads in public comments.

If an implementation needs changed meanings, removed fields, or mandatory
new input semantics, introduce and test a new schema version rather than
reinterpret v1. Gate readers reject unknown baseline/receipt major versions.
Display-only consumers may preserve unknown report fields.

## Test-change classifier

Inputs: trusted original blob, candidate blob, raw repository path, adapter,
and trusted test patterns. Outputs: disposition (`unchanged`, `allowed_addition`,
`review_required`, `unmeasurable`), reason code, affected scope, and replay need.

Python comparison removes source locations before comparing ASTs, but retains
every executable field. It must not normalize operators, defaults, decorators,
async status, class inheritance, or binding names away. Deleting docstrings
that are registered contracts follows the contract guard regardless of AST
equivalence. Comment-only changes are not executable changes.

Allowed terminal assertions appear only after the entire original function
body as its unchanged prefix. Restricted assertion expression syntax is in
R02. Appended assertions in branches, decorators, class bodies, or fixture
functions do not qualify. New top-level tests must not shadow any existing
binding. Added imports, assignments, aliases, fixtures, class mutations, and
non-test functions require review even when original lines are untouched.

Malformed source is `unmeasurable`; no parser exception becomes an empty
finding list. For unsupported languages, use conservative review requirements
and documented replay limits instead of heuristic claims of equivalence.

## Replay contract

Enumerate changed files once from a trusted Git comparison. Record all changed
existing test files before applying approval classification. Resolve paths
relative to the Git top level, then the configured subproject root; reject
escape, unexpected links, and decoding loss.

Construct a disposable worktree with candidate production code and the trusted
base versions of changed tests. Restore trusted shared fixture/config inputs
when they influence replay; do not evaluate originals with candidate-rewritten
fixtures. Select suites from trusted policy. Use the trusted baseline projected
onto the exact narrowed scope. If the projection cannot be proved complete,
run full suites. Existing full-suite error fallback remains fail closed.

If proposed config changes remove a suite, the old suite remains required
unless a valid scoped approval authorizes that specific migration. Record
before/after obligations and approved removal separately. Independent failures
in still-required evidence never become approved findings.

Replay cleanup is attempted in `finally`; cleanup failure becomes exit 2 if
it makes subsequent run isolation or termination uncertain. Never delete a
user checkout in cleanup. Temporary paths must have task-owned provenance.

## Python executable and init

Default generated pytest command: `["python", "-m", "pytest", "-q"]`.
Generated preflight uses the same `python` name. Resolve it with the runtime
PATH before spawn, then hold the resolved absolute path for that invocation.
The documented setup activates a target-project venv that provides `python`.
An explicit init option `--python EXECUTABLE` permits `python3`, a relative
project executable, or an absolute override. No shell fragments or interpolation.

Init checks the target interpreter and pytest there, not where Pawl happens
to be installed. Probe failures are exit 3. Measurements that cannot be parsed
are exit 2. Existing intentional commands remain unchanged during upgrades.

Init stages config, baseline, debt file, and optional workflow in a temporary
directory. All required validation and package-hash lookup occur before final
rename. On failure, leave pre-existing files byte-identical and remove staged
files. Multi-file commit uses a rollback journal so a partial filesystem error
cannot silently advertise complete setup. Offline init needs explicit hashes
for `--github`; otherwise fail with instructions before writing the workflow.

## Environment and resource policy

New optional `[execution]` fields, read from trusted config in CI:

| Field | Default | Validation |
| --- | --- | --- |
| `environment` | `inherit` | `inherit` or `minimal` |
| `pass_env` | `[]` | exact variable names; no wildcard |
| `max_output_bytes` | 8388608 | integer 65536..67108864 |
| `max_report_bytes` | 16777216 | integer 65536..268435456 |
| `max_test_records` | 200000 | integer 1..1000000 |
| `max_parse_depth` | 128 | integer 8..256 |
| `terminate_grace_seconds` | 5 | finite number 0..30 |

Suite timeouts retain current defaults. Per-suite limits may tighten global
values; loosening requires trusted policy review. Validate numeric types,
including rejecting bool-as-int, NaN, infinities, and negative values.

In minimal mode, construct an environment from trusted PATH, locale, a new
temporary HOME/TMPDIR, and trusted test-order variables, plus explicitly named
`pass_env` values. Do not inherit `PYTHONPATH`, loader injection variables,
cloud credentials, or Git configuration by accident. Some suites need network
credentials; enabling their explicit inheritance is a reviewed policy choice
and forfeits any claim those credentials are hidden from candidate code.

Stream stdout/stderr into bounded storage. Count bytes before decoding;
terminate on excess. Never truncate evidence and keep PASS. Report readers
check type, link status, size, and path bounds, then read from the verified
handle; avoid a check/reopen race. Duplicate identities follow the adapter's
documented worst-outcome rule only where duplicates are legitimate.

POSIX child groups are terminated, waited on, killed after grace if needed,
and reaped. A child escaping a process group requires stronger containment;
do not claim process groups constitute a sandbox. Windows remains unqualified
until equivalent lifecycle tests pass.

## Doctor

`pawl doctor [--json] [--ci-readiness] [--online] [--trusted-ref REF]`.
Default is offline and read-only. `--online` is explicit. It uses credentials
only in the trusted diagnostic process; it does not run candidate code.

Output has its own `doctor_schema_version: 1`, scope, timestamp, and checks:
`{id, status, severity, message, evidence_source, observed_at, remediation}`.
Status is `pass`, `fail`, `unknown`, or `not_applicable`. Aggregate readiness
is `ready`, `not_ready`, or `unknown`. Fail outranks unknown, which outranks
ready; required unknown checks cannot be hidden by unrelated passes.

Exit 0: all required checks in the selected scope verified.
Exit 1: a required check failed. Exit 2: no failure but a required check is
unknown, or doctor could not complete. The selected scope is always printed;
offline-local success does not certify remote CI readiness. No network request
occurs by default. No project imports, hooks, or configured suite commands run.

## Approval and key lifecycle

Read approvals from an independent event source before candidate execution.
Bind actor, actor type, event/action, repository, PR, head SHA, and allowed
policy-finding scope. Unknown actor type/identity, missing scope, wrong SHA,
revocation, or bot authority is invalid. A lingering label is not fresh consent.

CI's `--approved` use returns exit 2 with `APPROVAL_UNVERIFIED`. Local manual
override remains labeled as local and cannot be promoted into a CI receipt.
Review required check/guard tests that currently assume broad approval before
implementation; propose explicit test amendments for the owner, never silently
rewrite existing assertions.

Prefer ephemeral CI identity for remote reads and OIDC for publication. No
static release key in config, tests, artifacts, or candidate environment.
Rotation/revocation invalidates pending credentials and requires fresh
authorization; it does not mutate historical evidence. Do not log secrets.

## Qualification and optional controller receipt

Qualification manifest v1 contains source SHA, trusted policy SHA/digest,
gate version, workflow/run/attempt IDs, dependency lock digest, platform and
runtime versions, ordered test results, corpus digest/results, artifact paths
and SHA-256 digests, operator-evidence timestamps, and approval reference.
No fabricated timestamps or check receipts; unknown checks remain unknown.

The optional controller uses the receipt fields already proposed in
`docs/CI_TRUST_REVIEW.md`, plus `outcome_authenticity: candidate-produced`.
Its trusted validator rejects missing/mismatched repo, commit, run, attempt,
suite, nonce, policy, command, report digest/length, or termination facts.
A candidate-supplied hash or signature is not an authenticated receipt.
A valid controller receipt proves provenance/lifecycle only; the outcome
authenticity field cannot silently upgrade to verified.
