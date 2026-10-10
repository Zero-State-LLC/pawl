# Pawl for Codex

Copy `hooks.json` to `.codex/hooks.json` and add the contract in `../AGENTS.md`
to the project's AGENTS.md. Codex requires a human to review and trust hooks
before they run (`/hooks`).

The `PreToolUse` matcher covers shell (`Bash`), `apply_patch` (also matched
as `Edit` or `Write`) and every MCP tool (`mcp__.*`), so an MCP server that
writes files is checked too. Pawl reads the target from `file_path`, `path`,
`target_file` or `filePath` in the tool input; an MCP tool that names its
target differently is not checked.

`protect` denies a tool call with:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```

`stop` keeps the turn going with `{"decision": "block", "reason": "..."}`.
Pawl stops blocking after 5 consecutive red results (`--max-blocks`). Codex
notes that tool hooks are "a useful guardrail, not a complete enforcement
boundary"; CI is the authority. See https://developers.openai.com/codex/hooks.
