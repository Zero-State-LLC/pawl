# Static diagnostics

```sh
pawl doctor
pawl doctor --json
pawl doctor --trusted-ref origin/main --json
pawl doctor --ci-readiness --json
```

Default scope is `offline-local`. Doctor reads worktree configuration and baseline,
validates identity/metric compatibility, resolves configured executable files
without running them, and reports the selected execution boundary. It does not
run suites, preflight commands or project imports. It does not write reports,
install packages, fetch refs or change repository/provider settings.

`--trusted-ref` checks local commit availability using the launcher's Git with
network transports disabled. It does not load configuration from that ref:
configuration/baseline checks still inspect the worktree, as reported by the
command. Git from inside the candidate checkout is refused. Git availability,
timeouts and missing local refs have separate diagnostic outcomes.

| Scope | What READY means |
| --- | --- |
| `offline-local` | Required static local checks passed; no runtime qualification implied |
| `offline-ci` | Includes required remote controls, which remain UNKNOWN offline |
| `online-ci` | Requested by `--online`; explicit GitHub settings reads are available; unverifiable controls remain UNKNOWN |

Workflow presence never establishes CI readiness. Both `.yml` and `.yaml`
declarations are detected without interpreting workflow code. Missing declarations
fail CI scope; existing, unsafe or oversized directories leave semantics UNKNOWN.
Local scope reports CI declaration limitations without treating them as required
local checks. Executable resolution does not authenticate binaries, inspect their
versions or prove commands will run successfully.

Exit 0 means required checks in the selected scope passed. Exit 1 means a required
check failed. Exit 2 means a required check remains unknown without a known failure.
A known failure takes precedence over unknowns; optional checks never conceal a
required failure. Every output identifies its scope.

Local READY is not a passing test gate or permission to promote a release. Run
`pawl check`, protected review and exact-artifact qualification separately.

## Explicit GitHub reads

```sh
pawl doctor --online --repository Zero-State-LLC/pawl --branch main \
  --expected-check pawl --expected-app-id 15368 --json
```

The trusted diagnostic process reads GH_TOKEN or GITHUB_TOKEN from its environment.
Use an appropriately scoped read-only credential outside candidate execution;
never place it in a repository, command-line argument or report. The selected
context/app ID must come from trusted operator policy, not candidate config.
The example reflects Pawl's observed ruleset binding, not a universal app ID.

The client observes branch metadata, classic protection and active branch rules.
It may verify narrowly supported last-push/current-base settings, but cannot
certify identity separation, CODEOWNERS coverage, immutable workflow behavior
or publisher isolation. Access denial, partial rules and malformed responses
remain UNKNOWN. It never changes settings or follows redirects/pagination links.
See [assessment boundaries](../specs/005-promotion-hardening/github-doctor.md).
