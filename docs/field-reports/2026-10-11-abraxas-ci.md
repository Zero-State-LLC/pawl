# Field report: Pawl CI on Zero-State-LLC/Abraxas (2026-10-11)

Status: OBSERVED. Source: Danny, 2026-10-11 PT. Every number below was
re-checked against the GitHub Actions job metadata and logs for the three runs
(`gh run view --json jobs`, the jobs API for step timestamps, and the job logs).
No mismatches were found. Durations are computed from second-resolution
GitHub timestamps, so each can be off by about 1s.

## Runs

| Run | PR | Head SHA | Job conclusion | Pawl job |
| --- | --- | --- | --- | --- |
| [38134043760](https://github.com/Zero-State-LLC/Abraxas/actions/runs/38134043760) | #292 | `c38eae5f4d42a22e10f40cc19b777971b3f4d51b` | success | 257s |
| [38175330016](https://github.com/Zero-State-LLC/Abraxas/actions/runs/38175330016) | #293 (first) | `514e8d4d437decd6251dd4f13c4f2cd8610dbd2f` | failure (guard block) | 374s |
| [38178397925](https://github.com/Zero-State-LLC/Abraxas/actions/runs/38178397925) | #293 (repeat, same SHA) | `514e8d4d437decd6251dd4f13c4f2cd8610dbd2f` | failure (guard block) | 375s |

## Test inventory

All three runs report the same `core` suite row:

| Suite | Failures (baseline) | Collected (floor) |
| --- | --- | --- |
| core | 0 (0) | 4136 (3818) |

Each run notes `core: 318 new test(s) are not yet in the baseline`. That is
7.69% of the 4,136 collected tests, stable across all three runs.

## Runtime by step

| Step | #292 | #293 first | #293 repeat |
| --- | --- | --- | --- |
| Install the project | 90s | 94s | 94s |
| Pawl check (gate definition from the base branch) | 157s | 268s | 270s |
| Pawl guard (tamper detection and test replay) | <1s | <1s | <1s |
| Whole Pawl job | 257s | 374s | 375s |

- Same-SHA repeat on #293: `Pawl check` differs by 2s (0.74%).
- `Pawl check` on #293 averages 269s, 112s slower than #292.
- Project install is steady at 90 to 94s.

## Guard outcomes

- #292: `No tampering found.`
- #293 (both runs): `PROTECTED_CHANGED (block) .github/workflows/ci.yml:
  protected gate file modified`. This is the designed behavior for an
  unapproved edit to a protected workflow.
- No completed run with the `pawl-approved` label exists yet, so the
  authorized-label path is not measured.

## Interpretation

- The timing points to the `Pawl check` stage as the profiling target. It does
  not establish the cause of the #293 slowdown; the cause is UNKNOWN (the two
  PRs differ in content, so the difference may come from the project, not Pawl).
- Gather more same-SHA samples before optimizing.
- The Abraxas baseline and Pawl config were left unchanged.

## Recommended scorecard metrics (proposed)

Recorded as a backlog item in
[specs/001-trustworthy-agent-gate/spec.md](../../specs/001-trustworthy-agent-gate/spec.md):

- Unbaselined test count and rate, with trend across runs.
- Separate durations for install, collection/test execution, replay and
  reporting.
- Guard findings by rule and path, plus approval source and SHA.
