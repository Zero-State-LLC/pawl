# Design

This document states Pawl's rules and why each exists. RESEARCH.md has the
sources; docs/ARCHITECTURE_REVIEW.md checks the design against the threats.

## Goal

An agent (or a person) changing a codebase must not make the test signal worse
without a human seeing it. "Worse" means any of: a test that passed now fails,
a test that ran no longer runs, a test that ran now skips, a test's assertions
were weakened, or the gate itself was changed. Pawl does not judge whether new
code is good. It guarantees that the existing evidence about the code only moves
forward.

## Two places, two jobs

1. **The agent's loop (early check).** `pawl check` and the harness hooks tell
   the agent it is not done and why. They run in the agent's environment, so an
   agent with a shell can skip them. They exist to save a round trip, not to
   enforce.
2. **CI (authority).** A required status check runs `pawl check --ci
   --trusted-ref origin/<base>` and `pawl guard --ci --replay --base
   origin/<base>`. CODEOWNERS requires a human review for the gate files. The
   agent cannot change what CI runs without a human approving the change.

## The baseline

`pawl.baseline.json` records, per suite:

- `failing_ids`: tests known to fail (debt). A test that fails and is not in
  this list is a regression.
- `collected_ids` and `collected`: every test that ran, and the count, which
  is a floor.
- `skipped_ids`: tests that were already skipped.
- `confirmed_orders`: how many test orders agreed when the baseline was
  recorded. The default is 2 for pytest.
- `order_dependent`: tests known to depend on order, if a human allowed them.

and per metric, the value and the direction (`down` means lower is better).

Quarantine entries excuse a flaky test until an expiry date, at most
`quarantine_max_days` (default 30). The limit is enforced whenever a baseline
is read, not only by `pawl quarantine`: an entry that expires further out than
that from today is an error (exit 2).

## Check rules

`pawl check` runs every suite, parses the results, and compares them with the
baseline. Each rule below is a problem code in the JSON report.

| Code | Rule | Why |
| --- | --- | --- |
| `NEW_FAILURE` | A failing test ID that is not in `failing_ids` | Counting failures lets a fix in one place hide a break in another (the swapped-failure case). |
| `MISSING_TESTS` | A baseline test ID that did not run | Deleting, renaming, or deselecting a test is a silent way to pass. |
| `NEWLY_SKIPPED` | A baseline test that now skips or xfails | Skips and xfails produce no failure line, so a count-based gate misses them. |
| `COLLECTION_DROP` | Fewer tests collected than the floor | Kept from Abraxas; also the only structural rule in `identity = "count"` mode. |
| `ORDER_DEPENDENT_FAILURE` | A test fails only in a non-default order | Order dependence is the main cause of flaky Python tests. |
| `STALE_BASELINE` | A baseline failure now passes, under `--lock` (default in CI) | The tighter state must be recorded in the same change or it can be lost later. |
| `METRIC_REGRESSION` | A metric moved the wrong way | Generic ratchet for lint counts, type errors, coverage. |
| `SUITE_REMOVED`, `NOT_IN_BASELINE` | Config and baseline disagree | The gate must not silently stop covering a suite. |

New tests that pass are not problems. Pawl notes them and suggests
`pawl update` so they become protected.

## Fail closed

Pawl never reports green when it could not measure.

- Exit codes: 0 pass, 1 regression, 2 could not measure, 3 preflight failed.
- Each adapter reads a machine-readable report (JUnit XML, Jest JSON,
  `go test -json`, cargo output) written by this run. A report left over from an
  earlier run is deleted first.
- The runner's exit code, the parsed failures, and the runner's own summary
  must agree. If pytest exits 1 and no failure is parsed, the result is an
  error, not a pass.
- An unknown config key is an error.
- A metric command must exit with one of its `ok_exit_codes` (default `[0]`).
  A crashed linter prints no findings; counting them would read 0 and look
  like an improvement.

## Preflight

Before running tests, Pawl can check that the configured interpreter imports
the project's packages from inside the repository. Abraxas lost time to a stale
editable install that made a correct repo look broken (and the reverse is
worse: a stale install can make a broken repo look correct). A failed preflight
exits 3 with a message that says to fix the environment, not the baseline.

## Update rules

- `pawl update` records the current state. If that only tightens the baseline
  (fewer failures, more tests, better metrics), it writes it.
- If it would loosen anything, it refuses. A human runs `pawl update --loosen
  --reason "..."`, which writes the reason to the append-only debt log.
- Every baseline is confirmed in at least two orders when the adapter supports
  it. If the orders disagree, the update is refused unless a human passes
  `--allow-order-dependent`.
- `ci_only` suites keep their entries when `update` runs outside CI.

## Trust model in CI

`--trusted-ref origin/main` loads `pawl.toml` and the baseline from the merge
base, not from the branch. If the branch also has a baseline, Pawl uses the
stricter of the two, entry by entry: failing IDs are intersected, collected IDs
are unioned, the floor is the maximum, and each metric takes its better value.
So a branch can tighten the bar but not lower it. The only exit is a human:
the `pawl-approved` label (name read from the base config) or `--approved`.

The label approves one commit. It counts only in the run that applying it
triggered (a `labeled` event for that label) and only when the event's
`pull_request.head.sha` is the commit being checked (in a pull request run,
the second parent of the merge commit). A later push (`synchronize`) or a run
triggered by another label does not inherit it; a human removes and re-applies
the label to approve the new commit. Both reports print the approved commit.

The config is read from the base at the same path the root has in the working
tree, so a root at `pkg/` reads `pkg/pawl.toml` from the base. One module
(`pawl/trust.py`) resolves this for `check`, `guard`, and the stop hook, and
both reports carry the same `config_source`, notes, and approval.

If the base has no config, Pawl refuses (exit 2) instead of falling back to the
branch config. The first PR that adds Pawl is approved by a human with the
label (it changes protected files, so it needs the label anyway), or runs with
`--bootstrap`, which the report states.

## Guard rules

`pawl guard --base origin/main` reads the diff against the merge base.

| Rule | Fires when |
| --- | --- |
| `PROTECTED_CHANGED` | A gate file changed: `pawl.toml`, the baseline, workflows, CODEOWNERS, `conftest.py`, `pytest.ini`, `tox.ini`, `sitecustomize`, `.pth` files. For the baseline it is always reported: as a block when anything loosened, as info when the change is only a recognized tightening (what an honest `pawl update` writes) |
| `BASELINE_LOOSENED` | Any baseline change that is not a recognized tightening: a failing ID added, a test or suite removed, a metric bound or direction changed, fewer confirmed orders, a quarantine added or changed (compared whole: suite, ID, reason, expiry) |
| `DEBT_LOG_REWRITTEN` | Lines were removed from the debt log |
| `TEST_DELETED` | A test file was deleted or renamed away |
| `TEST_MODIFIED` | Existing test lines were changed or removed (adding tests is fine) |
| `SKIP_ADDED` | A skip, xfail, `.only`, `t.Skip`, or `#[ignore]` was added |
| `TEST_SHADOWED` | A test function is defined twice, so the first never runs |
| `HOOK_TAMPER` | A pytest hook that can rewrite outcomes was added |
| `TEST_CONFIG_CHANGED` | Test runner or coverage settings changed in `pyproject.toml`, `setup.cfg`, `package.json`, or `Cargo.toml` |
| `SUSPICIOUS_CODE` | Non-test code checks for the test runner (`PYTEST_CURRENT_TEST`, `JEST_WORKER_ID`, `testing.Testing()`) or defines `__eq__` that always returns true. Stack inspection and monkeypatching are warnings by default. |
| `ESCALATION_OPEN`, `ESCALATION_RESOLVED` | An escalation was opened, or one was closed without approval |
| `TESTS_WEAKENED_REPLAY` | With `--replay`: the base versions of the changed test files fail against the new code |

`TEST_MODIFIED` is deliberately strict. Agents must not edit existing tests;
when a test is wrong, the agent escalates and a human edits it (with the
approval label). This costs some friction on legitimate test refactors, which
is the price of making "edit the test until it passes" impossible to slip
through. Teams that want less friction can drop `tests` globs, but then rely
on replay alone.

Replay is the strongest tamper check: Pawl checks out the merge base in a
temporary worktree, copies the new code over it, restores the base versions of
the changed test files, and runs them. If tests that passed before now fail,
the change weakened them. This is the "revert the test changes and rerun"
check from Baker et al. (2025).

## Escalation

`pawl escalate "why" --test <id>` appends an entry to `.pawl/ESCALATIONS.md`
and tells the agent to stop. The guard blocks merge while an entry added in the
branch is open, and blocks an agent from closing one. Studies show agents cheat
less when they have a sanctioned way to report a broken test
(arXiv:2608.29460). The contract tells the agent to finish the work the spec
allows before escalating; without that clause, agents in the live trial
escalated before writing any code (BENCHMARKS.md).

## Holdouts and mutation

- A suite with `ci_only = true` runs only in CI. Put tests there that the agent
  never sees, ideally from outside its workspace (a separate checkout or
  package). They catch special-casing of visible test inputs. Property-based
  tests make good holdouts.
- `pawl mutate --base origin/main` applies a few mutants (comparison flips,
  arithmetic swaps, `and`/`or`, constant changes, `return None`) to changed
  Python lines and reports which survive. It is advisory by default; use
  `--min-score` to make it a gate.

## Hooks

`pawl hook stop` runs the check (and, with `--base`, the trusted-ref check and
guard with replay) and answers in the harness's format: `{"decision":
"block"}` for Claude Code, Codex, and Hermes, `{"followup_message"}` for
Cursor. It stops blocking after `--max-blocks` (5) consecutive red results so a
gate that cannot go green does not trap the agent; the agent is told to report
the red gate.

`pawl hook protect` blocks tool calls that would write a protected path or run
a human-only command (`pawl update --loosen`, `pawl quarantine`).

## What Pawl does not do

- It does not prove new code correct. Untested code passes the ratchet.
  Holdouts, mutation, and review cover that.
- It does not catch special-casing of inputs that only the visible tests use,
  unless a holdout or mutant exercises them.
- Its suspicious-code rules are patterns. Obfuscated tampering gets past them;
  replay and holdouts are the backstop.
- It is not an LLM judge and does not read agent reasoning.

## Abraxas, then and now

| Abraxas `test_ratchet.sh` | Pawl | Why |
| --- | --- | --- |
| Failure count may only go down | Failing test IDs may only shrink | A swapped failure kept the count and hid a regression |
| Collected count floor read from the `collected N items` line | Collected IDs and floor from JUnit | The line only prints because Abraxas sets `-v` in addopts; with `-q` it reads 0. Deselected tests also count as collected. |
| Preflight for `core` | Configurable import preflight, exit 3 | Same idea, any package |
| Isolation re-run annotates | Same, for pytest and Go | Kept as is |
| Baseline numbers in the script | Baseline JSON from the base branch, stricter of two | An agent could edit the script's numbers in the same change |
| Order dependence found by hand (TEST_DEBT.md) | Two orders on every update; order-only failures reported | Makes the 28 vs 31 discovery automatic |
| Covers the paths listed in the script | Covers every configured suite; `ci_only` for CI-only paths | The 2026-10-07 regression shipped through a path the script did not run |
| No tamper detection | Guard plus replay | Agents edit tests |
