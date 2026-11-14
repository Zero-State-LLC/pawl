# PAWL-005 acceptance and evidence plan

Every case below runs against the implementation, with frozen fixture inputs
and expected results. Synthetic attack details remain in local/private review
until the correction is ready, following SECURITY.md. Do not score the current
implementation as successful because it documents a miss.

## Test rules

- Unit tests validate contracts; real CLI subprocess scenarios validate safety.
- Run candidate code only in disposable fixtures, using synthetic secrets.
- Do not change existing test assertions to make a patch pass. Escalate a
  genuine conflict with the relevant requirement and proposed amendment.
- A new detection rule needs both attack and clean corpus cases.
- Test standard trusted-ref check AND CI replay guard. Isolated helper tests
  do not establish end-to-end correctness.
- Qualification artifacts record source SHA, versions, command, actual exit,
  expected exit, rule IDs, report digest, and duration. No estimated pass counts.

## Required scenarios

| ID | Given / action | Required oracle | Requirements |
| --- | --- | --- | --- |
| A01 | Existing test gains an early exit; code now violates its original assertion | Guard blocks `TEST_EXECUTION_CHANGED`; original test replay detects regression; no combined PASS | R01-R03 |
| A02 | Added decorator, fixture, assignment, alias, or module binding disables assertions without deleted lines | Review block and full affected-suite replay; expected result fixed per fixture | R02-R03 |
| A03 | Added terminal restricted assertion; originals and production code unchanged | Structural allow; replay completes; no false block | R01-R02 |
| A04 | New independent top-level test and reviewed tighter baseline | Pass when all original evidence and new test pass | R02,R07 |
| A05 | Comment/whitespace-only edit and normal README edit | No execution-change block; contract-marked prose still follows contract rules | R02 |
| A06 | Original tests need shared fixtures altered in candidate | Replay uses trusted fixture inputs; full-suite fallback catches changed behavior | R03 |
| A07 | Narrowed replay uncertain, base absent, parser crash, or timeout | Full replay if safe; otherwise exit 2, never `REPLAY_SKIPPED` plus PASS | R03 |
| A08 | Paths contain spaces, Unicode, tabs/newlines; path escapes or escaping links | Valid paths evaluated literally; unsafe paths exit 2; output escaped | R04 |
| A09 | Equivalent narrowed and full replay on attack and clean corpus | Equal safety verdict and protected-ID coverage; discrepancy disables narrowing | R03 |
| A10 | Init in venv A; clone to unrelated path and venv B | Generated command resolves target B; clean-host check passes without edits | R05 |
| A11 | Pawl installed by pipx/own venv, pytest only in target environment | Correct target interpreter used; missing target runtime exits 3 | R05-R06 |
| A12 | Missing pytest, unavailable PyPI hashes, failed measurement, or filesystem commit error | Transaction rolls back; existing files byte-identical; nonzero exit | R06 |
| A13 | Offline `init --github` with explicit valid hashes, and then missing hashes | Complete offline generation for valid input; fail before workflow write otherwise | R06 |
| A14 | Long/escaped parameters across supported pytest versions | Fixed explicit IDs match; unexpected drift blocks; no fuzzy merge | R07-R08 |
| A15 | Duplicate call/teardown records, skip/xfail, Unicode, path casing | Adapter-specific frozen expected identities/outcomes; worst outcome retained | R07 |
| A16 | Locked clean checkout and separate compatibility-version lane | Qualification passes reproducibly; unsupported drift clearly reported | R08 |
| A17 | Child writes beyond stdout/stderr budget | Terminate/reap, bounded diagnostics, `OUTPUT_LIMIT`, exit 2 | R09 |
| A18 | Oversized/deep report, too many records, malformed counts, link/race substitution | Reject before excessive allocation; exit 2; no partial success | R09 |
| A19 | Timeout with grandchild holding pipes; interrupt during replay | Bounded termination and cleanup; no orphan group/worktree; uncertain cleanup exits 2 | R09 |
| A20 | Synthetic env secret in inherit and minimal modes | Inherit remains disclosed; minimal excludes unless explicitly allowed; no value in diagnostics | R10 |
| A21 | Human policy label at SHA A, then push B/revoke/bot/malformed actor | Only valid A policy scope approved; all other cases rejected | R11 |
| A22 | Valid label or local flag accompanies regression/unknown measurement | Never suppress regression or error; CI manual flag rejected | R11 |
| A23 | Doctor sees malformed config, bad baseline, missing executable, or absent ref | Specific diagnostic and nonzero exit; no files/imports/suites executed | R13 |
| A24 | Offline `--ci-readiness`, online 403, and complete online settings | UNKNOWN when unverifiable; READY only for all verified required checks | R12-R13 |
| A25 | Remote action uses branch/tag/abbreviated SHA in .yml/.yaml | Strict shared validator blocks; valid full SHA/local action behavior explicit | R17 |
| A26 | Tag points at unqualified SHA, wrong version, changed wheel/hash, or failed check | Publish never obtains approval path for those artifacts | R14 |
| A27 | Qualified wheel installed outside source tree on supported Python versions | Version, help, init, check, regression catch, and report work | R14-R15 |
| A28 | Real fresh Python and JS customer projects use generated workflow | Required suites actually execute with installed toolchains; no skip-as-pass | R06,R14-R15 |
| A29 | Benchmark has frozen attacks, clean changes, known misses | Calls real CLI; exact per-scenario outcomes and denominators; no duplicate detector | R16 |
| A30 | Same source state but changed dependency/fixture/config invalidates optional cache | CI always executes; no cached PASS implementation ships | R17 |
| A31 | Corrupt/large trend or malicious rendered strings | Bounded informational failure; escaped output; cannot change verdict | R17 |
| A32 | Unmarked docstring change or uncovered input special case | Preserve known-miss classification; no invented universal detection claim | R15-R16 |
| A33 | Parser fails on changed test source | `unmeasurable`, exit 2; no empty-clean finding result | R02 |
| A34 | Existing non-Python tests gain meaningful additions | Conservative review requirement; documented adapter replay behavior | R02-R03 |

Exact CLI output for A01-A02 must distinguish the structural policy block from
the replay measurement. Running originals may detect a new failure, while a
review-only test edit with unchanged behavior still requires policy approval.
For approved intentional test repair, the approval scope names which old
obligation is retired; unrelated required tests cannot be waived.

## Later isolated-execution scenarios

| ID | Probe | Required observation |
| --- | --- | --- |
| I01 | Candidate installation/test attempts to write gate, policy, approval, controller journal | OS boundary denies; controller facts unchanged |
| I02 | Candidate reads synthetic publisher/reviewer marker | Marker absent from worker inputs/environment and inaccessible filesystem |
| I03 | Candidate forges receipt or reuses previous run/attempt/nonce | Trusted validator rejects, exit 2 |
| I04 | Wrong SHA, suite set, report hash/length, or termination record | Reject before comparison, exit 2 |
| I05 | Network access without reviewed permission | Denied by runtime policy; denied access observed independently |
| I06 | Candidate produces internally consistent false runner outcomes | Receipt may validate provenance; outcome remains candidate-produced, no authenticity claim |
| I07 | Controller/backend unavailable when isolated policy is required | Exit 2, never automatic fallback to inherited mode |

I06 is a limitation test, not a green security-efficacy result. A hostile-report
prevention claim remains prohibited until a separate design can enforce it.

## Definition of done

Implementation unit: affected existing tests pass, new contract tests and attack/
clean corpus cases pass, typing/lint/format pass, and changes have precise source
and requirement references. Any protected-file amendment has owner review.

Milestone M1: A01-A16, A21-A22, A33-A34 pass, main self-gate is reproducible,
and no existing critical fixture regresses. M2 adds A17-A24 and A26-A29/A32,
fresh operator evidence, and the artifact smoke. M3 adds A25/A30-A31 if those
features are shipped. M4 requires I01-I07 and a separately reviewed runtime.

Release promotion: `make check` and `pawl check --ci` both exit 0 on the exact
release commit; all promised adapters/platforms ran, critical corpus has zero
unexpected false PASS, no unexplained clean-case block, required operator
checks are verified, package bytes match the qualification manifest, and docs
state remaining risks. A failed or skipped required check blocks promotion.

Baseline test results before implementation are characterization only. Do not
mark these acceptance IDs complete using the November audit's passing tests.
