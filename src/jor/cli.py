"""Jor CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from jor.discovery.connectors.claude_code import ClaudeCodeConnector
from jor.discovery.connectors.codex import CodexConnector
from jor.discovery.index import load_index
from jor.discovery.scanner import Scanner
from jor.launchers.claude_code import ClaudeCodeLauncher
from jor.launchers.codex import CodexLauncher
from jor.session.reader import read_session
from jor.session.writers.claude_code import ClaudeCodeWriter
from jor.session.writers.codex import CodexWriter

JOR_HOME = Path.home() / ".jor"


def _jor_home() -> Path:
    home = JOR_HOME
    home.mkdir(exist_ok=True)
    (home / "sessions").mkdir(exist_ok=True)
    return home


@click.group()
def main() -> None:
    """Jor — discover, convert, and continue AI sessions across tools."""


@main.command()
def discover() -> None:
    """Scan the local machine for AI sessions and build the index."""
    jor_home = _jor_home()
    connectors = [ClaudeCodeConnector(), CodexConnector()]
    counts = Scanner(connectors=connectors, jor_home=jor_home).run()

    if not counts:
        click.echo("No sessions found.")
        return

    total = sum(counts.values())
    breakdown = ", ".join(f"{n} {tool}" for tool, n in counts.items())
    click.echo(f"Found {total} sessions: {breakdown}")
    click.echo(f"Index updated at {jor_home / 'index.json'}")


@main.command(name="list")
@click.option("--tool", default=None, help="Filter by source tool (claude_code, codex)")
@click.option("--query", "-q", default=None, help="Search titles")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results")
@click.option("--path", default=None, help="Filter by workspace path")
def list_sessions(tool: str | None, query: str | None, limit: int, path: str | None) -> None:
    """List indexed sessions."""
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")
    sessions = index.sessions

    if tool:
        sessions = [s for s in sessions if s.tool == tool]
    if query:
        q = query.lower()
        sessions = [s for s in sessions if q in s.title.lower()]
    if path:
        sessions = [s for s in sessions if path in s.project]

    sessions = sessions[:limit]

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<10} {'Tool':<12} {'Date':<12} {'Msgs':>5}  Title")
    click.echo("-" * 60)
    for s in sessions:
        date = s.started_at[:10] if s.started_at else "unknown"
        click.echo(f"{s.id[:8]:<10} {s.tool:<12} {date:<12} {s.message_count:>5}  {s.title[:40]}")


@main.command()
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Convert to Codex format")
@click.option("--claude-code", "claude_code", is_flag=True, help="Convert to Claude Code format")
def convert(session_id: str, codex: bool, claude_code: bool) -> None:
    """Translate a session to the target tool's native format.

    Defaults to the opposite tool (codex→claude-code, claude-code→codex).
    Use --codex or --claude-code to specify explicitly.
    """
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")

    entry = next((s for s in index.sessions if s.id.startswith(session_id)), None)
    if entry is None:
        click.echo(f"Session '{session_id}' not found. Run `jor discover` first.", err=True)
        raise SystemExit(1)

    if codex and claude_code:
        click.echo("Cannot specify both --codex and --claude-code.", err=True)
        raise SystemExit(1)

    if codex:
        target = "codex"
    elif claude_code:
        target = "claude_code"
    else:
        target = "codex" if entry.tool == "claude_code" else "claude_code"

    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = read_session(session_file)

    if target == "codex":
        writer = CodexWriter()
        target_dir = Path.home() / ".codex" / "sessions"
        _, out = writer.write(messages, target_dir)
    else:
        writer = ClaudeCodeWriter()
        target_dir = Path.home() / ".claude" / "projects" / "jor-imported"
        _, out = writer.write(messages, target_dir / f"{entry.id}.jsonl")

    cmd = writer.resume_command(out)
    click.echo(f"Session written to {out}")
    click.echo(f"\nTo resume, run:\n  {cmd}")


@main.command(name="open")
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Open in Codex")
@click.option("--claude-code", "claude_code", is_flag=True, help="Open in Claude Code")
def open_session(session_id: str, codex: bool, claude_code: bool) -> None:
    """Convert a session and launch the target tool.

    Defaults to the session's original tool. Use --codex or --claude-code to
    open in a different tool.
    """
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")

    entry = next((s for s in index.sessions if s.id.startswith(session_id)), None)
    if entry is None:
        click.echo(f"Session '{session_id}' not found. Run `jor discover` first.", err=True)
        raise SystemExit(1)

    if codex and claude_code:
        click.echo("Cannot specify both --codex and --claude-code.", err=True)
        raise SystemExit(1)

    if codex:
        target = "codex"
    elif claude_code:
        target = "claude_code"
    else:
        target = entry.tool

    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = read_session(session_file)

    same_tool = entry.tool == target
    source_id = entry.source_id if same_tool else None

    if target == "codex":
        CodexLauncher().launch(messages, session_id=source_id, project=entry.project)
    else:
        ClaudeCodeLauncher().launch(messages, session_id=source_id, project=entry.project)
