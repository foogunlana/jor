"""Codex session connector — reads ~/.codex/sessions/rollout-*.jsonl."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from jor.discovery.index import IndexEntry
from jor.session.schema import JorMessage, ToolCall, ToolResult


class CodexConnector:
    def __init__(self, codex_home: Path | None = None) -> None:
        self._home = codex_home or Path.home() / ".codex"

    def name(self) -> str:
        return "codex"

    def detect(self) -> bool:
        return (self._home / "sessions").exists()

    def scan(self, jor_home: Path) -> list[IndexEntry]:
        entries: list[IndexEntry] = []
        for session_path in self._home.glob("sessions/rollout-*.jsonl"):
            entry = self._process(session_path, jor_home)
            if entry is not None:
                entries.append(entry)
        return entries

    def _process(self, session_path: Path, jor_home: Path) -> IndexEntry | None:
        raw_lines = [line for line in session_path.read_text().splitlines() if line.strip()]
        if not raw_lines:
            return None

        records: list[dict] = []
        for line in raw_lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                return None

        messages: list[JorMessage] = []
        title = ""
        source_id = session_path.stem

        for rec in records:
            role = rec.get("role", "")
            content = rec.get("content", "") or ""

            if role == "system":
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="system",
                    content=content,
                    source_tool="codex",
                    source_id=source_id,
                ))

            elif role == "user":
                if not title:
                    title = content[:80]
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="user",
                    content=content,
                    source_tool="codex",
                    source_id=source_id,
                ))

            elif role == "assistant":
                raw_tool_calls = rec.get("tool_calls") or []
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        input=json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                    )
                    for tc in raw_tool_calls
                ] or None
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    source_tool="codex",
                    source_id=source_id,
                ))

            elif role == "tool":
                tool_call_id = rec.get("tool_call_id", "")
                result_content = content
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="tool_result",
                    content=result_content,
                    tool_result=ToolResult(
                        tool_call_id=tool_call_id,
                        content=result_content,
                    ),
                    source_tool="codex",
                    source_id=source_id,
                ))

        if not messages:
            return None

        entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(session_path)))
        jor_session = jor_home / "sessions" / f"{entry_id}.jsonl"
        jor_session.write_text(
            "\n".join(m.model_dump_json() for m in messages) + "\n"
        )

        # First user message timestamp not available in codex format — leave empty
        started_at = ""
        user_msgs = [m for m in messages if m.role == "user"]

        return IndexEntry(
            id=entry_id,
            tool="codex",
            source_id=source_id,
            source_path=str(session_path),
            title=title or session_path.stem,
            project="",
            started_at=started_at,
            message_count=len(messages),
        )
