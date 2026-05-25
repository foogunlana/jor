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
├── parser.py        # two functions: parse_record() + extract_metadata()
├── connector.py     # thin subclass of BaseConnector (~15 lines)
├── writer.py        # (optional) converts jor format back to native
└── launcher.py      # (optional) launches the tool with a resume command
```

### 1. schema.json

A JSON Schema that validates one line of the tool's session JSONL file. This is the format contract — it documents the native format and is validated against your test fixture automatically.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "One line of a MyTool session file",
  "type": "object",
  "required": ["type", "content"],
  "properties": {
    "type": { "type": "string" },
    "content": { "type": "string" }
  }
}
```

### 2. parser.py

Two standalone functions that handle the tool-specific parts:

```python
from jor.core.schema import JorMessage

def extract_metadata(records: list[dict], session_path: Path) -> dict:
    """Pull session-level info from the raw records.

    Must return a dict with keys: title, project, started_at, source_id.
    Any missing key gets a default. Title falls back to the first user message.
    """
    return {
        "source_id": session_path.stem,
        "started_at": records[0].get("timestamp", ""),
        "project": records[0].get("cwd", ""),
        "title": "",  # let BaseConnector use first user message
    }

def parse_record(record: dict, source_id: str) -> JorMessage | None:
    """Convert one native JSONL record to a JorMessage. Return None to skip."""
    if record.get("type") == "user":
        return JorMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=record["content"],
            source_tool="my_tool",
            source_id=source_id,
        )
    return None
```

### 3. connector.py

A thin subclass — just class attributes and delegation:

```python
from jor.connectors.base import BaseConnector
from jor.connectors.my_tool import parser

class MyToolConnector(BaseConnector):
    TOOL_NAME = "my_tool"
    GLOB_PATTERN = "sessions/*.jsonl"       # where to find session files
    DETECT_PATH = "sessions"                # dir to check in detect()
    DEFAULT_HOME = Path.home() / ".my_tool" # tool's home directory
    STRICT_JSON = False                     # True = abort file on bad line

    def __init__(self, my_tool_home=None):
        super().__init__(home_path=my_tool_home)

    def parse_record(self, record, source_id):
        return parser.parse_record(record, source_id)

    def extract_metadata(self, records, session_path):
        return parser.extract_metadata(records, session_path)
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
