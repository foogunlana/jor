"""Jor CLI entry point."""

from __future__ import annotations

import uuid
from pathlib import Path

import click

from jor.connectors.claude.connector import ClaudeConnector
from jor.connectors.codex.connector import CodexConnector
from jor.core.index import IndexEntry, load_index, save_index, upsert_session
from jor.core.reader import read_session
from jor.core.scanner import Scanner
from jor.spinner import Spinner

JOR_HOME = Path.home() / ".jor"

CONNECTORS = {
    "claude": ClaudeConnector,
    "codex": CodexConnector,
}


def _connector_for(tool: str) -> ClaudeConnector | CodexConnector:
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
    connectors = [ClaudeConnector(), CodexConnector()]
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
@click.option("--claude", "claude", is_flag=True, help="Show only Claude sessions")
@click.option("--query", "-q", default=None, help="Search titles")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results")
@click.option("--path", default=None, help="Filter by workspace path")
def list_sessions(codex: bool, claude: bool, query: str | None, limit: int, path: str | None) -> None:
    """List indexed sessions."""
    jor_home = _jor_home()

    # Incremental discovery
    connectors = [ClaudeConnector(), CodexConnector()]
    scanner = Scanner(connectors=connectors, jor_home=jor_home)
    with Spinner("Searching..."):
        scanner.run_incremental()

    index = load_index(jor_home / "index.json")
    sessions = index.sessions

    if codex:
        sessions = [s for s in sessions if s.tool == "codex"]
    elif claude:
        sessions = [s for s in sessions if s.tool == "claude"]
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

    click.echo(f"{'ID':<10} {'Tool':<12} {'Date':<12} {'Modified':<12} {'Msgs':>5}  {'Project':<20} {'Parent':<10} Title")
    click.echo("-" * 102)
    for s in sessions:
        date = s.started_at[:10] if s.started_at else "unknown"
        source = Path(s.source_path)
        modified = ""
        if source.exists():
            from datetime import datetime, timezone
            mtime = source.stat().st_mtime
            modified = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        project = Path(s.project).name if s.project else ""
        parent = s.parent_id[:8] if s.parent_id else ""
        click.echo(f"{s.id[:8]:<10} {s.tool:<12} {date:<12} {modified:<12} {s.message_count:>5}  {project:<20} {parent:<10} {s.title[:40]}")


@main.command()
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Convert to Codex format")
@click.option("--claude", "claude", is_flag=True, help="Convert to Claude format")
def convert(session_id: str, codex: bool, claude: bool) -> None:
    """Translate a session to the target tool's native format.

    Defaults to the opposite tool (codex→claude, claude→codex).
    Use --codex or --claude to specify explicitly.
    """
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")

    entry = next((s for s in index.sessions if s.id.startswith(session_id)), None)
    if entry is None:
        click.echo(f"Session '{session_id}' not found. Run `jor discover` first.", err=True)
        raise SystemExit(1)

    if codex and claude:
        click.echo("Cannot specify both --codex and --claude.", err=True)
        raise SystemExit(1)

    if codex:
        target = "codex"
    elif claude:
        target = "claude"
    else:
        target = "codex" if entry.tool == "claude" else "claude"

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
@click.option("--claude", "claude", is_flag=True, help="Open in Claude")
def open_session(session_id: str, codex: bool, claude: bool) -> None:
    """Convert a session and launch the target tool.

    Defaults to the session's original tool. Use --codex or --claude to
    open in a different tool.
    """
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")

    entry = next((s for s in index.sessions if s.id.startswith(session_id)), None)
    if entry is None:
        click.echo(f"Session '{session_id}' not found. Run `jor discover` first.", err=True)
        raise SystemExit(1)

    if codex and claude:
        click.echo("Cannot specify both --codex and --claude.", err=True)
        raise SystemExit(1)

    if codex:
        target = "codex"
    elif claude:
        target = "claude"
    else:
        target = entry.tool

    session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
    messages = read_session(session_file)

    same_tool = entry.tool == target
    source_id = entry.source_id if same_tool else None

    connector = _connector_for(target)
    # exec replaces this process — cd's to project dir first
    connector.launch(messages, session_id=source_id, project=entry.project)
