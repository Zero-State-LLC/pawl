# Recommended repository settings

Pawl in CI is only a gate if GitHub enforces it. Apply these by hand in the
repository settings; Pawl does not change settings through the API. The same
list applies to any repository that adopts Pawl, including this one.

## Branch ruleset for the default branch

Settings > Rules > Rulesets > New branch ruleset, target the default branch.

- Restrict deletions: on.
- Block force pushes: on.
- Require a pull request before merging: on.
  - Required approvals: 1.
  - Dismiss stale approvals when new commits are pushed: on.
  - Require review from Code Owners: on.
  - Require approval of the most recent reviewable push: on.
- Require status checks to pass: on.
  - Add the `pawl` job (from `.github/workflows/pawl.yml`).
  - For this repository, also add the `test` matrix jobs and `lint` from
    `ci.yml`.
  - Require branches to be up to date before merging: on (so the trusted ref
    is current).
- Bypass list: empty, or repository admins only. Do not add bots or agent
  accounts.

## Push ruleset (optional, stronger)

Settings > Rules > Rulesets > New push ruleset.

- Restrict file paths: `pawl.toml`, `pawl.baseline.json`, `PAWL_DEBT.md`,
  `.github/workflows/**`, `.github/CODEOWNERS`. Add the agent accounts or
  apps to the ruleset's scope so their pushes cannot touch these paths at all;
  humans change them through a reviewed PR.

## CODEOWNERS

Keep `.github/CODEOWNERS` with at least:

```text
pawl.toml            @scrimshawlife-ctrl
pawl.baseline.json   @scrimshawlife-ctrl
PAWL_DEBT.md         @scrimshawlife-ctrl
.github/             @scrimshawlife-ctrl
**/conftest.py       @scrimshawlife-ctrl
```

## Labels

Create a label named `pawl-approved` (or whatever `approval_label` is set to).
Only maintainers should apply it. Adding it re-runs the workflow and turns
gate-change blocks into approved findings for the commit the label was applied
at. A later push needs a fresh approval: remove the label and add it again.

## Actions

- Settings > Actions > General > Workflow permissions: "Read repository
  contents and packages permissions". The Pawl workflow asks for
  `pull-requests: write` itself, only to post its comment.
- Allow actions: only actions created by GitHub plus allow-listed actions,
  since workflows pin actions by commit SHA.
- Require approval for workflows from outside collaborators: on.

## Agent accounts and tokens

- Give agents a fine-grained token scoped to the repository with Contents:
  read and write, Pull requests: read and write, and nothing else. No admin,
  no Actions or Administration write, no ability to edit rulesets.
- Agents push to branches and open PRs. They never merge.

## Security

- Dependabot alerts and security updates: on (`.github/dependabot.yml` covers
  Actions and pip).
- Secret scanning and push protection: on.
- Private vulnerability reporting: on (see SECURITY.md).
