# PAWL-005: Promotion hardening and trustworthy operation

Status: PROPOSED, implementation-ready design, not implemented or release-qualified.
Date: 2026-11-13 PT. Baseline: main
`bc2fcee9d3d0fec63f129e5e3891347d98a95071`, Pawl 0.5.0.
Request: Daniel asked for a complete specification after a promotion-readiness review.

This proposal consolidates unfinished work from specs 001-003. Spec 004's
unbaselined-test rule remains in force. Historical acceptance records remain
unchanged. Merging this spec accepts the design, not evidence of implementation.

Read in order:

1. This file: doctrine, domain, requirements, journeys, states, and scope.
2. [contracts.md](contracts.md): commands, data, verdicts, and evidence.
3. [plan.md](plan.md): architecture, migration, security, and release operations.
4. [acceptance.md](acceptance.md): executable acceptance scenarios and oracles.
5. [tasks.md](tasks.md): dependency-ordered implementation and completion gates.
6. [decisions.md](decisions.md): resolved design choices and operator decisions.
7. [verification.md](verification.md): actual checks and dependency diagnosis.

## 1. Product outcome

A new user can install Pawl, initialize a project, transfer it to CI, and
receive a reproducible verdict. Existing tests cannot be silently disabled by
additive edits. An operator can see which trust controls are verified, missing,
or unknown. Releases come from the exact source and artifacts that passed
qualification. None of these controls substitutes for code review.

The first promotion is a limited early-adopter release of a regression and
test-tampering gate. It is not a hostile-code sandbox, correctness proof, or
proof that candidate-produced reports are truthful.

## 2. Constitution

- C1: Policy, gate code, baseline authority, and approvals come from the trusted
  side. A candidate cannot authorize its own exception.
- C2: Missing, inconsistent, stale, or unmeasurable required evidence never
  yields PASS. Preserve check exit codes 0/1/2/3.
- C3: A test remaining collected is not evidence that its assertions ran.
  Guard executable additions as well as removals.
- C4: One rule applies to every repository. No customer-specific exemptions,
  percentage tolerances for missing tests, or hidden bypasses.
- C5: Zero runtime dependencies, deterministic evaluation, no paid model judge
  in the required path. Optional infrastructure remains outside the core.
- C6: Keep routine development automatic. Human decisions are limited to
  protected authority changes, explicit exceptions, merge, and release.
- C7: A receipt establishes only the observations its issuer can independently
  make. Hashes, signatures, and containers do not prove test truth.
- C8: Benchmark the shipped CLI, not a duplicate detector. Report raw counts,
  known misses, uncertainty, and exact scope.
- C9: Never silently relax a baseline, rewrite existing tests to fit a patch,
  or convert an error into an advisory warning to get green.
- C10: No telemetry, credential persistence, customer upload, or external
  service requirement is added by default.

## 3. Evidence at the design baseline

OBSERVED on 2026-11-13 PT:

- Main CI and release runs for the baseline SHA succeeded in October.
- Local lint, format, and typing checks pass with freshly resolved tooling.
- A local suite has 244 passes, one Go-environment failure, and one Cargo skip.
  The available `go` executable is not a working Go compiler. This result is
  not a Go adapter defect or full platform qualification.
- The untouched self-gate reports a missing long parameter ID: the baseline
  contains the parameter text, while the fresh pytest run emits `text6-unique`.
  Test count remains 243. A controlled collection comparison confirms pytest
  9.1.1 matches all 13 `test_config.py` baseline IDs, while 9.2.0 changes one.
  See [verification.md](verification.md); no test or baseline was changed.
- A synthetic local fixture demonstrates additive control-flow edits that
  leave identities intact and escape replay. External unmodified holdouts
  still detect the corresponding function regression.
- Ruleset 24762283 is active, but requires zero approvals and has code-owner,
  last-push, and strict up-to-date checks disabled. Legacy protection read
  returned 403. PyPI reviewer and organization Actions settings are unverified.
- PR #41 at `2b6d4edefd142288f76b9c2b7c15230331bc5b74` has a mypy dashboard
  failure and 13 unbaselined tests. It is not a dependency of this work.

Sources: `src/pawl/{guard,runner,init,trust}.py`, repository workflows,
`docs/CI_TRUST_REVIEW.md`, and GitHub runs 38509258382, 38509258353,
38509276398, 38992329141, and 38992329128. These observations expire as
source, dependencies, or settings change. Refresh them at qualification.

## 4. Domain and ownership

| Object | Identity and owner | Meaning |
| --- | --- | --- |
| TrustedPolicy | target commit + policy digest; maintainer | Allowed commands, limits, baseline rules, approval policy |
| Candidate | repository + candidate/merge SHA; agent or author | Code under evaluation, never policy authority |
| TestIdentity | suite + adapter identity version + exact ID | Existing evidence protected by the ratchet |
| TestChange | raw Git path + old/new blob IDs | Structural change to test or fixture execution |
| ReplayPlan | policy digest + candidate SHA + suite/file set | Which base tests must run on candidate code |
| Measurement | run + attempt + suite + order | Parsed outcomes plus independent process facts |
| Approval | actor + head SHA + event + scope | Reviewed permission for named policy findings |
| Finding | stable code + subject + evidence | Block, warning, informational, or approved policy change |
| DoctorCheck | check ID + scope + status + source/time | Diagnostic fact; not itself a gate verdict |
| Qualification | immutable source SHA + artifact digests + checks | Evidence required before publication |
| ExecutionReceipt | trusted-controller run identity | Optional isolation/provenance evidence, not semantic proof |

Daniel or a designated independent maintainer owns policy and release choices.
Agents implement and prepare evidence. CI evaluates. Agent identities must not
hold policy administration, release authority, or another reviewer's credentials.

## 5. Requirements

### Test integrity

**R01, required before promotion.** Every modified existing test file enters
the replay plan in CI, even if the diff is additions only. Replay the trusted
base version, not candidate-provided backups. Removed files remain blocked.

**R02, required.** Classify Python additions structurally. Removing or changing
an existing executable statement, signature, decorator, import, fixture,
class base, or binding still blocks. Added control flow, rebinding, fixture
mutation, collection mutation, and module-level executable side effects block
as `TEST_EXECUTION_CHANGED`. Parse ambiguity is an error, not clean code.

Narrow permitted additions: comments/whitespace; new independent undecorated
top-level test functions with unique names; and terminal assertions appended
to an unchanged existing test body. An allowed terminal assertion must have
no calls, attributes, subscripts, named expressions, comprehensions, awaits,
yields, or lambdas in its expression or message. Names, constants, literal
containers, and ordinary operators are syntactically allowed. They are not a
purity proof, so replay remains mandatory. Arbitrary new lines are not allowed.
Non-test bindings and imports must remain unchanged for automatic permission.
Other legitimate additions require review; do not claim semantic equivalence.

For languages without a shipped structural classifier, meaningful changes to
existing test files conservatively require review. Brand-new test files still
run the existing guard rules, and new identities must enter the baseline.
Do not claim first-class Rust inline-test structural protection without a
separately tested classifier. Existing Cargo behavior remains documented.

**R03, required.** Replay narrowing is a measured optimization. Fixture,
module, class, import, or collection changes require full affected-suite
replay. Uncertain scope falls back to full replay. Missing original tests,
unavailable base, timeout, or parser failure returns exit 2, never a skipped
warning with PASS. Full replay is the correctness reference.

**R04, required.** Safe handling of raw Git paths: NUL-delimited enumeration,
literal paths, no shell evaluation, and no lossy quoted-path parsing. Reject
escaping symlinks and ambiguous paths before reading/replaying. Ordinary
Unicode and spaces work; report control characters escaped.

### Setup and identity

**R05, required.** Generated Python configuration uses a portable executable
name, resolved from the target project environment at execution time. Never
commit the initialization host's absolute interpreter by default. An explicit
absolute path is permitted but is reported as nonportable. Pawl's own isolated
venv must not be mistaken for the project's pytest environment.

**R06, required.** Init validates runner availability before measurement and
writes files transactionally. Missing runners, offline hash lookup, or failed
measurement cannot leave a configuration advertised as ready for CI. Existing
files are never overwritten without an explicit, documented operator action.
Generated workflows state and validate their project-specific install step.

**R07, required.** Test identities are stable within a declared compatibility
range. Characterize escaping, long parameters, duplicates, Unicode, paths,
teardown errors, skips, and runner-version drift. A count match cannot replace
identity checks. Fix Pawl's long-parameter fixture with a reviewed migration;
do not auto-delete the old identity or weaken the baseline.

**R08, required.** Commit reproducible development and qualification dependency
constraints. Test the lowest and selected current supported runner versions in
a separate compatibility lane. Pin the qualification environment. Runtime
dependencies remain empty.

### Boundaries and lifecycle

**R09, required.** Bound subprocess output, report size, parser depth/count,
and runtime. Kill the process group on POSIX timeout, reap children, clean
temporary worktrees, and return exit 2 on evidence truncation or uncertain
termination. Do not pass on partial output. Apply the same runner contract to
tests, metrics, preflight commands, and replay.

**R10, required.** Expose the inherited-environment limitation accurately.
Existing configurations retain inheritance for compatibility. A new explicit
minimal-environment mode uses trusted allowlisted variable names; diagnostics
record names/policy only, never values. It is defense in depth, not a sandbox.
No denylist is silently imposed on existing customer suites.

**R11, required.** CI approval is commit-bound, independently sourced, and
limited to policy-change findings. It cannot suppress a fresh test regression,
unknown measurement, stale receipt, or incomplete replay. Local manual flags
remain explicitly local; CI must not accept `--approved` as a substitute for
verified actor provenance. Gate-policy changes require separate normal PR
review even when the label is valid.

**R12, required for promotion.** Fresh operator evidence proves independent
review, code-owner review, last-push review, strict current-base checks, and
release controls. An API denial means UNKNOWN. The checker does not modify
settings. Candidate code must not choose its required check implementation
without independent workflow review.

### Diagnostics, distribution, and evidence

**R13, required.** `pawl doctor` checks parseability, baseline/identity
compatibility, executable resolution, trusted-ref availability, selected
execution boundary, and declared CI configuration. Optional online checks
verify settings with least-privilege credentials. Unknowns remain visible.
Doctor does not run suites, import project code, install packages, mutate
files/settings, or return a readiness verdict based only on file existence.

**R14, required.** Release qualification binds the exact source SHA, build
environment, wheel/sdist digests, smoke tests, corpus result, and required CI
results. Publication consumes those same artifacts in a separate approved
job. Main ancestry and twine alone are insufficient.

**R15, required.** Document actual supported versions, platforms, limitations,
upgrade steps, private reporting, and one reproducible user journey. Validate
the built wheel's quick start outside the source checkout. Record GitHub
release notes without inventing guarantees.

**R16, required.** The corpus invokes real Pawl commands in disposable fixture
repositories. Each new detection has attack and clean scenarios. Freeze
expected results before measuring; keep evidence-level distinctions. No model
calls or statistical efficacy claims are necessary for this release.

**R17, optional after qualification.** Salvage PR #41's trend and dashboard
ideas as informational outputs. Remove its unused unsafe cache predicate and
unimplemented incremental promise. CI never uses cached outcomes for PASS.
One shared action-reference validator covers `.yml` and `.yaml`, full remote
SHA pins, local actions, reusable workflows, and unsupported forms explicitly.

**R18, later isolated-execution milestone.** An external trusted controller
owns policy, gate code, approval, immutable inputs, and observed process
lifecycle. Candidate workers have no write access to these assets or release
credentials. Validate bounded receipt/run/SHA bindings before evaluation.
Candidate-controlled test output remains an untrusted claim even with a valid
receipt. This milestone does not assert that arbitrary in-process monkeypatching
or forged runner output is solved. A stronger truth claim requires a separate
measurement design and adversarial proof.

## 6. Journeys and workflows

| Journey | Workflow | Failure path | Required result |
| --- | --- | --- | --- |
| J1 First install | select project environment -> preflight -> measure -> atomic init -> clean-host smoke | runner/hash/install unavailable | actionable error, no false-ready config |
| J2 Honest feature | resolve policy -> diff -> check -> replay -> compare -> report | new IDs not baselined | explicit tightening task, never delete tests |
| J3 Test weakening | classify additions -> plan full/narrow replay -> use base tests | changed execution or broken originals | block; no PASS from unchanged IDs |
| J4 Legitimate test repair | show exact change -> human review -> scoped approval -> rerun all required checks | push after approval | invalidate exception and rerun |
| J5 Runner failure | bounded spawn -> collect -> terminate/reap -> validate | timeout/oversize/missing report | exit 2 with bounded diagnostics |
| J6 Maintainer adoption | doctor local -> verify remote settings -> remediate -> fresh readback | access denied or shared identity | NOT READY or UNKNOWN, never inferred readiness |
| J7 Release | pin candidate -> qualify artifact -> approve publish -> verify distribution | changed SHA/hash or red check | do not publish |
| J8 Upgrade | inspect current IDs/runtime -> reviewed migration -> shadow qualification -> switch required check | unexpected identity drop | stop migration, preserve old evidence |

## 7. State machines

Gate: `CREATED -> POLICY_RESOLVED -> PREFLIGHT_OK -> MEASURED -> REPLAYED
-> EVALUATED -> PASS | BLOCK`. Any required measurement or policy-resolution
error goes to `INDETERMINATE`; preflight failures go to `PREFLIGHT_ERROR`.
Terminal states are immutable for a run. A rerun gets a new attempt identity.
No edge from BLOCK or INDETERMINATE to PASS exists without new validated work.

Approval: `ABSENT -> VALID_FOR_SHA -> APPLIED_TO_POLICY_FINDINGS`.
A new head, actor mismatch, revoked label, or unrelated event transitions to
`INVALID`. Invalid approval never substitutes for normal review.

Release: `DRAFT -> QUALIFYING -> QUALIFIED -> APPROVED -> PUBLISHED
-> VERIFIED`. Failure before publication transitions to `HELD`. A source,
artifact, or trust-policy change invalidates qualification. Published artifacts
are immutable; repair with a new version and an explicit advisory if needed.

## 8. Scope and release gates

M1: R01-R08 and R11, core correctness and reproducibility.
M2: R09-R10 and R12-R16, bounded operation, operator controls, and packaging.
M3: R17, selected optional UX improvements after M1/M2.
M4: R18, separately qualified isolated execution.

Promotion requires M1 and M2, including fresh operator evidence. Do not hold
the correctness patch hostage to a dashboard, Databricks scaffold, a large
agent trial, Windows support, or a hosted service. Version numbers are selected
at release after reviewing compatibility; this spec does not reserve 0.5.1,
0.6.0, or claim 1.0 readiness.

No automatic merge, approval label, repository-setting mutation, publication,
customer-repository migration, memory write, or paid evaluation is authorized
by this document. Agents may implement reversible work and prepare reviewable
changes within repository instructions. Protected-file and red-gate constraints
remain explicit tasks, not reasons to weaken checks.
