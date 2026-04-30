"""Tests for session reader."""

from pathlib import Path

import pytest

from jor.session.reader import read_session, format_summary
from jor.session.schema import JorMessage, ToolCall


@pytest.fixture()
def session_file(tmp_path: Path) -> Path:
    messages = [
        JorMessage(id="1", role="user", content="Refactor auth module", timestamp="2026-04-20T10:30:00Z", source_tool="claude_code", source_id="s1"),
        JorMessage(id="2", role="assistant", content="I'll help refactor.", tool_calls=[ToolCall(id="tc1", name="Read", input={"file_path": "auth.py"})], timestamp="2026-04-20T10:30:05Z", source_tool="claude_code", source_id="s1"),
        JorMessage(id="3", role="assistant", content="Done.", timestamp="2026-04-20T10:35:00Z", source_tool="claude_code", source_id="s1"),
    ]
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(m.model_dump_json() for m in messages) + "\n")
    return f


def test_read_session_returns_messages(session_file: Path) -> None:
    messages = read_session(session_file)
    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


def test_read_session_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_session(tmp_path / "missing.jsonl")


def test_format_summary_contains_roles(session_file: Path) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, title="Auth refactor", source_tool="claude_code")
    assert "User" in summary or "user" in summary.lower()
    assert "Refactor auth module" in summary


def test_format_summary_header(session_file: Path) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, title="Auth refactor", source_tool="claude_code")
    assert "Auth refactor" in summary
    assert "claude_code" in summary
