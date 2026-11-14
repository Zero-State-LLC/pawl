# T15/T17 local release qualification

Observed November 14, 2026 UTC (November 13 Pacific). Result: local source and
package checks PASS; publication and promotion remain HOLD.

Qualified source: `63f07f015b5255ac54e33a42169e5a7f370431f9`.
Tree: `9a84bef09a6ba40aa0153141cdaffd476d3027b1`.
The later evidence-only commit records this candidate; it is not a claim that
an untested future merge or version bump is qualified.

## Assembly and actual checks

PR #52's branch now has a separate release-qualification child branch that
integrates PR #45's portable/transactional init. The existing-test amendment
is byte-identical to the owner-approved `tests/test_supply_chain.py` from
PR #45. No old baseline/debt file was copied. The CLI retained every one of
474 baseline identities and added 18, confirming two orders, with no loosening.

| Linux x86_64 interpreter | Full make check | Coverage | Installed same wheel |
| --- | --- | --- | --- |
| Python 3.11.18 | 495 passed, 0 skipped | 90.44% | PASS |
| Python 3.12.14 | 495 passed, 0 skipped | 90.44% | PASS |
| Python 3.13.18 | 495 passed, 0 skipped | 90.44% | PASS |

Each full check includes lint, format, strict types and coverage. Actual Go
1.27.4, Rust 1.100.0 and Node 24.22.1 ran the existing runtime tests, including
regression rejection. The Node test exercises generic JUnit with Node's test
runner, not a hosted Jest/Vitest customer workflow. Pawl's final self-gate
passes with 492 tests; its configuration intentionally excludes the three
runtime tests that the full check runs separately.

The source was exported from the exact commit with git archive. Build 1.6.1,
setuptools 84.2.1, wheel 0.48.0 and twine 7.0.0 produced an sdist then a wheel
from that sdist. Both pass twine's strict metadata check. The build ran once
for this candidate, without publishing. Full build dependency versions and
wheelhouse hashes are retained with the evidence.

| Artifact | SHA-256 |
| --- | --- |
| pawl_gate-0.5.0-py3-none-any.whl | 2ffabf6088b282670ec4096a1867d82332207aeddeec0266af54608a0104df6a |
| pawl_gate-0.5.0.tar.gz | f11290e6c896a80d5e9df1fa354e7fddca5b5e560d5f3f36d5891ee7fc74c827 |

All three smoke runs install that same wheel in new environments outside the
source tree. They verify import origin, both version declarations, py.typed,
CLI help/version, portable init, relocated clean PASS, real application
regression FAIL, Markdown reporting, recovery and offline local doctor READY.
Wrong-hash and wrong-version attempts each exit 1 and create no success receipt.

During harness development, the initial run on candidate 34ab3b7 failed because
the fixture put its test outside the auto-detected tests directory. A second
run exposed the harness using status instead of doctor's readiness field.
Both harness mistakes were fixed before committing and qualifying 63f07f0.
The preliminary candidate's artifacts are not the qualified artifacts above.
No existing test expectation was changed to accommodate these harness errors.

## Evidence and limits

The [manifest](../../docs/evidence/promotion-005-release/manifest.json) binds the
source SHA, tree, artifact hashes, runtime versions and individual results.
Adjacent files retain full check/build logs, self-gate JSON, baseline update,
package smoke receipts and negative-case logs. These are local observations,
not signed provider attestations or an authenticated release authorization.
The distribution bytes remain local build outputs; this packet does not
create a hosted release artifact or promise persistent artifact storage.

A26 is partial: local hash/version rejection works, but the hosted publish
job's qualification dependency and its rejection suite are not implemented.
A27 has Linux evidence on the three advertised Python minors. macOS remains
unqualified; native Windows execution is unsupported. A28 remains open because
fresh Python and JavaScript generated GitHub workflows were not executed.
T17 and the overall M1/M2 milestone are not closed by these local results.

The earlier process-cleanup timing flake has not recurred in these runs, but
its cause is still unproven. Same-user filesystem/process access and outcome
forgery remain outside Pawl's isolation claims. No environment allowlist or
artifact hash turns these results into proof of hostile-code containment.

## Required handoff

1. Resolve distinct reviewer/agent accounts and review the integrated test,
   spec and baseline changes. Activate the reviewed scoped assertion migration
   before relying on old-base replay. A self-gate PASS does not clear guard.
2. Apply the reviewed enforcement changes and read back effective policy.
   The named main ruleset still has zero approvals, code-owner review off,
   last-push approval off and strict required checks off. Classic protection
   and publish-environment controls remain unverified through this connector.
3. Review and implement the protected workflow changes in
   [RELEASING.md](../../docs/RELEASING.md), including independent artifact
   verification and rejection cases before the publish job.
4. Choose a new unpublished version, qualify that resulting exact commit and
   complete the missing support/customer matrix. The current 0.5.0 development
   artifacts must not replace or be confused with the published 0.5.0 release.
5. Obtain owner approval for that candidate and its artifacts, publish, then
   verify registry hashes before limited promotion.
