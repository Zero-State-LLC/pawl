# Owner-authorized independent reviewer

Decision: November 14, 2026 UTC. Daniel nominated Prabu to review PAWL-005 and,
after being told Prabu is an agent and the prior contract said human-only,
explicitly confirmed: "Prabu is fine as reviewer".

For this repository's PAWL-005 review, prabu-openclaw is an authorized
independent reviewer. This decision supersedes human-only wording for that
review role in the promotion packet, onboarding migration and escalation
handoff. Do not represent Prabu as a human or require Daniel to select another
reviewer merely because Prabu is an agent. Final publication is still an owner
action, and no merge, publishing or bypass authority is added by this change.

The collaborator-permission API reports admin access for prabu-openclaw.
PR #53 is authored by scrimshawlife-ctrl, a distinct login. A review has been
requested, but no submitted review was observed when this decision was added.
An owner's delegation authorizes review; it does not manufacture that review.

## Enforced policy

The repository configuration now proposes:

```toml
[guard]
approvers = ["prabu-openclaw"]
refuse_pr_author = true
```

Existing event validation is retained. Approval must come from the allowlisted
GitHub User account, on a labeled event bound to the candidate commit. Missing,
stale, unknown-type and GitHub Bot actors remain rejected. GitHub's User type
is an account classification, not proof of a biological human. No classifier
exception, arbitrary bot allowance, self-approval or direct CLI override is
introduced. Prabu cannot approve a PR authored by prabu-openclaw.

Keep config authority on the trusted base. This policy-only PR is based on
PR #52 and contains no assertion changes or replay migration. Review it first;
do not copy the policy into PR #53 and claim that candidate policy grants its
own authority. After the policy reaches the trusted base through reviewed
integration, refresh the migration's base SHA and module hashes, obtain
Prabu's review of that final candidate, record the escalation disposition,
then rerun check and guard with approval from Prabu's account. A GitHub review
alone is not the label event required by the current Pawl protocol.

This does not resolve missing effective branch-policy readback, workflow
qualification dependencies, hosted customer workflow checks, or publication
qualification. Independent accounts do not prove process isolation or prevent
same-user outcome forgery.

## Verification

The policy-only branch's full make check passed: 477 tests, no skips, 90.28%
coverage, lint/format and strict types. It is based on PR #52, before PR #53's
18 added init/package tests, so this count is not a regression from the
integrated release candidate. No test or baseline identity was changed.

A direct check of the configured policy with synthetic GitHub events accepted
prabu-openclaw as a distinct User reviewer and rejected self-review, an
unlisted reviewer, a Bot actor and a stale commit. These are local policy
checks, not evidence that Prabu has submitted a review or applied a live label.
