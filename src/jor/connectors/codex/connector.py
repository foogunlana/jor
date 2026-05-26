"""Codex connector — reads, writes, and launches sessions.

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
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from jor.connectors.base import BaseConnector
from jor.core.schema import JorMessage, ToolCall, ToolResult


class CodexConnector(BaseConnector):
    """Read, write, and launch Codex sessions."""

    TOOL_NAME = "codex"
    GLOB_PATTERN = "sessions/**/rollout-*.jsonl"
    DETECT_PATH = "sessions"
    DEFAULT_HOME = Path.home() / ".codex"
    STRICT_JSON = False
    RESUME_CMD = "codex resume {session_id}"

    def __init__(self, codex_home: Path | None = None) -> None:
        super().__init__(home_path=codex_home)

    # --- Reading ---

    def extract_metadata(self, records: list[dict], session_path: Path) -> dict:
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

    def from_record(self, record: dict, source_id: str) -> JorMessage | None:
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

    # --- Writing ---

    def to_record(self, msg: JorMessage, session_id: str) -> dict | list[dict]:
        ts = msg.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        if msg.role == "tool_result":
            return _envelope(ts, {
                "type": "function_call_output",
                "call_id": msg.tool_result.tool_call_id if msg.tool_result else "",
                "output": msg.content,
            })

        if msg.role == "assistant" and msg.tool_calls:
            records = []
            for tc in msg.tool_calls:
                records.append(_envelope(ts, {
                    "type": "function_call",
                    "call_id": tc.id,
                    "name": tc.name,
                    "arguments": json.dumps(tc.input),
                }))
            if msg.content:
                records.append(_envelope(ts, {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": msg.content}],
                }))
            return records

        role = "developer" if msg.role == "system" else msg.role
        text_type = "input_text" if role in ("user", "developer") else "output_text"
        return _envelope(ts, {
            "type": "message",
            "role": role,
            "content": [{"type": text_type, "text": msg.content}],
        })

    def write(self, messages: list[JorMessage], target_dir: Path) -> tuple[str, Path]:
        """Write messages with session_meta to target_dir. Returns (session_id, path)."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        date_str = now.strftime("%Y-%m-%dT%H-%M-%S")

        # Date-nested path
        year, month, day = now.strftime("%Y"), now.strftime("%m"), now.strftime("%d")
        out_dir = target_dir / year / month / day
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"rollout-{date_str}-{session_id}.jsonl"

        # Build records: session_meta first, then messages
        meta = _envelope(ts, {
            "id": session_id,
            "timestamp": ts,
            "cwd": "",
            "originator": "codex_cli_rs",
            "cli_version": "0.133.0",
            "source": "cli",
            "model_provider": "openai",
        }, record_type="session_meta")

        records = [meta]
        for msg in messages:
            result = self.to_record(msg, session_id)
            if isinstance(result, list):
                records.extend(result)
            else:
                records.append(result)

        out.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return session_id, out

    def resume_command(self, session_file: Path, session_id: str | None = None) -> str:
        if not session_id:
            # Extract UUID from stem like rollout-2026-05-26T16-34-37-<uuid>
            stem = session_file.stem
            stem = stem[len("rollout-"):] if stem.startswith("rollout-") else stem
            session_id = stem
        return f"codex resume {session_id}"

    def write_session(self, messages: list[JorMessage], project: str | None) -> tuple[str, str, Path]:
        target_dir = self._home / "sessions"
        sid, path = self.write(messages, target_dir)

        # Update cwd in the session_meta record
        if project:
            lines = path.read_text().splitlines()
            meta = json.loads(lines[0])
            meta["payload"]["cwd"] = project
            lines[0] = json.dumps(meta)
            path.write_text("\n".join(lines) + "\n")

        # Register in SQLite so codex sees it in history
        self._register_thread(sid, path, project, messages)

        return sid, self.resume_command(path, session_id=sid), path

    def _register_thread(self, session_id: str, path: Path, project: str | None, messages: list[JorMessage]) -> None:
        db_path = self._home / "state_5.sqlite"
        if not db_path.exists():
            return
        title = ""
        for msg in messages:
            if msg.role == "user" and msg.content:
                title = msg.content[:80]
                break
        now_epoch = int(time.time())
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "INSERT OR IGNORE INTO threads (id, rollout_path, created_at, updated_at, source, model_provider, cwd, title, sandbox_policy, approval_mode, created_at_ms, updated_at_ms, first_user_message, preview) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, str(path), now_epoch, now_epoch, "cli", "openai", project or "", title, '{"type":"read-only"}', "on-request", now_epoch * 1000, now_epoch * 1000, title, title),
            )
            conn.commit()
        finally:
            conn.close()


def _envelope(ts: str, payload: dict, record_type: str = "response_item") -> dict:
    return {"timestamp": ts, "type": record_type, "payload": payload}


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
