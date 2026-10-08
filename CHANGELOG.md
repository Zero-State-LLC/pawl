# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-08

### Added

- `pawl check`: per-test-ID ratchet with a collected floor, multi-order runs,
  isolation annotation, metrics, holdout suites (`ci_only`), quarantine with
  expiry, and fail-closed parsing. Exit codes 0, 1, 2, and 3.
- `pawl check --trusted-ref`: loads the config and baseline from the base
  branch and applies the stricter of the two baselines.
- `pawl update`: tightening is free; loosening needs `--loosen --reason` and is
  written to the append-only debt log. Baselines must agree under two orders.
- `pawl guard`: diff guard for gate files, test deletions and edits, new skips,
  shadowed tests, hook tampering, runner config changes, suspicious code, debt
  log rewrites, and escalations, plus `--replay` of the base tests.
- `pawl report`, `pawl init` (runner auto-detection), `pawl quarantine`,
  `pawl escalate`, and `pawl mutate`.
- `pawl hook stop` and `pawl hook protect` for Claude Code, Codex, Cursor, and
  Hermes, with a block cap and trusted-base mode.
- Adapters: pytest, Jest, Vitest, `go test -json`, `cargo test`, and JUnit XML.
- Integrations for GitHub Actions, pre-commit, Claude Code, Codex, Cursor,
  Hermes, and an `AGENTS.md` contract.
- Benchmarks (`python -m benchmarks run`) for effectiveness and performance,
  and a live-agent trial (`python -m benchmarks.live_trial`).
- The agent contract says to finish the possible work before escalating, based
  on the live trial.

[Unreleased]: https://github.com/Zero-State-LLC/pawl/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Zero-State-LLC/pawl/releases/tag/v0.1.0
