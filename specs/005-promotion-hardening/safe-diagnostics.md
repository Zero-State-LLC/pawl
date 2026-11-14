# T11 diagnostic rendering slice

Status: implemented for review, stacked on report-bounds PR #48.

## Behavior

Check and guard Markdown render a copy of the report. Field controls, line
separators, bidirectional formatting controls and surrogate characters become
visible escapes. Markdown delimiters that can break code spans, tables, links
or HTML become numeric character references. Field newlines cannot introduce
report headings or rows. Literal backslashes are distinguished from generated
escape sequences so distinct IDs retain separate isolation lookups. Ordinary Unicode remains readable.

CLI emission also escapes terminal controls on stdout and dynamic hook error
text on stderr. Renderer-owned line breaks remain intact. JSON emission already
escapes controls and remains lossless when decoded. Saved report evidence,
test IDs, baseline comparisons and exit codes are unchanged.

## Verification

The diagnostic corpus includes terminal controls, Markdown breakout, bidirectional
text and ordinary Unicode. Added tests verify check/guard rendering, isolation
lookup preservation, nonmutation of reports, control character classes, lossless
JSON emission, and a real CLI runner error that remains exit 2 with original
error evidence retained in the JSON report.

Full `make check` after the escape-identity fix passed: 381 tests, no skips,
89.95% coverage, lint, formatting and strict typing, with real Go and Rust
toolchains. Existing test
lines are unchanged. The broader effectiveness scenario list is unchanged and
was not rerun. The guard against PR #48 requires owner review only for these
two specification authority changes; no approval override was used.
Baseline and self-gate results are recorded in the pull request.

## Observed qualification instability

The first baseline update, run concurrently with full qualification, reported
order dependence in the existing grandchild pipe-timeout test. No failure
trace was retained by that update command. The complete runner suite then passed
34 tests; the affected test passed 20 isolated repetitions. An isolated two-order
update passed without a waiver. The cause remains unproven. This observation is
retained as a qualification risk, not claimed as a fixed runner bug. Subsequent
qualification jobs run sequentially. No existing test or timeout was changed.

## Boundaries

This prevents display interpretation of the covered control and markup characters.
It does not authenticate prose, stop misleading test names, redact secrets, or
sanitize Markdown files written by other tools. Consumers that decode raw JSON
must escape fields for their own display context. Raw hook reason values remain
machine data. CLI argparse usage errors and external subprocesses with their own
output surfaces are outside this renderer. Protected review and release
qualification remain open; this is not permission to promote Pawl.
