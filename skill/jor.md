---
name: jor
description: Transfer AI sessions between tools (Claude Code, Codex). Use when the user wants to continue a session in another tool, discover sessions, list sessions, or convert a session.
---

# Jor — AI Session Transfer

Use the `jor` CLI to discover, list, and transfer AI sessions between tools.

## Workflow

### 1. Discover sessions
```bash
jor discover
```
Scans the machine for AI sessions across all supported tools and updates the index.

### 2. List sessions
```bash
jor list
```
Shows all indexed sessions with their IDs, source tool, and timestamps. Pick the session ID you want to transfer.

### 3. Convert and get the resume command
```bash
jor convert <session-id>             # → Claude Code (default)
jor convert <session-id> --codex     # → Codex
```
Prints the resume command to run. The user can copy and run it, optionally adding their own flags.

### 4. (Optional) Convert and launch immediately
```bash
jor open <session-id>                # convert + launch Claude Code
jor open <session-id> --codex        # convert + launch Codex
```

## Supported Tools

- Claude Code (`~/.claude/projects/*/sessions/*.jsonl`)
- Codex (`~/.codex/sessions/rollout-*.jsonl`)

## Notes

- Run `jor discover` first before `jor list` to ensure the index is current.
- Session IDs come from `jor list` output.
- `jor convert` writes the session file and prints the resume command — the user runs it themselves.
- `jor open` does both and launches the tool automatically.
