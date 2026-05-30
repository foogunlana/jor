"""Jor CLI entry point."""

from __future__ import annotations

import functools
import logging
import time
from pathlib import Path

import click

from jor.connectors.claude.connector import ClaudeConnector
from jor.connectors.codex.connector import CodexConnector
from jor.core.index import load_index
from jor.core.reader import read_session
from jor.core.scanner import Scanner
from jor.spinner import Spinner

log = logging.getLogger("jor")

JOR_HOME = Path.home() / ".jor"

CONNECTORS = {
    "claude": ClaudeConnector,
    "codex": CodexConnector,
}


def _verbose_option(fn):
    """Add -v/--verbose to a command and configure logging."""
    @click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging with timing")
    @functools.wraps(fn)
    def wrapper(*args, verbose: bool, **kwargs):
        if verbose:
            logging.basicConfig(format="%(message)s", level=logging.DEBUG)
        return fn(*args, **kwargs)
    return wrapper


def _connector_for(tool: str) -> ClaudeConnector | CodexConnector:
    return CONNECTORS[tool]()


def _jor_home() -> Path:
    home = JOR_HOME
    home.mkdir(exist_ok=True)
    (home / "sessions").mkdir(exist_ok=True)
    return home


SHELL_INIT = """\
jor() {
  if [ "$1" = "open" ]; then
    eval "$(command jor "$@")"
  else
    command jor "$@"
  fi
}"""


@click.group()
def main() -> None:
    """Jor — list and continue AI sessions across tools."""


@main.command()
@click.argument("shell", type=click.Choice(["zsh", "bash"]))
def init(shell: str) -> None:
    """Print shell function for eval. Usage: eval "$(jor init zsh)" """
    click.echo(SHELL_INIT)


@main.command(name="list")
@click.option("--codex", is_flag=True, help="Show only Codex sessions")
@click.option("--claude", "claude", is_flag=True, help="Show only Claude sessions")
@click.option("--query", "-q", default=None, help="Search titles")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results")
@click.option("--path", default=None, help="Filter by workspace path")
@_verbose_option
def list_sessions(codex: bool, claude: bool, query: str | None, limit: int, path: str | None) -> None:
    """List indexed sessions."""
    jor_home = _jor_home()

    # Incremental discovery
    connectors = [ClaudeConnector(), CodexConnector()]
    scanner = Scanner(connectors=connectors, jor_home=jor_home)
    t0 = time.monotonic()
    with Spinner("Searching..."):
        scanner.run_incremental()
    log.debug("discovery: %.2fs", time.monotonic() - t0)

    t0 = time.monotonic()
    index = load_index(jor_home / "index.json")
    log.debug("load index (%d sessions): %.2fs", len(index.sessions), time.monotonic() - t0)
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


@main.command(name="open")
@click.argument("session_id")
@click.option("--codex", is_flag=True, help="Open in Codex")
@click.option("--claude", "claude", is_flag=True, help="Open in Claude")
@_verbose_option
def open_session(session_id: str, codex: bool, claude: bool) -> None:
    """Convert a session and launch the target tool.

    Defaults to the session's original tool. Use --codex or --claude to
    open in a different tool.
    """
    t0 = time.monotonic()
    jor_home = _jor_home()
    index = load_index(jor_home / "index.json")
    log.debug("load index: %.2fs", time.monotonic() - t0)

    entry = next((s for s in index.sessions if s.id.startswith(session_id)), None)
    if entry is None:
        click.echo(f"Session '{session_id}' not found. Run `jor list` first.", err=True)
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

    same_tool = entry.tool == target
    connector = _connector_for(target)
    log.debug("target=%s same_tool=%s", target, same_tool)

    if same_tool:
        log.debug("resuming directly (no conversion)")
        connector.launch([], session_id=entry.source_id, project=entry.project)
    else:
        session_file = jor_home / "sessions" / f"{entry.id}.jsonl"
        t0 = time.monotonic()
        messages = read_session(session_file)
        log.debug("read session (%d messages): %.2fs", len(messages), time.monotonic() - t0)
        t0 = time.monotonic()
        connector.launch(messages, session_id=None, project=entry.project)
        log.debug("write + launch: %.2fs", time.monotonic() - t0)
