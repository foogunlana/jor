"""Jor CLI entry point."""

from __future__ import annotations

import uuid
from pathlib import Path

import click

from jor.connectors.claude_code.connector import ClaudeCodeConnector
from jor.connectors.codex.connector import CodexConnector
from jor.core.index import IndexEntry, load_index, save_index, upsert_session
from jor.core.reader import read_session
from jor.core.scanner import Scanner

JOR_HOME = Path.home() / ".jor"

CONNECTORS = {
    "claude_code": ClaudeCodeConnector,
    "codex": CodexConnector,
}


def _connector_for(tool: str) -> ClaudeCodeConnector | CodexConnector:
    return CONNECTORS[tool]()


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
@click.option("--codex", is_flag=True, help="Show only Codex sessions")
@click.option("--claude-code", "claude_code", is_flag=True, help="Show only Claude Code sessions")
@click.option("--query", "-q", default=None, help="Search titles")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results")
@click.option("--path", default=None, help="Filter by workspace path")
def list_sessions(codex: bool, claude_code: bool, query: str | None, limit: int, path: str | None) -> None:
    """List indexed sessions."""
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")
    sessions = index.sessions

    if codex:
        sessions = [s for s in sessions if s.tool == "codex"]
    elif claude_code:
        sessions = [s for s in sessions if s.tool == "claude_code"]
    if query:
        q = query.lower()
        sessions = [s for s in sessions if q in s.title.lower()]
    if path:
        sessions = [s for s in sessions if path in s.project]

    sessions.sort(key=lambda s: s.started_at or "", reverse=True)
    sessions = sessions[:limit]

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<10} {'Tool':<12} {'Date':<12} {'Msgs':>5}  {'Project':<20} {'Parent':<10} Title")
    click.echo("-" * 90)
    for s in sessions:
        date = s.started_at[:10] if s.started_at else "unknown"
        project = Path(s.project).name if s.project else ""
        parent = s.parent_id[:8] if s.parent_id else ""
        click.echo(f"{s.id[:8]:<10} {s.tool:<12} {date:<12} {s.message_count:>5}  {project:<20} {parent:<10} {s.title[:40]}")


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

    connector = _connector_for(target)
    new_id, cmd, out = connector.write_session(messages, entry.project)

    new_entry = IndexEntry(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, str(out))),
        tool=target,
        source_id=new_id,
        source_path=str(out),
        title=entry.title,
        project=entry.project,
        started_at=entry.started_at,
        message_count=entry.message_count,
        parent_id=entry.id,
    )
    upsert_session(index, new_entry)
    save_index(index, jor_home / "index.json")

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

    connector = _connector_for(target)
    cmd, cwd = connector.launch(messages, session_id=source_id, project=entry.project)

    # After session exits, print resume command with cd if needed
    if cwd and str(Path.cwd()) != cwd:
        click.echo(f"\nTo resume, run:\n  cd {cwd} && {cmd}")
    else:
        click.echo(f"\nTo resume, run:\n  {cmd}")
