"""Tests for the Codex session writer (envelope format)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from jor.core.schema import JorMessage, ToolCall, ToolResult


def _parse_records(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l]


def test_codex_writer_extends_base_writer() -> None:
    from jor.connectors.base import BaseConnector
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    assert isinstance(CodexWriter(), BaseConnector)


# ---------------------------------------------------------------------------
# Envelope structure
# ---------------------------------------------------------------------------


def test_every_record_is_envelope(tmp_path: Path) -> None:
    """All records must have {timestamp, type, payload} envelope."""
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    messages = [JorMessage(id="m1", role="user", content="hello")]
    _, out_path = CodexWriter().write(messages, tmp_path)
    for rec in _parse_records(out_path):
        assert "timestamp" in rec
        assert "type" in rec
        assert "payload" in rec


def test_first_record_is_session_meta(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    messages = [JorMessage(id="m1", role="user", content="hello")]
    session_id, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    meta = records[0]
    assert meta["type"] == "session_meta"
    assert meta["payload"]["id"] == session_id
    assert "cwd" in meta["payload"]


# ---------------------------------------------------------------------------
# Message type mapping
# ---------------------------------------------------------------------------


def test_user_message_wrapped_as_response_item(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    messages = [JorMessage(id="m1", role="user", content="hello world")]
    _, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    # Skip session_meta
    msg_rec = records[1]
    assert msg_rec["type"] == "response_item"
    payload = msg_rec["payload"]
    assert payload["type"] == "message"
    assert payload["role"] == "user"


def test_assistant_message_wrapped_as_response_item(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    messages = [JorMessage(id="m1", role="assistant", content="I can help")]
    _, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    payload = records[1]["payload"]
    assert payload["type"] == "message"
    assert payload["role"] == "assistant"


def test_system_message_maps_to_developer_role(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    messages = [JorMessage(id="m1", role="system", content="You are helpful")]
    _, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    payload = records[1]["payload"]
    assert payload["role"] == "developer"


# ---------------------------------------------------------------------------
# Tool calls and results
# ---------------------------------------------------------------------------


def test_tool_call_produces_function_call_payload(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls -la"})
    messages = [JorMessage(id="m1", role="assistant", content="", tool_calls=[tc])]
    _, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    # Find function_call record
    fc_recs = [r for r in records if r.get("payload", {}).get("type") == "function_call"]
    assert len(fc_recs) == 1
    payload = fc_recs[0]["payload"]
    assert payload["call_id"] == "tc1"
    assert payload["name"] == "bash"
    assert json.loads(payload["arguments"]) == {"cmd": "ls -la"}


def test_tool_result_produces_function_call_output(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    tr = ToolResult(tool_call_id="tc1", content="file contents")
    messages = [JorMessage(id="m1", role="tool_result", content="file contents", tool_result=tr)]
    _, out_path = CodexWriter().write(messages, tmp_path)
    records = _parse_records(out_path)
    fco_recs = [r for r in records if r.get("payload", {}).get("type") == "function_call_output"]
    assert len(fco_recs) == 1
    payload = fco_recs[0]["payload"]
    assert payload["call_id"] == "tc1"
    assert payload["output"] == "file contents"


# ---------------------------------------------------------------------------
# Date-nested path
# ---------------------------------------------------------------------------


def test_write_session_uses_date_nested_path(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    writer = CodexWriter(codex_home=tmp_path)
    messages = [JorMessage(id="m1", role="user", content="hello")]
    sid, cmd, path = writer.write_session(messages, "/tmp/test-project")
    # Path should contain year/month/day structure
    rel = path.relative_to(tmp_path / "sessions")
    parts = rel.parts
    assert len(parts) == 4  # year/month/day/filename
    assert parts[0].isdigit() and len(parts[0]) == 4  # year
    assert parts[1].isdigit() and len(parts[1]) == 2  # month
    assert parts[2].isdigit() and len(parts[2]) == 2  # day
    assert parts[3].startswith("rollout-")


# ---------------------------------------------------------------------------
# Valid JSONL
# ---------------------------------------------------------------------------


def test_output_is_valid_jsonl(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    tc = ToolCall(id="tc1", name="bash", input={"cmd": "echo hi"})
    tr = ToolResult(tool_call_id="tc1", content="hi")
    messages = [
        JorMessage(id="m1", role="user", content="say hi"),
        JorMessage(id="m2", role="assistant", content="running bash", tool_calls=[tc]),
        JorMessage(id="m3", role="tool_result", content="hi", tool_result=tr),
        JorMessage(id="m4", role="assistant", content="done"),
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    for line in out_path.read_text().splitlines():
        obj = json.loads(line)
        assert "type" in obj
        assert "payload" in obj
        assert "\n" not in line


# ---------------------------------------------------------------------------
# SQLite registration
# ---------------------------------------------------------------------------


def test_write_session_inserts_sqlite_row(tmp_path: Path) -> None:
    from jor.connectors.codex.connector import CodexConnector as CodexWriter

    # Create a minimal state_5.sqlite with the threads table
    db_path = tmp_path / "state_5.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE threads (
        id TEXT PRIMARY KEY, rollout_path TEXT, created_at INTEGER,
        updated_at INTEGER, source TEXT, model_provider TEXT, cwd TEXT,
        title TEXT, sandbox_policy TEXT, approval_mode TEXT,
        created_at_ms INTEGER, updated_at_ms INTEGER,
        first_user_message TEXT, preview TEXT
    )""")
    conn.commit()
    conn.close()

    writer = CodexWriter(codex_home=tmp_path)
    messages = [JorMessage(id="m1", role="user", content="hello world")]
    sid, _, path = writer.write_session(messages, "/tmp/test-project")

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT id, cwd, title FROM threads WHERE id = ?", (sid,)).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == sid
    assert row[1] == "/tmp/test-project"
    assert row[2] == "hello world"
