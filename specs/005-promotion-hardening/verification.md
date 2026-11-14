# PAWL-005 specification verification

Date: 2026-11-13 PT. Source baseline:
`bc2fcee9d3d0fec63f129e5e3891347d98a95071`.
This file records specification validation and pre-existing implementation
behavior. It is not implementation acceptance or a release receipt.

## Documentation checks

Local Markdown links, requirement IDs R01-R18, acceptance IDs A01-A34, task
IDs T01-T24, punctuation, and `git diff --check` were validated. Source,
tests, workflows, configuration, and baseline were not modified by this spec.

## Existing code checks in fresh environment

Python 3.12.14; pytest 9.2.0; pytest-cov 7.1.0; ruff 0.17.5; mypy 2.4.1.

| Check | Observed result |
| --- | --- |
| Ruff lint | PASS |
| Ruff format | PASS |
| Mypy strict project configuration | PASS, 23 source files |
| Full pytest from `make check` | 244 passed, 1 failed, 1 skipped |
| Coverage | 88.86%, above configured 80% floor |
| Go failure | Host `/usr/bin/go` is not a working Go compiler; no JSON test events |
| Cargo skip | Cargo absent |

The full check is not green. No test was disabled to conceal the environment
failure. A proper qualification worker must provide actual supported toolchains.

## T01: Controlled test-identity comparison

Run `python -m pytest tests/test_config.py --collect-only -q -p no:cacheprovider`
in the same checkout and interpreter, changing only the pytest package loaded
from a separate temporary target directory. No source edits, baseline updates,
or runtime fuzzy matching were used.

| Pytest | Collection exit | Collected | Missing baseline IDs | Extra IDs |
| --- | --- | --- | --- | --- |
| 9.1.1 | 0 | 13 | 0 | 0 |
| 9.2.0 | 0 | 13 | 1 | 1 |

The changed case is `test_invalid_configs_fail_closed` with the duplicated
MINIMAL configuration and expected message `unique`. Version 9.1.1 includes
the escaped full configuration text in the parameter ID; 9.2.0 emits
`tests/test_config.py::test_invalid_configs_fail_closed[text6-unique]`.

This demonstrates version-dependent collection identity in the installed
packages, not a lost test or a production regression. It does not establish
the exact upstream commit that changed ID generation. Immediate proposal:
pin the known matching qualification toolchain; then introduce stable explicit
parameter IDs with a separately reviewed test/baseline migration. Never use
`--loosen` to hide this mismatch.

The November audit's unconstrained `pawl check --ci` collected 243 tests with
zero failures but correctly failed closed on this missing identity. New run
results, if added below, must retain that distinction.

Follow-up verification during this specification: `pawl check --ci` with
pytest 9.2.0 again failed on that one identity. The same command with pytest
9.1.1 selected in the temporary environment passed: 243 tests, zero failures,
zero ruff findings. No baseline or source edit was needed. This is a diagnostic
environment selection, not a committed dependency constraint or release fix.

`pawl guard --ci --base origin/main` reports eight `SPEC_AUTHORITY_CHANGED`
blocks for the new specification and ADR files. This is expected protected
authority review, not an implementation regression. No approval label or
manual override was applied. The PR must remain a draft pending owner review.

## Core implementation slice, 2026-11-14 UTC

Implementation starts from spec commit `067b907c85a525c32133633e6d14009fb1f814b0`.
Daniel authorized proceeding with implementation in this conversation. This is
not a merge approval, release receipt, or proof of active operator controls.

The slice covers additive-test classification, replay of every changed existing
test, full replay for shared configuration, missing-evidence errors, NUL-safe
Git paths, CI override rejection, malformed approval actors, and pinned dev
dependencies. It adds 25 test cases without editing existing test lines.

Focused integrity/replay/approval tests: 71 passed. Real effectiveness corpus:
Pawl CI caught 23/25 bad clean-baseline changes and 24/26 bad debt-baseline
changes; 0/9 and 0/10 clean changes blocked, respectively. The early-return and
module-binding attacks are caught in both baseline modes. A terminal assertion
addition passes in both. See generated BENCHMARKS.md and benchmarks/results.json.
These are finite corpus results, not general guarantees.

T02's pins preserve existing IDs. A future explicit-ID migration is still
reviewed work. T06's scope here rejects manual CI overrides and prevents
approval from clearing replay regressions or open escalations; the full scoped
approval migration remains open. T07-T08, M2, M3, and M4 remain unimplemented.

`make check` passed: Ruff lint and format, strict Mypy (24 source files),
271 tests, no skips, 90.04% coverage. Environment: Python 3.12.14 and the
committed requirements-dev.txt constraints; real Go 1.27.4 and Rust 1.100.0
were on PATH. The first full run exposed a missing JSON rule description;
that documentation was added before the passing run.

`pawl update --ci --json` recorded a tightening from 243 to 268 unit tests,
confirmed in two orders. All 243 existing IDs remain; 25 were added, none
removed, no failing IDs and no order dependence. No loosening option was used.
Runtime adapters are tested by make check, excluded from the self-gate as in
the unchanged repository configuration.

`pawl guard --ci --base origin/main --json` reports eight authority-review
blocks for the specification/ADR files. No existing tests or runner tool tables
were edited. No approval override was applied. Independent review remains
required before merge.

`pawl check --ci --json`: PASS, 268 collected unit tests, zero failures,
zero missing or unbaselined tests, zero Ruff findings (2026-11-14 03:16 UTC).
This verifies the core slice locally, not the unfinished promotion milestone.
