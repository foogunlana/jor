"""Jor CLI entry point."""

import click


@click.group()
def main() -> None:
    """Jor — discover, convert, and continue AI sessions across tools."""


@main.command()
def discover() -> None:
    """Scan the local machine for AI sessions and build the index."""
    click.echo("Not yet implemented.")


@main.command()
def list() -> None:
    """List indexed sessions."""
    click.echo("Not yet implemented.")


@main.command()
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Convert to Codex format (default: Claude Code)")
def convert(session_id: str, codex: bool) -> None:
    """Translate a session to the target tool's native format."""
    click.echo("Not yet implemented.")


@main.command()
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Open in Codex (default: Claude Code)")
def open(session_id: str, codex: bool) -> None:
    """Convert a session and launch the target tool."""
    click.echo("Not yet implemented.")
