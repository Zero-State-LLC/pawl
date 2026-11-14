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
| `online-ci` | Requested by `--online`; provider verification is not implemented in this slice, so remote controls remain UNKNOWN |

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
