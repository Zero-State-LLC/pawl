# QA and completion recommendations (post-0.4.0)

Date: 2026-10-10. Scope: local QA of
[Zero-State-LLC/pawl](https://github.com/Zero-State-LLC/pawl) after 0.4.0,
plus hardening that still belonged with the trust cut.

This is an engineering readiness note. It does not publish a release, change
repository settings, or claim P0 isolation is finished.

## Verdict

**0.4.0 is tagged; this branch closes remaining hardening gaps.** Contracts,
approval provenance, runner-evidence hardening, move detection, hook
provenance, and narrowed replay are present. QA still found a portable-init
PATH bug, linked-report forgery, customer-workflow trust drift, and stale
support metadata.

This branch closes those, regenerates corpus receipts for a marked-contract
catch (Pawl CI 21/23 debt, 0 false blocks), and leaves PyPI environment
reviewers / branch-protection work to operators.

## QA results (this environment)

| Check | Result |
| --- | --- |
| `ruff check` / `ruff format --check` | Pass |
| `mypy --strict` on `src/pawl` | Pass |
| `pytest --cov=pawl` | 235 passed |
| Coverage | About 89% (floor 80%) |
| `examples/run_demo.sh` | Pass including `SPEC_AUTHORITY_CHANGED` |
| Effectiveness (debt) | Pawl CI 21/23; only known misses remain |
| Open GitHub issues | None at inspection |

### Bug found in QA

`pawl init --runner pytest` wrote `command = ["python", "-m", "pytest", ...]`
and `preflight.python = "python"`. On hosts that only provide `python3`,
baseline measurement failed with exit 2 (`command not found: python`). Fixed
by writing `sys.executable`.

## What this branch completed

1. Linked-report rejection in `parse_junit`
2. Customer workflow trust parity (split report job)
3. Portable init via `sys.executable`
4. Demo step 5 + corpus `marked_contract_rewrite`
5. `SECURITY.md` support table for 0.3.x
6. Regenerated `BENCHMARKS.md` / effectiveness receipts
7. Public README doc links; CI trust completion update

## Update 2026-10-13

PyPI `pawl-gate` 0.4.0 is published. Release workflow runs for v0.3.0
(38087063957) and v0.4.0 (38091969331) succeeded. The symlink and hard-link
rejection, the split customer workflow, and `sys.executable` in `pawl init`
are on main and are not in the 0.4.0 tag. Cutting 0.4.1 is still an operator
step. Gap dispositions are in
[specs/002-gap-closure/spec.md](../specs/002-gap-closure/spec.md).

## Remaining operator work

| # | Action |
| --- | --- |
| 1 | Tag and publish `pawl-gate` 0.4.1 from main so the post-0.4.0 hardening ships. 0.4.0 is already on PyPI |
| 2 | Add reviewer on the `pypi` environment |
| 3 | Require 1 approval + code owners + last-push + strict up-to-date |
| 4 | Action allow-list + SHA pinning enforcement |
| 5 | Uncomment `[guard] approvers` / `refuse_pr_author` when the agent has a distinct account |

## Honest residual risk

Unmarked normative docstrings; same-user forged regular-file reports;
credential inheritance into the candidate runner; Windows untested. Do not
overclaim P0 isolation.

## Suggested checklist

```text
[ ] make check green on 3.11, 3.12, 3.13
[ ] make demo green
[ ] BENCHMARKS.md current
[x] PyPI 0.4.0 published (v0.3.0 and v0.4.0 release runs succeeded)
[ ] Tag and publish 0.4.1; pypi environment has a human reviewer
[ ] repo rules: approvals + code owners + strict checks + action pins
[ ] smoke: fresh repo -> pip install pawl-gate==0.4.1 -> pawl init --github
```
