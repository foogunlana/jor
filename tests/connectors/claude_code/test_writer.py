"""Tests for the Claude Code session writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jor.core.schema import JorMessage, ToolCall, ToolResult


# ---------------------------------------------------------------------------
# Writer protocol
# ---------------------------------------------------------------------------


def test_claude_code_writer_extends_base_writer() -> None:
    from jor.connectors.base import BaseConnector
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    assert isinstance(ClaudeCodeWriter(), BaseConnector)


# ---------------------------------------------------------------------------
# Return values
# ---------------------------------------------------------------------------


def test_write_returns_session_id_and_path(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [JorMessage(id="m1", role="user", content="hello")]
    session_id, out_path = ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert isinstance(out_path, Path)


def test_write_creates_file_at_target_path(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    target = tmp_path / "session.jsonl"
    msgs = [JorMessage(id="m1", role="user", content="hello")]
    _, out_path = ClaudeCodeWriter().write(msgs, target)
    assert out_path == target
    assert target.exists()


# ---------------------------------------------------------------------------
# JSONL line structure
# ---------------------------------------------------------------------------


def test_each_line_has_required_keys(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [JorMessage(id="m1", role="user", content="hello", timestamp="2026-01-01T00:00:00Z")]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    lines = [json.loads(l) for l in (tmp_path / "out.jsonl").read_text().splitlines() if l]
    assert len(lines) == 1
    rec = lines[0]
    assert "type" in rec
    assert "message" in rec
    assert "sessionId" in rec
    assert "timestamp" in rec


def test_session_id_is_consistent_across_lines(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [
        JorMessage(id="m1", role="user", content="hello"),
        JorMessage(id="m2", role="assistant", content="hi"),
    ]
    session_id, _ = ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    lines = [json.loads(l) for l in (tmp_path / "out.jsonl").read_text().splitlines() if l]
    for rec in lines:
        assert rec["sessionId"] == session_id


# ---------------------------------------------------------------------------
# Role -> type mapping
# ---------------------------------------------------------------------------


def test_user_message_maps_to_type_user(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [JorMessage(id="m1", role="user", content="hello")]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rec["type"] == "user"
    assert rec["message"]["role"] == "user"
    assert rec["message"]["content"] == "hello"


def test_assistant_message_maps_to_type_assistant(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [JorMessage(id="m1", role="assistant", content="here you go")]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rec["type"] == "assistant"
    assert rec["message"]["role"] == "assistant"


def test_tool_result_message_maps_to_type_tool_result(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [
        JorMessage(
            id="m1",
            role="tool_result",
            content="file contents",
            tool_result=ToolResult(tool_call_id="tc1", content="file contents"),
        )
    ]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rec["type"] == "tool_result"


# ---------------------------------------------------------------------------
# Content block reconstruction
# ---------------------------------------------------------------------------


def test_assistant_with_tool_calls_produces_tool_use_content_block(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    tc = ToolCall(id="tc1", name="Read", input={"file_path": "/foo.py"})
    msgs = [JorMessage(id="m1", role="assistant", content="reading file", tool_calls=[tc])]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    content = rec["message"]["content"]
    assert isinstance(content, list)
    tool_use_blocks = [b for b in content if b.get("type") == "tool_use"]
    assert len(tool_use_blocks) == 1
    assert tool_use_blocks[0]["id"] == "tc1"
    assert tool_use_blocks[0]["name"] == "Read"
    assert tool_use_blocks[0]["input"] == {"file_path": "/foo.py"}


def test_assistant_text_included_alongside_tool_use(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    tc = ToolCall(id="tc1", name="Read", input={"file_path": "/foo.py"})
    msgs = [JorMessage(id="m1", role="assistant", content="reading file", tool_calls=[tc])]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    content = rec["message"]["content"]
    text_blocks = [b for b in content if b.get("type") == "text"]
    assert len(text_blocks) == 1
    assert text_blocks[0]["text"] == "reading file"


def test_tool_result_content_block_structure(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [
        JorMessage(
            id="m1",
            role="tool_result",
            content="output here",
            tool_result=ToolResult(tool_call_id="tc1", content="output here"),
        )
    ]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    content = rec["message"]["content"]
    assert isinstance(content, list)
    result_blocks = [b for b in content if b.get("type") == "tool_result"]
    assert len(result_blocks) == 1
    assert result_blocks[0]["tool_use_id"] == "tc1"
    assert result_blocks[0]["content"] == "output here"


# ---------------------------------------------------------------------------
# Timestamp passthrough
# ---------------------------------------------------------------------------


def test_timestamp_preserved_in_output(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    ts = "2026-04-30T12:00:00Z"
    msgs = [JorMessage(id="m1", role="user", content="hi", timestamp=ts)]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rec["timestamp"] == ts


def test_missing_timestamp_gets_generated(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [JorMessage(id="m1", role="user", content="hi")]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    rec = json.loads((tmp_path / "out.jsonl").read_text().splitlines()[0])
    assert rec["timestamp"]  # must be non-empty for --resume to work


# ---------------------------------------------------------------------------
# UUID chain: records must have uuid + parentUuid linked list
# ---------------------------------------------------------------------------


def test_each_record_has_uuid(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [
        JorMessage(id="m1", role="user", content="hello", timestamp="2026-01-01T00:00:00Z"),
        JorMessage(id="m2", role="assistant", content="hi", timestamp="2026-01-01T00:00:01Z"),
    ]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    lines = [json.loads(l) for l in (tmp_path / "out.jsonl").read_text().splitlines() if l]
    for rec in lines:
        assert "uuid" in rec
        assert rec["uuid"]  # non-empty


def test_parent_uuid_forms_linked_list(tmp_path: Path) -> None:
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter

    msgs = [
        JorMessage(id="m1", role="user", content="hello", timestamp="2026-01-01T00:00:00Z"),
        JorMessage(id="m2", role="assistant", content="hi", timestamp="2026-01-01T00:00:01Z"),
        JorMessage(id="m3", role="user", content="thanks", timestamp="2026-01-01T00:00:02Z"),
    ]
    ClaudeCodeWriter().write(msgs, tmp_path / "out.jsonl")
    lines = [json.loads(l) for l in (tmp_path / "out.jsonl").read_text().splitlines() if l]
    assert lines[0]["parentUuid"] is None  # first record has no parent
    assert lines[1]["parentUuid"] == lines[0]["uuid"]
    assert lines[2]["parentUuid"] == lines[1]["uuid"]


# ---------------------------------------------------------------------------
# Round-trip: connector can re-parse what writer produces
# ---------------------------------------------------------------------------


def test_round_trip_parseable_by_connector(tmp_path: Path) -> None:
    """Writer output can be re-read by the ClaudeCodeConnector."""
    from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter
    from jor.connectors.claude_code.connector import ClaudeCodeConnector

    tc = ToolCall(id="tc1", name="Read", input={"file_path": "/foo.py"})
    tr = ToolResult(tool_call_id="tc1", content="file contents")
    messages = [
        JorMessage(id="m1", role="user", content="refactor this", timestamp="2026-01-01T00:00:00Z"),
        JorMessage(id="m2", role="assistant", content="ok", tool_calls=[tc], timestamp="2026-01-01T00:00:01Z"),
        JorMessage(id="m3", role="tool_result", content="file contents", tool_result=tr, timestamp="2026-01-01T00:00:02Z"),
    ]

    # Place output file where the connector expects it
    session_dir = tmp_path / ".claude" / "projects" / "proj"
    session_dir.mkdir(parents=True)
    target = session_dir / "roundtrip.jsonl"

    writer = ClaudeCodeWriter()
    writer.write(messages, target)

    # Now re-scan with the connector
    jor_home = tmp_path / ".jor"
    jor_home.mkdir()
    (jor_home / "sessions").mkdir()

    connector = ClaudeCodeConnector(claude_home=tmp_path / ".claude")
    entries = connector.scan(jor_home)
    assert len(entries) == 1

    jor_session = jor_home / "sessions" / f"{entries[0].id}.jsonl"
    recovered = [JorMessage.model_validate_json(l) for l in jor_session.read_text().splitlines() if l]

    user_msgs = [m for m in recovered if m.role == "user"]
    assistant_msgs = [m for m in recovered if m.role == "assistant"]
    tool_result_msgs = [m for m in recovered if m.role == "tool_result"]

    assert len(user_msgs) == 1
    assert user_msgs[0].content == "refactor this"

    assert len(assistant_msgs) == 1
    assert assistant_msgs[0].tool_calls is not None
    assert assistant_msgs[0].tool_calls[0].name == "Read"

    assert len(tool_result_msgs) == 1
    assert tool_result_msgs[0].tool_result.tool_call_id == "tc1"
