# PAWL-005 design decisions

These are proposed engineering decisions selected to make implementation
concrete. They are not records of separate user approval, deployed behavior,
or operator settings. Approval of the spec accepts them prospectively.

| ID | Decision | Reason / alternative rejected | Activation |
| --- | --- | --- | --- |
| D01 | Replay all modified existing tests, regardless of diff direction | Added lines can disable execution; checking only removed lines is incomplete | T05 |
| D02 | Permit only structurally bounded additions automatically; review other executable changes | A small list of suspicious strings is not a safe additive-edit policy | T04; supersedes ADR 0001's arbitrary-new-lines permission |
| D03 | Use conservative review when a language lacks a reliable classifier | Do not market heuristic parity across adapters | T04 |
| D04 | Resolve project Python from portable config; never default to author-machine absolute path | Host-local success is not transferable setup | T07 |
| D05 | Explicit IDs and reviewed migration, not fuzzy runtime identity matching | Fuzzy matching can hide a removed or replaced test | T01/T02 |
| D06 | Retain inherited environment for existing configs; offer explicit minimal mode | Existing suites may require variables; a silent denylist would break them without making a sandbox | T12; extends spec 002 G6/003 H3 |
| D07 | Keep report v1 for additive fields; version mandatory semantic changes separately | Preserve consumers without pretending incompatible meanings are additive | Each contract change |
| D08 | CI manual approval flags cannot replace independent authorization | A local convenience is not review evidence | T06 |
| D09 | Doctor reports scoped verified/failed/unknown checks and performs no implicit execution | File presence and API denial cannot prove readiness | T13 |
| D10 | Build once, test those exact bytes, publish separately | Rebuilding after qualification changes the artifact being trusted | T15 |
| D11 | No CI outcome cache and no independent miniature benchmark detector | Age/count do not establish unchanged behavior; evaluate the shipped implementation | T21 |
| D12 | Isolated controller proves boundary/provenance, not arbitrary runner truth | Signing a forged report does not make its contents true | T22-T24 |
| D13 | No new hosted platform, database, or runtime dependency | Correctness and onboarding have higher value than infrastructure for this release | All milestones |

## Resolved scope conflicts

Spec 001's old version roadmap is historical, not a list of shipped features.
Pawl 0.5.0 does not thereby include doctor or incremental checking. Specs 002
and 003 deferred environment, operator, and diagnostics work; this packet
defines new work without claiming those deferrals were previously completed.
Spec 004's per-repository-identical unbaselined-test behavior is unchanged.

ADR 0001 states that new asserts and new lines are allowed. The new rule is
narrower and applies only after implementation/review. Its history stays
intact. Existing tests that encode the former behavior must be identified,
reported, and amended through owner review rather than silently rewritten.

The current report of regular-file forgery remains an open limit. No receipt,
hash, environment allowlist, or venv in this plan closes it by declaration.

## Operator inputs not needed to write core code

| Decision | Default proposal | Needed by | If unresolved |
| --- | --- | --- | --- |
| Independent reviewer and distinct agent identity | Separate least-privilege agent and human reviewer accounts | T14 | Core work proceeds; promotion held |
| Release version and supported adapter/platform matrix | Conservative Linux/Python 3.11-3.13 claims, actual adapter toolchains required | T15/T18 | Do not advertise untested platforms |
| Available repository/organization enforcement features | Read effective rules; document real controls, no assumed plan features | T14 | UNKNOWN control stays visible |
| Isolated worker runtime | Choose only after capability/threat tests, no vendor assumed | T22 | M4 not active; core operation remains available |
| Pilot repositories/users | Small voluntary early-adopter group after qualification | T18 | No outreach or external adoption changes |

No cost, paid service, schedule, account provisioning, or communication to
others is committed by these defaults. Evidence-backed implementation choices
that do not alter policy may be made by the implementing engineer.
