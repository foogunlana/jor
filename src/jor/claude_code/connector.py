"""Claude Code session connector."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from jor.core.index import IndexEntry
from jor.core.schema import JorMessage, ToolCall, ToolResult


class ClaudeCodeConnector:
    def __init__(self, claude_home: Path | None = None) -> None:
        self._home = claude_home or Path.home() / ".claude"

    def name(self) -> str:
        return "claude_code"

    def detect(self) -> bool:
        return (self._home / "projects").exists()

    def scan(self, jor_home: Path) -> list[IndexEntry]:
        entries: list[IndexEntry] = []
        for session_path in self._home.glob("projects/*/*.jsonl"):
            entry = self._process(session_path, jor_home)
            if entry is not None:
                entries.append(entry)
        return entries

    def _process(self, session_path: Path, jor_home: Path) -> IndexEntry | None:
        raw_lines = [line for line in session_path.read_text().splitlines() if line.strip()]
        if not raw_lines:
            return None

        # Parse all lines; skip file if any line is malformed
        records: list[dict] = []
        for line in raw_lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                return None

        messages: list[JorMessage] = []
        title = ""
        project = ""
        started_at = ""
        source_id = session_path.stem

        for rec in records:
            if not started_at:
                started_at = rec.get("timestamp", "")
            if not project:
                project = rec.get("cwd", "")

            msg_type = rec.get("type", "")
            msg = rec.get("message", {})
            timestamp = rec.get("timestamp")
            metadata: dict = {}
            if rec.get("gitBranch"):
                metadata["gitBranch"] = rec["gitBranch"]

            session_id = rec.get("sessionId", "")

            if msg_type == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict)
                    )
                if not title:
                    title = content[:80]
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="user",
                    content=content,
                    timestamp=timestamp,
                    metadata=metadata or None,
                    source_tool="claude_code",
                    source_id=session_id,
                ))

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
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=text,
                    tool_calls=tool_calls,
                    timestamp=timestamp,
                    metadata=metadata or None,
                    source_tool="claude_code",
                    source_id=session_id,
                ))

            elif msg_type == "tool_result":
                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_call_id = block.get("tool_use_id", "")
                            result_content = block.get("content", "")
                            messages.append(JorMessage(
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

        if not messages:
            return None

        entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(session_path)))
        jor_session = jor_home / "sessions" / f"{entry_id}.jsonl"
        jor_session.write_text(
            "\n".join(m.model_dump_json() for m in messages) + "\n"
        )

        return IndexEntry(
            id=entry_id,
            tool="claude_code",
            source_id=source_id,
            source_path=str(session_path),
            title=title or session_path.stem,
            project=project,
            started_at=started_at,
            message_count=len(messages),
        )
