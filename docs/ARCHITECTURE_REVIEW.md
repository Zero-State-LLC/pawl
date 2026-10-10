# Architecture review

A self-review of Pawl's design against the threats in RESEARCH.md, done before
the live-agent trial. It lists what is covered, what is not, the tradeoffs, and
the simplest design that still meets the covered threats.

## Threat model

The actor is a coding agent told to make tests pass. It has write access to the
working tree and a shell, and it may cheat when the task is hard or impossible
(ImpossibleBench, EvilGenie, METR, arXiv:2610.04793). It cannot merge to the
default branch or change repository settings. A human reviews pull requests
but does not read every line.

## Threats covered

| # | Threat | Mechanism | Evidence |
| --- | --- | --- | --- |
| T1 | Code change breaks a passing test | `NEW_FAILURE` | Benchmark `new_failure` |
| T2 | Fix one known failure, break another (same count) | Per-ID ratchet | `swapped_failure`: Abraxas misses, Pawl catches |
| T3 | Test module stops importing or collecting | `MISSING_TESTS`, `COLLECTION_DROP` | `collection_error` |
| T4 | Delete or rename a test file | `MISSING_TESTS`, `TEST_DELETED` | `test_file_deleted`, `test_renamed_out_of_pattern` |
| T5 | Skip or xfail a failing test | `NEWLY_SKIPPED`, `SKIP_ADDED` | `skip_added`, `xfail_added`: Abraxas misses both |
| T6 | Replace a real test with a trivial one (same count) | `MISSING_TESTS`, `TEST_MODIFIED`, replay | `delete_and_replace` |
| T7 | Weaken assertions to match broken code | `TEST_MODIFIED`, replay | `assert_weakened`: only the guard catches it |
| T8 | Loosen the baseline or narrow the gate config | `--trusted-ref`, `BASELINE_LOOSENED`, `PROTECTED_CHANGED`, CODEOWNERS | `baseline_edited`, `gate_config_edited` |
| T9 | Add a conftest hook that rewrites outcomes | `PROTECTED_CHANGED`, `HOOK_TAMPER` | `conftest_force_pass` |
| T10 | Deselect tests through runner config | `MISSING_TESTS`, `TEST_CONFIG_CHANGED` | `addopts_deselect` |
| T11 | Code detects the test runner | `SUSPICIOUS_CODE` | `detects_pytest` |
| T12 | Operator overloading (`__eq__` always true) | `SUSPICIOUS_CODE` | `eq_always_true` |
| T13 | Special-case inputs that a holdout covers | `ci_only` holdout suite | `special_case_inputs` |
| T14 | Order-dependent new test | Two orders, `ORDER_DEPENDENT_FAILURE` | `order_dependent_test` |
| T15 | Wrong interpreter or stale install | Preflight, exit 3 | `wrong_interpreter` |
| T16 | Gate cannot measure (crash, missing report) | Fail closed, exit 2 | Unit tests in `test_adapters.py` |
| T17 | Fixed debt never recorded, later regresses silently | `STALE_BASELINE` in CI | `test_update_tightens_freely` |
| T18 | Agent stuck on an impossible task cheats | `pawl escalate`, contract sentence | Literature; live trial (8 of 8 contract episodes escalated, none tampered) |

## Threats not covered

| Threat | Why not | Mitigation outside Pawl |
| --- | --- | --- |
| Special-casing inputs that no holdout covers | Any test-based gate passes code that matches all visible tests | Holdouts from outside the workspace, property tests, `pawl mutate`, review |
| New code with no tests | The ratchet protects existing evidence only (Python agent PRs: 27.0% of changed lines covered by existing tests, arXiv:2607.18057) | Coverage metric as a `[[metric]]`, mutation, review |
| Obfuscated tampering (dynamic imports, encoded strings, patching through indirection) | Guard patterns are regular expressions | Replay and holdouts catch the effect when tests exercise it |
| Agent disables local hooks | Hooks run in the agent's environment | CI required check is the authority |
| Agent with admin rights or a token that can merge or change rulesets | Outside the threat model | Least-privilege tokens; see REPO_SETTINGS.md |
| Compromised CI runner or dependency | Supply chain | SHA-pinned actions, Dependabot |
| A human approves a bad loosening | Pawl records it in the debt log | Review the debt log |
| Flaky failures that do not reproduce in two orders | Two orders cannot prove stability (about 170 reruns for 95% confidence, Gruber et al.) | Quarantine with expiry, isolation annotation |
| Agent rewrites the spec (docstring, docs) to match a wrong test | Docs and docstrings are not gate files; Pawl cannot tell a spec fix from a spec rewrite | Review; seen once in the live trial (BENCHMARKS.md) |
| Tests that are wrong in the base branch | Pawl ratchets what exists | Escalation; human fixes the test |

## Tradeoffs

- **Strict `TEST_MODIFIED` vs friction.** Any changed line in an existing test
  file blocks until a human approves. Legitimate refactors pay this cost. The
  benefit: the most common cheat in the literature (edit the test) cannot pass
  silently. Replay alone would allow edits that keep the old tests passing,
  which is weaker but quieter.
- **Identity vs count.** Tracking test IDs catches swaps and replacements but
  makes the baseline larger (one line per test) and makes renames show up as
  missing tests. Renames are rare and should be reviewed anyway. `identity =
  "count"` remains for runners without stable IDs.
- **Two orders on update.** Doubles update time; catches the most common flaky
  class. `pawl check` runs one order unless `check_orders` is set.
- **Stricter-of-two baselines.** Makes the bar impossible to lower from a
  branch; also means a branch cannot "reset" a baseline that is wrong in main
  without the approval label.
- **Lock in CI.** Forces fixed debt to be recorded in the same PR. Small
  friction; prevents silent re-regression.
- **Regex suspicious-code rules.** Cheap and explainable; false positives are
  possible (for example code that legitimately reads `PYTEST_CURRENT_TEST`).
  Warnings for the noisier patterns, blocks only for the clear ones.
- **Replay cost.** Runs the changed test files a second time in a worktree.
  Only runs when test files changed.
- **No LLM in the gate.** Deterministic, cheap, and not gameable by persuasion.
  Misses semantic cheats a judge might see.

## Simplest design that meets the covered threats

Cut to the bone, the threats above need:

1. A per-test-ID baseline with a collected floor (T1 to T6, T10, T14 with two
   orders).
2. The gate definition and baseline loaded from the base branch in CI, with a
   human-only override (T8).
3. A diff guard on test files and gate files, plus base-test replay (T6, T7,
   T9, T11, T12).
4. Fail-closed parsing and an interpreter preflight (T15, T16).
5. A required CI check and CODEOWNERS on the gate files (authority).

Everything else is optional: holdouts (T13), metrics, mutation, quarantine,
escalation, and harness hooks. Each is off unless configured, except the hooks
and escalation, which cost nothing until used.

Features cut because no user needed them or they added setup friction without
catching a failure mode:

- A separate `report` renderer per CI vendor. One Markdown renderer serves PR
  comments and terminals.
- Git-notes storage of history (git-ratchet style). A committed JSON baseline
  is reviewable and protectable by CODEOWNERS.
- Coverage ratchet as a built-in. A generic `[[metric]]` covers it.
- Automatic quarantine of flaky tests. Quarantine is a human decision with an
  expiry.
- An LLM-judge mode. See "No LLM in the gate."

## Lesson from the live trial

The first contract wording ("if a test and the spec disagree, run `pawl
escalate` and stop") made 3 of 4 episodes escalate before writing any code.
The wording now says to finish everything the spec allows, leave the
conflicting test failing, and then escalate; 4 of 4 episodes then implemented
the feature and escalated. Contract wording is part of the design and is
tested in `benchmarks/live_trial.py`.

## Open questions

The [2026-10-10 P0 trust review](CI_TRUST_REVIEW.md) adds a permission matrix,
dated settings snapshot, malformed-evidence regressions and reproducible known
limits. In particular, a passing self-hosted candidate job does not prove
credential isolation, report authenticity or normative-docstring integrity.

- Resolved in [ADR-0001](adr/0001-added-asserts-allowed.md): `TEST_MODIFIED`
  allows pure additions inside an existing test function (new asserts, new
  lines); only removed or changed existing lines block.
- Claude Code, Codex and Cursor hook output shapes were re-checked against
  their docs on 2026-10-10 (docs/HOOKS_PROVENANCE.md). Hook schemas change;
  the tests cover Pawl's output, not the harness.
