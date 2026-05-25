"""Unit tests for Codex parser functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from jor.connectors.codex.parser import extract_metadata, parse_record
from jor.core.schema import JorMessage


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------


def test_extract_metadata_source_id_from_session_meta():
    records = [
        {"type": "session_meta", "payload": {"id": "codex-uuid-123", "timestamp": "t", "cwd": "/proj"}},
    ]
    meta = extract_metadata(records, Path("/fake/rollout-x.jsonl"))
    assert meta["source_id"] == "codex-uuid-123"


def test_extract_metadata_source_id_fallback_to_stem():
    records = [{"type": "response_item", "payload": {}}]
    meta = extract_metadata(records, Path("/fake/rollout-fallback.jsonl"))
    assert meta["source_id"] == "rollout-fallback"


def test_extract_metadata_started_at():
    records = [
        {"type": "session_meta", "payload": {"timestamp": "2026-01-01T00:00:00Z", "cwd": "/p"}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["started_at"] == "2026-01-01T00:00:00Z"


def test_extract_metadata_project_from_cwd():
    records = [
        {"type": "session_meta", "payload": {"timestamp": "t", "cwd": "/Users/me/code"}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["project"] == "/Users/me/code"


def test_extract_metadata_title_from_first_user_message():
    records = [
        {"type": "session_meta", "payload": {"timestamp": "t", "cwd": "/p"}},
        {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "system msg"}]}},
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Fix the bug"}]}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert meta["title"] == "Fix the bug"


def test_extract_metadata_title_truncated_to_80():
    long = "B" * 100
    records = [
        {"type": "response_item", "payload": {"type": "message", "role": "user", "content": long}},
    ]
    meta = extract_metadata(records, Path("/fake/s.jsonl"))
    assert len(meta["title"]) == 80


def test_extract_metadata_empty_records():
    meta = extract_metadata([], Path("/fake/s.jsonl"))
    assert meta["title"] == ""
    assert meta["started_at"] == ""
    assert meta["project"] == ""


# ---------------------------------------------------------------------------
# parse_record — skips non-response_item
# ---------------------------------------------------------------------------


def test_parse_session_meta_returns_none():
    rec = {"type": "session_meta", "payload": {"id": "x"}}
    assert parse_record(rec, "s1") is None


def test_parse_event_msg_returns_none():
    rec = {"type": "event_msg", "payload": {"type": "token_count"}}
    assert parse_record(rec, "s1") is None


# ---------------------------------------------------------------------------
# parse_record — message payloads
# ---------------------------------------------------------------------------


def test_parse_user_message():
    rec = {
        "type": "response_item",
        "payload": {"type": "message", "role": "user", "content": "hello"},
    }
    result = parse_record(rec, "s1")
    assert isinstance(result, JorMessage)
    assert result.role == "user"
    assert result.content == "hello"
    assert result.source_tool == "codex"


def test_parse_developer_mapped_to_system():
    rec = {
        "type": "response_item",
        "payload": {"type": "message", "role": "developer", "content": "be helpful"},
    }
    result = parse_record(rec, "s1")
    assert result.role == "system"


def test_parse_assistant_message():
    rec = {
        "type": "response_item",
        "payload": {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "I can help"}]},
    }
    result = parse_record(rec, "s1")
    assert result.role == "assistant"
    assert result.content == "I can help"


# ---------------------------------------------------------------------------
# parse_record — function_call
# ---------------------------------------------------------------------------


def test_parse_function_call():
    rec = {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "read_file",
            "arguments": '{"path": "/foo.py"}',
            "call_id": "call-1",
        },
    }
    result = parse_record(rec, "s1")
    assert result.role == "assistant"
    assert result.tool_calls is not None
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "read_file"
    assert result.tool_calls[0].id == "call-1"
    assert result.tool_calls[0].input == {"path": "/foo.py"}


def test_parse_function_call_bad_json_args():
    rec = {
        "type": "response_item",
        "payload": {
            "type": "function_call",
            "name": "bash",
            "arguments": "not json",
            "call_id": "call-2",
        },
    }
    result = parse_record(rec, "s1")
    assert result.tool_calls[0].input == {"raw": "not json"}


# ---------------------------------------------------------------------------
# parse_record — function_call_output
# ---------------------------------------------------------------------------


def test_parse_function_call_output():
    rec = {
        "type": "response_item",
        "payload": {
            "type": "function_call_output",
            "call_id": "call-1",
            "output": "file contents here",
        },
    }
    result = parse_record(rec, "s1")
    assert result.role == "tool_result"
    assert result.content == "file contents here"
    assert result.tool_result.tool_call_id == "call-1"


# ---------------------------------------------------------------------------
# parse_record — unknown payload type
# ---------------------------------------------------------------------------


def test_parse_unknown_payload_type_returns_none():
    rec = {
        "type": "response_item",
        "payload": {"type": "unknown_thing"},
    }
    assert parse_record(rec, "s1") is None
