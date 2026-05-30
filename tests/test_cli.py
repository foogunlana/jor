"""Tests for the CLI commands: list, open."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from jor.cli import main
from jor.core.index import IndexEntry, SessionIndex


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(
    id: str = "abc12345-0000-0000-0000-000000000000",
    tool: str = "claude",
    title: str = "Test session",
    project: str = "/home/user/project",
    started_at: str = "2026-04-01T10:00:00Z",
    message_count: int = 5,
    parent_id: str | None = None,
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
        parent_id=parent_id,
    )


# ---------------------------------------------------------------------------

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
    assert "Modified" in result.output
    assert "Msgs" in result.output
    assert "Project" in result.output
    assert "Parent" in result.output
    assert "Title" in result.output
    # data row
    assert "abc12345" in result.output
    assert "claude" in result.output
    assert "project" in result.output  # basename of /home/user/project
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
        _entry(id="aaa00000-0000-0000-0000-000000000000", tool="claude"),
        _entry(id="bbb00000-0000-0000-0000-000000000000", tool="codex"),
    ])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list", "--codex"])

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
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"), \
         patch("jor.cli.Spinner"):
        MockScanner.return_value.run_incremental.return_value = {}
        result = runner.invoke(main, ["list", "--limit", "3"])

    assert result.exit_code == 0
    lines = [l for l in result.output.splitlines() if "session" in l]
    assert len(lines) == 3


def test_list_shows_parent_id_for_copies(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[
        _entry(id="parent00-0000-0000-0000-000000000000", title="Original"),
        _entry(id="child000-0000-0000-0000-000000000000", title="Copy", parent_id="parent00-0000-0000-0000-000000000000"),
    ])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "parent00" in result.output  # parent_id shown truncated


def test_list_runs_incremental_discovery(tmp_path: Path) -> None:
    """jor list should run incremental discovery before listing."""
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"):
        MockScanner.return_value.run_incremental.return_value = {}
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    MockScanner.return_value.run_incremental.assert_called_once()


def test_list_no_discovery_message_in_output(tmp_path: Path) -> None:
    """Incremental discovery should not leave messages in stdout."""
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"):
        MockScanner.return_value.run_incremental.return_value = {"claude": 3}
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "Found" not in result.output


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
# jor open
# ---------------------------------------------------------------------------


def test_open_calls_launcher(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]
    mock_connector = MagicMock()

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli._connector_for", return_value=mock_connector):
        result = runner.invoke(main, ["open", "abc12345"])

    mock_connector.launch.assert_called_once()


def test_open_codex_flag_uses_codex_launcher(tmp_path: Path) -> None:
    runner = CliRunner()
    entry = _entry()
    index = SessionIndex(sessions=[entry])
    messages = [MagicMock()]
    mock_connector = MagicMock()

    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.read_session", return_value=messages), \
         patch("jor.cli._connector_for", return_value=mock_connector) as mock_for:
        result = runner.invoke(main, ["open", "abc12345", "--codex"])

    mock_for.assert_called_with("codex")
    mock_connector.launch.assert_called_once()


def test_open_unknown_id_exits_nonzero(tmp_path: Path) -> None:
    runner = CliRunner()
    index = SessionIndex(sessions=[])
    with patch("jor.cli.load_index", return_value=index):
        result = runner.invoke(main, ["open", "nonexistent"])

    assert result.exit_code != 0
