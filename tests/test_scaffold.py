"""Verify the project installs and CLI entry point works."""

from click.testing import CliRunner

from jor import __version__
from jor.cli import main


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "open" in result.output


def test_cli_list() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["list"])
    assert result.exit_code == 0


def test_cli_open_unknown_session() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["open", "nonexistent-session-id"])
    assert result.exit_code == 1
