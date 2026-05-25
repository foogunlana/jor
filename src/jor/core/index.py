"""Session index stored at ~/.jor/index.json.

The index is a lightweight catalog of all discovered sessions. It stores
metadata (tool, title, project, message count) but not the messages
themselves. Full session content lives in ~/.jor/sessions/<id>.jsonl.

The scanner builds this index by running connectors. The CLI reads it
for list, convert, and open commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class IndexEntry(BaseModel):
    """Metadata for one discovered session.

    source_id is the session's original ID in its native tool (e.g. the
    Claude Code sessionId or Codex thread UUID). source_path is the
    absolute path to the original session file on disk.
    """

    id: str
    tool: str
    source_id: str
    source_path: str
    title: str
    project: str
    started_at: str
    message_count: int
    ended_at: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    summary: Optional[str] = None


class SessionIndex(BaseModel):
    """The full index: a list of entries plus scan metadata."""

    version: int = 1
    sessions: list[IndexEntry] = []
    last_scan: Optional[str] = None


def load_index(path: Path) -> SessionIndex:
    """Load the index from disk, or return an empty index if missing."""
    if not path.exists():
        return SessionIndex()
    return SessionIndex.model_validate_json(path.read_text())


def save_index(index: SessionIndex, path: Path) -> None:
    """Write the index to disk as formatted JSON."""
    path.write_text(index.model_dump_json(indent=2))


def upsert_session(index: SessionIndex, entry: IndexEntry) -> None:
    """Add a new entry or update an existing one (matched by id)."""
    for i, s in enumerate(index.sessions):
        if s.id == entry.id:
            index.sessions[i] = entry
            return
    index.sessions.append(entry)
