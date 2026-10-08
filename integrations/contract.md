# The Pawl contract

Any harness can enforce Pawl with two rules, whatever its hook system looks like.

1. The agent cannot report done unless `pawl check` exits 0. If the harness has
   a stop or verify hook, run `python3 -m pawl hook stop` there. If it does not,
   run `pawl check` as the last step and reject the result otherwise.
2. The agent never edits the gate. If the harness can intercept writes, run
   `python3 -m pawl hook protect` before them. The protected paths are
   `pawl.toml`, `pawl.baseline.json`, the debt log, `.pawl/`, the workflows
   directory, CODEOWNERS, conftest files, and the test runner config.

Both hooks read a JSON payload on stdin and need no flags when the harness sets
`cwd` or `workspace_roots`. `--format` selects the output shape: `claude`,
`codex`, `hermes`, or `cursor`.

Hooks are a fast early check. An agent with a shell can disable them. The
authority is CI: the `pawl` job is a required status check, and CODEOWNERS
requires review for the gate files. See `docs/RECOMMENDATION.md`.
