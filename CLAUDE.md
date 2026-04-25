# Jor — Claude Code Context

## What is Jor

Jor is a CLI tool that discovers, indexes, and converts AI sessions across tools (Claude Code, Codex, Aider, Cursor, etc.) so you can continue any session in any tool. It's the missing session layer for AI — like Jupyter Notebooks unified data science, Jor unifies AI conversations.

## Current State

Phase 1 — not yet implemented. Design spec complete.

## Key Docs

| File | Purpose |
|------|---------|
| `docs/superpowers/specs/2026-04-25-jor-mcp-phase1-design.md` | Full Phase 1 design spec — session format, CLI commands, project structure, connectors, writers, success criteria |
| `docs/go-to-market.md` | Vision, MVP scope, demo script, 6-phase roadmap, positioning |
| `docs/parking-lot.md` | Deferred ideas (auto-discovery on session start) |
| `docs/research/session-formats-and-competitors.md` | Competitive landscape, session format details per tool, reading list |

## Architecture

**CLI tool (`jor`)** with 4 commands:
- `jor discover` — scan machine for AI sessions across tools, build index
- `jor list` — list/filter indexed sessions
- `jor convert <id>` — translate session to target tool's native format, print resume command
- `jor open <id>` — convert + launch target tool

**Claude Code skill** — wraps the CLI for in-session use.

**No MCP server in Phase 1.** MCP deferred to Phase 2 when remote storage is added.

## Tech Stack

- Python 3.11+
- Pydantic (schema/types)
- pytest (testing)
- uv (package management)
- Published to PyPI as `jor`
- Minimal deps — stdlib for json, pathlib, sqlite3, subprocess

## Project Structure

```
src/jor/
├── cli.py                    # CLI entry point
├── discovery/
│   ├── scanner.py            # Orchestrates connectors, builds index
│   ├── index.py              # Read/write ~/.jor/index.json
│   └── connectors/
│       ├── base.py           # Connector protocol
│       ├── claude_code.py    # Claude Code JSONL → Jor
│       └── codex.py          # Codex JSONL → Jor
├── session/
│   ├── schema.py             # JorMessage, ToolCall, ToolResult (Pydantic)
│   ├── reader.py             # Read Jor sessions, format for output
│   └── writers/
│       ├── base.py           # Writer protocol
│       ├── claude_code.py    # Jor → Claude Code native
│       └── codex.py          # Jor → Codex native
├── launchers/
│   ├── base.py               # Launcher protocol
│   ├── claude_code.py        # Write session + run `claude --resume`
│   └── codex.py              # Write session + run `codex --resume`
└── utils.py
```

## Phase 1 Connectors

**Claude Code:** `~/.claude/projects/*/sessions/*.jsonl` — JSONL with typed messages linked by parentUuid
**Codex:** `~/.codex/sessions/rollout-*.jsonl` — JSONL using OpenAI chat completion format

## Key Design Decisions

- **Jor session format is JSONL** — one JSON object per line, append-only, lossless
- **Relative file paths only** — sessions are portable across machines
- **`metadata` field** preserves raw source data that doesn't fit the schema
- **`source_tool` and `source_id`** track provenance back to the original session
- **`convert` and `open` are separate** — `convert` writes the file and prints the resume command, `open` also launches the tool. This lets users add their own flags.
- **Default target is `--claude-code`**, `--codex` is an alternative flag

## Rules

- Read the design spec before implementing — it has the full schema, CLI interface, and success criteria
- Test with real session data from the local machine
- Keep dependencies minimal
- Follow the project structure in the spec
- Reference CASS (`franken_agent_detection`) parser code for format details when needed
