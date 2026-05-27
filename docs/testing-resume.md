# Testing Cross-Tool Session Resume

## How to verify a converted session works

### Claude Code

**Check context is preserved** (non-interactive):
```bash
claude --resume <session-id> -p "what were we talking about?"
```

**Check history is visible in UI** (interactive capture):
```bash
timeout 10 script -q /tmp/cc-test.txt sh -c 'claude --resume <session-id>; exit'
# Then inspect the output:
cat /tmp/cc-test.txt | strings | grep -i "<keyword from conversation>"
```

### Codex

**Check context is preserved** (non-interactive):
```bash
codex exec resume <session-id> "what were we talking about?"
```

**Check history is visible** (requires TTY):
```bash
codex resume <session-id>
```

## Minimum viable Claude Code session format

Records need these fields for `--resume` to load and display history:

```json
{
  "type": "user|assistant",
  "message": {"role": "user", "content": "..."},
  "uuid": "<unique-uuid>",
  "parentUuid": "<previous-record-uuid or null>",
  "isSidechain": false,
  "sessionId": "<matches-filename>",
  "timestamp": "2026-05-26T16:00:00.000Z"
}
```

**Critical rules discovered by testing:**
- `timestamp` must be non-empty — empty string = "No conversation found"
- `uuid` + `parentUuid` form a linked list (first record has `parentUuid: null`)
- `isSidechain: false` required for main conversation display
- `sessionId` must match the JSONL filename (without `.jsonl`)
- File must be in `~/.claude/projects/<cwd-as-dashes>/`
- Assistant `message` should have Anthropic API shape (`id`, `type: "message"`, `model`, `stop_reason`) for full UI rendering
- Tool results must use `type: "user"` (not `type: "tool_result"`) with `tool_result` content blocks

## Minimum viable Codex session format

```json
{"timestamp": "...", "type": "session_meta", "payload": {"id": "<uuid>", "originator": "codex_cli_rs", "cli_version": "0.133.0", ...}}
{"timestamp": "...", "type": "response_item", "payload": {"type": "message", "role": "user", "content": [...]}}
```

**Critical rules:**
- First record must be `session_meta` with `originator: "codex_cli_rs"` and `cli_version`
- Messages wrapped in `{timestamp, type: "response_item", payload: {...}}`
- Date-nested path: `sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl`
- Row in `~/.codex/state_5.sqlite` `threads` table for history visibility
- User content uses `input_text`, assistant uses `output_text` block types

## How Claude Code loads sessions (from source analysis)

1. `gxK(sessionId)` → reads `<project-dir>/<sessionId>.jsonl`
2. `pB()` parses JSONL lines
3. `xo(record)` filters: only `type === "user"|"assistant"|"attachment"|"system"`
4. Records stored in `Map<uuid, record>`
5. `fg8()` finds latest non-sidechain record by `Date.parse(timestamp)`
6. `Qq6()` walks backward via `parentUuid` chain to build transcript
7. Transcript rendered in UI
