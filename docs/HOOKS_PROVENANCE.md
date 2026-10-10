# Hook provenance

Every `pawl hook` invocation appends one JSON line to `.pawl/hook-log.jsonl`.
The log records what the harness told Pawl about a hook event and what Pawl
decided. It holds no tool input and no transcript content.

## Fields

| Field         | Meaning                                                    |
| ------------- | ---------------------------------------------------------- |
| `v`           | Log schema version.                                        |
| `ts`          | UTC timestamp of the hook run.                             |
| `pawl`        | Pawl version that wrote the line.                          |
| `harness`     | `claude`, `codex`, `cursor` or `hermes`.                   |
| `hook`        | Hook name as invoked, for example `protect`.               |
| `event`       | Harness event, for example `PreToolUse`.                   |
| `session`     | Harness session id, when the harness sends one.            |
| `turn`        | Turn or prompt id, when the harness sends one.             |
| `agent`       | Subagent id or type, when the harness sends one.           |
| `tool`        | Tool name, for example `Write` or `Edit`.                  |
| `tool_use_id` | Harness tool call id, when the harness sends one.          |
| `model`       | Model id, when the harness sends one.                      |
| `paths`       | Paths the hook was asked to check.                         |
| `decision`    | `allow`, `block`, `error` or `budget`.                     |
| `reason`      | Short reason, truncated to 500 characters.                 |

## Codex tool coverage

Checked 2026-10-10 against the official Codex hooks page
(developers.openai.com/codex/hooks). `PreToolUse` runs for shell commands
(`Bash`, including unified exec), for file edits through `apply_patch`
(matcher `apply_patch`, `Edit` or `Write`; input reports
`tool_name: "apply_patch"` with the patch in `tool_input.command`), for MCP
tools (matcher is the MCP tool name, such as `mcp__fs__write`), and for
other local function tools. It does not run for hosted tools such as web
search. The docs warn that some specialized tool paths can opt out and call
tool hooks a guardrail, not a complete enforcement boundary. A hook error,
timeout or malformed output does not block in Codex, and `ask` is not
supported. Pawl's Codex config matches `Bash|apply_patch|Edit|Write`; MCP
tools that write files are not matched by default. CI remains the authority.

## Where each id comes from

| Harness | Session              | Turn             | Agent                     | Tool call     | Model          |
| ------- | -------------------- | ---------------- | ------------------------- | ------------- | -------------- |
| Claude  | `session_id`         | `prompt_id`      | `agent_id`/`agent_type`   | `tool_use_id` | not sent       |
| Codex   | `session_id`         | `turn_id`        | as sent                   | `tool_use_id` | as sent        |
| Cursor  | `conversation_id`    | `generation_id`  | as sent                   | as sent       | model field    |
| Hermes  | whichever of these it sends; missing fields stay empty.                         |

## Never recorded

- Tool input contents or file bodies.
- Shell commands, arguments or output.
- Transcript paths or transcript text.
- Environment variables, credentials or user identity.

## Authority

The log is local, agent-writable evidence. It is not authority. It can be
edited or deleted by the same agent it describes. Gates that must hold act
on CI, not on this file. Treat the log as a debugging and review aid.

Signing the log (so a reviewer can tell an edited log from an intact one)
is planned for a later release. Until then it is a debugging aid only.

## Fail closed

`protect` looks for `pawl.toml` in the hook's working directory and then in
each parent directory. If one is found but cannot be loaded (bad TOML,
invalid settings, unreadable), the hook blocks every write it is asked about
and logs decision `error`, until a human repairs the config. If no
`pawl.toml` exists anywhere up the tree, Pawl is not set up there and the
hook allows the call.

## Protected contract paths

The `protect` hook blocks contract paths as well as its other patterns:
`guard.contracts` and `pawl.contracts.json` are never writable by an agent,
whatever the harness claims.

## Format checks

Hook output shapes were re-checked on 2026-10-10 against the Claude Code,
Codex and Cursor hook docs. Block shapes are unchanged:

- Claude Code: exit 2 with a message on stderr, or
  `hookSpecificOutput.permissionDecision` set to deny.
- Codex: `hookSpecificOutput` with deny; a Stop decision of block needs a
  non-empty reason.
- Cursor: `permission` deny or exit 2, `followup_message` for stop, and
  `failClosed` on `preToolUse`. Cursor also reads Claude-format hooks.
