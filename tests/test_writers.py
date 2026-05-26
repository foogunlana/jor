"""Tests for session writers (Jor → native format)."""

import json
from pathlib import Path

import pytest

from jor.core.schema import JorMessage, ToolCall, ToolResult
from jor.connectors.claude_code.connector import ClaudeCodeConnector as ClaudeCodeWriter
from jor.connectors.codex.connector import CodexConnector as CodexWriter


@pytest.fixture()
def simple_messages() -> list[JorMessage]:
    return [
        JorMessage(
            id="msg-1",
            role="user",
            content="Refactor the auth module",
            timestamp="2026-04-20T10:30:00.000Z",
            source_tool="codex",
            source_id="codex-session-1",
        ),
        JorMessage(
            id="msg-2",
            role="assistant",
            content="I'll help with that.",
            tool_calls=[ToolCall(id="tc-1", name="Read", input={"file_path": "auth.py"})],
            timestamp="2026-04-20T10:30:05.000Z",
            source_tool="codex",
            source_id="codex-session-1",
        ),
        JorMessage(
            id="msg-3",
            role="tool_result",
            content="def login(): ...",
            tool_result=ToolResult(tool_call_id="tc-1", content="def login(): ...", is_error=False),
            timestamp="2026-04-20T10:30:06.000Z",
            source_tool="codex",
            source_id="codex-session-1",
        ),
        JorMessage(
            id="msg-4",
            role="assistant",
            content="Here is the refactored code.",
            timestamp="2026-04-20T10:35:00.000Z",
            source_tool="codex",
            source_id="codex-session-1",
        ),
    ]


# --- ClaudeCodeWriter ---

class TestClaudeCodeWriter:
    def test_write_creates_file(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = ClaudeCodeWriter().write(simple_messages, tmp_path / "test-session.jsonl")
        assert out.exists()

    def test_write_valid_jsonl(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = ClaudeCodeWriter().write(simple_messages, tmp_path / "test-session.jsonl")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 4

    def test_user_message_format(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = ClaudeCodeWriter().write(simple_messages, tmp_path / "sess.jsonl")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        user = lines[0]
        assert user["type"] == "user"
        assert user["message"]["role"] == "user"
        assert user["message"]["content"] == "Refactor the auth module"

    def test_assistant_with_tool_calls(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = ClaudeCodeWriter().write(simple_messages, tmp_path / "sess.jsonl")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        asst = lines[1]
        assert asst["type"] == "assistant"
        content_blocks = asst["message"]["content"]
        text_blocks = [b for b in content_blocks if b["type"] == "text"]
        tool_blocks = [b for b in content_blocks if b["type"] == "tool_use"]
        assert text_blocks[0]["text"] == "I'll help with that."
        assert tool_blocks[0]["name"] == "Read"
        assert tool_blocks[0]["id"] == "tc-1"

    def test_tool_result_format(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = ClaudeCodeWriter().write(simple_messages, tmp_path / "sess.jsonl")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        tr = lines[2]
        assert tr["type"] == "tool_result"
        blocks = tr["message"]["content"]
        assert blocks[0]["type"] == "tool_result"
        assert blocks[0]["tool_use_id"] == "tc-1"

    def test_resume_command(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        writer = ClaudeCodeWriter()
        _, out = writer.write(simple_messages, tmp_path / "my-session.jsonl")
        cmd = writer.resume_command(out)
        assert "claude" in cmd
        assert "my-session" in cmd


# --- CodexWriter ---

class TestCodexWriter:
    def test_write_creates_file(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = CodexWriter().write(simple_messages, tmp_path)
        assert out.exists()

    def test_write_valid_jsonl(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = CodexWriter().write(simple_messages, tmp_path)
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # session_meta + 4 messages (tool_calls assistant splits into function_call + text)
        assert len(lines) >= 5
        assert lines[0]["type"] == "session_meta"

    def test_user_message_format(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = CodexWriter().write(simple_messages, tmp_path)
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        user_rec = lines[1]  # after session_meta
        assert user_rec["type"] == "response_item"
        assert user_rec["payload"]["role"] == "user"

    def test_assistant_with_tool_calls(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = CodexWriter().write(simple_messages, tmp_path)
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        fc_recs = [r for r in lines if r.get("payload", {}).get("type") == "function_call"]
        assert len(fc_recs) == 1
        assert fc_recs[0]["payload"]["call_id"] == "tc-1"
        assert fc_recs[0]["payload"]["name"] == "Read"

    def test_tool_result_maps_to_function_call_output(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        _, out = CodexWriter().write(simple_messages, tmp_path)
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        fco_recs = [r for r in lines if r.get("payload", {}).get("type") == "function_call_output"]
        assert len(fco_recs) == 1
        assert fco_recs[0]["payload"]["call_id"] == "tc-1"
        assert fco_recs[0]["payload"]["output"] == "def login(): ..."

    def test_resume_command(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        writer = CodexWriter()
        session_id, out = writer.write(simple_messages, tmp_path)
        cmd = writer.resume_command(out)
        assert "codex" in cmd
        assert session_id in cmd
