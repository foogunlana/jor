"""Tests for the 4 CLI commands: discover, list, convert, open."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jor.cli import main
from jor.discovery.index import IndexEntry, SessionIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    id: str = "abc12345-0000-0000-0000-000000000000",
    tool: str = "claude_code",
    title: str = "Test session",
    project: str = "/home/user/project",
    started_at: str = "2026-04-01T10:00:00Z",
    message_count: int = 5,
) -> IndexEntry:
    return IndexEntry(
        id=id,
        tool=tool,
        source_id="src-1",
        source_path="/some/path",
        title=title,
        project=project,
        started_at=started_at,
        message_count=message_count,
    )


# ---------------------------------------------------------------------------
# jor discover
# ---------------------------------------------------------------------------


def test_discover_prints_found_sessions(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch("jor.cli.Scanner") as MockScanner, \
             patch("jor.cli.ClaudeCodeConnector"), \
             patch("jor.cli.CodexConnector"):
            MockScanner.return_value.run.return_value = {"claude_code": 3, "codex": 1}
            result = runner.invoke(main, ["discover"])

    assert result.exit_code == 0
    assert "Found 4 sessions" in result.output
    assert "3 claude_code" in result.output
    assert "1 codex" in result.output


def test_discover_no_sessions_found(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch("jor.cli.Scanner") as MockScanner, \
             patch("jor.cli.ClaudeCodeConnector"), \
             patch("jor.cli.CodexConnector"):
            MockScanner.return_value.run.return_value = {}
            result = runner.invoke(main, ["discover"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


# ---------------------------------------------------------------------------
# jor list
# ---------------------------------------------------------------------------


def test_list_prints_table_with_columns(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    # header columns
    assert "ID" in result.output
    assert "Tool" in result.output
    assert "Date" in result.output
    assert "Msgs" in result.output
    assert "Title" in result.output
    # data row
    assert "abc12345" in result.output
    assert "claude_code" in result.output
    assert "Test session" in result.output


def test_list_empty_index_prints_no_sessions(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_list_filter_by_tool(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[
        _entry(id="aaa00000-0000-0000-0000-000000000000", tool="claude_code"),
        _entry(id="bbb00000-0000-0000-0000-000000000000", tool="codex"),
    ])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list", "--tool", "codex"])

    assert result.exit_code == 0
    assert "bbb00000" in result.output
    assert "aaa00000" not in result.output


def test_list_filter_by_query(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[
        _entry(id="aaa00000-0000-0000-0000-000000000000", title="auth refactor"),
        _entry(id="bbb00000-0000-0000-0000-000000000000", title="UI changes"),
    ])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list", "--query", "auth"])

    assert result.exit_code == 0
    assert "auth refactor" in result.output
    assert "UI changes" not in result.output


def test_list_limit_restricts_results(tmp_path: Path) -> None:
    runner = CliRunner()
    sessions = [
        _entry(id=f"{i:08x}-0000-0000-0000-000000000000", title=f"session {i}")
        for i in range(10)
    ]
    index = SessionIndex(sessions=sessions)
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list", "--limit", "3"])

    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if "session" in l]
    assert len(lines) == 3


def test_list_filter_by_path(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[
        _entry(id="aaa00000-0000-0000-0000-000000000000", project="/home/user/myapp"),
        _entry(id="bbb00000-0000-0000-0000-000000000000", project="/home/user/other"),
    ])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list", "--path", "myapp"])

    assert result.exit_code == 0
    assert "aaa00000" in result.output
    assert "bbb00000" not in result.output


# ---------------------------------------------------------------------------
# jor convert
# ---------------------------------------------------------------------------


def test_convert_default_writes_claude_code_format(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli.ClaudeCodeWriter") as MockWriter:
        mock_writer = MockWriter.return_value
        out_path = tmp_path / "out.jsonl"
        mock_writer.write.return_value = ("sess-id", out_path)
        mock_writer.resume_command.return_value = "claude --resume sess-id"

        result = runner.invoke(main, ["convert", "abc12345"])

    assert result.exit_code == 0
    assert str(out_path) in result.output
    assert "claude --resume sess-id" in result.output
    mock_writer.write.assert_called_once()


def test_convert_codex_flag_writes_codex_format(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli.CodexWriter") as MockWriter:
        mock_writer = MockWriter.return_value
        out_path = tmp_path / "rollout-xyz.jsonl"
        mock_writer.write.return_value = ("xyz", out_path)
        mock_writer.resume_command.return_value = "codex --resume xyz"

        result = runner.invoke(main, ["convert", "abc12345", "--codex"])

    assert result.exit_code == 0
    assert str(out_path) in result.output
    assert "codex --resume xyz" in result.output
    mock_writer.write.assert_called_once()


def test_convert_unknown_id_prints_error_and_exits(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["convert", "nonexistent"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "not found" in (result.output + (result.exception or "")).lower()


def test_convert_prints_resume_command(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli.ClaudeCodeWriter") as MockWriter:
        mock_writer = MockWriter.return_value
        out_path = tmp_path / "session.jsonl"
        mock_writer.write.return_value = ("sid", out_path)
        mock_writer.resume_command.return_value = "claude --resume sid"

        result = runner.invoke(main, ["convert", "abc12345"])

    assert "claude --resume sid" in result.output


# ---------------------------------------------------------------------------
# jor open
# ---------------------------------------------------------------------------


def test_open_calls_launcher(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli.ClaudeCodeLauncher") as MockLauncher:
        mock_launcher = MockLauncher.return_value
        result = runner.invoke(main, ["open", "abc12345"])

    assert result.exit_code == 0
    mock_launcher.launch.assert_called_once()


def test_open_codex_flag_uses_codex_launcher(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli.CodexLauncher") as MockLauncher:
        mock_launcher = MockLauncher.return_value
        result = runner.invoke(main, ["open", "abc12345", "--codex"])

    assert result.exit_code == 0
    mock_launcher.launch.assert_called_once()


def test_open_unknown_id_exits_nonzero(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["open", "nonexistent"])

    assert result.exit_code != 0
