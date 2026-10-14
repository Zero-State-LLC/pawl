# PAWL-003: Remaining gaps after 0.4.1

Status: ACCEPTED for H1. Date: 2026-10-13. Baseline: PAWL 0.4.1 on main
`69ae87a`, which is tag `v0.4.1`. PyPI `pawl-gate` 0.4.1 serves the wheel
and the sdist. Authority: specs/002-gap-closure/spec.md,
specs/001-trustworthy-agent-gate/spec.md, docs/QA_COMPLETION.md,
docs/REPO_SETTINGS.md, and docs/CI_TRUST_REVIEW.md. This spec does not
change exit codes, problem codes, or `schema_version`.

## Constitution

1. Spec 002 G1, G2, G3, and G4 are closed. This spec does not reopen them.
2. Repository settings stay operator actions. This spec records the live
   2026-10-13 ruleset read. It does not call the settings API.
3. Known misses stay known misses. New passing tests stay a note in this
   spec. Spec 004 accepts `UNBASELINED_TESTS` when the collected count is
   above the baseline.
4. This spec does not change behavior. Spec 004's `UNBASELINED_TESTS` rule
   applies in every repository, including one whose collected count is
   already above its baseline.
5. Dogfood keeps installing the trusted git ref. Pinning dogfood to the
   PyPI artifact is a later decision, because the next commit on main
   would otherwise wait for another release before it could gate.

## Gaps

| ID | Gap | Disposition |
| --- | --- | --- |
| H1 | QA and settings docs still say 0.4.1 is uncut, and that the candidate job holds `pull-requests: write`. Spec 001 still says the scorecard is not accepted. Spec 002 still says G4 is not done | Execute |
| H2 | One account can approve a protected change, merge it, create a `v*` tag, and publish. Ruleset `main` requires 0 approvals. Code-owner review, last-push approval, and strict status checks are off. The `pypi` environment has no reviewer. `[guard] approvers` and `refuse_pr_author` stay commented | Operator. Do not change settings or `pawl.toml` |
| H3 | The suite process inherits the job environment. A same-user regular-file JUnit report is accepted. Symlink and hard-link reports are already rejected | Open. No denylist and no parser change |
| H4 | `spec_docstring_rewrite` and `special_case_no_holdout` remain `known_miss` | Open |
| H5 | New passing tests are a note under `lock_in_ci` | Superseded by specs/004-unbaselined-tests/spec.md |
| H6 | GitHub Actions policy is `allowed_actions: all` and does not require SHA pins. CI `scripts/check_actions.py` still enforces the repo allow-list | Operator |
| H7 | The scorecard has no trend and no separate install, check, replay, and report durations | Open. Do not add fields. The 2026-10-11 report asked for more same-SHA samples first |
| H8 | `pawl doctor`, `pawl explain`, Windows, a larger evaluation, and draft PR #33 | Out of this cut |
| H9 | Dogfood installs a git archive of the trusted ref, not hash-pinned `pawl-gate==0.4.1` | Keep the archive |

## H1: doc truth

- `docs/QA_COMPLETION.md` records that tag `v0.4.1` is `69ae87a` and that
  release run 38483924992 published `pawl-gate` 0.4.1. The operator table
  no longer asks for that tag. The `pypi` reviewer, review rules, and
  Actions allow-list stay open. The checklist marks the 3.11, 3.12, and
  3.13 CI result for `69ae87a` (run 38483692433). Demo, BENCHMARKS
  regeneration, and a full `pawl init --github` in a fresh project stay
  unchecked.
- `docs/REPO_SETTINGS.md` says the gate job is `contents: read` and the
  report job holds `pull-requests: write`. Required approvals, code-owner
  review, last-push approval, and strict checks are still absent.
- Spec 001's scorecard backlog bullet says the point-in-time fields
  shipped in 0.4.1. Trend and split durations stay open.
- Spec 002 records that G4's acceptance condition was met on 2026-10-13.

## Deferred acceptance

H2 and H6 are done when a fresh settings read matches spec 002's G5
acceptance. H5 is accepted by spec 004. H3, H4, and H7 stay open until a
later spec accepts a design. H8 stays in the 0.5.0 and 1.0.0 rows of spec
001. H9 stays the dogfood install in `.github/workflows/pawl.yml`.

## Non-goals

- Enabling `[guard] approvers` while the agent and the code owner share a login.
- A scorecard that fails the build, or a time-series database of CI runs.
- Editing Abraxas.
- Tagging or publishing from this change.
