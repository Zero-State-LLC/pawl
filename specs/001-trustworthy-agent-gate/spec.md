# PAWL-001: Trustworthy, Low-Friction Agent Regression Gate

Status: PROPOSED. Date: 2026-10-10. Baseline: PAWL 0.2.0.
Authority: existing DESIGN.md, AGENTS.md, SECURITY.md, REPO_SETTINGS.md. This proposal does not change enforcement.

## Constitution and non-negotiable invariants

1. PAWL protects the evidence available before an agent changed the repository. It does not claim that passing tests establish correctness.
2. Only a protected CI environment is authoritative. Local hooks are advisory and bypassable.
3. Unmeasurable, inconsistent or malformed evidence is never reported as a passing gate.
4. The effective branch baseline is at least as strict as the protected merge-base baseline.
5. Human exception authority must be explicit, commit-bound, auditable and revocable; never infer it from a label name alone.
6. Rules must be deterministic, explainable and budgeted. No LLM in a required gate; optional semantic review cannot override deterministic blocks.
7. Existing supported workflows and the zero-runtime-dependency core remain intact unless evidence justifies a breaking change.
8. Preserve the agent's ability to complete non-conflicting work before escalating a specification/test conflict.

## Domain model

- TrustedRef: immutable Git commit from a protected target branch.
- ChangeSet: diff from merge base to candidate commit, including renames and untracked workspace facts where relevant.
- Baseline: versioned map of suite, stable test identity, outcomes, collection floor, metrics, quarantine, provenance.
- EvidenceRun: isolated invocation, effective command, environment fingerprint, report hashes, parsed test outcomes, timing.
- GatePolicy: rule set loaded from TrustedRef and approved exceptions.
- Finding: stable code, severity, affected object, evidence references, remediation and policy version.
- Approval: specific actor, scope, candidate SHA, event receipt, expiration and reason.
- Escalation: conflict, affected tests/spec evidence, candidate commit, disposition and approving reviewer.
- Decision: PASS, BLOCK, INDETERMINATE or PREFLIGHT_ERROR. Keep current CLI exit codes 0/1/2/3.
- Scenario: reproducible mutation with independent oracle labeling it malicious, legitimate, ambiguous or unmeasurable.
- Trial: paired A/B agent execution with a shared frozen task fixture, model and budget.

## Validated observations and limits

- README documents 21 synthetic adversarial scenarios and 8 clean changes; CI detected 20/21 attacks with 0/8 clean blocked. Treat as in-repo benchmark evidence, not a population-level efficacy estimate.
- Live trial: 12 episodes using one model and one task. A spec/docstring rewrite escaped substantive detection; STALE_BASELINE was the only block. Baseline condition exposure was imperfect. These are small exploratory trials, not generalizable failure rates.
- Current strict TEST_MODIFIED intentionally adds legitimate test-maintenance friction. Do not relax without equivalent evidence protection and a measured false-block improvement.
- CI executes untrusted candidate project tests. Pinned PAWL installation does not sandbox those tests or make untrusted PR code safe.

## Risk-ranked architecture gaps

### P0: CI trust boundary and execution isolation
Problem: candidate tests execute in the gate job. Threats include exfiltration of CI credentials, tampering with local reports and trusted checkout artifacts, process escape from weak separation, and privilege abuse.

Requirements:
- Document an explicit permission matrix for fork PRs, same-repository PRs, bots, labels, workflow_dispatch and protected branch pushes.
- Enforce read-only contents permission, no secrets or elevated tokens in untrusted execution, immutable action pinning, and protected required checks. Never use pull_request_target to execute candidate code.
- Separate an untrusted test execution stage from authoritative policy evaluation wherever feasible. Treat report outputs as untrusted and check invocation provenance, exit status, freshness, integrity and binding to candidate SHA.
- Threat-test path traversal, symlink/hardlink escapes, malicious test IDs, ANSI payloads, resource exhaustion, generated workflows and git worktree cleanup.
- Fail closed when protected ref, comparison base, provenance or execution receipt cannot be validated.

Acceptance: malicious fixtures cannot obtain privileged credentials, cause a false PASS through forged/stale artifacts, or silently skip a required suite. CI reports the precise failure mode. A permission review confirms GitHub branch/ruleset settings, which code alone cannot establish.

### P0: Specification integrity and legitimate semantic change
Problem: a live episode rewrote a specification-bearing docstring without detection.
- Introduce configurable protected-spec path patterns with conservative defaults (specs/**, docs/requirements/**, ADRs, explicit executable contract fixtures); never blindly block all docs or all docstrings.
- Detect changes to declared normative sources and docstrings explicitly marked as contracts. Require commit-bound human approval for semantic authority changes; allow ordinary comments and explanatory docs by default.
- Provide a mechanism to register source-of-truth contracts and their hash in protected policy, together with intentional human-approved migrations.
- Report SPEC_AUTHORITY_CHANGED separately from TEST_MODIFIED and distinguish harmless relocation from substantive edits when supported by deterministic evidence.
- Default to REVIEW/BLOCK on declared authority changes, not purported semantic inference from a language model.

Acceptance: replicate the observed docstring rewrite as a regression fixture; the CI decision must not PASS silently. Legitimate README edits and non-normative docstring maintenance remain green. Approved migrations retain immutable before/after evidence.

### P1: Test identity, oracle quality and determinism
- Specify parameterized test IDs, duplicate IDs, path casing, Unicode normalization, adapter drift, test renames, skip/xfail semantics and cross-platform path behavior.
- Characterize order dependence and stochastic failures with repeated seeded runs; record run distributions and quarantine expiry, without laundering a fresh failure into known debt.
- Keep hidden tests genuinely out of the agent workspace and ensure no hidden data appears in logs or PR artifacts.
- Add metamorphic/property-based tests as optional holdouts; mutation is advisory unless empirical precision warrants promotion to required status.
- Add clean-change fixtures for refactoring, authorized test fixes, renamed cases and intentionally changed specifications.

Acceptance: same sealed fixture yields stable identifiers and decision codes across supported environments; ambiguous or missing evidence returns INDETERMINATE.

### P1: Adapters, packaging and integration correctness
- Maintain contract tests for pytest, Jest, Vitest, Go, Cargo, generic JUnit, CI templates, hooks and approval events.
- Pin fixture runner versions and add compatibility test matrices, including Python 3.11-3.13 and POSIX shells; Windows remains explicitly unsupported until validated.
- Verify generated workflow package pinning, isolated venv installation, GitHub event SHA handling, approval reset after pushes, CODEOWNERS and protected-workflow behavior.
- Add offline init and installation failure cases, schema evolution and downgrade resistance tests.

Acceptance: golden JSON reports and exit-code contracts are stable; newly supported platforms have verified CI coverage before being claimed.

### P2: UX and operational adoption
- `pawl doctor` checks local config, baseline, runner availability, effective trust ref, CI readiness and protection gaps without modifying anything.
- `pawl explain <finding>` suggests bounded repairs and clearly marks human-only actions.
- Incremental local checks may reduce latency, but CI must always execute complete required coverage.
- Output machine-readable evidence manifest, concise PR annotations and a reproducible diagnostic bundle with privacy-safe redaction.

Acceptance: new user completes install and first valid protected PR using a documented dry run, and failure remediation remains actionable.

## Journey -> workflow -> state transition -> contract -> acceptance test -> task

### J1: Honest feature change
Journey: agent edits code; local hook checks; CI tests and protects evidence; merge.
Workflow: capture trusted baseline -> run suite -> compare identities/outcomes -> guard diff -> publish decision.
State: BASELINED -> CANDIDATE -> MEASURED -> PASS or BLOCK/INDETERMINATE -> MERGED.
Contract: PASS requires every required runner successful/parseable, zero new failing or missing tests, zero newly skipped or xfailed baseline tests (the gate reports NEWLY_SKIPPED; see src/pawl/check.py), zero unauthorized protected edits, and no unresolved escalation.
Acceptance: 8 clean fixtures and expanded clean corpus must pass without special overrides.
Tasks: cross-adapter golden fixtures; report manifest; CI matrix.

### J2: Agent weakens a test or spec
Journey: agent tries to obtain green by changing an oracle or normative contract.
Workflow: identify authoritative inputs -> compare protected diff -> replay baseline tests -> classify finding -> human review.
State: CANDIDATE -> BLOCKED -> ESCALATED -> APPROVED_REVISION or FIXED -> RECHECK.
Contract: approval is SHA-scoped; a later push invalidates it. Protected baseline alone cannot authorize its own loosening.
Acceptance: test-assertion rewrite and observed spec/docstring rewrite never silently pass.
Tasks: protected-spec authority registry; negative/clean corpus; approval provenance tests.

### J3: Impossible or conflicting task
Journey: implement all feasible spec work; leave conflict visible; escalate.
Workflow: run tasks -> identify exact conflict evidence -> write escalation -> human disposition -> recheck.
State: CANDIDATE -> PARTIAL_VALID_WORK -> ESCALATED -> APPROVED_TEST_CORRECTION / REQUIREMENT_CHANGE / REJECTED.
Contract: an unresolved escalation blocks merge, but should not force premature abandonment of feasible changes.
Acceptance: in a sealed paired trial, measure completion of feasible requirements and unauthorized oracle edits separately.
Tasks: escalation state-machine tests; contract wording A/B experiments.

### J4: Test runner or environment compromised
Journey: malicious change emits forged/stale/partial reports or suppresses collection.
Workflow: run in low-privilege environment -> independently verify report binding and exit -> authoritative compare.
State: CANDIDATE -> MEASURED -> BLOCK (exit 1) when suppression is measurable and provable, specifically MISSING_TESTS, COLLECTION_DROP or NEWLY_SKIPPED from a parseable, validated report; CANDIDATE -> UNMEASURABLE -> INDETERMINATE (exit 2) when evidence cannot be validated, including stale, truncated, forged, killed runner or count mismatch; never PASS.
Acceptance: measurable suppression (MISSING_TESTS, COLLECTION_DROP or NEWLY_SKIPPED) backed by a parseable, validated report must BLOCK with exit 1; stale report, truncated JSON/XML, count mismatch, forged path and killed runner must be UNMEASURABLE and return INDETERMINATE with exit 2, never PASS.
Tasks: environment isolation, evidence provenance, adversarial fixture pack.

## Benchmarking protocol

Freeze a versioned task corpus with independent ground-truth labels, signed or hashed scenario inputs, expected outcomes and a contamination register. Never score a detector with only its own labels.

Tracks:
1. Deterministic adversarial corpus: attacks detected / total, false blocks / legitimate changes, false PASS (critical), INDETERMINATE, per-category coverage.
2. Paired agent behavior: same model, task, starting commit, token/tool/time budgets; randomize treatment order and use distinct sandbox copies. Conditions: plain, contract-only, PAWL hooks, PAWL full CI. Blind outcome adjudication and disclose any condition leakage.
3. Performance: p50/p95 overhead, replay cost, CPU/memory, test count scaling and incremental vs full CI.
4. Integration: reproducible acceptance matrix by runner version and OS.

Use binomial confidence intervals for detection and false-block rates; report raw denominators and per-scenario results. Use paired comparisons with uncertainty where the same task is run across treatments; do not declare a universal percentage from 12 episodes. Preserve raw artifacts, task hashes, prompt revisions, model/provider/version, temperatures, token counts and dollar spend. Keep a hard budget cap and early-stop rule for invalid environments, not favorable outcomes.

Promotion gates: zero false PASS in critical P0 threat fixtures; no regression against existing 21-cheat and 8-clean corpus; improved detection or lower friction on predeclared held-out scenarios; adapter golden tests and code quality checks pass. Statistical efficacy claims require larger independent samples and uncertainty reporting.

## Delivery plan

| Version | Scope | Blocking exit criteria |
| --- | --- | --- |
| 0.2.x hardening | Trust review, regression fixture for docstring/spec rewrite, evidence schema and threat matrix, reproducible CI tests | Existing features preserved; P0 threats documented and reproducible |
| 0.3.0 | Protected normative-spec registry, SHA-bound approval evidence, replay and forged-report coverage | No silent PASS on P0 tampering fixtures |
| 0.4.0 | Deterministic identity/adapters, report provenance, expanded platform matrix | Cross-adapter golden fixtures and documented platform support |
| 0.5.0 | `doctor`, diagnostics, cleaner escalation UX, incremental local optimization | CI unchanged in authority; measurable adoption and latency improvement |
| 1.0.0 | Stable config/report schemas, security audit, independently repeated A/B evaluation, release guide | Threat-model/benchmark claims independently verified; no unresolved critical risks |

## Implementation boundaries

Recommended folders: `specs/001-trustworthy-agent-gate/` (this specification), `tests/security/` for deterministic attacks, `benchmarks/fixtures/` for labeled cases, `docs/` for operator guidance. Existing repository layout and policy files remain canonical until explicitly migrated.

Every implementation PR must identify constitution/invariant, requirement, journey, workflow, state transition, contract, acceptance tests, risk, backward compatibility, docs and rollback. Keep design and implementation separate until acceptance criteria are accepted. Any open question that can be answered from code, verified documentation or adversarial tests should be resolved by evidence and recorded as an ADR.

## Explicit non-goals

- Claiming PAWL proves code correct or prevents every agent reward hack.
- Replacing deterministic CI with a paid model judge.
- Running hidden test material inside the untrusted agent workspace.
- Automatic human approval, silent baseline relaxation, automatic indefinite quarantine.
- Enterprise service or dashboard before correctness and security gates are established.
