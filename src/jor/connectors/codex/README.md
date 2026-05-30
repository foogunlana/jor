# Codex Session Format

## Overview

Codex is OpenAI's CLI agent. Sessions are JSONL files where every record is wrapped in a `{timestamp, type, payload}` envelope. Unlike Claude's single-purpose records, Codex uses distinct envelope types to separate model context (what the LLM sees) from TUI display (what the user sees) from operational metadata.

## Storage Layout

```
~/.codex/
├── sessions/
│   ├── rollout-<uuid>.jsonl                                          # legacy flat
│   └── 2026/03/03/                                                   # date-nested
│       └── rollout-2026-03-03T10-46-21-019cb34e-...-bcd3.jsonl
├── state_5.sqlite        # thread registry (required for history UI)
├── session_index.jsonl    # lightweight index
├── config.toml            # main config
└── history.jsonl          # command history
```

- **Session files** follow the pattern `rollout-<timestamp>-<uuid>.jsonl` inside date-nested dirs (`YYYY/MM/DD/`)
- **Older sessions** may be flat under `sessions/` without date nesting
- **SQLite** (`state_5.sqlite`) is the authoritative thread registry — sessions must be registered here to appear in the Codex history UI
- **`session_index.jsonl`** is a lightweight index with `{id, thread_name, updated_at}` per line

## File Format

Every line is a JSON envelope with three fields:

```json
{
  "timestamp": "2026-03-03T10:46:55.944Z",
  "type": "session_meta | response_item | event_msg | turn_context",
  "payload": { ... }
}
```

### Envelope Types

| Type | Purpose | Used by |
|------|---------|---------|
| `session_meta` | One-time session metadata | Both model and TUI |
| `response_item` | Model context — messages, tool calls, tool results | LLM |
| `event_msg` | TUI display — user/agent messages, reasoning, tokens | UI |
| `turn_context` | Per-turn execution config (model, policies, effort) | Runtime |

**For conversion, only `session_meta` and `response_item` carry conversation content.** The other types are operational metadata.

## Record Types in Detail

### session_meta

Appears once, usually the first record. Contains global session info.

```json
{
  "timestamp": "2026-03-03T10:46:55.944Z",
  "type": "session_meta",
  "payload": {
    "id": "019cb34e-55f7-75d2-a509-3a205bc9bcd3",
    "timestamp": "2026-03-03T10:46:21.434Z",
    "cwd": "/Users/foo/code/bar",
    "originator": "codex_cli_rs",
    "cli_version": "0.106.0",
    "source": "cli",
    "model_provider": "openai",
    "base_instructions": { "text": "..." },
    "git": {
      "commit_hash": "a0a86e99...",
      "branch": "main",
      "repository_url": "https://github.com/foo/bar.git"
    }
  }
}
```

- `payload.id` is the session UUID (used as thread ID in SQLite)
- `payload.timestamp` is session creation time (may differ from envelope `timestamp`)
- `base_instructions` contains system prompt / AGENTS.md content
- `git` captures repo state at session start

### response_item — message

Three roles: `user`, `assistant`, `developer`.

**User message:**
```json
{
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "user",
    "content": [
      { "type": "input_text", "text": "Fix the bug in parser.py" }
    ]
  }
}
```

**Assistant message:**
```json
{
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "assistant",
    "content": [
      { "type": "output_text", "text": "I'll fix that bug." }
    ],
    "phase": "commentary"
  }
}
```

**Developer message (system prompt):**
```json
{
  "type": "response_item",
  "payload": {
    "type": "message",
    "role": "developer",
    "content": [
      { "type": "input_text", "text": "<permissions>...</permissions>" }
    ]
  }
}
```

Key points:
- Content is always an array of typed blocks
- User/developer blocks use `"input_text"`, assistant blocks use `"output_text"`
- Content can also be a plain string (rare, but handle it)
- `phase` on assistant messages can be `"commentary"` — informational, not a final answer

### response_item — function_call

Represents the assistant requesting a tool invocation.

```json
{
  "type": "response_item",
  "payload": {
    "type": "function_call",
    "name": "exec_command",
    "call_id": "call_PQvCCIKw...",
    "arguments": "{\"cmd\":\"rg --files\"}"
  }
}
```

- `arguments` is a **JSON-encoded string**, not a dict. Must be parsed with `json.loads()`.
- `call_id` links this to its corresponding `function_call_output`
- Common function names: `exec_command`, `read_file`, `write_file`, `list_directory`

### response_item — function_call_output

The result of a tool invocation.

```json
{
  "type": "response_item",
  "payload": {
    "type": "function_call_output",
    "call_id": "call_PQvCCIKw...",
    "output": "Chunk ID: fa2824\nWall time: 0.0510 seconds\nProcess exited with code 0\n..."
  }
}
```

- `call_id` matches the `function_call` it responds to
- `output` is a string (may also be an array of content blocks in some cases)

### turn_context

Per-turn configuration snapshot. One per user turn.

```json
{
  "type": "turn_context",
  "payload": {
    "turn_id": "019cb34e-dc9b-...",
    "cwd": "/Users/foo/code/bar",
    "approval_policy": "on-request",
    "sandbox_policy": {
      "type": "workspace-write",
      "network_access": false
    },
    "model": "gpt-5.3-codex",
    "personality": "pragmatic",
    "effort": "high",
    "summary": "auto",
    "truncation_policy": { "mode": "tokens", "limit": 25000 },
    "collaboration_mode": {
      "mode": "default",
      "settings": {
        "model": "gpt-5.3-codex",
        "reasoning_effort": "high"
      }
    }
  }
}
```

Not used for conversion, but captures what model/settings were active for each turn.

### event_msg types

Event messages drive the TUI. All share the envelope `{ "type": "event_msg", "payload": { "type": "...", ... } }`.

| `payload.type` | Purpose | Key fields |
|-----------------|---------|------------|
| `user_message` | Display user input | `message`, `images`, `local_images` |
| `agent_message` | Display assistant text | `text` |
| `agent_reasoning` | Display chain-of-thought | `text` |
| `token_count` | Token usage tracking | `info.total_token_usage`, `info.last_token_usage` |
| `task_started` | Turn began | `turn_id`, `model_context_window` |
| `task_complete` | Turn finished | `turn_id`, `last_agent_message` |
| `turn_aborted` | Turn was cancelled | `turn_id` |

**Example — user_message:**
```json
{
  "type": "event_msg",
  "payload": {
    "type": "user_message",
    "message": "Fix the bug",
    "images": [],
    "local_images": [],
    "text_elements": []
  }
}
```

**Example — token_count:**
```json
{
  "type": "event_msg",
  "payload": {
    "type": "token_count",
    "info": {
      "total_token_usage": {
        "input_tokens": 9730,
        "cached_input_tokens": 6656,
        "output_tokens": 359,
        "reasoning_output_tokens": 240,
        "total_tokens": 10089
      },
      "model_context_window": 258400
    }
  }
}
```

## Message Linking & Ordering

Codex uses **sequential file order** — no linked-list mechanism. Records are simply read top-to-bottom. There is no UUID chain.

Within the file, the typical sequence for one turn is:

```
turn_context          — config for this turn
event_msg/task_started
event_msg/user_message
response_item/message (user)
response_item/message (developer)  — system prompt, injected each turn
event_msg/agent_reasoning          — one or more
response_item/function_call        — tool request
response_item/function_call_output — tool result
event_msg/agent_reasoning
response_item/message (assistant)  — final response
event_msg/agent_message
event_msg/token_count
event_msg/task_complete
```

The same content often appears in **both** a `response_item` (for the model) and an `event_msg` (for the TUI). They're not duplicates — they serve different consumers.

## Session Lifecycle

1. **Creation** — User runs `codex`. A `session_meta` record is written first. The session is registered in `state_5.sqlite` with a thread row.

2. **Growth** — Each turn appends a block of records: `turn_context`, event messages, response items. The SQLite `threads.updated_at` is bumped.

3. **Resume** — Codex can resume from the JSONL by replaying `response_item` records to reconstruct model context. Event messages are replayed for TUI display.

4. **No explicit close** — Like Claude, sessions just stop being written to. `task_complete` event marks the end of a turn, not the session.

## SQLite Thread Registry

Sessions must be registered in `state_5.sqlite` to appear in the history UI:

```sql
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    rollout_path TEXT NOT NULL,
    created_at INTEGER NOT NULL,       -- unix seconds
    updated_at INTEGER NOT NULL,       -- unix seconds
    source TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    cwd TEXT NOT NULL,
    title TEXT NOT NULL,
    sandbox_policy TEXT NOT NULL,
    approval_mode TEXT NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    has_user_event INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    archived_at INTEGER,
    git_sha TEXT,
    git_branch TEXT,
    git_origin_url TEXT,
    cli_version TEXT NOT NULL DEFAULT '',
    first_user_message TEXT NOT NULL DEFAULT '',
    agent_nickname TEXT,
    agent_role TEXT,
    memory_mode TEXT NOT NULL DEFAULT 'enabled',
    model TEXT,
    reasoning_effort TEXT,
    agent_path TEXT,
    created_at_ms INTEGER,             -- unix milliseconds
    updated_at_ms INTEGER,             -- unix milliseconds
    thread_source TEXT,
    preview TEXT NOT NULL DEFAULT ''
);
```

Other tables:
- `thread_spawn_edges` — parent-child thread relationships
- `stage1_outputs` — analysis results
- `agent_jobs` — batch job tracking

## Resume Mechanism

Codex resumes by:
1. Loading the JSONL file referenced by `threads.rollout_path`
2. Replaying all `response_item` records to rebuild the model context window
3. Replaying `event_msg` records for TUI display
4. Applying `turn_context` settings from the last turn

There is no `--resume <id>` flag equivalent to Claude's. Resume is handled internally via the thread UI.

## Gotchas

1. **`arguments` is a JSON string, not a dict.** In `function_call` payloads, `arguments` is `"{\"cmd\":\"ls\"}"` — a serialized JSON string. Must `json.loads()` it. If it's malformed, fall back to `{"raw": arguments_string}`.

2. **Dual representation of messages.** The same user message appears as both `response_item/message` (for the model) and `event_msg/user_message` (for the TUI). When reading, use `response_item` records. When writing, you must emit **both** or the TUI won't show the conversation.

3. **`developer` role ≠ `system`.** Codex uses `"developer"` where other tools use `"system"`. Map `developer` → `system` when reading, `system` → `developer` when writing.

4. **Content block type names differ by role.** User/developer messages use `{"type": "input_text", "text": "..."}`. Assistant messages use `{"type": "output_text", "text": "..."}`. Using the wrong type may confuse the model on resume.

5. **`output` in function_call_output can be an array.** Usually a string, but sometimes an array of content blocks. Handle both.

6. **SQLite registration is required.** Writing a JSONL file alone won't make the session visible. You must also INSERT into `state_5.sqlite`'s `threads` table with correct timestamps, paths, and metadata.

7. **Date-nested vs flat paths.** Older sessions are at `sessions/rollout-<uuid>.jsonl`. Newer ones are at `sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl`. Discovery must glob both patterns.

8. **`session_meta.payload.timestamp` vs envelope `timestamp`.** The payload timestamp is the session creation time. The envelope timestamp is when the record was written. They can differ by seconds.

9. **Lenient JSON parsing.** Some Codex session lines may be malformed (truncated writes, crashes). Unlike Claude (where strict parsing is safe), Codex sessions should be parsed leniently — skip bad lines rather than failing the whole session.

10. **`response_item` is the only type with conversation content.** `turn_context` and `event_msg` are metadata/display. `session_meta` is one-time config. Only `response_item` records carry what the model actually saw.

## Jor Transformation Notes

### What to read
- `session_meta` — extract session ID, project path, start time, git info
- `response_item` records only — these carry conversation content
- Skip `event_msg`, `turn_context` entirely

### response_item/message
- `role: "user"` → `JorMessage(role="user")`
- `role: "assistant"` → `JorMessage(role="assistant")`
- `role: "developer"` → `JorMessage(role="system")`
- Extract text from content blocks (both `input_text` and `output_text` have a `text` field)
- Content may also have an `output` field instead of `text` — check both

### response_item/function_call
- `name` → `ToolCall.name`
- `call_id` → `ToolCall.id`
- `json.loads(arguments)` → `ToolCall.input` (with `{"raw": ...}` fallback)
- Wrap in `JorMessage(role="assistant", tool_calls=[...])`

### response_item/function_call_output
- `call_id` → `ToolResult.tool_call_id`
- `output` → `ToolResult.content` (extract text if array)
- Wrap in `JorMessage(role="tool_result", tool_result=...)`

### Metadata extraction
- `source_tool = "codex"`
- `source_id = session_meta.payload.id` (fall back to file stem)
- `started_at = session_meta.payload.timestamp`
- `project = session_meta.payload.cwd`
- `title` = first `response_item/message` with `role: "user"`, truncated to 80 chars
- `provider = "openai"` (from `session_meta.payload.model_provider`)

### Writing back to Codex format
- Must emit `session_meta` as first record
- For each message, emit **both** `event_msg` and `response_item` records
- Event messages: `user_message` for user, `agent_message` for assistant
- Use `input_text` type for user/developer content blocks, `output_text` for assistant
- Assistant messages with tool calls become **multiple records**: one `function_call` per tool call, plus optionally a `message` record if there's text content
- Create date-nested path: `sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl`
- Register in `state_5.sqlite` threads table with all required fields
