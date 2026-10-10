# PAWL 0.2.x P0 trust review

Date: 2026-10-10. Scope: PAWL-001, J2 and J4; DESIGN.md remains canonical.
This is engineering evidence and an operator action plan. It does not govern or activate.

## Boundary and evidence

OBSERVED: main was `af5e3c4` and proposed spec PR #13 was
`58b42146bd95455346bdb7aab1256cd4074853cd` at inspection. PR #13 was open.
The settings snapshot records full SHAs and API responses:
[p0-repo-settings-20261010.json](evidence/p0-repo-settings-20261010.json).
Its SHA-256 is
`4194638b49163abffd4b01bc97f8da72a4cdeaf05c04b5a747113ada145e25b3`.
These are dated observations, not a continuous settings guarantee.

OBSERVED: repository AGENTS.md prohibits agent edits to workflows, gate files,
test runner configuration, and existing test lines. This change adds tests and
fixtures, tightens report validation, and updates documentation. It leaves those
protected surfaces intact. No settings were changed and no release or merge was performed.

## CI execution permission matrix

| Trigger / actor | Current execution | Credential / privilege boundary | Required operator disposition |
| --- | --- | --- | --- |
| Same-repository PR, human or ordinary bot | Candidate checkout, editable candidate PAWL install, project tests; self-hosted macOS | `contents: read`, but `pawl` job also requests `pull-requests: write`; a later same-job reporting step receives `github.token` | Move untrusted execution to a disposable restricted runner; keep its job token read-only; remove same-job privileged reporting |
| Fork PR | Workflow declares `pull_request`, but verified private-fork policy disables fork PR workflows | Write-token and secrets/variables forwarding are both disabled | Preserve these settings; any future fork enablement needs the same runner isolation as other candidate code |
| Dependabot PR | Same PR triggers and self-hosted execution | GitHub normally gives Dependabot PR runs read-only tokens and no ordinary Actions secrets | Keep runner restrictions identical; a read-only token does not protect host resources |
| `labeled` / `unlabeled` | Same candidate job reruns | Existing approval is limited to the matching labeled event and head SHA; it is not execution isolation or verified actor provenance | Maintain approval provenance review; never treat a label as permission to expose credentials |
| Protected `main` push | Candidate PAWL install and check; guard step is PR-only | Same job permission declaration; trust depends on branch review and runner integrity | Tighten review settings and isolate from PR workers before relying on the push path |
| `workflow_dispatch` | Not declared | No dispatch authorization path exists | Any future path must bind a reviewed SHA; do not add an execution override by inference |
| `pull_request_target` | Not declared | Elevated base-context execution must not run candidate code | Keep candidate execution off this trigger |
| Release tag | Build and publish use self-hosted macOS; publish uses `pypi` environment and `id-token: write` | Tag must match version and be on main; `pypi` accepts `v*` tags but has no reviewer protection rule | Isolate release workers from PR workers and add an operator review gate |

OBSERVED: checked-in actions are pinned by full SHA and checkout disables persisted
credentials. Repository default workflow permission is read-only and workflow PR
approval is disabled. However, the `pawl` job overrides the token permission to
request PR write. A new venv and a pinned binary provide dependency separation,
not OS/user isolation. The dogfood workflow installs the candidate PAWL itself;
the shipped integration installs a hash-pinned release, but both execute candidate
tests in the same user/job as policy evaluation and reporting.

INFERRED: candidate code can change the checkout, local reports, installed gate,
or subsequent executable lookup, and can leave processes that observe later job
steps. Host credentials, network access and other jobs' resources depend on runner
configuration. No exploit against a real token or host was attempted.

GitHub documents persistent compromise risks for self-hosted runners, including
private repositories: [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use).
Dependabot defaults are documented in
[Dependabot on Actions](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-on-actions).

## Observed repository settings and blockers

| Setting | API observation | Readiness consequence |
| --- | --- | --- |
| Main ruleset 24762283 | Active; requires `pawl`, `lint`, `test (3.11)`, `test (3.12)`, `test (3.13)` from GitHub Actions | Check names are required, but this does not independently bind their implementation |
| PR review | Zero approvals; code-owner review false; last-push approval false; stale reviews dismissed | The human-review trust premise in DESIGN.md is not enforced by these settings |
| Up-to-date requirement | `strict_required_status_checks_policy: false` | Candidate can be checked against an older base |
| Bypass | OrganizationAdmin, PR-only | Operator bypass exists; no claim that bypass is impossible |
| Action policy | `allowed_actions: all`, `sha_pinning_required: false` | Current workflow pins exist; repository-wide enforcement does not |
| PyPI environment | Only branch-policy rule; `v*` tag restriction | No reviewer gate observed; no publication was attempted |
| Legacy branch protection | API returns 404 `Branch not protected` | Not evidence that main is unprotected: the active ruleset is the protection mechanism |
| Private-fork policy | Correct private-repository endpoint: workflows disabled; write-token and secret/variable forwarding disabled | Fork PRs currently do not execute through this path |
| Host policy | Host not inspected | NOT_COMPUTABLE from this inspection; do not invent isolation guarantees |

Operator changes: require one human approval, code-owner and last-push review,
strict up-to-date checks, action allow-list and SHA enforcement; remove PR-write
from candidate execution; use disposable restricted PR workers separated from
release workers; protect the publish environment. Reconcile these changes with
docs/REPO_SETTINGS.md and review protected workflow changes through the code owner.
This PR does not apply any of them. Billing limitations mentioned in workflow
comments were not independently verified.

## Reproducible threat fixtures and residual risk

| Threat | Fixture / evidence | 0.2.x result or remaining boundary |
| --- | --- | --- |
| Normative docstring rewrite | `test_p0_spec_rewrite.py`: exact `"1h1s" is 3601 seconds` to `3660` substitution from plain-3; code/tests/baseline frozen | Default check and guard still pass; explicitly configured protected source blocks via existing `PROTECTED_CHANGED`. Known miss, not acceptance of spec integrity |
| Legitimate explanatory docs | `explanatory_docstring` and existing `docs_only` corpus cases | Remain clean; no blanket docstring/docs blocking introduced |
| Invalid XML/root/identity; omitted failure/error/skip records | Labeled `p0_reports.json`, registered in `benchmarks/corpus.py`, exercised by real subprocess adapters | `ParseError`, never fabricated passing outcomes; optional outcome summaries must agree with testcase records |
| Abnormal pytest exit with passing report | Exit 3, 4, 5, 7 and 137 probes | Rejected; real empty collection with exit 5 remains measurable so baseline collection rules apply |
| Stale report | CLI probe with valid baseline and runner that writes nothing | Stale file removed; exit 2 and error JSON |
| Generated workflow / unavailable base | Temporary Git repository probes | Existing protected-path block / comparison-ref error remain effective |
| Git replay cleanup | Before/after `git worktree list --porcelain` probe | Ordinary replay removes its temporary worktree; not proof against a surviving malicious subprocess |
| Credential inheritance | Synthetic `GH_TOKEN` marker only | Candidate runner inherits it. No credential-exfiltration protection claimed |
| Symlink/hardlink report escape | Links to synthetic XML under pytest temp directory | Parser currently accepts them. Same-user report authenticity remains unresolved |
| Malicious IDs / traversal | Path and shell-looking identity string in XML | Treated as data, no shell command executed; not a general traversal or log-sanitization guarantee |
| Internally consistent forged report | Linked synthetic report probe | Accepted. Shape/exit validation cannot authenticate an untrusted producer |
| ANSI payloads; resource exhaustion | Review only | Deferred: bounded report sizes/output, control-character encoding, child-process cleanup and nested-document budgets need dedicated fixtures |

No successful fixture establishes zero critical false PASS. Spec integrity,
same-user forged reports and execution isolation remain open P0 risks.
Malformed evidence fixes implement DESIGN.md's existing fail-closed contract;
they do not add a normative-spec registry or change approval semantics.

`tests` summary counts are not newly enforced here: pytest can emit multiple
records for one identity, including call and teardown results. Current identity
deduplication and baseline collection checks stay unchanged. New validation
counts failure/error/skip XML records before identity deduplication, preserving
the existing worst-outcome-wins teardown behavior.

## Receipt contract for future stage separation

This is a proposed schema, not a new runtime guarantee. Current CLI JSON fields
and exit codes remain unchanged. A future trusted supervisor must independently
produce and validate these fields before policy evaluation:

| Field | Binding / validation |
| --- | --- |
| `schema`, `policy_sha256`, `gate_artifact_sha256` | Versioned receipt and immutable gate/policy selected outside candidate execution |
| `repository`, `candidate_sha`, `merge_sha`, `trusted_sha`, `merge_base_sha` | Exact checked-out commits; verify Git ancestry and candidate merge parent |
| `run_id`, `attempt`, `suite`, `nonce`, `argv_sha256` | Match the expected invocation and complete required suite set |
| `started_at`, `finished_at`, `exit_code`, `termination` | Supervisor observations; classify timeout/signal/error independently of runner output |
| `report_sha256`, `report_bytes`, `report_type` | Recompute after safe bounded transfer; reject links, traversal, duplicates, stale attempts and unexpected files |
| `runner_policy_id`, `environment_fingerprint` | Validated low-privilege isolation policy; never include credential values or hidden test contents |
| `approval_receipt` | Separate actor/scope/head-SHA/event evidence; a report cannot authorize its own exception |

A hash made by the candidate is not authentication. Missing, mismatched or
unverifiable receipt fields must yield INDETERMINATE (exit 2). Any reporting job
with write permission must use trusted code, consume bounded data only, validate
workflow/run/attempt/SHA binding, and never execute candidate artifacts. Merely
moving the comment to `workflow_run` would not make those artifacts trusted.

## Reproduction and completion boundary

OBSERVED local validation: WSL Ubuntu, Python 3.12.3, pytest 9.1.1, ruff 0.17.0,
mypy 2.4.0. `make check` exited 0: 199 passed, one skipped (Go not installed),
88.50% coverage against the required 80%; lint, formatting and strict types passed.
The 29 added test cases include attack fixtures, clean controls, characterization
of known limits and existing-boundary checks. No Windows support is claimed.

`pawl check` measured 197 unit tests, zero failures, ruff metric zero and reported
PASS / exit 0. [Check receipt](evidence/p0-check-20261010.json), SHA-256:
`b5a3b8175736386c20c23aecba373dc070c4305d2d0a775155844dbdd2986009`.
The trusted guard against PR #13 reported PASS / exit 0, no findings and no
approval override. [Guard receipt](evidence/p0-guard-20261010.json), SHA-256:
`cfa9802227275e18c7bda041f29e2a15d2762390dd8be3ab1c8183abf2f49cca`.
The gate notes 100 passing IDs outside the unchanged 97-ID baseline. Only 29
are introduced by this PR; the rest predate it. They run and new failures still
block, but their absence is not individually ratcheted yet. A reviewed baseline
tightening is an additional operator follow-up under the protected-file boundary.

The [expanded effectiveness receipt](evidence/p0-effectiveness-20261010.json)
records 60 scenario/base runs, zero execution errors and zero unexpected PAWL CI
outcomes. SHA-256:
`abe48358e511f0353d82b4d57d4d54eef99303dc3524dc7089464b3c995082ee`.
In the debt base, CI caught 20/22 attacks and blocked 0/9 clean changes; in the
clean base it caught 19/21 and blocked 0/8. The extra miss is the normative
docstring rewrite. The original 21/8 debt corpus retains its 20 caught attacks
and zero clean blocks. These are manually labeled in-repo scenarios, not an
independent security evaluation. Input-file hashes bind the executed working
tree; `source_head` is the parent spec commit because the implementation was
uncommitted when the run began. Historical performance and live trials were
not rerun or overwritten.

Use a POSIX development environment, `python -m pip install -e ".[dev]"`, then:

```sh
python -m pytest tests/test_p0_reports.py tests/test_p0_spec_rewrite.py tests/test_p0_boundaries.py -q
make check
pawl check
python -m benchmarks.p0_validation --output /tmp/pawl-p0-effectiveness.json
```

The P0 command writes a separate machine/source-hashed effectiveness receipt;
it does not rewrite BENCHMARKS.md, historical results or performance/live-trial
data. A known-miss fixture is deliberately scored as a miss.
No efficacy rate from this synthetic corpus is a population estimate.

0.2.x delivery is regression characterization, a dated trust review and targeted
malformed-evidence fixes. 0.3.0 must add protected normative sources and trusted
approval provenance. Execution/report authenticity needs operator-approved CI
isolation work; do not mark full P0 security acceptance complete from these tests.

Provenance: Zero-State-LLC/pawl PR #13; existing DESIGN.md and AGENTS.md;
plain-3 archived transcript and live_trial_notes.md; dated GitHub settings snapshot
with the SHA-256 above. No Abraxas Loop or Sprint references apply.
