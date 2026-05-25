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

# List indexed sessions
jor list

# Convert a session to another tool's format
jor convert <session-id> --codex     # Claude Code → Codex
jor convert <session-id>             # anything → Claude Code (default)

# Convert and launch the target tool
jor open <session-id> --codex
```

## How It Works

1. **Discover** scans known session directories for each supported tool
2. **Convert** translates messages, tool calls, and tool results into a common schema (JSONL)
3. **Write** outputs the session in the target tool's native format
4. **Open** writes + launches the tool with a resume command

Sessions are portable — file paths are stored relative, and source provenance is preserved.

## Adding a Connector

Each connector lives in `src/jor/connectors/<tool_name>/` and has 4 files:

```
src/jor/connectors/my_tool/
├── schema.json      # describes what one JSONL line looks like
├── connector.py     # subclass of BaseConnector — reads native format
├── writer.py        # subclass of BaseWriter — writes native format
└── launcher.py      # subclass of BaseLauncher — launches the tool
```

### 1. schema.json

A JSON Schema that validates one line of the tool's session JSONL file. This is the format contract — it documents the native format and catches format drift in tests. Be specific about the message structure, not just top-level fields.

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

Subclass `BaseConnector` and implement two methods — `extract_metadata()` and `parse_record()`. All JSONL scanning, file writing, and index creation is handled by the base class.

```python
from jor.connectors.base import BaseConnector
from jor.core.schema import JorMessage

class MyToolConnector(BaseConnector):
    TOOL_NAME = "my_tool"
    GLOB_PATTERN = "sessions/*.jsonl"       # where to find session files
    DETECT_PATH = "sessions"                # dir to check in detect()
    DEFAULT_HOME = Path.home() / ".my_tool" # tool's home directory
    STRICT_JSON = False                     # True = abort file on bad line

    def __init__(self, my_tool_home=None):
        super().__init__(home_path=my_tool_home)

    def extract_metadata(self, records, session_path):
        """Pull session-level info from the raw records.

        Must return dict with keys: title, project, started_at, source_id.
        Title falls back to the first user message if left empty.
        """
        return {
            "source_id": session_path.stem,
            "started_at": records[0].get("timestamp", ""),
            "project": records[0].get("cwd", ""),
            "title": "",
        }

    def parse_record(self, record, source_id):
        """Convert one native JSONL record to a JorMessage. Return None to skip."""
        if record.get("type") == "user":
            return JorMessage(
                id=str(uuid.uuid4()),
                role="user",
                content=record["message"]["content"],
                source_tool="my_tool",
                source_id=source_id,
            )
        return None
```

### 4. Testing

Add a fixture at `tests/fixtures/my_tool_session.jsonl` with real (or realistic) session data. Then create tests at `tests/connectors/my_tool/`:

- **test_parser.py** — unit tests for `parse_record()` and `extract_metadata()`
- **test_connector.py** — integration tests that scan a fixture and verify IndexEntry output

The schema is validated automatically — add a test class to `tests/test_schemas.py`:

```python
class TestMyToolSchema(BaseSchemaTest):
    connector = "my_tool"
    fixture = "my_tool_session.jsonl"
```

### 5. Register

Add your connector to `cli.py`:

```python
from jor.connectors.my_tool.connector import MyToolConnector

connectors = [ClaudeCodeConnector(), CodexConnector(), MyToolConnector()]
```

## License

MIT
