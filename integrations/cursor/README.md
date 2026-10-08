# Pawl for Cursor

Copy `hooks.json` to `.cursor/hooks.json` and add the contract in `../AGENTS.md`
to the project's instructions. Project hooks run from the repository root and
also run for cloud agents.

`protect` returns `{"permission": "deny", "user_message": "...", "agent_message": "..."}`.
`stop` returns `{"followup_message": "..."}`, which Cursor submits as the next
user message, bounded by `loop_limit` (default 5). See
https://cursor.com/docs/hooks.
