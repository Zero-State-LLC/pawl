# ADR 0001: Added asserts allowed

Status: Accepted 2026-10-10

## Context

`docs/ARCHITECTURE_REVIEW.md` left open whether `TEST_MODIFIED` should block
pure additions inside an existing test function. Adding asserts only tightens
an oracle, so a blanket block on any change to a test file would reject work
that cannot hide a regression. Spec PAWL-001 asks that open questions answered
by evidence be recorded as ADRs.

## Decision

`TEST_MODIFIED` allows pure additions inside an existing test function: new
asserts and new lines. Only removed or changed existing lines block.

## Consequences

- An agent can add weak asserts that do not loosen anything.
- Removing or rewriting an existing line still blocks.
- Revisit only with measured evidence.
