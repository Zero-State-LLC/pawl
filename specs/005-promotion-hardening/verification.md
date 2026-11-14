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
