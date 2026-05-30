# Claude Code Session Format

## Overview

Claude Code is Anthropic's CLI agent. Sessions are append-only JSONL files — one JSON record per line, each representing a message, system event, or metadata snapshot. The conversation is a linked list threaded by UUIDs.

## Storage Layout

```
~/.claude/
├── projects/
│   └── -Users-foo-code-bar/           # project dir (path with / → -)
│       ├── 242e743b-...830.jsonl      # session file (named by sessionId)
│       └── 242e743b-...830/           # session artifacts dir
│           └── subagents/
│               ├── agent-a0a3c23af.jsonl      # subagent session
│               └── agent-a0a3c23af.meta.json  # subagent metadata
├── settings.json
└── history.jsonl
```

- **Project dirs** are derived from the absolute working directory: `/Users/foo/code/bar` → `-Users-foo-code-bar`
- **Session files** are named `<sessionId>.jsonl` where sessionId is a UUID
- **Subagent sessions** live in `<sessionId>/subagents/`. Each has a `.jsonl` (conversation) and `.meta.json` (type + description)

## File Format

Each line is a self-contained JSON record. Every record has a `type` field that determines its structure.

**Two categories of records:**

| Category | Types | Purpose |
|----------|-------|---------|
| **Conversation** | `user`, `assistant` | Messages in the chat (including tool use/results) |
| **Metadata** | `system`, `file-history-snapshot`, `queue-operation`, `custom-title`, `agent-name`, `last-prompt` | Bookkeeping, not part of the conversation |

## Message Types & Content Blocks

### Common Fields

Every conversation record (`user`, `assistant`) shares these top-level fields:

```json
{
  "type": "user | assistant",
  "uuid": "dbe98558-...",
  "parentUuid": "7c5ff64c-... | null",
  "isSidechain": false,
  "sessionId": "242e743b-...",
  "timestamp": "2026-05-26T10:34:47.321Z",
  "cwd": "/Users/foo/code/bar",
  "version": "2.1.87",
  "userType": "external",
  "entrypoint": "cli | sdk-cli",
  "message": { "role": "...", "content": "..." }
}
```

Optional fields that appear on some records:
- `promptId` — groups all records within one user turn (user msg + all tool cycles until next user msg)
- `gitBranch` — git branch at time of message
- `slug` — auto-generated human-readable session name (e.g. `"rustling-painting-spark"`)
- `requestId` — Anthropic API request ID (assistant messages only)
- `model` — model name, only on assistant messages (e.g. `"claude-opus-4-6"`)
- `sourceToolAssistantUUID` — on tool results, points to the assistant message that issued the tool_use
- `agentId` — on subagent messages, identifies which agent

### User Message (plain text)

```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": "Fix the bug in parser.py"
  }
}
```

`content` is a plain string.

### Assistant Message (text only)

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "model": "claude-sonnet-4-6",
    "id": "msg_018K77fBKj...",
    "type": "message",
    "content": [
      { "type": "text", "text": "I'll fix that bug." }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "usage": { "input_tokens": 3, "output_tokens": 27, "..." : "..." }
  }
}
```

Key points:
- `message.content` is always an **array of content blocks** (never a plain string)
- `message.type` is always `"message"` (not to be confused with the outer `type`)
- `stop_reason`: `"end_turn"` (finished), `"tool_use"` (wants to call a tool), or `null` (streaming/partial)
- `usage` tracks token counts including cache hits

### Assistant Message (with tool use)

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_017J9LMH...",
        "name": "Read",
        "input": { "file_path": "/path/to/file.py" }
      }
    ],
    "stop_reason": "tool_use"
  }
}
```

An assistant message can have **mixed content blocks** — text and tool_use interleaved:

```json
"content": [
  { "type": "text", "text": "Let me read that file." },
  { "type": "tool_use", "id": "toolu_...", "name": "Read", "input": { ... } },
  { "type": "text", "text": "And also check this." },
  { "type": "tool_use", "id": "toolu_...", "name": "Bash", "input": { ... } }
]
```

Tool use blocks may include a `caller` field:
```json
{ "type": "tool_use", "id": "...", "name": "Read", "input": { ... },
  "caller": { "type": "direct" } }
```

### Assistant Message (with thinking)

Extended thinking appears as a content block:

```json
"content": [
  {
    "type": "thinking",
    "thinking": "The user wants me to...",
    "signature": "ErsDCmMIDhgCKkBJ3bLV..."
  },
  { "type": "text", "text": "I'll do that." }
]
```

`signature` is a cryptographic signature for thinking block verification. Thinking blocks always come first in the content array.

### Tool Result

Tool results are **user-type records** with content blocks of type `tool_result`. This is because in the Anthropic API, tool results are sent as user messages.

```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_017J9LMH...",
        "content": "file contents here...",
        "is_error": false
      }
    ]
  },
  "sourceToolAssistantUUID": "7c5ff64c-...",
  "toolUseResult": { ... }
}
```

**Critical:** `type: "user"` at the record level, but `content[].type: "tool_result"` inside. This is the main source of ambiguity — you must inspect `message.content` to distinguish a real user message from a tool result.

**Disambiguation rule:** If `message.content` is an array and any block has `"type": "tool_result"`, the record is a tool result, not a user message.

The `toolUseResult` field (separate from `message`) carries structured metadata about what happened:

```json
"toolUseResult": {
  "stdout": "...",
  "stderr": "",
  "interrupted": false
}
```

For file operations, `toolUseResult` has richer structure:

```json
// File edit
"toolUseResult": {
  "type": "update",
  "filePath": "/path/to/file.py",
  "content": "new file contents...",
  "structuredPatch": [ { "oldStart": 1, "oldLines": 3, "newStart": 1, "newLines": 46, "lines": [...] } ],
  "originalFile": "old file contents..."
}

// File creation
"toolUseResult": {
  "type": "create",
  "filePath": "/path/to/new_file.py",
  "content": "file contents...",
  "structuredPatch": [],
  "originalFile": null
}

// Cached read (file unchanged)
"toolUseResult": {
  "type": "file_unchanged",
  "file": { "filePath": "/path/to/file.py" }
}
```

A single tool result record can contain **multiple tool_result blocks** (one per tool call in the preceding assistant message):

```json
"content": [
  { "type": "tool_result", "tool_use_id": "toolu_aaa...", "content": "result 1" },
  { "type": "tool_result", "tool_use_id": "toolu_bbb...", "content": "result 2" }
]
```

Tool result content can itself be an array of typed blocks:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_...",
  "content": [
    { "type": "tool_reference", "tool_name": "TaskCreate" },
    { "type": "tool_reference", "tool_name": "TaskUpdate" }
  ]
}
```

## Message Linking & Ordering

Conversation order is maintained by a **linked list** via `uuid` and `parentUuid`:

```
Record 1: uuid="aaa", parentUuid=null        ← first message
Record 2: uuid="bbb", parentUuid="aaa"
Record 3: uuid="ccc", parentUuid="bbb"
...
```

This is what `--resume` uses to reconstruct the conversation. `isSidechain=false` marks records that are part of the main conversation thread.

**Subagent records** have `isSidechain=true` and an `agentId` field. They live in separate files under `<sessionId>/subagents/`.

**Within a single turn** (one user prompt → assistant response cycle), records share the same `promptId`.

## Session Metadata Records

These records are interspersed in the JSONL but are **not conversation messages**. They track operational state.

### system

```json
{
  "type": "system",
  "subtype": "turn_duration | stop_hook_summary | api_error | local_command",
  "timestamp": "...",
  "uuid": "...",
  "parentUuid": "..."
}
```

Subtypes:
- `turn_duration` — timing: `{ "durationMs": 62231, "messageCount": 29 }`
- `stop_hook_summary` — hook execution results: `{ "hookCount": 1, "hookErrors": [...] }`
- `api_error` — retry info: `{ "retryInMs": 580.99, "retryAttempt": 1, "maxRetries": 10 }`
- `local_command` — CLI slash commands: `{ "content": "<command-name>/resume</command-name>..." }`

### file-history-snapshot

Tracks file backups for undo capability:

```json
{
  "type": "file-history-snapshot",
  "messageId": "dbe98558-...",
  "snapshot": {
    "trackedFileBackups": {
      "README.md": {
        "backupFileName": "30020b029f985625@v1",
        "version": 1,
        "backupTime": "2026-05-23T10:51:35.979Z"
      }
    }
  },
  "isSnapshotUpdate": true
}
```

### Other metadata types

```json
{ "type": "custom-title", "customTitle": "fix-jor-bugs", "sessionId": "..." }
{ "type": "agent-name", "agentName": "fix-jor-bugs", "sessionId": "..." }
{ "type": "last-prompt", "lastPrompt": "Fix the parser", "sessionId": "..." }
{ "type": "queue-operation", "operation": "enqueue", "content": "...", "sessionId": "..." }
```

## Session Lifecycle

1. **Creation** — User runs `claude` or `claude --resume <id>`. A new session file is created at `~/.claude/projects/<project>/<sessionId>.jsonl`. The first record is the user's message with `parentUuid: null`.

2. **Growth** — Each interaction appends records. A typical turn:
   - `user` record (the prompt, `parentUuid` → previous record)
   - `file-history-snapshot` (backup state before changes)
   - `assistant` record (response, possibly with `tool_use`)
   - `user` record (tool results, `type: "tool_result"` in content)
   - ... (tool loop repeats)
   - `assistant` record (final answer, `stop_reason: "end_turn"`)
   - `system` record (`subtype: "turn_duration"`)

3. **Resume** — `claude --resume <sessionId>` loads the JSONL, reconstructs the linked list via UUIDs, and continues. The `local_command` system record marks a resume point.

4. **No explicit close** — Sessions are never deleted or marked as ended. They're just files that stop being appended to.

## Resume Mechanism

`claude --resume <sessionId>` reconstructs the conversation by:
1. Reading the session JSONL
2. Following the `uuid`/`parentUuid` chain to build ordered conversation
3. Filtering to `isSidechain=false` records
4. Skipping metadata types (`system`, `file-history-snapshot`, etc.)
5. Sending the conversation to the API as context

When **writing** a session for resume, each record must have:
- `uuid` — unique UUID for this record
- `parentUuid` — the `uuid` of the immediately preceding record (`null` for first)
- `isSidechain` — `false` for main conversation
- `sessionId` — consistent across all records

## Gotchas

1. **Tool results masquerade as user messages.** The outer `type` is `"user"` but the content is tool results. You must check `message.content[].type == "tool_result"` to distinguish them. This is the #1 source of bugs.

2. **Assistant content is always an array.** Unlike user messages (which can be a plain string), assistant `message.content` is always an array of typed blocks. Never assume it's a string.

3. **Empty/partial assistant records.** During streaming, intermediate assistant records are written with `stop_reason: null` and incomplete content. Skip records with no text blocks and no tool_use blocks.

4. **Multiple tool calls per message.** An assistant can issue several tool_use blocks in one message. The corresponding tool result record has one `tool_result` block per call, matched by `tool_use_id`.

5. **Thinking blocks contain signatures.** The `signature` field on thinking blocks is opaque and must be preserved for verification, but has no semantic meaning for conversion.

6. **`toolUseResult` is bonus metadata.** The `toolUseResult` field on tool result records contains structured data (diffs, file contents) that the `message.content` doesn't have. For conversion, `message.content` is authoritative; `toolUseResult` is supplementary.

7. **Subagent sessions are separate files.** The main session references agents via `agentId`, but their conversation lives in `subagents/agent-<id>.jsonl`. These are currently ignored by Jor.

8. **`entrypoint` varies.** `"cli"` for direct use, `"sdk-cli"` for SDK-launched sessions (e.g., Ralph). Doesn't affect the format.

9. **No explicit `tool_result` record type.** Despite the schema.json listing `"tool_result"` as a valid `type`, real sessions encode tool results as `type: "user"` records. The `type: "tool_result"` at the record level is rare/legacy.

## Jor Transformation Notes

### What to read
- Only `user` and `assistant` record types carry conversation content
- Skip `system`, `file-history-snapshot`, `custom-title`, `agent-name`, `last-prompt`, `queue-operation`

### User messages
- If `message.content` is a string → plain user message
- If `message.content` is an array with `tool_result` blocks → split into one `JorMessage(role="tool_result")` per block
- If `message.content` is an array with `text` blocks → join text, treat as user message

### Assistant messages
- Extract text from `{ "type": "text" }` blocks, join with newlines
- Extract tool calls from `{ "type": "tool_use" }` blocks → `ToolCall(id, name, input)`
- Skip `{ "type": "thinking" }` blocks (not portable across tools)
- Skip messages with no text and no tool calls (streaming artifacts)

### Tool results
- `tool_use_id` → `ToolResult.tool_call_id`
- `content` (string) → `ToolResult.content`
- `is_error` → `ToolResult.is_error`
- Ignore `toolUseResult` structured metadata (not part of the conversation)

### Timestamps
- Preserve `timestamp` from each record as-is (already ISO 8601 UTC)

### Provenance
- `source_tool = "claude"`
- `source_id = record["sessionId"]`
- `model = message.get("model")` (assistant records only)
- `provider = "anthropic"`

### Writing back to Claude format
- Must generate `uuid`/`parentUuid` chain for resume to work
- Tool results must be encoded as `type: "user"` records with `tool_result` content blocks
- Assistant messages need a synthetic `message.id` (format: `msg_<24 hex chars>`)
- Set `stop_reason` to `"tool_use"` if tool calls present, else `"end_turn"`
- `isSidechain` must be `false` on all records
