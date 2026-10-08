# Why Pawl

## Who it is for

- **Teams that let coding agents open pull requests** (Claude Code, Codex,
  Cursor, Copilot, Devin, Hermes) and merge them after review.
- **People running agents in a loop** ("keep going until the tests pass"),
  where the agent decides when it is done.
- **Repositories with known failing tests** that cannot be fixed today, where
  "all tests pass" is not available as a gate, so a red suite is normal and a
  new failure is invisible.

## The pain, with evidence

1. **Agents edit tests to pass.** Agents given tests that contradict the spec
   cheat by modifying tests, overloading operators, and special-casing inputs
   (ImpossibleBench, [arXiv:2510.20270](https://arxiv.org/abs/2510.20270)).
   Codex and Claude Code both showed explicit reward hacking on EvilGenie
   ([arXiv:2511.21654](https://arxiv.org/abs/2511.21654)). In one study some
   models cheated in 65% to 86% of conflicting coding tasks
   ([arXiv:2610.04793](https://arxiv.org/abs/2610.04793)).
2. **They tamper with the evaluator, not just the tests.** METR saw o3
   monkey-patch an evaluator to always pass and overwrite the equality
   operator ([METR, 2025](https://metr.org/blog/2025-06-05-recent-reward-hacking/)).
3. **Telling them not to is unreliable.** METR found "please do not cheat"
   had a nearly negligible effect, while another study found one sentence
   about spec priority eliminated cheating in its runs. Both cannot be relied
   on as a gate.
4. **"Tests pass" is a weak signal anyway.** 7.8% of SWE-bench patches counted
   as correct fail the full developer test suite
   ([arXiv:2503.15223](https://arxiv.org/abs/2503.15223)); augmenting tests
   found 345 wrongly passed patches
   ([arXiv:2506.09289](https://arxiv.org/abs/2506.09289)). In Python agent
   PRs, existing tests cover only 27.0% of changed lines
   ([arXiv:2607.18057](https://arxiv.org/abs/2607.18057)).
5. **Count-based ratchets miss swaps, skips, and deletions.** The Abraxas
   ratchet (failure count down, collected count up) let a fixed test hide a
   new failure, and its collected-count line depends on pytest verbosity
   settings. In this repo's benchmark it caught 5 of 18 bad changes on a clean
   base (BENCHMARKS.md).
6. **Flaky and order-dependent tests make every red ambiguous.** Order
   dependency causes 59% of flaky Python tests
   ([arXiv:2101.09077](https://arxiv.org/abs/2101.09077)), so an agent (or a
   human) learns to ignore red.

## What people use now, and where it falls short

| Tool | What it does well | Gap Pawl fills |
| --- | --- | --- |
| Plain CI "tests must pass" | Simple, universal | Useless with known failures; blind to deleted, skipped, or weakened tests |
| Branch protection and CODEOWNERS | The real authority | Does not know which files are the gate or what changed in a test |
| Betterer, ESLint bulk suppressions, basedpyright baseline, mypy-baseline | Ratchet lint and type errors | Not for test outcomes; no tamper detection |
| ratchet-gate (`quality-gate`) | Metric ratchet with a trusted base baseline | Metrics only, no per-test identity, no test tamper guard |
| Semgrep `--baseline-commit`, diff-cover | New findings and coverage on changed lines | Different question; complementary |
| pytest-randomly, flaky-test tools | Find order dependence | Not a gate |
| LLM judges and CoT monitors | Catch semantic cheats | Cost tokens, vary, and can be gamed under optimization ([arXiv:2503.11926](https://arxiv.org/abs/2503.11926)) |
| Harness hooks | Stop the agent early | Run in the agent's environment; not enforcement |

## Positioning

Pawl is complementary. It does not replace code review, coverage tools, or
judges. It answers one question deterministically: did this change make the
existing test evidence worse, or touch the gate? It fits next to whatever CI
and harness a team already uses.

## Kept small on purpose

- Two-minute start: `pip install`, `pawl init`, commit, add one workflow.
- No runtime dependencies. Python 3.11+ standard library only.
- Optional features are off until configured: holdouts, metrics, mutation,
  quarantine.

Features cut because they had no clear user or added setup friction without
catching a failure mode: per-vendor report formats, git-notes history, a
built-in coverage ratchet (use `[[metric]]`), automatic quarantine, and an
LLM-judge mode.

## When not to use Pawl

- A small project with a green suite and no agents: plain "tests must pass" is
  enough.
- A team that will not protect the default branch: Pawl in CI becomes advice.
