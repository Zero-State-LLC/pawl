# ADR 0002: Additive test edits require structural checks and replay

Status: Proposed 2026-11-13. Supersedes the executable-addition permission in
ADR 0001 only when PAWL-005 is accepted and implemented. No current behavior
changes in this documentation commit.

## Context

An existing test can keep its identity and every original line while added
control flow prevents its assertions from running. The current guard records
replay obligations only when meaningful existing test lines are removed. Thus
the premise that arbitrary additions cannot weaken existing evidence is false.

## Decision

Use one complete changed-file inventory. Schedule every modified existing test
for trusted-base replay in CI. Classify Python additions structurally, allowing
only the limited cases defined in PAWL-005 R02. Other executable additions
require review. Shared fixture, import, binding, or collection changes trigger
full affected-suite replay. Missing or ambiguous replay is an error.

Keep approval separate from measurement: a reviewed policy edit does not make
independent failing tests pass. Preserve narrow legitimate additions, and add
clean corpus cases so the policy's friction is measured rather than guessed.

## Consequences

- Some previously accepted additions will block until reviewed.
- Replay runs more often and may run the full suite; correctness takes priority.
- A structural allowlist is not a proof of Python purity or report authenticity.
- Non-Python edits use conservative review until a tested classifier exists.
- Existing tests and baseline migrations need the repository's protected-file
  review. No automatic evidence reset accompanies this decision.

Implementation, contracts, and acceptance are in
[PAWL-005](../../specs/005-promotion-hardening/spec.md).
