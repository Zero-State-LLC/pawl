# Pawl for Codex

Copy `hooks.json` to `.codex/hooks.json` and add the contract in `../AGENTS.md`
to the project's AGENTS.md. Codex requires a human to review and trust hooks
before they run (`/hooks`).

`protect` denies a tool call with:

```json
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "..."}}
```

`stop` keeps the turn going with `{"decision": "block", "reason": "..."}`.
Pawl stops blocking after 5 consecutive red results (`--max-blocks`). Codex
notes that tool hooks are "a useful guardrail, not a complete enforcement
boundary"; CI is the authority. See https://developers.openai.com/codex/hooks.
