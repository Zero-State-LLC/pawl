# Pawl for Claude Code

Add the contract in `../AGENTS.md` to the project's CLAUDE.md, and add hooks so
the agent is stopped before it edits the gate or reports done.

`.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [
          { "type": "command", "command": "python3 -m pawl hook protect", "onFailure": "block" }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 -m pawl hook stop --base origin/main" }
        ]
      }
    ]
  }
}
```

`protect` exits 2 to block a write to a gate file; stderr is the reason. `stop`
prints `{"decision": "block", "reason": "..."}` while the gate is red, which
keeps the agent working. Pawl stops blocking after 5 consecutive red results
(`--max-blocks`) so a gate that cannot go green does not trap the loop; the
agent is told to report the red gate instead of claiming success. See
https://code.claude.com/docs/en/hooks.

`onFailure: "block"` (Claude Code 2.1.295 or later) makes a crashed or
missing Pawl block the write instead of letting it through. Every
`pawl hook` run appends one line to `.pawl/hook-log.jsonl` (harness,
event, session, turn, tool, paths, decision); see
docs/HOOKS_PROVENANCE.md.
