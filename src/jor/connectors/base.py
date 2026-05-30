"""Base class for tool connectors.

Each tool connector (Claude, Codex, etc.) inherits from BaseConnector
and provides:

Reading (discover):
- TOOL_NAME, GLOB_PATTERN, DETECT_PATH, DEFAULT_HOME, STRICT_JSON
- from_record(record, source_id) -> JorMessage | list[JorMessage] | None
- extract_metadata(records, session_path) -> dict

Writing (convert):
- to_record(msg, session_id) -> dict
- resume_command(session_file) -> str
- write_session(messages, project) -> tuple[str, str, Path]

Launching (open):
- RESUME_CMD — format string (e.g. "claude --resume {session_id}")
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from jor.core.index import IndexEntry
from jor.core.schema import JorMessage


class BaseConnector(ABC):
    """One class per tool — handles reading, writing, and launching sessions."""

    # --- Class attributes (set by each subclass) ---
    TOOL_NAME: str
    GLOB_PATTERN: str
    DETECT_PATH: str
    DEFAULT_HOME: Path
    STRICT_JSON: bool
    RESUME_CMD: str  # e.g. "claude --resume {session_id}"

    def __init__(self, home_path: Path | None = None) -> None:
        self._home = home_path or self.DEFAULT_HOME

    # --- Reading: discover native sessions ---

    def name(self) -> str:
        return self.TOOL_NAME

    def detect(self) -> bool:
        return (self._home / self.DETECT_PATH).exists()

    def scan(self, jor_home: Path, since: float | None = None) -> list[IndexEntry]:
        entries: list[IndexEntry] = []
        for session_path in self._home.glob(self.GLOB_PATTERN):
            if since is not None and session_path.stat().st_mtime <= since:
                continue
            entry = self._process(session_path, jor_home)
            if entry is not None:
                entries.append(entry)
        return entries

    @abstractmethod
    def from_record(self, record: dict, source_id: str) -> JorMessage | list[JorMessage] | None:
        """Convert a single native record to JorMessage(s). Return None to skip."""
        ...

    @abstractmethod
    def extract_metadata(self, records: list[dict], session_path: Path) -> dict:
        """Extract session metadata. Return dict with keys: title, project, started_at, source_id."""
        ...

    # --- Writing: convert jor sessions to native format ---

    @abstractmethod
    def to_record(self, msg: JorMessage, session_id: str) -> dict | list[dict]:
        """Convert one JorMessage to native record(s)."""
        ...

    @abstractmethod
    def resume_command(self, session_file: Path) -> str:
        """Shell command to resume this session in the target tool."""
        ...

    @abstractmethod
    def write_session(self, messages: list[JorMessage], project: str | None) -> tuple[str, str, Path]:
        """Write a new session file. Returns (session_id, resume_command, path)."""
        ...

    def write_jsonl(self, messages: list[JorMessage], path: Path, session_id: str) -> None:
        """Serialize messages to a JSONL file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        records: list[dict] = []
        for msg in messages:
            result = self.to_record(msg, session_id)
            if isinstance(result, list):
                records.extend(result)
            else:
                records.append(result)
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    # --- Launching: resume or write + launch ---

    def launch(self, messages: list[JorMessage], session_id: str | None = None, project: str | None = None) -> None:
        """Print shell commands for eval: cd to project dir and run the tool."""
        if session_id:
            cmd = self.RESUME_CMD.format(session_id=session_id)
        else:
            _, cmd, _ = self.write_session(messages, project)

        parts = []
        cwd = project if project and Path(project).is_dir() else None
        if cwd:
            parts.append(f"cd {shlex.quote(cwd)}")
        parts.append(cmd)
        print(" && ".join(parts))

    # --- Internal ---

    def _process(self, session_path: Path, jor_home: Path) -> IndexEntry | None:
        raw_lines = [line for line in session_path.read_text().splitlines() if line.strip()]
        if not raw_lines:
            return None

        records: list[dict] = []
        for line in raw_lines:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                if self.STRICT_JSON:
                    return None
                continue

        meta = self.extract_metadata(records, session_path)
        title = meta.get("title", "")
        project = meta.get("project", "")
        started_at = meta.get("started_at", "")
        source_id = meta.get("source_id", session_path.stem)

        messages: list[JorMessage] = []
        for rec in records:
            result = self.from_record(rec, source_id)
            if result is None:
                continue
            if isinstance(result, list):
                messages.extend(result)
            else:
                messages.append(result)

        if not messages:
            return None

        if not title:
            for msg in messages:
                if msg.role == "user" and msg.content:
                    title = msg.content[:80]
                    break

        if not title:
            title = session_path.stem

        entry_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(session_path)))
        jor_session = jor_home / "sessions" / f"{entry_id}.jsonl"
        jor_session.write_text(
            "\n".join(m.model_dump_json() for m in messages) + "\n"
        )

        return IndexEntry(
            id=entry_id,
            tool=self.TOOL_NAME,
            source_id=source_id,
            source_path=str(session_path),
            title=title,
            project=project,
            started_at=started_at,
            message_count=len(messages),
        )
