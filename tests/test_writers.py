"""Tests for session writers (Jor → native format)."""

import json
from pathlib import Path

import pytest

from jor.session.schema import JorMessage, ToolCall, ToolResult
from jor.session.writers.claude_code import ClaudeCodeWriter
from jor.session.writers.codex import CodexWriter


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
        out = ClaudeCodeWriter().write(simple_messages, tmp_path, session_id="test-session")
        assert out.exists()

    def test_write_valid_jsonl(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = ClaudeCodeWriter().write(simple_messages, tmp_path, session_id="test-session")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 4

    def test_user_message_format(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = ClaudeCodeWriter().write(simple_messages, tmp_path, session_id="sess")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        user = lines[0]
        assert user["type"] == "user"
        assert user["message"]["role"] == "user"
        assert user["message"]["content"] == "Refactor the auth module"

    def test_assistant_with_tool_calls(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = ClaudeCodeWriter().write(simple_messages, tmp_path, session_id="sess")
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
        out = ClaudeCodeWriter().write(simple_messages, tmp_path, session_id="sess")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        tr = lines[2]
        assert tr["type"] == "tool_result"
        blocks = tr["message"]["content"]
        assert blocks[0]["type"] == "tool_result"
        assert blocks[0]["tool_use_id"] == "tc-1"

    def test_resume_command(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        writer = ClaudeCodeWriter()
        out = writer.write(simple_messages, tmp_path, session_id="my-session")
        cmd = writer.resume_command(out)
        assert "claude" in cmd
        assert "my-session" in cmd


# --- CodexWriter ---

class TestCodexWriter:
    def test_write_creates_file(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = CodexWriter().write(simple_messages, tmp_path, session_id="test-session")
        assert out.exists()

    def test_write_valid_jsonl(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = CodexWriter().write(simple_messages, tmp_path, session_id="test-session")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert len(lines) == 4

    def test_user_message_format(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = CodexWriter().write(simple_messages, tmp_path, session_id="sess")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert lines[0]["role"] == "user"
        assert lines[0]["content"] == "Refactor the auth module"

    def test_assistant_with_tool_calls(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = CodexWriter().write(simple_messages, tmp_path, session_id="sess")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        asst = lines[1]
        assert asst["role"] == "assistant"
        assert asst["tool_calls"][0]["id"] == "tc-1"
        assert asst["tool_calls"][0]["function"]["name"] == "Read"

    def test_tool_result_maps_to_tool_role(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        out = CodexWriter().write(simple_messages, tmp_path, session_id="sess")
        lines = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        tr = lines[2]
        assert tr["role"] == "tool"
        assert tr["tool_call_id"] == "tc-1"
        assert tr["content"] == "def login(): ..."

    def test_resume_command(self, tmp_path: Path, simple_messages: list[JorMessage]) -> None:
        writer = CodexWriter()
        out = writer.write(simple_messages, tmp_path, session_id="my-session")
        cmd = writer.resume_command(out)
        assert "codex" in cmd
        assert "my-session" in cmd
