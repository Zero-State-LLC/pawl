# Recommendation

## The question

Is "the CI required check plus CODEOWNERS is the authority; the harness hook is
only a fast early check" the right design?

## Answer: confirmed, with one refinement

The research and the benchmark both support it.

- Hooks run in the agent's environment, and harness vendors say so: Codex calls
  tool hooks "a useful guardrail, not a complete enforcement boundary"
  ([docs](https://developers.openai.com/codex/hooks)). An agent with a shell
  can edit the hook config, the baseline, or the gate script.
- In the benchmark, gate tampering (`baseline_edited`, `conftest_force_pass`,
  `assert_weakened`) passes every agent-side check that trusts the working
  tree, and is caught only when the gate definition comes from the base branch
  and the diff is guarded (BENCHMARKS.md).
- Prompting helps but is not reliable: one sentence eliminated cheating in one
  study (arXiv:2610.04793), while METR found "please do not cheat" had a nearly
  negligible effect
  ([METR](https://metr.org/blog/2025-06-05-recent-reward-hacking/)).

The refinement: the authority must load the gate definition from the base
branch (`--trusted-ref`), not from the branch under test. A required check that
runs the branch's own `pawl.toml` and baseline is gameable in the same PR.
CODEOWNERS makes changes visible; the trusted ref makes them ineffective until
a human approves.

In 4 sentences: CI is the authority, and it must run `pawl check --ci
--trusted-ref origin/main` and `pawl guard --ci --replay --base origin/main` as
a required status check. CODEOWNERS on `pawl.toml`, the baseline, the debt log,
workflows, and conftest files puts a human on every gate change, and the
`pawl-approved` label is the only way to loosen the bar. Harness hooks (`pawl
hook stop` and `pawl hook protect`) are fast early checks that save round trips
and should use `--base` so they apply the same trust model locally. The agent
contract adds the "spec takes priority" sentence and `pawl escalate`, because
giving the agent a sanctioned way out reduces cheating.

## Migration from the Abraxas ratchet

Abraxas today: `scripts/test_ratchet.sh` with `BASELINE_FAILURES=0` and
`BASELINE_COLLECTED=3773`, running `python -m pytest tests/ abraxas/evidence/
-q --no-header -p no:cacheprovider`, with a preflight for the `core` namespace
package and an isolation re-run of up to 10 failed IDs.

### 1. Install and initialize

```bash
pip install "pawl-gate==0.2.1"
pawl init --runner pytest
```

Edit the generated `pawl.toml` to match the script exactly:

```toml
[pawl]
baseline = "pawl.baseline.json"
debt_log = "PAWL_DEBT.md"
lock_in_ci = true

[[suite]]
name = "core"
adapter = "pytest"
command = ["python", "-m", "pytest", "tests/", "abraxas/evidence/", "-q"]
check_orders = 1
isolate_max = 10

[preflight]
python = "python"   # on the Hermes host, the toolchain interpreter
imports = [{ module = "core", expect_under = "core" }]
```

Then `pawl update --orders 2` to record the baseline. If the two orders
disagree, Pawl refuses: that is the 28 vs 31 order dependence from
TEST_DEBT.md. Fix it or record it with `--allow-order-dependent` and a note in
the debt log.

### 2. Keep the script until Pawl has run green in CI for a week

Run both in CI. They should agree except where Pawl is stricter.

### 3. Things that change

- **Count to identity.** Pawl tracks which tests fail. A PR that fixes one
  known failure and breaks another used to pass; now it fails.
- **The `collected N items` fragility.** The script reads the floor from a line
  pytest prints only because Abraxas sets `-v` in `addopts` and the script
  passes `-q` (they cancel to normal verbosity). If someone removes `-v` from
  `addopts`, the script reads `collected=0` and fails every run; if pytest
  changes the line, the floor silently reads 0. Pawl reads JUnit XML instead.
  Deselected tests counted as collected in the script; in Pawl a deselected
  baseline test is `MISSING_TESTS`.
- **Coverage gap with CI.** The 2026-10-07 regression shipped because CI ran
  files the script did not. In Pawl, make CI call `pawl check` instead of a
  separate pytest command, so the gate and CI cannot drift. If CI must run an
  explicit file list, put it in a `[[suite]]` with `ci_only = true`.
- **`MAX_ALLOWED_VIOLATIONS = 81` in `tests/test_coupling_lint.py`.** Move it
  to a metric so it ratchets automatically:

  ```toml
  [[metric]]
  name = "coupling_violations"
  command = ["python", "scripts/count_coupling_violations.py"]
  direction = "down"
  extract = "regex:(\\d+)"
  ```

- **Debt log.** TEST_DEBT.md stays the narrative; PAWL_DEBT.md is the
  machine-written log of every baseline change.
- **Gate files.** Add CODEOWNERS for `pawl.toml`, `pawl.baseline.json`,
  `PAWL_DEBT.md`, `.github/workflows/`, and `**/conftest.py`.
- **Agents.** Add `integrations/AGENTS.md` to Abraxas's AGENTS.md next to the
  interpreter rule and the one-writer-per-tree rule.

### 4. Retire the script

When Pawl has been the required check for a week with no disagreements, delete
`scripts/test_ratchet.sh` in a PR that a human approves.
