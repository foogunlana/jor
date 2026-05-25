"""Discover and import Claude Code sessions into jor.

Claude Code stores sessions as JSONL files at:
    ~/.claude/projects/<project-name>/<session-uuid>.jsonl

Each line is a JSON record with {sessionId, timestamp, type, message}.
Record types: "user", "assistant", "tool_result". Assistant messages
use Anthropic's content block format (text blocks + tool_use blocks).
"""

from __future__ import annotations

from pathlib import Path

from jor.connectors.base import BaseConnector
from jor.connectors.claude_code import parser


class ClaudeCodeConnector(BaseConnector):
    """Scan ~/.claude/projects/ for session files and convert to jor format."""

    TOOL_NAME = "claude_code"
    GLOB_PATTERN = "projects/*/*.jsonl"
    DETECT_PATH = "projects"
    DEFAULT_HOME = Path.home() / ".claude"
    STRICT_JSON = True

    def __init__(self, claude_home: Path | None = None) -> None:
        super().__init__(home_path=claude_home)

    def parse_record(self, record, source_id):
        return parser.parse_record(record, source_id)

    def extract_metadata(self, records, session_path):
        return parser.extract_metadata(records, session_path)
