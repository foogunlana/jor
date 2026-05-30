---
name: connector-readme
description: Generate a README.md documenting how an AI CLI tool manages sessions, for a Jor connector. Use when a new connector has been written (or is being written) and needs session format documentation. Triggers on "document this connector", "write a connector readme", "generate session docs", or when a new connector directory exists under src/jor/connectors/ without a README.md.
---

# Connector README Generator

Generate a `README.md` in `src/jor/connectors/<tool>/` that documents how the target AI CLI tool manages sessions — thorough enough that someone could write the connector from scratch.

## Research Phase

Before writing, gather all source material. Use parallel agents where possible.

### 1. Read the connector code

Read `src/jor/connectors/<tool>/connector.py` in full. Extract:
- What record types are handled in `from_record()`
- What fields are extracted in `extract_metadata()`
- What normalization happens (role mapping, content block parsing, JSON fallbacks)
- What `to_record()` produces (writing format)
- What `write_session()` does beyond writing JSONL (SQLite, UUID chains, event records)
- The class attributes: `TOOL_NAME`, `GLOB_PATTERN`, `DETECT_PATH`, `STRICT_JSON`, `RESUME_CMD`

### 2. Read the schema.json if it exists

Check `src/jor/connectors/<tool>/schema.json` for the declared record structure.

### 3. Read real session files

Find real session files on disk using the tool's home directory and glob pattern from the connector. Read 50-100 lines from 1-2 sessions that have a variety of message types (user, assistant, tool use, tool results). Note every field present in real data that isn't in the connector code or schema.

### 4. Check for auxiliary storage

Look for SQLite databases, index files, config files, or other non-JSONL storage in the tool's home directory. If SQLite exists, dump the schema of relevant tables.

### 5. Read existing READMEs for style

Read the existing READMEs at `src/jor/connectors/claude/README.md` and `src/jor/connectors/codex/README.md` to match tone, depth, and formatting conventions.

## Writing Phase

Write `src/jor/connectors/<tool>/README.md` with these sections in order:

### Required Sections

**1. Overview** (2-3 sentences)
- What the tool is, who makes it
- Format philosophy in one phrase (e.g. "append-only JSONL", "envelope-wrapped records")

**2. Storage Layout**
- ASCII tree showing directory structure under the tool's home dir
- Bullet points explaining naming conventions, path derivation, auxiliary files

**3. File Format**
- Top-level record structure (what fields every line has)
- Table categorizing record types by purpose (conversation vs metadata vs display)

**4. Message Types & Content Blocks**
- Common fields shared across record types (with JSON example)
- One subsection per message type with a real JSON example:
  - User message (plain text)
  - Assistant message (text only)
  - Assistant message (with tool use)
  - Tool result
  - Any tool-specific types (thinking blocks, reasoning, function calls)
- Document content block polymorphism: where `content` can be string vs array, what block types exist, what fields each block type has
- Call out the gotcha if tool results masquerade as a different role

**5. Message Linking & Ordering**
- How conversation order is maintained (linked list? sequential? turn IDs?)
- What fields are involved and how they chain

**6. Session Lifecycle**
- Creation (what triggers it, what first record looks like)
- Growth (typical sequence of records per turn)
- Resume (how the tool reconstructs from the file)
- Close (explicit or implicit)

**7. Resume Mechanism**
- The exact command or process used to resume
- What data structures must be present (UUID chains, SQLite rows, etc.)
- What happens when writing a session for resume

**8. Gotchas**
- Numbered list, each starting with a bold one-line summary
- Focus on things that cause bugs: type ambiguity, encoding surprises, required-but-not-obvious steps, format variations across versions

**9. Jor Transformation Notes**
- Organized by direction: reading (native → Jor) and writing (Jor → native)
- **What to read**: which record types carry conversation content, which to skip
- **Per message type**: how to map fields to `JorMessage` (role, content, tool_calls, tool_result)
- **Metadata extraction**: source_tool, source_id, timestamps, model, provider
- **Writing back**: what extra records/registrations are needed beyond JSONL

### Style Rules

- Terse. No filler. Lead with the fact.
- Use JSON examples from real session data, not hypothetical. Redact sensitive content but keep structure intact.
- Use `code blocks` for field names, file paths, and JSON.
- Use tables for categorization, not prose lists.
- Bold the first phrase of each gotcha item.
- Keep the Jor Transformation Notes practical — someone should be able to implement `from_record()` and `to_record()` from this section alone.

## Reference

The Jor schema that all connectors target:

```
JorMessage: id, role (user|assistant|system|tool_result), content, tool_calls?, tool_result?, files?, model?, provider?, timestamp?, metadata?, source_tool?, source_id?
ToolCall: id, name, input (dict)
ToolResult: tool_call_id, content, is_error
```

Base connector interface: `from_record()`, `extract_metadata()`, `to_record()`, `resume_command()`, `write_session()`.
