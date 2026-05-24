"""Tests for the Claude Code session connector."""

from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_session.jsonl"


@pytest.fixture
def claude_home(tmp_path: Path) -> Path:
    """Set up a fake ~/.claude directory with one session."""
    project_dir = tmp_path / ".claude" / "projects" / "-Users-foo-code-my-app"
    project_dir.mkdir(parents=True)
    session_file = project_dir / "abc-123-session.jsonl"
    session_file.write_text(FIXTURE.read_text())
    return tmp_path / ".claude"


@pytest.fixture
def jor_home(tmp_path: Path) -> Path:
    jor = tmp_path / ".jor"
    jor.mkdir()
    (jor / "sessions").mkdir()
    return jor


def test_connector_name():
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=Path("/nonexistent"))
    assert c.name() == "claude_code"


def test_detect_true(claude_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    assert c.detect() is True


def test_detect_false(tmp_path: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=tmp_path / ".claude")
    assert c.detect() is False


def test_scan_returns_one_entry(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entries = c.scan(jor_home)
    assert len(entries) == 1


def test_scan_entry_source_tool(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    assert entry.tool == "claude_code"


def test_scan_entry_source_id(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    assert entry.source_id == "abc-123-session"


def test_scan_entry_title_from_first_user_message(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    assert entry.title == "Refactor the auth module to use JWT tokens"


def test_scan_entry_project_path(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    assert entry.project == "/Users/foo/code/my-app"


def test_scan_writes_jor_session_file(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    assert session_file.exists()


def test_scan_jor_session_has_messages(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    from jor.session.schema import JorMessage
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = [JorMessage.model_validate_json(line) for line in session_file.read_text().splitlines() if line]
    assert len(messages) > 0


def test_scan_maps_user_role(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    from jor.session.schema import JorMessage
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = [JorMessage.model_validate_json(line) for line in session_file.read_text().splitlines() if line]
    user_msgs = [m for m in messages if m.role == "user"]
    assert len(user_msgs) == 2


def test_scan_maps_assistant_with_tool_calls(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    from jor.session.schema import JorMessage
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = [JorMessage.model_validate_json(line) for line in session_file.read_text().splitlines() if line]
    assistant_with_tools = [m for m in messages if m.role == "assistant" and m.tool_calls]
    assert len(assistant_with_tools) == 1
    assert assistant_with_tools[0].tool_calls[0].name == "Read"


def test_scan_maps_tool_result(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    from jor.session.schema import JorMessage
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = [JorMessage.model_validate_json(line) for line in session_file.read_text().splitlines() if line]
    tool_results = [m for m in messages if m.role == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0].tool_result is not None
    assert tool_results[0].tool_result.tool_call_id == "tool-001"


def test_scan_stores_git_branch_in_metadata(claude_home: Path, jor_home: Path):
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    from jor.session.schema import JorMessage
    c = ClaudeCodeConnector(claude_home=claude_home)
    entry = c.scan(jor_home)[0]
    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = [JorMessage.model_validate_json(line) for line in session_file.read_text().splitlines() if line]
    msg = messages[0]
    assert msg.metadata is not None
    assert msg.metadata.get("gitBranch") == "main"


def test_scan_title_truncated_to_80_chars(tmp_path: Path, jor_home: Path):
    """Title is truncated to 80 chars if first user message is long."""
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    long_msg = "A" * 100
    session_dir = tmp_path / ".claude" / "projects" / "proj"
    session_dir.mkdir(parents=True)
    import json
    line = json.dumps({"type": "user", "message": {"role": "user", "content": long_msg}, "timestamp": "2026-01-01T00:00:00Z", "sessionId": "s1", "cwd": "/proj"})
    (session_dir / "s1.jsonl").write_text(line + "\n")
    c = ClaudeCodeConnector(claude_home=tmp_path / ".claude")
    entry = c.scan(jor_home)[0]
    assert len(entry.title) <= 80


def test_scan_handles_empty_file(tmp_path: Path, jor_home: Path):
    """Empty session file is skipped without crashing."""
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    session_dir = tmp_path / ".claude" / "projects" / "proj"
    session_dir.mkdir(parents=True)
    (session_dir / "empty.jsonl").write_text("")
    c = ClaudeCodeConnector(claude_home=tmp_path / ".claude")
    entries = c.scan(jor_home)
    assert entries == []


def test_scan_handles_malformed_file(tmp_path: Path, jor_home: Path):
    """Malformed JSONL is skipped without crashing."""
    from jor.discovery.connectors.claude_code import ClaudeCodeConnector
    session_dir = tmp_path / ".claude" / "projects" / "proj"
    session_dir.mkdir(parents=True)
    (session_dir / "bad.jsonl").write_text("not json at all\n{also bad}\n")
    c = ClaudeCodeConnector(claude_home=tmp_path / ".claude")
    entries = c.scan(jor_home)
    assert entries == []
