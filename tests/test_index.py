"""Failing tests for session index read/write/upsert — RED phase."""

import json
from pathlib import Path

import pytest


def make_entry(**kwargs):
    from jor.core.index import IndexEntry

    defaults = {
        "id": "jor-abc123",
        "tool": "claude_code",
        "source_id": "orig-uuid",
        "source_path": "~/.claude/projects/hash/sessions/uuid.jsonl",
        "title": "Auth module refactor",
        "project": "/Users/foo/code/my-app",
        "started_at": "2026-04-20T10:30:00Z",
        "ended_at": "2026-04-20T11:45:00Z",
        "message_count": 42,
        "model": "claude-sonnet-4-6",
        "provider": "anthropic",
        "summary": "Refactored auth middleware...",
    }
    defaults.update(kwargs)
    return IndexEntry(**defaults)


def test_index_entry_required_fields():
    entry = make_entry()
    assert entry.id == "jor-abc123"
    assert entry.tool == "claude_code"
    assert entry.source_id == "orig-uuid"
    assert entry.source_path == "~/.claude/projects/hash/sessions/uuid.jsonl"
    assert entry.title == "Auth module refactor"
    assert entry.project == "/Users/foo/code/my-app"
    assert entry.started_at == "2026-04-20T10:30:00Z"
    assert entry.message_count == 42
    assert entry.model == "claude-sonnet-4-6"
    assert entry.provider == "anthropic"


def test_index_entry_optional_fields_default_none():
    from jor.core.index import IndexEntry

    entry = IndexEntry(
        id="jor-x",
        tool="claude_code",
        source_id="s1",
        source_path="~/path",
        title="t",
        project="/p",
        started_at="2026-01-01T00:00:00Z",
        message_count=1,
    )
    assert entry.ended_at is None
    assert entry.model is None
    assert entry.provider is None
    assert entry.summary is None


def test_session_index_model():
    from jor.core.index import SessionIndex

    idx = SessionIndex()
    assert idx.version == 1
    assert idx.sessions == []
    assert idx.last_scan is None


def test_session_index_with_sessions():
    from jor.core.index import SessionIndex

    entry = make_entry()
    idx = SessionIndex(sessions=[entry], last_scan="2026-04-25T10:00:00Z")
    assert len(idx.sessions) == 1
    assert idx.last_scan == "2026-04-25T10:00:00Z"


def test_load_index_missing_file(tmp_path):
    from jor.core.index import load_index

    idx = load_index(tmp_path / "index.json")
    assert idx.version == 1
    assert idx.sessions == []


def test_save_and_load_index(tmp_path):
    from jor.core.index import IndexEntry, SessionIndex, load_index, save_index

    entry = make_entry()
    idx = SessionIndex(sessions=[entry], last_scan="2026-04-25T10:00:00Z")
    path = tmp_path / "index.json"

    save_index(idx, path)
    assert path.exists()

    loaded = load_index(path)
    assert loaded.version == 1
    assert len(loaded.sessions) == 1
    assert loaded.sessions[0].id == "jor-abc123"
    assert loaded.last_scan == "2026-04-25T10:00:00Z"


def test_save_index_creates_valid_json(tmp_path):
    from jor.core.index import SessionIndex, save_index

    idx = SessionIndex()
    path = tmp_path / "index.json"
    save_index(idx, path)

    data = json.loads(path.read_text())
    assert data["version"] == 1
    assert data["sessions"] == []


def test_upsert_session_adds_new_entry():
    from jor.core.index import SessionIndex, upsert_session

    idx = SessionIndex()
    entry = make_entry()
    upsert_session(idx, entry)
    assert len(idx.sessions) == 1
    assert idx.sessions[0].id == "jor-abc123"


def test_upsert_session_updates_existing():
    from jor.core.index import SessionIndex, upsert_session

    idx = SessionIndex()
    entry = make_entry(title="Original title")
    upsert_session(idx, entry)

    updated = make_entry(title="Updated title")
    upsert_session(idx, updated)

    assert len(idx.sessions) == 1
    assert idx.sessions[0].title == "Updated title"


def test_upsert_session_multiple_entries():
    from jor.core.index import SessionIndex, upsert_session

    idx = SessionIndex()
    upsert_session(idx, make_entry(id="jor-1"))
    upsert_session(idx, make_entry(id="jor-2"))
    upsert_session(idx, make_entry(id="jor-3"))

    assert len(idx.sessions) == 3


def test_round_trip_preserves_all_fields(tmp_path):
    from jor.core.index import SessionIndex, load_index, save_index

    entry = make_entry()
    idx = SessionIndex(sessions=[entry], last_scan="2026-04-25T10:00:00Z")
    path = tmp_path / "index.json"

    save_index(idx, path)
    loaded = load_index(path)

    assert loaded == idx
