"""Session index — read/write ~/.jor/index.json."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class IndexEntry(BaseModel):
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
    version: int = 1
    sessions: list[IndexEntry] = []
    last_scan: Optional[str] = None


def load_index(path: Path) -> SessionIndex:
    if not path.exists():
        return SessionIndex()
    return SessionIndex.model_validate_json(path.read_text())


def save_index(index: SessionIndex, path: Path) -> None:
    path.write_text(index.model_dump_json(indent=2))


def upsert_session(index: SessionIndex, entry: IndexEntry) -> None:
    for i, s in enumerate(index.sessions):
        if s.id == entry.id:
            index.sessions[i] = entry
            return
    index.sessions.append(entry)
