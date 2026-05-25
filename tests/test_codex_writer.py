"""Failing tests for the Codex session writer — RED phase."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jor.core.schema import JorMessage, ToolCall, ToolResult


def test_codex_writer_implements_writer_protocol() -> None:
    from jor.codex.writer import CodexWriter
    from jor.core.protocols import Writer

    assert isinstance(CodexWriter(), Writer)


def test_codex_writer_write_returns_session_id_and_path(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    messages = [JorMessage(id="m1", role="user", content="hello")]
    writer = CodexWriter()
    session_id, out_path = writer.write(messages, tmp_path)
    assert session_id
    assert out_path.exists()


def test_codex_writer_maps_user_message(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    messages = [JorMessage(id="m1", role="user", content="hello world")]
    _, out_path = CodexWriter().write(messages, tmp_path)

    lines = out_path.read_text().splitlines()
    assert len(lines) == 1
    msg = json.loads(lines[0])
    assert msg["role"] == "user"
    assert msg["content"] == "hello world"


def test_codex_writer_maps_assistant_message(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    messages = [JorMessage(id="m1", role="assistant", content="I can help")]
    _, out_path = CodexWriter().write(messages, tmp_path)

    msg = json.loads(out_path.read_text().splitlines()[0])
    assert msg["role"] == "assistant"
    assert msg["content"] == "I can help"


def test_codex_writer_maps_system_message(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    messages = [JorMessage(id="m1", role="system", content="You are helpful")]
    _, out_path = CodexWriter().write(messages, tmp_path)

    msg = json.loads(out_path.read_text().splitlines()[0])
    assert msg["role"] == "system"
    assert msg["content"] == "You are helpful"


def test_codex_writer_maps_tool_calls(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls -la"})
    messages = [
        JorMessage(id="m1", role="assistant", content="running bash", tool_calls=[tc])
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    msg = json.loads(out_path.read_text().splitlines()[0])
    assert msg["role"] == "assistant"
    assert "tool_calls" in msg
    assert len(msg["tool_calls"]) == 1
    tc_out = msg["tool_calls"][0]
    assert tc_out["id"] == "tc1"
    assert tc_out["type"] == "function"
    assert tc_out["function"]["name"] == "bash"
    assert json.loads(tc_out["function"]["arguments"]) == {"cmd": "ls -la"}


def test_codex_writer_maps_multiple_tool_calls(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    tc1 = ToolCall(id="tc1", name="read_file", input={"path": "/foo"})
    tc2 = ToolCall(id="tc2", name="write_file", input={"path": "/bar", "content": "x"})
    messages = [
        JorMessage(
            id="m1", role="assistant", content="reading and writing", tool_calls=[tc1, tc2]
        )
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    msg = json.loads(out_path.read_text().splitlines()[0])
    assert len(msg["tool_calls"]) == 2
    assert msg["tool_calls"][0]["id"] == "tc1"
    assert msg["tool_calls"][1]["id"] == "tc2"


def test_codex_writer_maps_tool_result_to_role_tool(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    tr = ToolResult(tool_call_id="tc1", content="file contents")
    messages = [
        JorMessage(id="m1", role="tool_result", content="file contents", tool_result=tr)
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    msg = json.loads(out_path.read_text().splitlines()[0])
    assert msg["role"] == "tool"
    assert msg["tool_call_id"] == "tc1"
    assert msg["content"] == "file contents"


def test_codex_writer_output_is_valid_jsonl(tmp_path: Path) -> None:
    from jor.codex.writer import CodexWriter

    tc = ToolCall(id="tc1", name="bash", input={"cmd": "echo hi"})
    tr = ToolResult(tool_call_id="tc1", content="hi")
    messages = [
        JorMessage(id="m1", role="user", content="say hi"),
        JorMessage(id="m2", role="assistant", content="running bash", tool_calls=[tc]),
        JorMessage(id="m3", role="tool_result", content="hi", tool_result=tr),
        JorMessage(id="m4", role="assistant", content="done"),
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    lines = out_path.read_text().splitlines()
    assert len(lines) == 4
    for line in lines:
        obj = json.loads(line)
        assert "role" in obj
        assert "\n" not in line


def test_codex_writer_round_trip(tmp_path: Path) -> None:
    """Messages written out can be re-read and verify the full structure."""
    from jor.codex.writer import CodexWriter

    tc = ToolCall(id="tc99", name="grep", input={"pattern": "foo", "path": "."})
    tr = ToolResult(tool_call_id="tc99", content="match: foo.py:10")
    messages = [
        JorMessage(id="m1", role="system", content="Be helpful."),
        JorMessage(id="m2", role="user", content="find foo"),
        JorMessage(id="m3", role="assistant", content="searching", tool_calls=[tc]),
        JorMessage(id="m4", role="tool_result", content="match: foo.py:10", tool_result=tr),
        JorMessage(id="m5", role="assistant", content="found it"),
    ]
    _, out_path = CodexWriter().write(messages, tmp_path)

    lines = out_path.read_text().splitlines()
    assert len(lines) == 5

    # system
    assert json.loads(lines[0]) == {"role": "system", "content": "Be helpful."}

    # user
    assert json.loads(lines[1]) == {"role": "user", "content": "find foo"}

    # assistant with tool_call
    assistant_msg = json.loads(lines[2])
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "grep"

    # tool result
    tool_msg = json.loads(lines[3])
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "tc99"

    # final assistant
    assert json.loads(lines[4]) == {"role": "assistant", "content": "found it"}
