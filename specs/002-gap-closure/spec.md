# PAWL-002: Gap closure after the 2026-10-13 review

Status: ACCEPTED for G1, G2, and G3. Date: 2026-10-13. Baseline: PAWL 0.4.0
on main `05d0df6`, which is ahead of tag `v0.4.0`.
Authority: DESIGN.md, AGENTS.md, docs/ARCHITECTURE_REVIEW.md,
docs/CI_TRUST_REVIEW.md, docs/field-reports/2026-10-11-abraxas-ci.md, and
specs/001-trustworthy-agent-gate/spec.md. This spec does not change exit
codes, problem codes, or `schema_version`.

## Constitution

1. A required Pawl check is authoritative only when the gate binary is not
   the candidate tree.
2. New report fields are additive on `schema_version` 1. They do not change
   pass, fail, or indeterminate.
3. Repository settings, tags, and PyPI publishes are operator actions. This
   spec records them. It does not perform them.
4. Known misses stay known misses until a separate accepted design changes
   the default policy.
5. A behavior change that would turn current Abraxas pull requests red is
   not part of this cut.

## Gaps

| ID | Gap | Disposition |
| --- | --- | --- |
| G1 | Dogfood `.github/workflows/pawl.yml` installs the pull request with `pip install -e ".[dev]"`, so the required `pawl` check is the candidate's own Pawl | Execute |
| G2 | Check and guard JSON omit the point-in-time scorecard from the 2026-10-11 Abraxas field report | Execute. Fields only |
| G3 | QA and trust docs still describe PyPI 0.3.0, an unrun release workflow, and the 2026-10-10 job shape as current | Execute |
| G4 | Tag `v0.4.0` and PyPI 0.4.0 do not contain the post-tag hardening on main: symlink and hard-link report rejection, the split customer workflow, and `sys.executable` in `pawl init` | Operator cuts 0.4.1. Do not tag or publish here |
| G5 | Ruleset `main` (24762283) requires zero approvals. Code-owner review, last-push approval, and strict status checks are off. Actions policy is `allowed_actions: all` with SHA pinning not required. The `pypi` environment has a branch policy and no reviewer. `[guard] approvers` and `refuse_pr_author` stay commented because the agent account is the code owner | Operator settings. Do not call the GitHub settings API |
| G6 | A same-user regular-file JUnit report is accepted. The candidate process inherits the job environment, including credentials. A venv does not sandbox the runner | Open. No environment denylist: a customer suite may need those variables. Isolation is a runner policy, not a Pawl scrub |
| G7 | `spec_docstring_rewrite` and `special_case_no_holdout` remain `known_miss` | Open. Do not block unmarked docstrings or invent holdouts |
| G8 | New passing tests are a note. `lock_in_ci` raises `STALE_BASELINE` for fixed failures and improved metrics only. On 2026-10-11 Abraxas reported 318 of 4136 `core` tests (7.69%) not in the baseline, stable across three runs | Open. Turning that note into a failure would make those pull requests red. Needs a separate acceptance |
| G9 | `pawl doctor`, `pawl explain`, Windows, an evaluation larger than the 12-episode trial, and draft PR #33 (Databricks scaffold) | Out of this cut |

## G1: trusted dogfood binary

The customer template installs hash-pinned `pawl-gate` into its own venv and
calls it by absolute path. Dogfood cannot use that pin until 0.4.1 is
published, because PyPI 0.4.0 is behind main.

On `pull_request`, the `pawl` job archives `pyproject.toml`, `README.md`,
`LICENSE`, and `src/pawl` from `origin/$BASE_REF` and installs that tree
into `$RUNNER_TEMP/pawl-venv`. On a `push` to `main`, it archives `HEAD`.
It then installs the candidate checkout with `pip install -e ".[dev]"` into
the job venv, so `python -m pytest` and `ruff` are the candidate's tools.
Check, guard, and report call `$PAWL` from the trusted venv.

Acceptance:

- The workflow file no longer invokes a bare `pawl` from the candidate install.
- `integrations/github/pawl.yml` and `src/pawl/templates.py` stay unchanged.
- The two venvs are separate, so a candidate `pip install` cannot replace
  the gate console script that the job executes.

The workflow file is a protected gate path. Merging needs the
`pawl-approved` label on that commit. This spec does not apply the label.

## G2: scorecard

`pawl check` JSON gains `scorecard`:

| Field | Meaning |
| --- | --- |
| `unbaselined_tests` | Sum over suite summaries of `max(0, collected - baseline_collected)` |
| `unbaselined_rate` | `unbaselined_tests / collected` across those suites, or `0.0` when collected is 0 |
| `suite_seconds` | Map of suite name to the existing `seconds` value |

`pawl guard` JSON gains `scorecard`:

| Field | Meaning |
| --- | --- |
| `findings` | `{rule, severity, path}` for each finding, in order |
| `approval_source` | `approval.source`, or null |
| `approval_sha` | `approval.sha`, or null |

Install duration and replay duration are not in this object. Install is a
workflow step. Replay time is not measured. A trend across runs is not
stored. The 2026-10-11 field report asked for more same-SHA samples before
any optimization, and this cut does not optimize.

Acceptance: `tests/test_scorecard.py` builds a `Report` and a `GuardReport`
in memory and reads these fields. Exit codes stay 0, 1, 2, and 3.

## G3: doc truth

- `docs/QA_COMPLETION.md` names PyPI `pawl-gate` 0.4.0 as published and
  records that the v0.3.0 and v0.4.0 release workflow runs succeeded.
  Post-tag hardening is described as on main and absent from the 0.4.0
  artifact.
- `docs/CI_TRUST_REVIEW.md` states that the permission matrix is the
  2026-10-10 snapshot. The historical rows stay as written.
- The `release.yml` header no longer says the workflow has not been run
  end to end.

## Deferred acceptance

G4 is done when a `v0.4.1` tag points at a main commit that contains the
post-0.4.0 hardening and `pypi.org/pypi/pawl-gate/json` reports 0.4.1.
G5 is done when a fresh ruleset read shows one required approval, code-owner
review, last-push approval, strict status checks, an Actions allow-list with
SHA pinning required, and a human reviewer on `pypi`. G6, G7, and G8 stay
open until a later spec accepts a design. G9 stays in the 0.5.0 and 1.0.0
rows of spec 001.

## Non-goals

- Claiming the P0 trust review is closed.
- Editing Abraxas baselines or config.
- Enabling `[guard] approvers` while the agent and the code owner share a login.
- A scorecard that fails the build, or a time-series database of CI runs.
