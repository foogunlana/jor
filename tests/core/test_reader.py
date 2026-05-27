"""Tests for session reader."""

import json
from pathlib import Path

import pytest

from jor.core.index import IndexEntry
from jor.core.reader import format_full, format_summary, read_session
from jor.core.schema import JorMessage, ToolCall


def make_message(i: int, role: str = "user", content: str = "", files: list[str] | None = None) -> JorMessage:
    return JorMessage(
        id=str(i),
        role=role,
        content=content or f"Message {i}",
        files=files,
        source_tool="claude",
        source_id="s1",
        timestamp="2026-04-20T10:30:00Z",
    )


@pytest.fixture()
def entry() -> IndexEntry:
    return IndexEntry(
        id="jor-abc",
        tool="claude",
        source_id="s1",
        source_path="projects/foo/sessions/s1.jsonl",
        title="Auth refactor",
        project="myproject",
        started_at="2026-04-20T10:30:00Z",
        message_count=3,
        model="claude-opus-4-6",
        provider="anthropic",
    )


@pytest.fixture()
def session_file(tmp_path: Path) -> Path:
    messages = [
        JorMessage(
            id="1",
            role="user",
            content="Refactor auth module",
            timestamp="2026-04-20T10:30:00Z",
            source_tool="claude",
            source_id="s1",
            files=["auth.py", "tests/test_auth.py"],
        ),
        JorMessage(
            id="2",
            role="assistant",
            content="I'll help refactor.",
            tool_calls=[ToolCall(id="tc1", name="Read", input={"file_path": "auth.py"})],
            timestamp="2026-04-20T10:30:05Z",
            source_tool="claude",
            source_id="s1",
        ),
        JorMessage(
            id="3",
            role="assistant",
            content="Done.",
            timestamp="2026-04-20T10:35:00Z",
            source_tool="claude",
            source_id="s1",
        ),
    ]
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(m.model_dump_json() for m in messages) + "\n")
    return f


# --- read_session ---


def test_read_session_returns_messages(session_file: Path) -> None:
    messages = read_session(session_file)
    assert len(messages) == 3
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"


def test_read_session_missing_file_raises_with_clear_message(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        read_session(missing)


# --- format_summary ---


def test_format_summary_includes_tool_in_header(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "claude" in summary


def test_format_summary_includes_model_in_header(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "claude-opus-4-6" in summary


def test_format_summary_includes_project_in_header(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "myproject" in summary


def test_format_summary_includes_date_in_header(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "2026-04-20" in summary


def test_format_summary_prefixes_user_turns(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "User:" in summary
    assert "Refactor auth module" in summary


def test_format_summary_prefixes_assistant_turns(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "Assistant:" in summary


def test_format_summary_includes_files_referenced_section(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "Files" in summary
    assert "auth.py" in summary
    assert "tests/test_auth.py" in summary


def test_format_summary_no_files_section_when_no_files(entry: IndexEntry) -> None:
    messages = [make_message(1, role="user"), make_message(2, role="assistant")]
    summary = format_summary(messages, entry)
    assert "Files" not in summary


def test_format_summary_truncates_long_sessions(entry: IndexEntry) -> None:
    messages = [make_message(i, role="user" if i % 2 == 0 else "assistant") for i in range(70)]
    summary = format_summary(messages, entry)
    assert "50" in summary
    assert "20" in summary  # 70 - 50 = 20 omitted


def test_format_summary_shows_all_messages_when_not_over_50(session_file: Path, entry: IndexEntry) -> None:
    messages = read_session(session_file)
    summary = format_summary(messages, entry)
    assert "omitted" not in summary


# --- format_full ---


def test_format_full_returns_raw_jsonl(session_file: Path) -> None:
    result = format_full(session_file)
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 3
    for line in lines:
        obj = json.loads(line)
        assert "id" in obj
        assert "role" in obj


def test_format_full_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(FileNotFoundError, match=str(missing)):
        format_full(missing)
