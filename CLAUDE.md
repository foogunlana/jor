# Jor — Claude Code Context

## What is Jor

Jor is a CLI tool that finds AI sessions across tools (Claude Code, Codex, Aider, Cursor, etc.) and lets you continue any session in any tool. It's the missing session layer for AI — like Jupyter Notebooks unified data science, Jor unifies AI conversations.

## Current State

Phase 1 — implemented, not yet published to PyPI.

## Key Docs

| File | Purpose |
|------|---------|
| `docs/superpowers/specs/2026-04-25-jor-mcp-phase1-design.md` | Full Phase 1 design spec — session format, CLI commands, project structure, connectors, writers, success criteria |
| `docs/go-to-market.md` | Vision, MVP scope, demo script, 6-phase roadmap, positioning |
| `docs/parking-lot.md` | Deferred ideas (auto-discovery on session start) |
| `docs/research/session-formats-and-competitors.md` | Competitive landscape, session format details per tool, reading list |

## Architecture

**CLI tool (`jor`)** with 2 commands:
- `jor list` — auto-discover and list sessions across tools
- `jor open <id>` — convert session to target tool's format + launch

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
├── cli.py                    # CLI entry point (list, open)
├── spinner.py                # Terminal spinner for async feedback
├── connectors/
│   ├── base.py               # BaseConnector protocol (read, write, launch)
│   ├── claude/
│   │   └── connector.py      # Claude Code JSONL ↔ Jor
│   └── codex/
│       └── connector.py      # Codex JSONL ↔ Jor
└── core/
    ├── schema.py             # JorMessage, ToolCall, ToolResult (Pydantic)
    ├── reader.py             # Read Jor sessions
    ├── scanner.py            # Orchestrates connectors, builds index
    └── index.py              # Read/write ~/.jor/index.json
```

## Phase 1 Connectors

**Claude Code:** `~/.claude/projects/*/sessions/*.jsonl` — JSONL with typed messages linked by parentUuid
**Codex:** `~/.codex/sessions/rollout-*.jsonl` — JSONL using OpenAI chat completion format

## Key Design Decisions

- **Jor session format is JSONL** — one JSON object per line, append-only, lossless
- **Relative file paths only** — sessions are portable across machines
- **`metadata` field** preserves raw source data that doesn't fit the schema
- **`source_tool` and `source_id`** track provenance back to the original session
- **`open` handles conversion implicitly** — converts to the target format and launches in one step

## Rules

- Read the design spec before implementing — it has the full schema, CLI interface, and success criteria
- Test with real session data from the local machine
- Keep dependencies minimal
- Follow the project structure in the spec
- Reference CASS (`franken_agent_detection`) parser code for format details when needed
- **Minimal code** — write the least code possible. Use libraries over hand-rolled solutions. Lean on stdlib and deps (click, pydantic) heavily. No abstractions until forced.
- **No premature structure** — don't create files, directories, or `__init__.py` until they're needed by actual code
- **TDD workflow** — see `.claude/workflows/tdd.md`. Every feature gets a test bead then an impl bead. Ralph processes them in order.

## Git Workflow

**Branching:** All work happens on feature branches. Never commit directly to `main`.

```bash
git checkout -b feat/short-description   # new feature
git checkout -b fix/short-description    # bug fix
```

**Conventional commits:** All commit messages must follow [conventional commits](https://www.conventionalcommits.org/):

```
feat: add incremental discovery to jor list
fix: remove duplicate sessions on re-convert
refactor: extract spinner into standalone module
test: add mtime filtering tests for BaseConnector
docs: update README install instructions
chore: add CI/CD workflows
```

- Use `feat:` for new functionality
- Use `fix:` for bug fixes
- Use `refactor:` for code changes that don't add features or fix bugs
- Use `test:` for test-only changes
- Use `docs:` for documentation-only changes
- Use `chore:` for build/CI/tooling changes
- Keep the subject line under 72 characters
- Use imperative mood ("add" not "added")

**Pull requests:** Open a PR to merge into `main`. PRs run CI (tests on Python 3.11-3.13) and require passing before merge.

**Releases:** Create a GitHub release with a version tag (e.g. `v0.2.0`) to auto-publish to PyPI.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
