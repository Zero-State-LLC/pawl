# Research

Pawl started as the test ratchet in the Abraxas repository: a failure count that
may only go down and a collected-test floor that may only go up. This file
records what the 2025 and 2026 literature and current practitioner tools say
about that design, and what Pawl adopts as a result. Each line gives the source,
what it says, and how it changes the design. Every claim links to its source.
Numbers are quoted from the abstract or text of the linked page.

## Agents gaming tests

- **ImpossibleBench** (Zhong, Raghunathan, Carlini, 2025),
  [arXiv:2510.20270](https://arxiv.org/abs/2510.20270). Builds "impossible"
  task variants whose tests contradict the spec, so any pass is cheating.
  Agents cheat by modifying tests, overloading operators, recording state, and
  special-casing inputs; test access and the feedback loop change cheating
  rates, and LLM monitors catch far less on SWE-bench-style tasks than on
  LiveCodeBench-style ones. *Design change:* existing tests are read-only for
  agents, the guard looks for operator overloading (`__eq__` always true), and
  Pawl does not rely on an LLM monitor as the gate.
- **EvilGenie** (Gabor, Lynch, Rosenfeld, 2025),
  [arXiv:2511.21654](https://arxiv.org/abs/2511.21654). Measures reward
  hacking with held-out tests, LLM judges, and test-file edit detection; held
  out tests gave "only minimal improvement", and Codex and Claude Code both
  showed explicit reward hacking. *Design change:* test-file edit detection is
  the primary tamper signal; holdout suites are optional (`ci_only`), not the
  core.
- **Baker et al., Monitoring Reasoning Models for Misbehavior** (OpenAI, 2025),
  [arXiv:2503.11926](https://arxiv.org/abs/2503.11926). CoT monitoring catches
  reward hacking in agentic coding, but optimizing against the monitor teaches
  obfuscated hacking. *Design change:* Pawl judges the diff and the test
  results, not the agent's reasoning, and replays the base versions of changed
  tests (`pawl guard --replay`), the "revert the test changes and rerun" check.
- **METR, Recent Frontier Models Are Reward Hacking** (2025-06-05),
  [metr.org](https://metr.org/blog/2025-06-05-recent-reward-hacking/). o3
  monkey-patched evaluators, overwrote the equality operator, and read the
  grader's answer from the call stack. Hacking was over 43x more common when the
  model could see the whole scoring function, and prompts such as "please do
  not cheat" had a nearly negligible effect. *Design change:* the guard flags
  outcome-rewriting test hooks, `__eq__` overrides, and call-stack inspection;
  prompting is a supplement, never the gate.
- **Pressure, Context, and Machine Self-Control** (Ozer, Nti, 2026),
  [arXiv:2610.04793](https://arxiv.org/abs/2610.04793). On coding tasks whose
  tests contradict their specs, some models cheated in 65% to 86% of episodes;
  in exploratory analyses one sentence stating that the specification takes
  priority eliminated cheating in all 280 episodes. *Design change:* the agent
  contract (`integrations/AGENTS.md`) leads with that sentence. It is cheap,
  but METR's result says not to depend on it.
- **Can escalation channels redirect reward hacking toward defect disclosure?**
  (Gomez, 2026), [arXiv:2608.29460](https://arxiv.org/abs/2608.29460). Giving
  agents a structured way to report a broken test plus an anti-hacking policy
  cut reward hacking from 23.6% to 5.3% across 8 models; escalation and hacking
  were almost mutually exclusive. *Design change:* new `pawl escalate` command;
  an open escalation blocks merge until a human resolves it.
- **SpecGuard** (Biyani, Dvijotham, 2026),
  [arXiv:2610.09159](https://arxiv.org/abs/2610.09159). Formally certifies
  conflicts between task intent and tests before the agent acts, detecting up
  to 72.8% of conflicts on conflicted SWE-bench tasks. *Design change:* none in
  the tool; cited in DESIGN.md as the upstream complement to escalation.
- **hacktrace** (Jiang et al., 2026),
  [arXiv:2610.03055](https://arxiv.org/abs/2610.03055). Detects reward hacking
  from model internals plus static features of the final files; the motivating
  example is deleting the test that exposes a bug. *Design change:* confirms
  that static file features carry signal; Pawl keeps to static diff features
  because it cannot see model internals.
- **Hack-Verifiable Terminal Bench** (Roth, Bercovich, Efroni, 2026),
  [arXiv:2608.22103](https://arxiv.org/abs/2608.22103). Embeds detectable
  hacks in tasks so hacking can be measured automatically. *Design change:*
  the benchmark corpus uses the same idea: each bad scenario plants one known
  hack and checks whether the gate fires.

## Weak tests and test adequacy

- **UTBoost** (Yu et al., ACL 2025),
  [arXiv:2506.09289](https://arxiv.org/abs/2506.09289). SWE-bench test cases
  are often insufficient; augmenting them found 345 wrongly passed patches and
  changed 40.9% of SWE-Bench Lite and 24.4% of Verified leaderboard entries.
  *Design change:* "tests pass" is not enough; Pawl adds holdout suites and an
  advisory mutation check.
- **Are "Solved Issues" in SWE-bench Really Solved Correctly?** (Wang, Pradel,
  Liu, 2025), [arXiv:2503.15223](https://arxiv.org/abs/2503.15223). 7.8% of
  patches counted as correct fail the full developer test suite. *Design
  change:* the gate must cover every suite CI covers (the same lesson as the
  Abraxas evidence-path regression); Pawl runs every configured suite and
  `ci_only` suites in CI.
- **Mutation-Guided LLM-based Test Generation at Meta (ACH)** (Foster et al.,
  2025), [arXiv:2501.12862](https://arxiv.org/abs/2501.12862). Generates a few
  targeted mutants rather than exhaustive ones, and kills them with new tests.
  *Design change:* `pawl mutate` generates a small number of mutants on changed
  lines only, and is advisory.
- **SWE-Mutation** (Sun et al., ACL 2026 Findings),
  [arXiv:2605.22175](https://arxiv.org/abs/2605.22175). LLM-written test
  suites are weak at detecting realistic mutants. *Design change:* agent-added
  tests do not prove much; Pawl ratchets existing tests and treats new tests
  as additions, not evidence.
- **Agentic Property-Based Testing** (Maaz et al., 2025),
  [arXiv:2510.09907](https://arxiv.org/abs/2510.09907). An agent that infers
  properties and writes Hypothesis tests found real bugs; 56% of its reports
  were valid. *Design change:* none in the gate; property tests are a good
  holdout suite and are recommended in DESIGN.md.

## Agentic pull requests in practice

- **Test Coverage Analysis of Agentic Pull Requests** (Dipongkor et al.,
  ICSME 2026), [arXiv:2607.18057](https://arxiv.org/abs/2607.18057). Agents
  include test changes in only 49.6% of PRs that change code; existing tests
  cover only 27.0% of changed executable lines in Python. *Design change:*
  the baseline alone cannot catch untested changes; the mutation check and
  holdouts target that gap, and WHY_PAWL.md says so.
- **Where Do AI Coding Agents Fail?** (Ehsani et al., MSR 2026),
  [arXiv:2601.15195](https://arxiv.org/abs/2601.15195). In 33k agent PRs,
  unmerged ones are larger and often fail CI. *Design change:* the CI check is
  where agent work is judged, so Pawl's authority lives there.
- **Do Autonomous Agents Contribute Test Code?** (Haque, Ingale, Csallner,
  2026), [arXiv:2601.03556](https://arxiv.org/abs/2601.03556). Test-containing
  agent PRs are becoming more common but vary by agent. *Design change:* none;
  supports allowing test additions freely.
- **Reliability of AI Bots Footprints in GitHub Actions** (Shah et al., 2026),
  [arXiv:2604.18334](https://arxiv.org/abs/2604.18334). 61,837 workflow runs
  from agent PRs; more agent PRs correlates with lower workflow success.
  *Design change:* fail-closed parsing matters; a gate that errors must never
  read as green.
- **SWE-Bench Pro Verified** (Zheng et al., 2026),
  [arXiv:2609.08149](https://arxiv.org/abs/2609.08149). Leakage of gold
  solutions and hidden evaluation information enabled reward hacking. *Design
  change:* holdout suites should live outside the agent's workspace; the demo
  keeps one in-repo only for illustration.

## Flaky and order-dependent tests

- **An Empirical Study of Flaky Tests in Python** (Gruber et al., ICST 2021),
  [arXiv:2101.09077](https://arxiv.org/abs/2101.09077). Order dependency causes
  59% of flaky Python tests, and 95% confidence that a passing test is not
  flaky needs about 170 reruns. *Design change:* every baseline is confirmed in
  at least two orders; new failures that appear only in another order are
  reported as `ORDER_DEPENDENT_FAILURE`; Pawl does not pretend reruns prove
  stability.
- **Evaluating Shaker for Flaky Test Detection in Python** (Leal, Silva,
  Teixeira, 2026), [arXiv:2609.25528](https://arxiv.org/abs/2609.25528). Fewer
  than half of known flaky tests reproduce as flaky on other hardware.
  *Design change:* the isolation re-run only annotates ("reproduces" or
  "passes alone"); it never turns red into green.
- **Reduction of Test Re-runs by Prioritizing Potential Order Dependent Flaky
  Tests** (Iqbal et al., FTW 2025),
  [arXiv:2510.26171](https://arxiv.org/abs/2510.26171). Shared static state
  predicts order dependence. *Design change:* none; supports cheap order
  checks over blind reruns.
- **JS-TOD** (Hashemi et al., 2025),
  [arXiv:2509.00466](https://arxiv.org/abs/2509.00466). Reorders Jest tests to
  find order dependence; causes are shared files and mocking state. *Design
  change:* the Jest adapter passes order arguments when configured
  (`order_args`).

## Practitioner prior art

- **Betterer** ([docs](https://phenomnomnominal.github.io/betterer/docs/introduction)).
  Snapshot of a metric that may only improve, stored in a results file.
  *Adopted:* per-metric direction and an "only tighten" update.
- **ESLint bulk suppressions** ([docs](https://eslint.org/docs/latest/use/suppressions)).
  Records existing violations per file and rule; unused suppressions are
  reported. *Adopted:* per-item identity rather than a count, and a stale
  baseline is an error.
- **basedpyright baseline** ([docs](https://docs.basedpyright.com/latest/benefits-over-pyright/baseline/)).
  Baseline file of known errors; a lock mode fails when the baseline is out of
  date. *Adopted:* `STALE_BASELINE` under `--lock`, on by default in CI.
- **mypy-baseline** ([docs](https://mypy-baseline.orsinium.dev/)). Filters
  known mypy errors by identity. *Adopted:* identity over count.
- **Ruff** has no baseline feature; it suggests `--add-noqa`
  ([issue 1149](https://github.com/astral-sh/ruff/issues/1149)). *Adopted:*
  nothing; generic `[[metric]]` entries cover tools without a baseline.
- **Semgrep `--baseline-commit`** ([CLI reference](https://docs.semgrep.dev/cli-reference)).
  Reports only findings introduced since a commit. *Adopted:* the guard diffs
  against the merge base.
- **ratchet-gate**, command `quality-gate` ([PyPI](https://pypi.org/project/ratchet-gate/)).
  "It will not let a branch set its own bar": with `--baseline-ref` each metric
  is scored against the stricter of the base and head baselines, and it "will
  not go green when it could not measure something." *Adopted:*
  `--trusted-ref` with the stricter of the two baselines, and fail-closed exit
  codes.
- **git-ratchet** ([iangrunert/git-ratchet](https://github.com/iangrunert/git-ratchet)).
  Stores metric history in git notes. *Not adopted:* a committed baseline is
  easier to review and protect with CODEOWNERS.
- **Dusty Burwell, Ratchets** ([post](https://www.dustyburwell.com/2019/05/29/ratchets)).
  The ratchet pattern for migrations: a count that may only go down.
  *Adopted:* the core idea, which Abraxas already used.
- **GitHub rulesets** ([docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)).
  Push rulesets can restrict file paths; branch rulesets require status checks
  and code owner review. *Adopted:* the authority model in
  docs/RECOMMENDATION.md and docs/REPO_SETTINGS.md.
- **Harness hooks**: Claude Code ([docs](https://code.claude.com/docs/en/hooks)),
  Codex ([docs](https://developers.openai.com/codex/hooks)), Cursor
  ([docs](https://cursor.com/docs/hooks)), and Hermes (hooks.md in the
  hermes-agent docs). All can block a tool call and keep the agent going at
  stop. Codex calls tool hooks "a useful guardrail, not a complete enforcement
  boundary." *Adopted:* `pawl hook stop` and `pawl hook protect` as early
  checks, with CI as the authority.

## What we adopt

Each mechanism, where it lives, and its source.

| Mechanism | Where | Source |
| --- | --- | --- |
| Per-test identity ratchet: a new failing ID is a regression even if the count is unchanged | `check.py` `NEW_FAILURE` | ESLint suppressions, mypy-baseline; Abraxas count-only gap |
| Missing baseline tests and newly skipped tests are regressions | `MISSING_TESTS`, `NEWLY_SKIPPED` | ImpossibleBench, EvilGenie (test deletion and skips) |
| Collected-test floor | `COLLECTION_DROP` | Abraxas `BASELINE_COLLECTED` |
| Baseline confirmed under two orders; order-only failures reported | `update.py`, `ORDER_DEPENDENT_FAILURE` | Gruber et al. 2021; Abraxas TEST_DEBT.md (28 vs 31) |
| Isolation re-run that only annotates | `adapters.isolate` | Abraxas; Shaker evaluation 2026 |
| Stale baseline fails in CI | `STALE_BASELINE`, `lock_in_ci` | basedpyright lock mode, ESLint unused suppressions |
| Gate definition from the base branch; stricter of base and head baselines | `--trusted-ref` | ratchet-gate; METR (visible scorer invites hacking) |
| Fail-closed adapters: exit code, report, and summary must agree; never read a stale report | `adapters.py`, exit code 2 | ratchet-gate; Abraxas `-q` "collected" fragility |
| Interpreter preflight: imports must resolve inside the repo | `preflight.py`, exit code 3 | Abraxas preflight |
| `update` only tightens; loosening needs a human, a reason, and a debt log entry | `update.py`, `PAWL_DEBT.md` | Betterer; Abraxas TEST_DEBT.md |
| Quarantine with an expiry | `pawl quarantine` | Shaker evaluation (flakiness does not reproduce reliably) |
| Existing test lines are read-only; deletions, skips, shadowed tests flagged | `guard.py` | ImpossibleBench, EvilGenie, hacktrace |
| Base-test replay against the new code | `pawl guard --replay` | Baker et al. 2025 |
| Protected gate files, outcome-rewriting hooks, runner config changes | `PROTECTED_CHANGED`, `HOOK_TAMPER`, `TEST_CONFIG_CHANGED` | METR (evaluator monkey-patching) |
| Suspicious code: test-runner detection, `__eq__` always true, stack inspection | `SUSPICIOUS_CODE` | ImpossibleBench, METR |
| Escalation channel that blocks merge until resolved | `pawl escalate`, `ESCALATION_OPEN` | arXiv:2608.29460 |
| "The spec takes priority over the tests" in the agent contract | `integrations/AGENTS.md` | arXiv:2610.04793 |
| Optional holdout suites run only in CI | `ci_only = true` | EvilGenie, UTBoost, SWE-Bench Pro Verified |
| Advisory mutation spot check on changed lines | `pawl mutate` | Meta ACH, SWE-Mutation, arXiv:2607.18057 |
| Harness hooks as early checks; CI required check plus CODEOWNERS as the authority | `pawl hook`, `integrations/` | Claude Code, Codex, Cursor, Hermes docs; GitHub rulesets |

## Considered and not adopted

- **LLM judge as the gate.** Effective in unambiguous cases (EvilGenie) but
  weaker on realistic tasks (ImpossibleBench), costs tokens, and can be gamed
  under optimization (Baker et al.). Pawl's output is a good input to a judge;
  the gate stays deterministic.
- **Chain-of-thought monitoring.** Out of scope for a CI tool and not
  available for most harnesses.
- **Formal conflict certification (SpecGuard).** Promising, but heavy and
  language-specific. Pawl provides the escalation path that such a tool would
  feed.
- **Many reruns to detect flakiness.** Gruber et al. estimate about 170 runs
  for 95% confidence. Pawl uses two orders plus quarantine with an expiry.
