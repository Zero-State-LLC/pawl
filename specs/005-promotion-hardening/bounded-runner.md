# T10: bounded command execution

The shared runner now streams stdout and stderr with one byte budget, counted
before decoding. It returns complete output within that budget or raises an
error; output exceeding the limit is never truncated into a passing result.
Failure excerpts are separately bounded to roughly 4 KiB of text.

## Configuration

```toml
[execution]
max_output_bytes = 8388608
terminate_grace_seconds = 5
```

These defaults apply to existing configs too. Output is bounded across both
streams combined, not separately. The allowed byte range is 65536..67108864;
cleanup grace is a finite number from 0 to 30 seconds. Boolean values are not
numbers here. Suite/metric timeouts must be finite positive numbers. Invalid
limits fail before measurement. A legitimate project with larger output must
reduce verbosity or review an explicit budget increase in trusted policy.

Parsed limits reach every adapter, isolated Go reruns, metric commands,
preflight imports/commands, and trusted test replay. Unapproved head policy
cannot raise a limit read from the trusted base. Candidate environment
inheritance is unchanged; T12's minimal mode is not implemented by this slice.

Only these two execution-table fields are implemented here. Report-size,
record/depth limits, environment policy and per-suite tightening are separate
remaining work. Git helper subprocesses also remain outside this shared
runner and need their own bounded-command audit.

## Lifecycle and errors

On POSIX, each command starts in a new session with noninteractive stdin.
Stdout and stderr are drained concurrently. The deadline applies even if the
direct child exits while a grandchild holds a pipe, or if a child closes both
pipes but keeps running. Timeout, output excess or a Python interruption
triggers group SIGTERM, a bounded direct-child wait, then group SIGKILL and a
bounded final wait. The direct child is reaped and capture handles are closed.
Normal completion also cleans up any remaining members of its process group.

The parent cannot reap grandchildren it does not own; the host reaper owns
that job. The tests distinguish live processes from non-child zombies. A
descendant that changes session/group can escape this boundary. Process groups
are not a sandbox, a memory limit or a guarantee against host/process crashes.
Native Windows execution is rejected as unqualified rather than silently
using an unbounded fallback. The implementation is verified on Linux only.

Structured check/guard reports expose typed `error_code` values including
`OUTPUT_LIMIT`, `RUN_TIMEOUT`, `RUN_INTERRUPTED`, `RUN_IO_FAILED`,
`RUN_START_FAILED`, `TERMINATION_UNCERTAIN`, `INVALID_EXECUTION_POLICY` and
`UNSUPPORTED_PLATFORM` when available. They are errors, exit 2. Cleanup
uncertainty overrides a putative success. No raw output is included in output
limit diagnostics.

Replay does not retry a resource failure as a wider run. Replay worktrees are
cleaned in `finally`, including failed preparation; cleanup failure is itself
an error rather than ignored. This does not complete all hostile Git lifecycle
or signal-handling cases required for full M2 qualification.

## Acceptance evidence

Tests cover exact combined byte budgets, stdout/stderr floods, invalid UTF-8,
bounded diagnostics, direct-child reaping, a grandchild holding pipes and
ignoring SIGTERM, closed pipes with a live child, Python interruption, signaling
failure, unsupported platforms, malformed configuration, all measurement
paths, structured CLI errors, trusted policy, replay timeout and cleanup error.
The corpus includes a metric flood attack and a clean bounded diagnostic.

This is the command-execution part of R09 and T10. T11 report parsing, T12
environment control, external isolation and release qualification remain open.

## Verified implementation checkpoint

2026-11-13 Pacific Time. Base: PR #46 at
`59cdf4294a48643316073180d50f0fcf32f95f30`. No existing test lines or live
runner configuration were edited.

Make check passes: 336 tests, no skips, 89.71% coverage; Ruff lint/format and
strict Mypy pass. Real Go and Rust toolchains were present. Thirty-four new
test cases were added. The tightening workflow recorded 299 -> 333 unit tests
in two orders, with no removed old IDs, failures or order dependence.

The real CLI corpus catches the output-flood attack in clean/debt modes and
accepts the bounded diagnostic in both. Overall CI catches 25/27 and 26/28
bad changes with zero false positives among 11 and 12 clean changes. The two
pre-existing known misses remain. These finite corpus results do not establish
a sandbox or a universal regression-detection guarantee.

Guard against PR #46 reports only two authority-review blocks for this document
and the task queue. No approval override or live reviewer setting was applied.

Final pawl check --ci: PASS with 333 collected unit tests, no missing or
unbaselined IDs, zero failures and zero Ruff findings. The three runtime
adapter tests are covered by make check under the unchanged self-gate policy.
