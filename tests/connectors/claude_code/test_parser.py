"""Unit tests for Claude Code connector parsing methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from jor.connectors.claude_code.connector import ClaudeCodeConnector
from jor.core.schema import JorMessage

_connector = ClaudeCodeConnector(claude_home=Path("/fake"))
extract_metadata = _connector.extract_metadata
from_record = _connector.from_record


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------


def test_extract_metadata_source_id_from_stem():
    records = [{"timestamp": "2026-01-01T00:00:00Z", "cwd": "/proj"}]
    meta = extract_metadata(records, Path("/fake/sessions/my-session-id.jsonl"))
    assert meta["source_id"] == "my-session-id"


def test_extract_metadata_started_at_from_first_record():
    records = [
        {"timestamp": "2026-01-01T00:00:00Z"},
        {"timestamp": "2026-01-01T00:01:00Z"},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["started_at"] == "2026-01-01T00:00:00Z"


def test_extract_metadata_project_from_cwd():
    records = [{"timestamp": "t", "cwd": "/Users/foo/code/bar"}]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["project"] == "/Users/foo/code/bar"


def test_extract_metadata_title_from_first_user_message():
    records = [
        {"type": "assistant", "message": {"content": "hi"}},
        {"type": "user", "message": {"role": "user", "content": "Refactor this module"}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["title"] == "Refactor this module"


def test_extract_metadata_title_from_list_content():
    records = [
        {"type": "user", "message": {"role": "user", "content": [{"text": "Hello world"}]}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["title"] == "Hello world"


def test_extract_metadata_title_truncated_to_80():
    long = "A" * 100
    records = [
        {"type": "user", "message": {"role": "user", "content": long}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert len(meta["title"]) == 80


def test_extract_metadata_empty_records():
    meta = extract_metadata([], Path("/fake/s.jsonl"))
    assert meta["title"] == ""
    assert meta["started_at"] == ""
    assert meta["project"] == ""


# ---------------------------------------------------------------------------
# parse_record — user messages
# ---------------------------------------------------------------------------


def test_parse_user_message():
    rec = {
        "type": "user",
        "message": {"role": "user", "content": "hello"},
        "timestamp": "2026-01-01T00:00:00Z",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert isinstance(result, JorMessage)
    assert result.role == "user"
    assert result.content == "hello"
    assert result.source_tool == "claude_code"


def test_parse_user_message_list_content():
    rec = {
        "type": "user",
        "message": {"role": "user", "content": [{"text": "hello"}, {"text": "world"}]},
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert result.content == "hello world"


def test_parse_user_preserves_git_branch():
    rec = {
        "type": "user",
        "message": {"role": "user", "content": "hi"},
        "timestamp": "t",
        "sessionId": "s1",
        "gitBranch": "feature/auth",
    }
    result = from_record(rec, "s1")
    assert result.metadata == {"gitBranch": "feature/auth"}


# ---------------------------------------------------------------------------
# parse_record — assistant messages
# ---------------------------------------------------------------------------


def test_parse_assistant_text():
    rec = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "I can help"}]},
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert result.role == "assistant"
    assert result.content == "I can help"
    assert result.tool_calls is None


def test_parse_assistant_with_tool_use():
    rec = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "reading"},
                {"type": "tool_use", "id": "tc1", "name": "Read", "input": {"path": "/f"}},
            ],
        },
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "Read"
    assert result.tool_calls[0].id == "tc1"


def test_parse_assistant_string_content():
    rec = {
        "type": "assistant",
        "message": {"role": "assistant", "content": "simple text"},
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert result.content == "simple text"


# ---------------------------------------------------------------------------
# parse_record — tool_result messages
# ---------------------------------------------------------------------------


def test_parse_tool_result():
    rec = {
        "type": "tool_result",
        "message": {
            "role": "tool_result",
            "content": [{"type": "tool_result", "tool_use_id": "tc1", "content": "output"}],
        },
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].role == "tool_result"
    assert result[0].tool_result.tool_call_id == "tc1"
    assert result[0].content == "output"


def test_parse_tool_result_multiple_blocks():
    rec = {
        "type": "tool_result",
        "message": {
            "role": "tool_result",
            "content": [
                {"type": "tool_result", "tool_use_id": "tc1", "content": "out1"},
                {"type": "tool_result", "tool_use_id": "tc2", "content": "out2"},
            ],
        },
        "timestamp": "t",
        "sessionId": "s1",
    }
    result = from_record(rec, "s1")
    assert isinstance(result, list)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# parse_record — unknown types
# ---------------------------------------------------------------------------


def test_parse_unknown_type_returns_none():
    rec = {"type": "unknown", "message": {}, "timestamp": "t", "sessionId": "s1"}
    assert from_record(rec, "s1") is None


def test_parse_empty_record_returns_none():
    assert from_record({}, "s1") is None
