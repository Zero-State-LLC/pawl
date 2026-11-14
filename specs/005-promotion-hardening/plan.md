# PAWL-005 implementation plan

## Architecture and change map

Extend the existing CLI and stdlib modules. No service, database, queue,
authentication product, dashboard backend, or runtime package is required.

| Boundary | Existing module | Planned responsibility |
| --- | --- | --- |
| Policy | `config.py`, `trust.py` | Validated execution limits and scoped independent approval |
| Change inventory | `gitutil.py` | NUL-safe paths, blob identities, literal reads |
| Test classification | new `test_changes.py` | Python structural comparison and conservative fallback |
| Guard/replay | `guard.py`, `replay_scope.py` | Complete replay plan, original evidence, error propagation |
| Process lifecycle | `runner.py` | Streaming bounds, environment policy, termination/reaping |
| Parsing | `adapters.py`, `metrics.py` | Bounded verified reads and identity compatibility |
| Initialization | `init.py`, `templates.py`, `cli.py` | Portable project interpreter, transactional generation |
| Diagnosis | new `doctor.py` | Offline checks, explicit online evidence, actionable results |
| Action references | shared validator module | Consistent strict validation used by CLI and CI script |
| Release | reviewed workflow changes | Exact-source qualification and artifact-only publication |
| Evaluation | existing `benchmarks/` | Real CLI execution with fixed oracles and receipts |

Keep replay planning separate from findings and approval presentation. Approval
must not remove a file from the replay plan. Keep policy evaluation separate
from report rendering. Rendering untrusted fields must escape Markdown/HTML
where appropriate and terminal control characters in text output.

## Test additions and replay design

1. Resolve the trusted target and merge base once. Record immutable SHAs.
2. Enumerate one ChangeSet with raw paths and base/candidate blobs.
3. Classify contract/protected/test changes; build required replay obligations
   independently of the finding severity or approval state.
4. Run the normal configured suites against the candidate.
5. Replay modified existing tests. Use full-suite scope for shared bindings,
   fixtures, imports, class changes, and uncertain collection dependencies.
6. Compare against the appropriate trusted baseline and current quarantine.
7. Apply valid scoped policy exceptions. Independent regressions remain red.
8. Persist bounded JSON and produce the human report.

Adversarial review must include additions outside a test function that affect
it indirectly, new shadowing bindings, pytest fixtures, decorators, and files
with unusual names. Do not implement only the originally observed symptom.

Narrowing must be equivalent to full replay for the scenario corpus. When it
cannot be shown safe, prefer the slower full run. Measure the added cost and
explain it; never silently omit replay to meet a latency goal.

## Migration and backward compatibility

The behavior change is intentional: some previously green additive edits will
require review or fail replay. Document this in release notes. Existing exit
codes and scorecard meanings remain stable. Old configs default to inherited
environment mode. Limits are explicit, validated, and may reject previously
unbounded output; provide a reviewed increase path for large suites.

Existing absolute interpreter configurations continue to work on their original
machine. Doctor detects them; an operator selects and commits a portable
command after a second-host smoke. Never rewrite existing configs during check.

For the self-gate ID mismatch:

1. Reproduce in the unchanged checkout and record exact old/new ID sets.
2. Compare a constrained runner environment with the fresh environment to
   identify the cause. Do not infer a deleted test from an ID rename alone.
   The initial comparison is complete: pytest 9.1.1 matches the stored IDs,
   while 9.2.0 changes one. Pinning the measured qualification environment
   is the immediate compatibility action; no baseline loosening is needed
   merely to retain the existing 9.1.1 identities.
3. Prefer stable explicit parameter IDs in a reviewed test amendment. Existing
   test lines are protected under AGENTS.md, so prepare an owner-visible patch
   rather than editing them during an unrestricted implementation step.
4. Produce a bijective migration table with old ID, new ID, source location,
   parameter digest, and outcomes in both environments. Ambiguous mappings stop.
5. Owner reviews any necessary baseline replacement/ID retirement. Ordinary
   added tests use tightening only. Never use `--loosen` to mask drift.
6. Run the entire suite and self-gate after migration; retain the migration
   record. No automated fuzzy ID matching is added to production comparison.

Read-only specs can be prepared while qualification is blocked, but code must
not be called complete or merged until `make check` and `pawl check` pass.
When gate or test conflicts arise, use the existing escalation path and stop
the affected implementation, preserving feasible work and evidence.

## Security, privacy, and governance

Threat actor: an agent controls candidate source and visible tests and can run
shell commands. It cannot legitimately control protected policy, independent
reviewer identity, repository settings, or release credentials. If those
assumptions fail, doctor marks the installation unready or unknown.

Attack surfaces: candidate install hooks, test imports, runner output, XML/JSON,
diffs and paths, approval events, workflow files, diagnostic artifacts, and
package publication. Candidate build/install code is also untrusted execution;
separating only the pytest subprocess is not sufficient isolation.

Near-term constraints:

- Read-only token in candidate jobs; no publication credentials or independent
  reviewer identity. No candidate execution under `pull_request_target`.
- Protect gate code, workflows, baseline, trusted policy, and release manifests
  through independent review. Required check names alone do not protect code.
- Separate report writing from candidate execution. Reports are data only;
  never execute commands, templates, or URLs from them.
- Redact control characters and sensitive local path prefixes in diagnostic
  bundles. Store environment variable names only. Hidden-test contents and
  full stdout are private by default, not PR-comment material.
- Keep `.pawl` outputs local by default, gitignored. Diagnostic bundles are
  explicit opt-in exports. Cap each report using execution limits.
- Optional trend: retain at most 1000 entries or 10 MiB, whichever comes first,
  using atomic replacement. Corrupt history produces a warning and cannot
  alter gate status. No external telemetry.
- CI diagnostic artifacts: three-day default retention. Release evidence:
  retain with the immutable release, excluding raw secrets and hidden data.
  Operators may select shorter diagnostic retention without changing verdicts.
- No automated quarantine, approval, baseline relaxation, or public disclosure
  of exploit details. Follow SECURITY.md for private vulnerability handling.

## Isolated execution, separately qualified

The controller runs outside the candidate OS/user security boundary and holds
the immutable policy, gate installation, approval input, and lifecycle journal.
The worker receives a disposable candidate tree and only the inputs necessary
for the run. Read-only mounts alone do not protect a controller sharing the
same writable installation or credentials. Network is disabled by default;
explicit dependency installation uses a separate reviewed preparation phase.

The worker cannot write controller state, executable lookup, receipt signing
material, or publish credentials. Use ephemeral workers and bounded data-only
transfer. Controller records process exit and termination independently and
validates output size, nonce, SHA, suite, and attempt before parsing.

This design protects assets and provenance. It does not authenticate assertions
inside a compromised Python/JS process. Candidate code can still affect an
in-process runner or fabricate internally consistent output. Holdouts and
separate measurement designs need distinct claims and tests. No requirement
here permits labeling such outcome data as independently verified.

Container/VM provider choice is deferred to the isolated milestone, with a
threat-tested runtime contract and explicit capability discovery. Core Pawl
must remain installable without that infrastructure. Absence of a backend is
an error only when isolated execution is explicitly required by trusted policy.

## CI and release design

Qualification runs on the exact commit to be tagged, in a constrained environment:
lint, format, typing, full required Python matrix, self-gate, attack/clean corpus,
build, metadata validation, fresh-wheel smoke, and generated-workflow smoke.
Cross-language support claims require actual toolchains and actual executions;
skips are not successful qualification. Pin their installation independently.

Build once. Hash wheel and sdist. Smoke-test that wheel outside the checkout.
Before publish, verify tag/version declarations, source SHA, trusted workflow
identity, complete successful checks, manifest, and exact artifact digests.
Only the publish job obtains OIDC identity. It runs no candidate build/install
scripts and publishes the qualified distributions without rebuilding.

Repository controls to verify:

- Independent approval, code-owner review, last-push approval, and current-base
  status checks. Dismiss stale approvals. No agent bypass role.
- Release tags limited to authorized maintainers; protected PyPI environment
  with reviewer; ephemeral publisher identity and correct workflow binding.
- SHA-pinned allowed Actions, enforced where the account supports it. If an
  organization feature is unavailable, document the verified alternative
  control; never claim account-wide enforcement from a source-code lint alone.
- Code owners cover the gate implementation and qualification workflow, not
  only its configuration. An agent editing the evaluator needs human review.

After publish, verify registry version, file digests, attestation identity, and
a clean install of the published artifact. Failure holds promotion even if
upload succeeded. Do not overwrite a package version or relax checks to repair
publication. Ship a new version; use an advisory/yank only with owner action.

Rollback: restore the previously qualified required-check version and trusted
policy after owner review, retaining all baselines and reports. If that version
has a known bypass, pause promotion and restrict use rather than silently
restoring a false safety claim. Correctness fixtures remain permanent.

## Performance and usability

Measure full check, replay, parse, and report durations on fixed 100, 5000, and
20000-test fixtures; record environment and at least five repeats. Report
median and p95 with sample count, plus peak memory where available. No numeric
speed claim is made before measurement. A correctness change may increase
replay cost; document that cost rather than make a security skip conditional
on a time budget. All commands remain bounded by trusted resource policy.

Pilot records: installation success, time to first valid CI check, unexpected
blocks with scenario IDs, accepted review exceptions, and failures by stable
code. Gather only operator-supplied data. Do not build analytics infrastructure
for this release.

## Existing PRs

PR #41: do not merge as a prerequisite. Reuse code only after requirement-level
review. Repair mypy, baseline its new tests through proper review, implement
real doctor checks, replace its separate benchmark detector, and remove the
unused count/age cache shortcut. Its description must match the actual files.

PR #42: review Actions pins and run exact-head checks; handle separately from
behavior changes. PR #33: keep Databricks work outside qualification scope.
No PR is auto-closed, merged, or relabeled by this spec.
