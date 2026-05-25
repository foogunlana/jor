"""Discover and import Codex sessions into jor.

Codex stores sessions as JSONL files at:
    ~/.codex/sessions/<year>/<month>/<day>/rollout-<timestamp>-<uuid>.jsonl

Each line is a JSON record with {timestamp, type, payload}. Record types:
"session_meta" (session info), "response_item" (messages, tool calls,
tool results), "event_msg" (internal events like token counts), and
"turn_context" (per-turn metadata). Only session_meta and response_item
carry data we convert.
"""

from __future__ import annotations

from pathlib import Path

from jor.connectors.base import BaseConnector
from jor.connectors.codex import parser


class CodexConnector(BaseConnector):
    """Scan ~/.codex/sessions/ for session files and convert to jor format."""

    TOOL_NAME = "codex"
    GLOB_PATTERN = "sessions/**/rollout-*.jsonl"
    DETECT_PATH = "sessions"
    DEFAULT_HOME = Path.home() / ".codex"
    STRICT_JSON = False

    def __init__(self, codex_home: Path | None = None) -> None:
        super().__init__(home_path=codex_home)

    def parse_record(self, record, source_id):
        return parser.parse_record(record, source_id)

    def extract_metadata(self, records, session_path):
        return parser.extract_metadata(records, session_path)
