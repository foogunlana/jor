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

import json
import uuid
from pathlib import Path

from jor.core.index import IndexEntry
from jor.core.schema import JorMessage, ToolCall, ToolResult


class CodexConnector:
    """Scan ~/.codex/sessions/ for session files and convert to jor format."""

    def __init__(self, codex_home: Path | None = None) -> None:
        self._home = codex_home or Path.home() / ".codex"

    def name(self) -> str:
        return "codex"

    def detect(self) -> bool:
        return (self._home / "sessions").exists()

    def scan(self, jor_home: Path) -> list[IndexEntry]:
        entries: list[IndexEntry] = []
        for session_path in self._home.glob("sessions/**/rollout-*.jsonl"):
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
                continue  # skip malformed lines instead of aborting

        messages: list[JorMessage] = []
        title = ""
        source_id = session_path.stem
        started_at = ""
        project = ""

        for rec in records:
            rec_type = rec.get("type", "")
            payload = rec.get("payload", {})

            if rec_type == "session_meta":
                started_at = payload.get("timestamp", "")
                project = payload.get("cwd", "")
                source_id = payload.get("id", source_id)
                continue

            if rec_type != "response_item":
                continue

            payload_type = payload.get("type", "")

            if payload_type == "message":
                role = payload.get("role", "")
                content = _extract_text(payload.get("content", ""))

                if role == "developer":
                    role = "system"

                if role == "user" and not title and content:
                    title = content[:80]

                if role in ("system", "user", "assistant"):
                    messages.append(JorMessage(
                        id=str(uuid.uuid4()),
                        role=role,
                        content=content,
                        source_tool="codex",
                        source_id=source_id,
                    ))

            elif payload_type == "function_call":
                call_id = payload.get("call_id", "")
                name = payload.get("name", "")
                raw_args = payload.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    args = {"raw": raw_args}

                tc = ToolCall(id=call_id, name=name, input=args)
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content="",
                    tool_calls=[tc],
                    source_tool="codex",
                    source_id=source_id,
                ))

            elif payload_type == "function_call_output":
                call_id = payload.get("call_id", "")
                output = _extract_text(payload.get("output", ""))
                messages.append(JorMessage(
                    id=str(uuid.uuid4()),
                    role="tool_result",
                    content=output,
                    tool_result=ToolResult(tool_call_id=call_id, content=output),
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

        return IndexEntry(
            id=entry_id,
            tool="codex",
            source_id=source_id,
            source_path=str(session_path),
            title=title or session_path.stem,
            project=project,
            started_at=started_at,
            message_count=len(messages),
        )


def _extract_text(content: str | list | None) -> str:
    """Extract text from Codex content which can be a string or list of content blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text", "")
                if not text:
                    text = block.get("output", "")
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""
