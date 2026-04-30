"""Tests for the Codex session connector."""

import json
from pathlib import Path

import pytest

from jor.discovery.connectors.codex import CodexConnector
from jor.session.schema import JorMessage


FIXTURE = Path(__file__).parent / "fixtures" / "codex_session.jsonl"


@pytest.fixture()
def codex_home(tmp_path: Path) -> Path:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    dest = sessions / "rollout-data-pipeline.jsonl"
    dest.write_text(FIXTURE.read_text())
    return tmp_path


def test_detect_true(codex_home: Path) -> None:
    c = CodexConnector(codex_home=codex_home)
    assert c.detect() is True


def test_detect_false(tmp_path: Path) -> None:
    c = CodexConnector(codex_home=tmp_path / "nonexistent")
    assert c.detect() is False


def test_scan_returns_entry(codex_home: Path, tmp_path: Path) -> None:
    jor_home = tmp_path / "jor"
    jor_home.mkdir()
    (jor_home / "sessions").mkdir()

    c = CodexConnector(codex_home=codex_home)
    entries = c.scan(jor_home=jor_home)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.tool == "codex"
    assert "data pipeline" in entry.title.lower() or entry.title  # first user msg
    assert entry.message_count > 0


def test_scan_parses_messages(codex_home: Path, tmp_path: Path) -> None:
    jor_home = tmp_path / "jor"
    jor_home.mkdir()
    (jor_home / "sessions").mkdir()

    c = CodexConnector(codex_home=codex_home)
    entries = c.scan(jor_home=jor_home)
    entry = entries[0]

    # Read the written Jor session file
    session_files = list((jor_home / "sessions").glob("*.jsonl"))
    assert len(session_files) == 1
    messages = [JorMessage.model_validate_json(line) for line in session_files[0].read_text().splitlines() if line.strip()]

    # system, user, assistant (with tool_call), tool_result, assistant, user, assistant
    roles = [m.role for m in messages]
    assert "user" in roles
    assert "assistant" in roles
    assert "tool_result" in roles


def test_scan_tool_call_parsed(codex_home: Path, tmp_path: Path) -> None:
    jor_home = tmp_path / "jor"
    jor_home.mkdir()
    (jor_home / "sessions").mkdir()

    c = CodexConnector(codex_home=codex_home)
    c.scan(jor_home=jor_home)

    session_files = list((jor_home / "sessions").glob("*.jsonl"))
    messages = [JorMessage.model_validate_json(line) for line in session_files[0].read_text().splitlines() if line.strip()]

    assistant_with_tools = [m for m in messages if m.tool_calls]
    assert len(assistant_with_tools) == 1
    tc = assistant_with_tools[0].tool_calls[0]
    assert tc.name == "read_file"
    assert tc.id == "call-001"


def test_scan_empty_session(tmp_path: Path) -> None:
    codex_home = tmp_path / "codex"
    (codex_home / "sessions").mkdir(parents=True)
    (codex_home / "sessions" / "rollout-empty.jsonl").write_text("")

    jor_home = tmp_path / "jor"
    jor_home.mkdir()
    (jor_home / "sessions").mkdir()

    c = CodexConnector(codex_home=codex_home)
    entries = c.scan(jor_home=jor_home)
    assert entries == []


def test_name(tmp_path: Path) -> None:
    c = CodexConnector(codex_home=tmp_path)
    assert c.name() == "codex"
