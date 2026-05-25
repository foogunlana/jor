"""Parse Codex JSONL records into JorMessage objects.

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

from jor.core.schema import JorMessage, ToolCall, ToolResult


def extract_metadata(records: list[dict], session_path: Path) -> dict:
    """Extract session metadata from Codex records."""
    source_id = session_path.stem
    started_at = ""
    project = ""

    for rec in records:
        if rec.get("type") == "session_meta":
            payload = rec.get("payload", {})
            started_at = payload.get("timestamp", "")
            project = payload.get("cwd", "")
            source_id = payload.get("id", source_id)
            break

    # Title: first user message content[:80]
    title = ""
    for rec in records:
        if rec.get("type") != "response_item":
            continue
        payload = rec.get("payload", {})
        if payload.get("type") == "message" and payload.get("role") == "user":
            content = _extract_text(payload.get("content", ""))
            if content:
                title = content[:80]
                break

    return {
        "source_id": source_id,
        "started_at": started_at,
        "project": project,
        "title": title,
    }


def parse_record(record: dict, source_id: str) -> JorMessage | list[JorMessage] | None:
    """Convert a single Codex record to a JorMessage. Returns None to skip."""
    rec_type = record.get("type", "")

    if rec_type != "response_item":
        return None

    payload = record.get("payload", {})
    payload_type = payload.get("type", "")

    if payload_type == "message":
        role = payload.get("role", "")
        content = _extract_text(payload.get("content", ""))

        if role == "developer":
            role = "system"

        if role in ("system", "user", "assistant"):
            return JorMessage(
                id=str(uuid.uuid4()),
                role=role,
                content=content,
                source_tool="codex",
                source_id=source_id,
            )

    elif payload_type == "function_call":
        call_id = payload.get("call_id", "")
        name = payload.get("name", "")
        raw_args = payload.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {"raw": raw_args}

        tc = ToolCall(id=call_id, name=name, input=args)
        return JorMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content="",
            tool_calls=[tc],
            source_tool="codex",
            source_id=source_id,
        )

    elif payload_type == "function_call_output":
        call_id = payload.get("call_id", "")
        output = _extract_text(payload.get("output", ""))
        return JorMessage(
            id=str(uuid.uuid4()),
            role="tool_result",
            content=output,
            tool_result=ToolResult(tool_call_id=call_id, content=output),
            source_tool="codex",
            source_id=source_id,
        )

    return None


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
