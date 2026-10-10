# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - TBD

Protected normative contracts, approval provenance, and runner-evidence
hardening. 0.3.0 also contains everything prepared for 0.2.1, which was never
published: 0.2.0 is followed directly by 0.3.0.

### Exit codes

Exit codes stay 0 (pass), 1 (block), 2 (indeterminate), 3 (preflight error).
What changed: malformed or inconsistent runner evidence (unknown JUnit roots,
empty testcase names, summaries that disagree with cases, abnormal pytest
exits, exit 5 with cases) is now rejected and exits 2 instead of being
measured, so a pipeline that relied on such a report passing will now see
exit 2. Measurable suppression (missing tests, collection drop, newly
skipped) still blocks with exit 1. A changed protected contract blocks with
exit 1 (`SPEC_AUTHORITY_CHANGED`).

### Added

- Protected contracts: files matching `[guard] contracts` (default
  `specs/**`, `docs/requirements/**`, `docs/adr/**`, `contracts/**`; plus
  `extra_contracts`), docstrings with a `pawl: contract` line, and entries in
  `pawl.contracts.json` are normative. Adds the contract registry (stored by
  SHA-256, protected by default), the `pawl contracts update|show` command,
  and the `SPEC_AUTHORITY_CHANGED` finding, which blocks until a human
  approves that exact commit. A regression test covers the live-trial
  docstring rewrite. This repo commits its own registry.
- Approval provenance: the actor, event, run, and PR are recorded in a new
  `approval_provenance` report field. A label event with no sender, a bot
  sender, or an actor outside `[guard] approvers` never approves; label
  removal is recorded as revocation. The `approval` object is unchanged.
- `[guard] refuse_pr_author` refuses an approval label applied by the pull
  request author. `approvers` and `refuse_pr_author` are read from the trusted
  base config only; this repo ships both commented out until the agent has
  its own account.
- The performance benchmark measures a 20000-test suite by default.

### Hardening

- Reject JUnit reports with unknown roots, empty testcase names, or failure,
  error and skip summaries inconsistent with the XML cases. Reject abnormal
  pytest exits and exit 5 paired with test cases. Preserve optional summaries,
  real empty collection, and duplicate teardown records.
- Add labeled attack/clean fixtures, a reproduction of the live-trial spec
  docstring rewrite, and bounded CI trust probes.
- Record the CI permission matrix, settings blockers and receipt proposal in
  [the P0 trust review](docs/CI_TRUST_REVIEW.md). No isolation, merge, release,
  workflow or repository-settings changes are claimed.

### Changed

- `pawl guard --replay` replays only the changed test files when every changed
  test path is a pytest test file that the base baseline attributes to a
  pytest suite with ID identity. Otherwise it replays the whole suite, as
  before. A narrowed replay that fails or finds a weakened test is re-run in
  full, so a finding never rests on the narrowed run alone. The replay note
  says which scope ran.
- The Pawl baseline for this repo protects 197 tests (was 97).
- This repo's CI runs on GitHub-hosted ubuntu-latest; a macOS run on the
  self-hosted Mac is optional and manual. The Pawl report is posted by a
  separate job, and workflow actions must be SHA-pinned and allow-listed.

### Documentation

- Windows is documented as untested.
- ADR-0001: added asserts inside an existing test are allowed.

### Known gaps

- Unmarked docstrings are not protected. A docstring that states a contract
  but has no `pawl: contract` line (the original live-trial `parse_duration`
  rewrite, 3601 to 3660 seconds) still passes the default policy. Mark such
  docstrings, or list the file in `[guard] extra_contracts`.
- A moved or renamed contract file blocks as a delete plus an add; move
  detection is on the backlog.

## [0.2.0] - 2026-10-08

Closes the findings of the 2026-10-08 architecture review (F1, F2, F3, F5,
the report exit code, and the workflow supply chain). Each reproduced bug has
a regression test in `tests/test_regressions.py`.

### Security

- The approval label counts only for the commit it was applied at. A label
  left on a pull request no longer approves later pushes; re-apply it after
  the last push. Reports print the approved commit. (F5)
- The baseline guard flags every baseline edit as a protected change, compares
  quarantine entries whole (extending an expiry or changing a reason is a
  loosening), treats unknown metric fields and a lower `confirmed_orders` as
  loosening, and the 30-day quarantine maximum is enforced whenever a baseline
  is read, not only when `pawl quarantine` writes it (an error for `check` and
  `update`, a `BASELINE_LOOSENED` block for `guard`). `stricter()` keeps the
  earlier quarantine expiry. (F3)
- One trust module (`pawl/trust.py`) resolves the gate definition for `check`,
  `guard`, and `hook stop`. The trusted config is read at the Pawl root's path
  inside the repository (subdirectory roots work), and a base ref without a
  config is refused unless the change is approved or `--bootstrap` is passed;
  in that case only the default `pawl-approved` label counts, never a label
  named by the branch's own config. Check and guard reports print where the
  gate came from. (F2)
- `pawl hook protect` resolves `..` and symlinks before matching protected
  paths.
- The workflow written by `pawl init --github` installs Pawl first, into its
  own virtual environment, hash-pinned (`--require-hashes --no-deps
  --only-binary :all:`), at the version of the Pawl that wrote it, and calls it
  by absolute path. `init` reads the hashes from PyPI, or takes
  `--wheel-sha256` and `--sdist-sha256`.

### Changed

- Metrics fail closed: a metric command that exits outside `ok_exit_codes`
  (default `[0]`) is an error (exit 2), never a value, including for
  `count-regex` and `count-lines`. New metric keys `ok_exit_codes`, `cwd`, and
  `tolerance` (finite, >= 0). (F1)
- `pawl mutate` with a subdirectory `--root` only mutates files under that
  root, and matches test patterns relative to it.
- JSON reports carry `schema_version` (1), `kind`, and `exit_code`. The exit
  codes and problem codes are documented as a stable contract in
  `docs/JSON.md`.

### Added

- `pawl report --exit-status` exits with the worst exit code of the reports it
  read (plain `pawl report` still exits 0). `report --format json` adds
  `worst_exit_code`.
- `pawl update --json`.
- `--bootstrap` for `pawl check` and `pawl guard`.

## [0.1.1] - 2026-10-08

### Changed

- README rewritten for PyPI readers: install with `pip install pawl-gate`,
  absolute links only, and no references to files that are not in the
  package. The source repository is not public; access is on request.
- Package metadata: the project URL is now the PyPI page, because the
  GitHub Source and Issues URLs are not reachable by the public.
- The workflow written by `pawl init --github` (and
  `integrations/github/pawl.yml`) installs `pawl-gate==0.1.1` from PyPI
  instead of `git+https` from the private repository, so it works without
  credentials. `docs/RECOMMENDATION.md` uses the same install line.

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

[Unreleased]: https://github.com/Zero-State-LLC/pawl/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Zero-State-LLC/pawl/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Zero-State-LLC/pawl/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Zero-State-LLC/pawl/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Zero-State-LLC/pawl/tree/v0.1.0
