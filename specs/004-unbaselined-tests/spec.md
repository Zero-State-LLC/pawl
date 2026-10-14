# PAWL-004: Collected tests outside the baseline fail the check

Status: ACCEPTED. Date: 2026-10-13. Baseline: main `e7e9854`, two commits
ahead of tag `v0.4.1` (`69ae87a`). PyPI `pawl-gate` 0.4.1 stays the published
artifact. This spec does not tag or publish. Authority:
specs/003-remaining-gaps/spec.md H5, specs/002-gap-closure/spec.md G8, and
the product rule that Pawl gives the same verdict in every repository.

## Constitution

1. The verdict does not depend on which repository runs Pawl. There is no
   rate threshold and no per-repository exception.
2. `schema_version` stays 1. Exit codes stay 0, 1, 2, and 3. The scorecard
   stays informational.
3. `pawl update` is how a new collected test enters the baseline. Loosening
   stays human-only.
4. This spec does not change replay, `NEW_FAILURE` isolation, workflow
   concurrency, the suite environment, or GitHub settings.
5. Abraxas is not edited. A repository whose collected count is already
   above its baseline goes red on the next Pawl that includes this rule,
   until `pawl update` records those tests.

## Rule

`UNBASELINED_TESTS` is a problem when a suite collects more tests than its
baseline records. It is a problem on a local check and in CI. `lock_in_ci`
does not gate it.

When `identity` is `ids`, the problem lists the collected ids that are
absent from `collected_ids`. When `identity` is `count`, the problem carries
the count delta and an empty id list. Count mode still cannot see an id
swap that keeps the same count. That limit is unchanged
(`test_swapped_failure_passes_in_count_mode`).

A one-for-one replacement keeps the same count. The baseline id that was
not collected is already `MISSING_TESTS`, so the check fails. This rule
does not add a second code in that case.
`tests/test_check.py::test_deleted_test_replaced_by_new_one_is_caught` stays
as written.

`pawl update` on the change records the new ids. CI uses the stricter of
the base and head baselines, so the recorded ids stay protected and a head
baseline cannot drop a base id.

## Corpus

- `add_passing_test` is a bad scenario: a new passing test with no
  `pawl update`.
- `add_passing_test_updated` is the clean scenario: the same addition after
  `pawl update`.
- `feature_plus_test`, `metric_within_tolerance`, and `metric_clean_change`
  record their new tests with `pawl update`, so ordinary work stays clean.

## Non-goals

- A second confirmation run of `NEW_FAILURE`.
- Collapsing a replay finding that restates `NEW_FAILURE`.
- Changing `cancel-in-progress` on the published workflow.
- Tuning parsers or timers.
- Editing Abraxas, tagging, or publishing.
