# Release qualification and operator handoff

Status: local qualification tooling, not an enabled publish gate. The current
release workflow only requires its build job. A successful package smoke test
does not repair that missing dependency. Do not tag this development candidate.
Its version remains 0.5.0, an already published version.

## Candidate assembly

The release-qualification branch is based on PR #52 and includes the portable
init implementation from PR #45. Its two existing-test assertion changes are
the same owner-approved changes from that PR. The old baseline and debt log
were not copied: the CLI tightens the PR #52 baseline with the added tests.
Do not merge PR #45 again as an unrelated second implementation. Review the
integration diff and keep its approval/migration requirements visible.

The scoped replay policy is not activated in the live repository. A green
self-check is not approval of protected source, tests, baseline, or specs.
Old-base replay can still reject the two intentionally changed assertions.

## Reproducible local package checks

1. Run `make check` with the pinned development requirements and actual Go and
   Rust toolchains. Retain the test count, skip count, coverage and versions.
2. Tighten additions through `pawl update --ci --json`, then run
   `pawl check --ci --json`. Run these sequentially. Never use `--loosen` or an
   order-dependence waiver to obtain a release result.
3. Commit the candidate. Require a clean tracked/untracked working tree. Record
   its full SHA and tree. Export that commit with `git archive` into a new
   temporary directory. Build there, not from an editable checkout.
4. In a dedicated build environment install build==1.6.1, setuptools==84.2.1,
   wheel==0.48.0 and twine==7.0.0. Record the full dependency freeze. Run
   `python -m build --no-isolation --outdir DIST SOURCE` and
   `python -m twine check --strict DIST/*`. Build's default flow makes the
   sdist first and builds the wheel from that sdist. Preserve those exact bytes.
5. Compute SHA-256 for both distributions. Prepare a separate wheelhouse with
   pytest==9.1.1 and its dependencies. Record those file hashes too. Run the
   committed script using absolute paths:

   ```sh
   python scripts/smoke_wheel.py /absolute/dist/pawl_gate-0.5.0-py3-none-any.whl \
     --sha256 ACTUAL_WHEEL_SHA256 --version 0.5.0 \
     --wheelhouse /absolute/wheelhouse --receipt /absolute/new-receipt.json
   ```

   It installs the verified wheel bytes and pytest into a fresh venv, disables
   index access during installation, verifies import origin/metadata/py.typed,
   exercises version/help, initializes a customer project, relocates it,
   confirms PASS, injects a real application regression, requires FAIL, renders
   the report, restores the application and checks local doctor readiness.
   It does not execute a generated GitHub workflow or certify CI readiness.
6. Run negative smokes: change the expected hash and expected version in
   separate invocations. Require nonzero exit and no success receipt. Never
   overwrite an earlier receipt. Preserve logs outside the source tree.
7. Repeat full-source and installed-wheel checks on every advertised supported
   Python/platform combination using the same wheel. Linux/Python 3.12 alone
   does not qualify 3.11, 3.13, macOS or native Windows. Native Windows runner
   support remains explicitly unavailable.

The script executes trusted package code. It is not a hostile-package sandbox,
an authenticated receipt signer, a network isolation mechanism, or a substitute
for independent release approval. Its JSON always says release_authorized=false.
The build environment and dependency freeze are evidence, not a fully locked
hermetic supply chain. Archive file hashes and logs with the candidate receipt.

## Required reviewed workflow changes before publication

The protected `.github/workflows/` files are not changed by this implementation.
The operator workflow review must implement these job contracts:

| Job | Inputs and permissions | Required result |
| --- | --- | --- |
| Source qualification | Exact immutable commit; read-only token; disposable worker; pinned toolchains | Lint/types/full tests, no missing-runtime skips, self gate and approved replay/migration; receipts bind the same SHA |
| Build | Same SHA after source qualification; no publisher credential | Build sdist then wheel once; version agreement; hash both artifacts; upload one immutable artifact bundle |
| Package matrix | Download that bundle by run and artifact ID; no publisher credential | Verify digests, install the same wheel outside source on Python 3.11/3.12/3.13; positive/negative smoke and customer workflow checks |
| Qualification decision | Trusted verifier outside candidate ownership | All required jobs succeeded for same SHA, version and artifact digests; no skipped/cancelled/missing result accepted |
| Publish | Needs successful decision; protected pypi environment; isolated worker; OIDC only here | Download exact qualified artifact ID, recheck digests/version/tag/SHA, attest and upload without rebuilding or running candidate code |

Do not rely on artifact names across arbitrary runs. Bind repository, workflow
identity, event, run ID/attempt, source SHA, artifact ID, version, both file hashes
and matrix outcomes. A candidate-supplied JSON field saying PASS is not trusted
authorization. The trusted verifier must obtain job status and artifact identity
from the provider and check them against the approved candidate.

Review rejection cases before enabling publishing: wrong source SHA, tag/version
mismatch, altered wheel or sdist, wrong run/artifact, unsuccessful source check,
missing/skipped matrix result, stale approval, and rebuild after qualification.
Each must prevent entry to the publish job. This acceptance suite is pending;
local hash/version rejection tests cover only a small subset of A26.

After workflow review and effective-policy readback, select a new version,
update both version declarations, and rerun qualification on the resulting
commit. The owner then approves the exact candidate and artifacts. After
publication, download registry files and compare their hashes before limited
promotion. No tagging, publishing, ruleset changes or review labels are part
of the local qualification command.
