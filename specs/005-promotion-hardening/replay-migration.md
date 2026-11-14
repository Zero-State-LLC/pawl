# Scoped assertion migration, T06 implementation contract

An intentional specification change can invalidate an old assertion. Waiving
the resulting failure would also waive regressions. Instead, reconstruct the
trusted original test module with only reviewed assertion blocks replaced,
then run full replay and compare every original test identity. No finding or
failure ID is removed from the replay result.

## Authority and binding

The candidate may propose `pawl.replay-migration.json` at the Pawl root. This
file is protected even when custom guard patterns omit it. It grants no
authority by itself. A new or changed proposal activates only when all of the
following hold:

1. The trusted merge-base config has a nonempty `guard.approvers` allowlist and
   `guard.refuse_pr_author = true`.
2. The existing GitHub-event verifier accepts an authorized allowlisted reviewer
   distinct from the known PR author, on a `pull_request` / `labeled` event,
   with a run ID and PR number. The event binds the checked-out candidate SHA.
3. The proposal equals the blob at that reviewed SHA. The candidate worktree
   has no tracked or nonignored untracked modifications.
   Generate and commit normal report metadata before review, and declare
   runtime log ignore rules before approval. An untracked `.pawl/.gitignore`
   or `.pawl/hook-log.jsonl` correctly prevents activation. Never commit logs
   containing user data merely to make the worktree clean.
4. The proposal's exact base commit matches the replay merge base. Each test
   module's before/after SHA-256 matches its base/reviewed candidate contents.
5. Every target is a unique existing pytest baseline identity and an
   undecorated, synchronous, top-level Python test function.
6. Replay is enabled. A flag, a stale label, candidate-only reviewer policy,
   or a missing author cannot activate the proposal.

This uses Pawl's existing provider-event trust boundary. It does not prove
that same-user candidate code cannot alter the event file, evaluator, imports,
or reports. A trusted external evaluator and separate identities remain
promotion prerequisites. The tests use simulated provider events only.
Approval remains an owner-controlled policy decision: hashes prove which assertions were
reviewed, not that the replacement contract is sufficiently strong or correct.

## Replacement grammar

Schema version 1 has exactly `schema_version`, `base_sha`, and `entries`.
Each entry has exactly `path`, `function`, `before_sha256`, `after_sha256`,
`reason`, and `replacements`. Each replacement has exact `before` and `after`
source strings, including indentation and final newline. Duplicate/unknown
keys and unsupported versions fail closed.

The before block must match complete, contiguous statements exactly once in
the named original function. It may contain assertions and simple assignments
to one local name. The after block must contain assertions only, including at
least one, and occur exactly once in the candidate function. AST validation
proves the replacement cannot escape the declared statement span or change
the enclosing function header, imports, other functions, or other statements.
The original module is reconstructed, never replaced wholesale by a candidate
module. All untouched assertions, setup, cleanup, decorators outside the
target, and shared inputs remain governed by normal replay.

Bounds: 256 KiB manifest, 16 entries, 16 replacements per entry, 32 KiB per
block, and 1 MiB per source module. These are migration parser limits, not a
claim that the still-pending general Git/process/report resource work is done.

## Execution and evidence

Use the trusted base suite configuration and baseline. Full replay is
mandatory. `REPLAY_MIGRATION_APPLIED` records affected IDs, reviewer and SHA;
`REPLAY_PASSED` explicitly describes the reconstructed contract. Any failure,
skip or missing test detected by replay still blocks, including a failing
replacement assertion. Source/hash/authority errors exit 2 with
`REPLAY_MIGRATION_INVALID`. No error becomes an approved result.

Once a migration is merged, an identical manifest on the trusted base is
history and has no effect. A later migration must replace it and obtain fresh
approval. It is never a standing test-file exemption.

## Pawl onboarding migration

[onboarding-migration.example.json](onboarding-migration.example.json) is an
inactive, mechanically verified proposal for the two owner-authorized changes
in PR #45, based on core commit `a69f56ae4ed2f2ea4ef230521c5591ec90d966a8`
and candidate `760fe89396c1c364c5c8f277e575fd7e67722366`.
Reconstruction equals the approved candidate test module except for the
harmless original `import sys`, which remains in replay. The hash assertions
and all other tests are retained.

Do not copy it into active use unchanged after rebasing. An operator first
establishes the independent reviewer policy on the trusted base, then updates
the exact base SHA and test hashes, includes the proposal in the reviewed
candidate, and applies approval to that final SHA. No live approval label or
reviewer configuration was changed by this implementation. Current Pawl base
policy lacks the required independent reviewer configuration, so activation
is deliberately unavailable until T14 is completed.

## Remaining scope

This implements assertion migration only. Broader suite/config/baseline
migrations, all-platform isolation, bounded execution, and release qualification
remain open. It does not change the existing `check` approval behavior or
authorize loosening a baseline. Merge implementation before rebasing the
onboarding work onto it; this branch depends on PR #44, not PR #45.

## Implementation verification

2026-11-13 Pacific Time. Source base: PR #44 at
`a69f56ae4ed2f2ea4ef230521c5591ec90d966a8`. No existing test assertions were
edited in this implementation branch.

Final make check: 302 passed, no skips, 89.68% coverage; Ruff lint/format and
strict Mypy pass. Real Go and Rust toolchains were present. Thirty-one new
test cases exercise valid migration, same-file unrelated regression, failing
replacement assertions, stale/author/bot/missing-author approvals, candidate
policy injection, dirty trees, malformed manifests and encoding, statement
escape, consumed-manifest behavior, and assignment retirement.

Real CLI effectiveness corpus: the approved clean migration passes both CI and
stop hook in clean/debt modes. The attempted same-file regression remains
TESTS_WEAKENED_REPLAY and blocks in both modes, even without holdout evidence.
Overall CI catches 24/26 and 25/27 bad changes, with 0/10 and 0/11 clean false
positives. Two pre-existing known misses remain. These are finite synthetic
corpus results and simulated approval events, not live security certification.

The tightening workflow recorded 268 -> 296, then 296 -> 299 unit tests as
three additional malformed-provider cases were added. Both updates confirmed
two orders, with no loosenings, missing old IDs, failures, or order dependence.
The final approval-focused run passed 47 cases. No existing test was amended.

Guard against PR #44 reports four specification/authority-review blocks only.
No active migration proposal was installed and no approval override was used.
This branch is the implementation dependency for PR #45; it does not activate
the onboarding migration on the live repository.

Final pawl check --ci: PASS, 299 collected unit tests, zero failures, no
missing/unbaselined IDs and zero Ruff findings. The three runtime adapter
tests are verified by make check under the unchanged self-gate configuration.
