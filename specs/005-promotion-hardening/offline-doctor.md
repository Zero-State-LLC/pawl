# T13 offline diagnostic slice

Status: implemented for review, stacked on PR #50. Online provider verification
and live CI readiness remain pending. This is partial T13 delivery, not closure
of A24's complete-online-settings case or R12 operator controls.

## Implemented behavior

The CLI has doctor, JSON output and explicit local/CI/online scopes. Each check
has status, severity, required flag, source, observation time and remediation.
Required failure outranks unknown; required unknown outranks READY. Optional CI
checks do not block a correctly labeled offline-local result.

File reads are bounded to 1 MiB, with verified-descriptor file/link checks.
Baseline JSON nesting is limited to depth 64.
Baseline checks reject duplicate keys/IDs, invalid numeric types, uncollected
outcomes, identity mismatches, missing configured records and metric direction
mismatches. Configured executable files and working directories are inspected
without executing suite/preflight commands or importing project modules.

A requested ref is checked only for availability, not used as a source of config.
Git is resolved from the trusted launcher, not a candidate shim, with network
protocols disabled, external Git config environment removed and a five-second
limit. Doctor writes no reports or project files. It does not invoke a network
provider, even when --online is requested in this partial implementation.

Workflow enumeration is bounded and does not follow links. File presence always
leaves workflow semantics/enforcement UNKNOWN. The five remote review/release
controls stay UNKNOWN until authenticated provider verification exists.

## Evidence and limits

Corpus cases exercise the real CLI for valid configuration, malformed config,
malformed baseline, missing executables and identity mismatch. Tests additionally
cover no project execution/network/mutation, scope and exit semantics, malformed
identity records, duplicate keys, links, local ref absence/timeouts, and candidate
Git shims, malformed recursive config and diagnostic display controls. Existing
test lines are unchanged. Full make check passed: 438 tests, no skips, 89.99%
coverage, lint, formatting and strict typing, with real Go and Rust toolchains.
Baseline and self-gate results are recorded in the PR. Broader effectiveness
scenarios are unchanged and were not rerun. Guard against PR #50 requires
owner review for the two specification authority changes; no override was used.

On this checkout, offline-local inspection returns READY (0), while offline-ci
returns UNKNOWN (2). This is static evidence only. The implementation does not
validate executable contents/versions, test collection, workflow YAML semantics,
remote settings, publisher controls or separation of human/agent credentials.
The earlier intermittent cleanup test remains a documented qualification risk;
sequential passes do not prove its cause was fixed.
