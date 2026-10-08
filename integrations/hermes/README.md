# Pawl for Hermes

Merge `config.yaml` into the profile `config.yaml` and add the contract in
`../AGENTS.md` to the project's AGENTS.md.

- `pre_tool_call` with `fail_closed: true` blocks the tool when the hook exits
  2, errors, or times out.
- `pre_verify` fires when the agent edited code and would otherwise accept its
  final answer. Pawl answers `{"decision": "block", "reason": "..."}`, which
  Hermes accepts at the verify gate, while the gate is red. Consecutive
  continuations are capped by `agent.max_verify_nudges` (default 3).
- Shell hook timeouts above 300 seconds are clamped. If the suite takes longer,
  run the stop hook without `--base` or use the CI gate only.
- On hosts with several Python installs, set `python` in the `[preflight]`
  table of `pawl.toml` to the interpreter the project must use, so a wrong
  interpreter fails the preflight instead of producing a misleading red run.
