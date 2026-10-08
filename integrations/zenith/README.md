# Pawl for Zenith

Use `pawl check` as validator evidence or as a sealing gate.

- Validator: run `pawl check --json` and put the JSON in the validator's
  Evidence field. A non-zero exit fails the validator.
- Gate: run `pawl check` and `pawl guard --base <ref> --replay`. If either exits
  non-zero, seal the gate (skill null, empty body) so the agent cannot report
  done.
- Add the contract in `../AGENTS.md` to the agent's instructions: the spec takes
  priority over the tests, and conflicts are escalated with `pawl escalate`.
