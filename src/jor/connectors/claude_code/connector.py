"""Discover and import Claude Code sessions into jor.

Claude Code stores sessions as JSONL files at:
    ~/.claude/projects/<project-name>/<session-uuid>.jsonl

Each line is a JSON record with {sessionId, timestamp, type, message}.
Record types: "user", "assistant", "tool_result". Assistant messages
use Anthropic's content block format (text blocks + tool_use blocks).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from jor.connectors.base import BaseConnector
from jor.core.schema import JorMessage, ToolCall, ToolResult


class ClaudeCodeConnector(BaseConnector):
    """Scan ~/.claude/projects/ for session files and convert to jor format."""

    TOOL_NAME = "claude_code"
    GLOB_PATTERN = "projects/*/*.jsonl"
    DETECT_PATH = "projects"
    DEFAULT_HOME = Path.home() / ".claude"
    STRICT_JSON = True

    def __init__(self, claude_home: Path | None = None) -> None:
        super().__init__(home_path=claude_home)

    def extract_metadata(self, records: list[dict], session_path: Path) -> dict:
        source_id = session_path.stem
        started_at = ""
        project = ""

        for rec in records:
            if not started_at:
                started_at = rec.get("timestamp", "")
            if not project:
                project = rec.get("cwd", "")
            if started_at and project:
                break

        title = ""
        for rec in records:
            if rec.get("type") == "user":
                msg = rec.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict)
                    )
                if content:
                    title = content[:80]
                    break

        return {
            "source_id": source_id,
            "started_at": started_at,
            "project": project,
            "title": title,
        }

    def parse_record(self, record: dict, source_id: str) -> JorMessage | list[JorMessage] | None:
        msg_type = record.get("type", "")
        msg = record.get("message", {})
        timestamp = record.get("timestamp")
        metadata: dict = {}
        if record.get("gitBranch"):
            metadata["gitBranch"] = record["gitBranch"]

        session_id = record.get("sessionId", "")

        if msg_type == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
            return JorMessage(
                id=str(uuid.uuid4()),
                role="user",
                content=content,
                timestamp=timestamp,
                metadata=metadata or None,
                source_tool="claude_code",
                source_id=session_id,
            )

        elif msg_type == "assistant":
            content_blocks = msg.get("content", [])
            if isinstance(content_blocks, str):
                text = content_blocks
                tool_calls = None
            else:
                text = " ".join(
                    b.get("text", "") for b in content_blocks
                    if isinstance(b, dict) and b.get("type") == "text"
                )
                tool_calls = [
                    ToolCall(id=b["id"], name=b["name"], input=b.get("input", {}))
                    for b in content_blocks
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                ] or None
            return JorMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=text,
                tool_calls=tool_calls,
                timestamp=timestamp,
                metadata=metadata or None,
                source_tool="claude_code",
                source_id=session_id,
            )

        elif msg_type == "tool_result":
            content_blocks = msg.get("content", [])
            if isinstance(content_blocks, list):
                results = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_call_id = block.get("tool_use_id", "")
                        result_content = block.get("content", "")
                        results.append(JorMessage(
                            id=str(uuid.uuid4()),
                            role="tool_result",
                            content=result_content,
                            tool_result=ToolResult(
                                tool_call_id=tool_call_id,
                                content=result_content,
                            ),
                            timestamp=timestamp,
                            metadata=metadata or None,
                            source_tool="claude_code",
                            source_id=session_id,
                        ))
                return results if results else None

        return None
