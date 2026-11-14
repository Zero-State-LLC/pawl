# PAWL-005 implementation queue

T01's collection diagnosis is complete. T02-T06 and T09 have a first
implementation slice under review; their full acceptance closure remains open. Order by
dependency, not perceived feature size. A task
is DONE only with its acceptance evidence and required review. No task is
complete merely because a spec, test stub, or UI label exists.

Roles: E = implementing engineer/agent; V = reviewer validating the result;
O = Daniel or an independent authorized operator. These are responsibilities,
not assignments to people who have not agreed to the work.

The T06 assertion-migration slice is implemented for review. See
[replay-migration.md](replay-migration.md) for exact authority, grammar,
verification, and remaining live-policy prerequisites. This is not completion
of all approval/config migration work or activation in the live repository.

## M1: Correctness and reproducibility

| ID | Work and files | Depends on | Owner | Acceptance |
| --- | --- | --- | --- | --- |
| T01 | DONE: reproduce unchanged self-gate ID drift and compare pytest 9.1.1/9.2.0; see verification.md | none | E/V | Diagnosis evidence only; A14/A16 qualification still belongs to T02 |
| T02 | Prepare locked dev/qualification toolchain and stable-ID migration; propose protected test/config/baseline amendments | T01 | E prepares, O reviews | A14-A16; full check and gate green after approved migration |
| T03 | Implement NUL-safe Git ChangeSet and safe path resolution in `gitutil.py` | none | E/V | A08; Unicode, control characters, links, subprojects |
| T04 | Add structural test-change classifier and conservative language fallback | T03 | E/V | A01-A05,A33-A34; no arbitrary-addition allowance |
| T05 | Decouple replay plan from removed-line findings; trusted fixture restoration and complete scope | T03,T04 | E/V | A01,A02,A06-A09,A34 |
| T06 | Scope approval; reject unverified CI override; preserve regression/error verdicts | T05 | E/V, O for protected test amendments | A21-A22 |
| T07 | Portable target-project interpreter selection and runtime diagnostics | none | E/V | A10-A11 |
| T08 | Transactional init, offline hashes, and validated installation recipes | T07 | E/V | A12-A13,A28 |
| T09 | Integrate real CLI attack/clean cases in existing benchmark harness | T04-T08 | E/V | A01-A16,A21-A22,A29,A33-A34 |

T02 must not be performed by rewriting existing test lines or using a baseline
loosening flag without the repository's owner review. Prepare the smallest
concrete patch and migration table. Ordinary additions after that use the
documented tightening workflow and required protected-file review.

## M2: Bounded operation and releasable product

T10's shared-runner slice is implemented for review. See
[bounded-runner.md](bounded-runner.md). It covers command output/lifecycle and
replay cleanup, not completion of report parsing, environment control, hostile
Git subprocess handling, Windows qualification, or isolated execution.

| ID | Work and files | Depends on | Owner | Acceptance |
| --- | --- | --- | --- | --- |
| T10 | Streaming bounded runner, POSIX process cleanup, interruption handling | T02 | E/V | A17,A19 across suite/metric/preflight/replay |
| T11 | Parser and diagnostic slices under review; see report-bounds.md and safe-diagnostics.md. Verified bounded report reads, parser budgets, escaped diagnostics | T10 | E/V | A18 plus existing malformed-report suite |
| T12 | Implemented for review, see minimal-environment.md: explicit minimal environment policy with compatibility-preserving default | T10 | E/V | A20; no hidden isolation claim |
| T13 | Offline slice implemented for review (offline-doctor.md); online settings reads pending | T02,T07,T12 | E/V | A23-A24 |
| T14 | Prepare operator changes: separate agent identity, review rules, evaluator CODEOWNERS, release controls; apply only through authorized operator action | T06,T13 | E prepares, O executes | A24; fresh readback, no shared reviewer credentials |
| T15 | Build-once exact-SHA qualification and artifact-only publication design in reviewed workflows | T02,T09-T11 | E prepares, O reviews | A26-A28; no tag/publish from implementation |
| T16 | Update README, supported versions, QA, migration guide, release notes, limitations, private reporting | T09-T15 | E/V | A27-A29,A32; docs match built artifact |
| T17 | Run exact-head full qualification, archive safe manifest, owner review | T01-T16 | V/O | M1+M2 definition of done |
| T18 | Owner-controlled release, verify registry bytes, then limited promotion | T17 | O | Verified publication and honest support/claim scope |

The full M1/M2 dependency closure is the promotion gate. A small correctness
patch can be reviewed and released earlier if its documented scope is limited,
but that patch is not completion of the entire promotion milestone.

## M3: Useful upgrades, separately mergeable

| ID | Work | Depends on | Acceptance |
| --- | --- | --- | --- |
| T19 | Consolidate action-pin validation; handle both YAML extensions and reference forms | T17 | A25; one implementation used by all callers |
| T20 | Salvage trend/dashboard from PR #41, fix typing, bound storage and rendering | T17 | A31; additive informational schema only |
| T21 | Remove unimplemented incremental help/unused unsafe cache and replace duplicate trial detector | T17 | A29-A30; real CLI only, no cached CI PASS |

PR #41 is not merged wholesale. Cherry-pick or reimplement reviewed pieces in
separate branches after rebasing. Preserve author attribution where applicable.
PR #42 is an independent dependency maintenance review. PR #33 stays separate.

## M4: Isolation with precise claims

| ID | Work | Depends on | Acceptance |
| --- | --- | --- | --- |
| T22 | Select runtime by threat-tested capability contract; document worker preparation and network policy | T17 | plan.md boundaries; operator environment decision |
| T23 | Implement external controller and bounded receipt validator outside candidate ownership | T22 | I01-I05,I07 |
| T24 | Publish measured isolation scope and unresolved outcome-authenticity limits | T23 | I06; never convert provenance into a correctness claim |

## Agent execution contract

1. Read AGENTS.md, this packet, existing specs/ADR, and current HEAD. Recheck
   open PR heads; do not assume this packet's snapshot is still current.
2. Work in an isolated branch/worktree. Preserve unrelated edits. Begin with
   T01 and prepare its concrete migration evidence; do not reset the baseline.
3. Implement one coherent dependency slice at a time. Add tests and corpus
   scenarios before calling a detection complete. Keep the trusted gate
   separate from the candidate implementation during verification.
4. Run targeted tests during development, then required `make check` and
   `pawl check`. Record exact commands and failures. A red gate is not DONE.
5. If an existing test conflicts with the accepted design or a protected file
   must change, produce the minimal reviewable proposal and invoke the existing
   escalation process. Do not amend assertions, apply approval labels, or
   loosen evidence yourself.
6. PR descriptions name requirements, acceptance IDs, compatibility effects,
   protected changes, actual validation, and remaining risk. Do not merge,
   publish, or claim operator controls are active without observed evidence.

## Current blocker register

| ID | Evidence | Effect | Resolution owner |
| --- | --- | --- | --- |
| B01 | Pytest 9.1.1 matches stored IDs; 9.2.0 emits `text6-unique` for one case | Unconstrained fresh self-gate red before this spec | T02 pins qualification environment; stable-ID migration separately reviewed |
| B02 | RESOLVED locally: real Go 1.27.4 and Rust 1.100.0 installed for verification | Runtime adapter tests can execute | T15 must still qualify release workers |
| B03 | Spec/ADR additions are protected authority changes | Draft cannot be treated as approved merge | Independent code-owner review and exact-head approval |
| B04 | Live ruleset lacks review/current-base controls; release settings unknown | Promotion cannot be declared ready | T14 fresh verification and operator action |

Record additional blockers with evidence, affected task, owner, and next
mechanical action. Avoid manual ceremonies for routine edits or reversible
checks. Do not hide a blocker by renaming a check or changing its expected exit.
