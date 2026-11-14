# T11 report parsing slice

Status: implemented for review, not promotion approval. Base: PR #47.

## Contract

All JUnit, Jest and Vitest report reads use a single verified descriptor, reject
symlinks in any path component, reject hard links and special files, and enforce
a byte budget before decoding. Nonblocking opens prevent FIFO replacement from
hanging the reader. Inode substitution between stat and open fails. Metadata
changes during reading fail. Limits propagate from trusted replay configuration.

XML rejects DTD declarations, limits depth and testcase records before allocation
of each element, and applies a separate element budget. Existing optional failure,
error and skip summaries continue to reconcile against raw XML records.
JSON scans nesting before decoding and rejects nonfinite constants. Jest validates
container shapes and failure count types. Go event and Cargo testcase counts are
bounded before deduplication. JSON metric extraction uses the same byte/depth guard.

Resource errors report REPORT_LIMIT or PARSE_LIMIT and exit 2. Malformed reports
also exit 2, with the existing ParseError contract. No partial result is accepted.

## Verification

New corpus fixtures in benchmarks/corpus.py run through the actual CLI in
 tests/test_report_bounds.py: deep XML, entity declaration, excess duplicate
records, and a valid report. Additional tests cover exact byte boundary, FIFO,
file and parent symlinks, hard links, inode replacement, growth during reading,
UTF-16 DTD, JSON string escaping, invalid counters and policy values, and duplicate
records in each text/JSON adapter. Existing tests remain unchanged.

Full `make check`: 365 passed, no skips, 89.86% coverage; lint, formatting
and strict typing passed with the installed Go and Rust toolchains. The four
new corpus fixtures are part of this run. The broader effectiveness benchmark
was not rerun because its scenario list is unchanged.

Guard against PR #47 blocks only the two specification authority changes, as
expected pending owner review. No approval override was used.

Baseline tightening passed in two test orders: 333 to 362 IDs, all prior IDs
preserved, no loosening or order dependence.

## Limits and remaining work

This is a bounded in-process parser, not a memory sandbox. XML retains a tree
within byte, element and depth budgets. Concurrent same-user forgery is still
possible; metadata checks cannot prove authenticity. An attacker that can escape
the runner's process group remains outside these guarantees. Native Windows is
not qualified. Diagnostic control-character escaping, broader schema consistency,
environment controls, and protected release qualification remain separate work.
