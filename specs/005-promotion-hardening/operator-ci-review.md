# T14 operator CI review: observed gaps and proposed changes

Observed November 13, 2026 (America/Los_Angeles), through the connected GitHub
read-only API. No settings were changed. Main still points to
bc2fcee9d3d0fec63f129e5e3891347d98a95071; the hardening PR stack is not merged.

## Evidence

- Branch metadata: https://api.github.com/repos/Zero-State-LLC/pawl/branches/main
- Main ruleset: https://api.github.com/repos/Zero-State-LLC/pawl/rulesets/24762283
- Release tags: https://api.github.com/repos/Zero-State-LLC/pawl/rulesets/24762289
- Classic branch protection: HTTP 403, Resource not accessible by integration.
- Effective branch-rules endpoint: unsupported by this connector's URL allowlist.

These are observations of named rulesets, not a complete effective-policy
certificate. Classic protection and any unobserved enforcement remain UNKNOWN.

| Main ruleset 24762283 | Observed | Proposed reviewed value |
| --- | --- | --- |
| Enforcement | active | retain |
| Target | default branch | retain |
| Required approving reviews | 0 | 1, after distinct reviewer access is verified |
| Dismiss stale reviews | true | retain |
| Code-owner review | false | true, after CODEOWNERS coverage is verified |
| Last-push approval | false | true |
| Strict required checks | false | true |
| Required check source | GitHub App 15368 | retain after verifying app identity and workflow binding |
| OrganizationAdmin bypass | pull_request | decide explicitly; do not assume bypass proves independent review |

Existing check contexts are pawl, lint, test (3.11), test (3.12), test (3.13).
Preserve their bindings during any reviewed update. Do not replace the rule set
with a partial body that drops existing deletion/non-fast-forward protections.

Release-tags ruleset 24762289 is active for refs/tags/v*, and restricts creation,
update, deletion and non-fast-forward changes. OrganizationAdmin has always
bypass. This does not prove separated publisher credentials or protected release
environments. Those require their own evidence.

## Concrete rollout sequence

1. Establish distinct human reviewer and agent accounts; verify their actual
   repository permissions. Account separation is unresolved, not inferred from
   the actor shown by this session's connector.
2. Verify CODEOWNERS coverage and the trusted implementation behind each check.
3. Obtain authenticated read access for classic protection and effective rules.
4. Review a minimal ruleset update using the proposed values above, with an
   explicit bypass decision and no unrelated changes.
5. Apply only after owner authorization, then read back effective controls and
   exercise positive/negative pull-request cases. Doctor must retain UNKNOWN
   for any unverified control.
6. Qualify exact source/artifacts and publisher boundaries before release.

No reviewer invitations, labels, settings updates, merges or releases are
performed by this document. This is an actionable review packet, not approval.

## Follow-up enforcement review, November 14 UTC (November 13 Pacific)

Fresh reads of main and both named rulesets returned the same values above.
Classic protection still returns 403. The publish-environment read route is
not supported by this connector. Environment reviewers, self-review prevention,
deployment branch/tag policy, administrator bypass and the PyPI trusted
publisher binding remain unverified.

The checked-in CODEOWNERS wildcard and explicit gate/source paths name
@scrimshawlife-ctrl. This covers the paths textually, but neither proves that
account has current write permission nor provides a distinct reviewer for
changes submitted through that account. Verify those identities before enabling
a mandatory approval rule that the team cannot satisfy.

The current release workflow checks tag/version agreement and membership in
main, builds distributions, runs twine, then allows publish with `needs: build`.
It has no dependency on full tests, Pawl, an installed-wheel matrix, or a
qualified-artifact decision. Its publish job has no source checkout and limits
OIDC to publishing, which is useful separation, but the pypi environment's
actual enforcement is unknown. Tag membership in main is not qualification.

The CI runtime receipt explicitly permits missing-runtime tests to skip. It is
not evidence that every adapter ran. The proposed release qualification must
fail required missing-runtime checks. See [the release runbook](../../docs/RELEASING.md)
for concrete job contracts, rejection cases and remaining operator decisions.
