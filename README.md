# jor

Transfer AI sessions between tools. Start a conversation in Claude Code, continue it in Codex — or vice versa.

Jor discovers sessions across AI tools on your machine, converts them to a common format, and writes them back in the target tool's native format so you can resume seamlessly.

## Supported Tools

- **Claude Code** — reads and writes `.jsonl` sessions
- **Codex** — reads and writes `.jsonl` sessions

## Install

```bash
pip install jor
```

## Usage

```bash
# Discover all AI sessions on your machine
jor discover

# List indexed sessions (newest first)
jor list
jor list --codex                     # only Codex sessions
jor list --claude               # only Claude Code sessions
jor list -q "auth refactor"          # search titles
jor list --path /code/myapp          # filter by project

# Convert a session to another tool's format
jor convert <session-id>             # auto: converts to the other tool
jor convert <session-id> --codex     # explicit: convert to Codex
jor convert <session-id> --claude

# Open a session (resume in its original tool, or cross-tool)
jor open <session-id>                # resume in original tool
jor open <session-id> --codex        # open in Codex
jor open <session-id> --claude  # open in Claude Code
```

## How It Works

1. **Discover** scans known session directories for each supported tool
2. **Convert** translates messages, tool calls, and tool results into a common schema (JSONL)
3. **Write** outputs the session in the target tool's native format
4. **Open** writes + launches the tool with a resume command

Sessions are portable — file paths are stored relative, and source provenance is preserved.

## Adding a Connector

Each connector is one class + one schema. That's it.

```
src/jor/connectors/my_tool/
├── __init__.py
├── schema.json      # format contract — what one JSONL line looks like
└── connector.py     # one class: reads, writes, and launches sessions
```

### 1. schema.json

A JSON Schema that validates one line of the tool's native session file. This catches format drift — if the tool changes its format, schema validation fails in tests before the parser silently produces garbage.

Be specific about the message structure, not just top-level fields:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "One line of a MyTool session file",
  "type": "object",
  "required": ["type", "message"],
  "properties": {
    "type": { "type": "string", "enum": ["user", "assistant"] },
    "message": {
      "type": "object",
      "required": ["role", "content"],
      "properties": {
        "role": { "type": "string" },
        "content": { "type": "string" }
      }
    }
  }
}
```

### 2. connector.py

Subclass `BaseConnector` and implement these methods:

| Method | Purpose |
|--------|---------|
| `extract_metadata(records, session_path)` | Pull title, project, timestamps from raw records |
| `from_record(record, source_id)` | Convert one native record → JorMessage (reading) |
| `to_record(msg, session_id)` | Convert one JorMessage → native record (writing) |
| `write(messages, target)` | Write a session file, return (session_id, path) |
| `resume_command(session_file)` | Shell command to resume (e.g. `"mytool resume {id}"`) |
| `write_session(messages, project)` | Write + return (session_id, resume_cmd, path) |

The base class handles all boilerplate: JSONL scanning, JSON parsing, index creation, launching.

```python
import uuid
from pathlib import Path

from jor.connectors.base import BaseConnector
from jor.core.schema import JorMessage

class MyToolConnector(BaseConnector):
    TOOL_NAME = "my_tool"
    GLOB_PATTERN = "sessions/*.jsonl"       # where to find session files
    DETECT_PATH = "sessions"                # dir to check in detect()
    DEFAULT_HOME = Path.home() / ".my_tool" # tool's home directory
    STRICT_JSON = False                     # True = abort entire file on bad line
    RESUME_CMD = "mytool resume {session_id}"

    def __init__(self, my_tool_home=None):
        super().__init__(home_path=my_tool_home)

    # --- Reading ---

    def extract_metadata(self, records, session_path):
        return {
            "source_id": session_path.stem,
            "started_at": records[0].get("timestamp", "") if records else "",
            "project": records[0].get("cwd", "") if records else "",
            "title": "",  # falls back to first user message
        }

    def from_record(self, record, source_id):
        """Native record → JorMessage. Return None to skip."""
        if record.get("type") == "user":
            return JorMessage(
                id=str(uuid.uuid4()),
                role="user",
                content=record["message"]["content"],
                source_tool="my_tool",
                source_id=source_id,
            )
        return None

    # --- Writing ---

    def to_record(self, msg, session_id):
        """JorMessage → native record."""
        return {"type": msg.role, "message": {"role": msg.role, "content": msg.content}}

    def write(self, messages, target_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        sid = str(uuid.uuid4())
        path = target_dir / f"{sid}.jsonl"
        self.write_jsonl(messages, path, sid)
        return sid, path

    def resume_command(self, session_file):
        return f"mytool resume {session_file.stem}"

    def write_session(self, messages, project):
        sid, path = self.write(messages, self._home / "sessions")
        return sid, self.resume_command(path), path
```

### 3. Testing

Create a fixture at `tests/fixtures/my_tool_session.jsonl` with real session data (copy from the actual tool, don't invent it — see RALPH.md ground truth rules).

Then add tests at `tests/connectors/my_tool/`:

- **test_parser.py** — unit tests for `from_record()`, `to_record()`, and `extract_metadata()`
- **test_connector.py** — integration tests that scan a fixture and verify IndexEntry output

Schema validation is automatic — add a test class to `tests/test_schemas.py`:

```python
class TestMyToolSchema(BaseSchemaTest):
    connector = "my_tool"
    fixture = "my_tool_session.jsonl"
```

### 4. Register

Add your connector to `cli.py`:

```python
from jor.connectors.my_tool.connector import MyToolConnector

# In discover:
connectors = [ClaudeCodeConnector(), CodexConnector(), MyToolConnector()]

# In CONNECTORS dict:
CONNECTORS = {
    "claude_code": ClaudeCodeConnector,
    "codex": CodexConnector,
    "my_tool": MyToolConnector,
}
```

## License

MIT
