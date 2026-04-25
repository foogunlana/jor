# Jor — Phase 1 Design Spec

**Date:** 2026-04-25
**Status:** Draft
**Scope:** CLI tool for AI session discovery, conversion, and cross-tool continuation
**Timeline:** 1 week
**Milestone:** Community event demo (May 2026)

---

## 1. Problem

AI sessions are fragmented across tools (Claude Code, Codex, Aider, Cursor, etc.) with no way to:
- See all your sessions in one place
- Continue a session started in one tool using another
- Share sessions with others

No interchange format or cross-tool session layer exists.

## 2. Solution

A Python CLI that discovers AI sessions across tools on your local machine, converts them to a unified format, and lets you continue any session in any tool.

**Two interfaces:**
- **CLI (`jor`)** — the core tool. Discover, list, convert, and open sessions across tools.
- **Claude Code skill** — wraps the CLI for in-session discovery. Runs `jor list`, presents results, runs `jor convert`, and tells the user the resume command.

## 3. Phase 1 Scope

### What ships
- **Jor CLI** (`jor`) — discover, list, convert, and open sessions across tools
- **Claude Code skill** — in-session wrapper for the CLI
- Session discovery for Claude Code and Codex
- Jor session format (JSONL schema)
- Session translators (Claude Code JSONL and Codex JSONL → Jor format)
- Reverse translators (Jor format → Claude Code native, Jor format → Codex native)
- Local session index
- Published to PyPI as `jor`

### What doesn't ship
- MCP server (deferred to Phase 2 when there's a remote backend)
- Remote storage, sync, auth
- Web UI
- Git integration
- Push/pull/share
- Real-time session capture
- Connectors beyond Claude Code and Codex

## 4. CLI

The CLI is the primary interface. It shares all discovery and translation logic with the MCP server.

### `jor discover`

Scans the local machine for AI sessions. Builds/updates the session index.

```bash
$ jor discover
Found 23 sessions: 15 claude_code, 8 codex
Index updated at ~/.jor/index.json
```

### `jor list`

Lists indexed sessions with optional filters.

```bash
$ jor list
 #  Tool         Date        Messages  Title
 1  claude_code  Apr 20      42        Auth module refactor
 2  codex        Apr 18      28        Data pipeline fix
 3  claude_code  Apr 17      15        README update
...

$ jor list --tool codex
 1  codex  Apr 18  28  Data pipeline fix
 2  codex  Apr 15  63  API endpoint migration
...

$ jor list --query "auth"
 1  claude_code  Apr 20  42  Auth module refactor
```

**Flags:**
- `--tool` — filter by source tool (`claude_code`, `codex`)
- `--query` / `-q` — search titles and first user message
- `--limit` / `-n` — max results (default 20)
- `--project` — filter by workspace path

### `jor convert`

Translates a session to the target tool's native format and writes it. Does NOT launch the tool — prints the command you need to run.

```bash
# Convert session #1 to Claude Code format (default)
$ jor convert 1
Session written to ~/.claude/projects/.../sessions/abc123.jsonl

To resume, run:
  claude --resume abc123

# Convert session #1 to Codex format
$ jor convert 1 --codex
Session written to ~/.codex/sessions/rollout-abc123.jsonl

To resume, run:
  codex --resume abc123
```

**Target tool flags:**
- `--claude-code` (default) — write Claude Code native session file
- `--codex` — write Codex native session file

**What happens:**
1. Reads the Jor session from `~/.jor/sessions/<id>.jsonl`
2. Translates Jor format → target tool's native session format (reverse translation)
3. Writes the native session file to the target tool's session directory
4. Prints the exact command to resume, so the user can add their own flags

### `jor open`

Convenience command — runs `jor convert` then launches the tool. For when you don't need custom flags.

```bash
# Convert and launch in Claude Code (default)
$ jor open 1
Session written to ~/.claude/projects/.../sessions/abc123.jsonl
Launching: claude --resume abc123
...

# Convert and launch in Codex
$ jor open 1 --codex
Session written to ~/.codex/sessions/rollout-abc123.jsonl
Launching: codex --resume abc123
...
```

**Same flags as `jor convert`** — `--claude-code` (default), `--codex`.

Internally, `jor open` is just `jor convert` + `subprocess.run()`.

### `jor serve`

Starts the MCP server (used by Claude Code MCP config, not called manually).

```bash
$ jor serve
# Starts FastMCP server on stdio
```

---

## 5. Claude Code Skill

A skill that wraps the CLI for in-session use. The user says "/jor" or asks to find sessions, and the skill runs the CLI commands via Bash.

**Skill flow:**
1. Run `jor discover` — show the user what was found
2. Run `jor list` — present sessions in a readable format
3. User picks a session
4. Run `jor convert <id> --claude-code` (or `--codex`)
5. Tell the user the resume command: "Run `claude --resume <id>` to continue this session"

**The skill is a markdown file** — no code beyond the CLI it wraps. Installed in the user's skills directory.

## 5. Jor Session Format

JSONL file where each line is a JSON object representing one message.

### Message Schema

```python
class JorMessage(BaseModel):
    id: str                              # UUID
    role: Literal["user", "assistant", "system", "tool_result"]
    content: str                         # Message text (markdown)
    tool_calls: list[ToolCall] | None    # Tool invocations by assistant
    tool_result: ToolResult | None       # Result of a tool call
    files: list[str] | None             # Relative paths referenced/modified
    model: str | None                    # e.g. "claude-sonnet-4-6", "o3"
    provider: str | None                 # e.g. "anthropic", "openai"
    timestamp: str                       # ISO 8601
    metadata: dict | None               # Extensible, tool-specific data
    source_tool: str                     # Original tool: "claude_code", "codex"
    source_id: str | None               # Original session ID in source tool

class ToolCall(BaseModel):
    id: str
    name: str                            # Tool name
    input: dict                          # Tool arguments

class ToolResult(BaseModel):
    tool_call_id: str                    # Links to ToolCall.id
    content: str                         # Result content
    is_error: bool
```

### Design Decisions
- **Relative paths only** for file references — portable across machines
- **Lossless** — tool calls and results are preserved, not just conversation text
- **`metadata` field** carries raw source data that doesn't fit the schema (like CASS's `extra` field)
- **`source_tool` and `source_id`** — provenance tracking back to the original session
- **Append-only** — new messages appended, never overwritten
- **One file per session** — `~/.jor/sessions/<id>.jsonl`

### File Structure

```
~/.jor/
├── config.json            # Global Jor config (discovered tool paths, preferences)
├── index.json             # Session index (id, tool, title, project, date, summary)
└── sessions/
    ├── jor-abc123.jsonl    # Converted session
    └── jor-def456.jsonl
```

## 6. Session Discovery

### Scanner

The scanner iterates over registered connectors and collects sessions.

```python
class Connector(Protocol):
    def name(self) -> str: ...
    def detect(self) -> bool: ...
    def scan(self) -> list[NormalizedSession]: ...
```

Each connector:
1. Checks if the tool is installed (detect)
2. Scans known paths for session files (scan)
3. Parses native format into `NormalizedSession` (same structure as `JorMessage` list)

### Claude Code Connector

**Source:** `~/.claude/projects/*/sessions/*.jsonl`

**Native format:** JSONL, each line has:
- `type`: `"user"` | `"assistant"` | `"tool_use"` | `"tool_result"`
- `message.role`, `message.content` (string or content block array)
- `timestamp`, `sessionId`, `cwd`, `gitBranch`
- Content blocks with `type: "tool_use"` contain `name`, `input`, `id`
- Content blocks with `type: "tool_result"` contain `tool_use_id`, `content`

**Translation:** Map `type` → `role`, extract tool calls from content blocks, convert `cwd` to workspace path, preserve `sessionId` as `source_id`, store `gitBranch` in metadata.

### Codex Connector

**Source:** `~/.codex/sessions/rollout-*.jsonl`

**Native format:** JSONL using OpenAI chat completion message format:
- `role`: `"user"` | `"assistant"` | `"system"` | `"tool"`
- `content`: string
- `tool_calls`: array of `{id, type: "function", function: {name, arguments}}`
- Tool results: `role: "tool"` with `tool_call_id` and `content`

**Translation:** Direct mapping — OpenAI's format is close to Jor's. Extract `tool_calls` as-is, map `role: "tool"` to `role: "tool_result"`, preserve session metadata.

## 7. Session Index

`~/.jor/index.json` — a JSON file mapping session IDs to metadata for fast listing and filtering.

```json
{
  "version": 1,
  "sessions": [
    {
      "id": "jor-abc123",
      "tool": "claude_code",
      "source_id": "original-session-uuid",
      "source_path": "~/.claude/projects/-hash/sessions/uuid.jsonl",
      "title": "Auth module refactor",
      "project": "/Users/foo/code/my-app",
      "started_at": "2026-04-20T10:30:00Z",
      "ended_at": "2026-04-20T11:45:00Z",
      "message_count": 42,
      "model": "claude-sonnet-4-6",
      "provider": "anthropic",
      "summary": "Refactored auth middleware to use JWT tokens..."
    }
  ],
  "last_scan": "2026-04-25T10:00:00Z"
}
```

**Title generation:** First user message, truncated to 80 chars. If the source tool has a title (Continue.dev does), use that.

**Summary generation:** Not in Phase 1. Use the first user message as a stand-in. Phase 2 could use an LLM to generate summaries.

## 8. `jor_open` — Session Continuation

When the user calls `jor_open`, the MCP returns the session formatted for the current tool to continue.

**Format options:**

### `"summary"` (default)
Returns the full conversation as readable markdown. No AI summarization in Phase 1 — just a structured rendering of all messages. For long sessions, truncate to the last 50 messages with a note about omitted history.

```
# Continuing session: Auth module refactor
# Originally in: Claude Code | Model: claude-sonnet-4-6
# Project: /Users/foo/code/my-app
# Date: 2026-04-20

## Conversation (42 messages, showing key turns)

**User:** Refactor the auth middleware to use JWT tokens instead of session cookies...
**Assistant:** I'll restructure the auth module. Here's my plan...
[... condensed conversation ...]

## Files Referenced
- src/auth/middleware.ts
- src/auth/jwt.ts
- tests/auth.test.ts
```

### `"full"`
Returns the complete Jor JSONL content. Useful for tools that can ingest structured history.

## 9. Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| CLI framework | `click` or `argparse` (stdlib) |
| Schema/types | Pydantic |
| Testing | pytest |
| Package manager | uv |
| Distribution | PyPI (`jor`) |
| SQLite parsing | stdlib `sqlite3` |
| JSON/JSONL | stdlib `json` |
| File discovery | stdlib `pathlib` |

**Minimal dependencies: Pydantic + optionally click for CLI.**

## 10. Project Structure

```
jor/
├── src/
│   └── jor/
│       ├── __init__.py
│       ├── cli.py                    # CLI entry point (jor discover/list/convert/open)
│       ├── discovery/
│       │   ├── __init__.py
│       │   ├── scanner.py            # Orchestrates connectors, builds index
│       │   ├── index.py              # Read/write ~/.jor/index.json
│       │   └── connectors/
│       │       ├── __init__.py
│       │       ├── base.py           # Connector protocol
│       │       ├── claude_code.py    # Claude Code JSONL parser (native → Jor)
│       │       └── codex.py          # Codex JSONL parser (native → Jor)
│       ├── session/
│       │   ├── __init__.py
│       │   ├── schema.py             # JorMessage, ToolCall, ToolResult (Pydantic)
│       │   ├── reader.py             # Read Jor sessions, format for output
│       │   └── writers/
│       │       ├── __init__.py
│       │       ├── base.py           # Writer protocol
│       │       ├── claude_code.py    # Jor → Claude Code native session file
│       │       └── codex.py          # Jor → Codex native session file
│       ├── launchers/
│       │   ├── __init__.py
│       │   ├── base.py              # Launcher protocol
│       │   ├── claude_code.py       # Write session + run `claude --resume`
│       │   └── codex.py             # Write session + run `codex --resume`
│       └── utils.py                  # Timestamp parsing, path normalization
├── skill/
│   └── jor.md                       # Claude Code skill wrapping the CLI
├── tests/
│   ├── conftest.py
│   ├── test_scanner.py
│   ├── test_claude_code_connector.py
│   ├── test_codex_connector.py
│   ├── test_claude_code_writer.py
│   ├── test_codex_writer.py
│   ├── test_schema.py
│   └── fixtures/                     # Sample session files for testing
│       ├── claude_code_session.jsonl
│       └── codex_session.jsonl
├── pyproject.toml                    # uv config, PyPI metadata, [project.scripts] for CLI
├── README.md
├── LICENSE
└── docs/
```

**Entry points in `pyproject.toml`:**
```toml
[project.scripts]
jor = "jor.cli:main"
```

## 11. Testing Strategy

- **Unit tests** for each connector: given a fixture file in native format, verify correct translation to Jor schema
- **Unit tests** for the session schema: validate JSONL serialization/deserialization round-trips
- **Integration test** for scanner: given a mock filesystem with sessions from multiple tools, verify discovery and indexing
- **Integration test** for `jor_open`: verify session loads and formats correctly for continuation
- **Fixture files** with real (anonymized) session data from Claude Code and Codex

## 12. Success Criteria

1. `pip install jor` (or `uvx jor`) installs cleanly, provides the `jor` CLI
2. `jor discover` finds sessions from Claude Code and Codex on the local machine
3. `jor list` shows sessions with tool, title, date, project
4. `jor list --tool codex` filters correctly
5. `jor convert 1` writes a Claude Code native session file and prints the resume command
6. `jor convert 1 --codex` writes a Codex native session file and prints the resume command
7. `jor open 1` converts and launches `claude --resume` with native conversation history
8. Claude Code skill wraps the CLI — user can discover and convert sessions from within a session
9. The whole thing works offline with zero configuration beyond installation
10. Demo-ready in under 1 week
