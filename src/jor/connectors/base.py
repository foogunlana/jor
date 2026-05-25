"""Base classes for connectors, writers, and launchers.

All tool connectors inherit from BaseConnector. Each subclass provides:
- Class attributes: TOOL_NAME, GLOB_PATTERN, DETECT_PATH, DEFAULT_HOME, STRICT_JSON
- parse_record(record, source_id) -> JorMessage | list[JorMessage] | None
- extract_metadata(records, session_path) -> dict with keys: title, project, started_at, source_id

Writers inherit from BaseWriter. Each subclass provides:
- to_record(msg) -> dict — convert one JorMessage to the native format

Launchers inherit from BaseLauncher. Each subclass provides:
- RESUME_CMD — format string for the resume command (e.g. "claude --resume {session_id}")
- _write_session(messages, project) -> tuple[str, Path] — write session file and return (session_id, path)
"""

from __future__ import annotations

import json
import subprocess
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from jor.core.index import IndexEntry
from jor.core.schema import JorMessage


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class BaseConnector(ABC):
    """Shared scanning boilerplate for JSONL-based session connectors."""

    TOOL_NAME: str
    GLOB_PATTERN: str
    DETECT_PATH: str
    DEFAULT_HOME: Path
    STRICT_JSON: bool

    def __init__(self, home_path: Path | None = None) -> None:
        self._home = home_path or self.DEFAULT_HOME

    def name(self) -> str:
        return self.TOOL_NAME

    def detect(self) -> bool:
        return (self._home / self.DETECT_PATH).exists()

    def scan(self, jor_home: Path) -> list[IndexEntry]:
        entries: list[IndexEntry] = []
        for session_path in self._home.glob(self.GLOB_PATTERN):
            entry = self._process(session_path, jor_home)
            if entry is not None:
                entries.append(entry)
        return entries

    @abstractmethod
    def parse_record(self, record: dict, source_id: str) -> JorMessage | list[JorMessage] | None:
        """Convert a single native record to JorMessage(s). Return None to skip."""
        ...

    @abstractmethod
    def extract_metadata(self, records: list[dict], session_path: Path) -> dict:
        """Extract session metadata. Return dict with keys: title, project, started_at, source_id."""
        ...

    def _process(self, session_path: Path, jor_home: Path) -> IndexEntry | None:
        raw_lines = [line for line in session_path.read_text().splitlines() if line.strip()]
        if not raw_lines:
            return None

        # Parse all lines; behavior depends on STRICT_JSON
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
            result = self.parse_record(rec, source_id)
            if result is None:
                continue
            if isinstance(result, list):
                messages.extend(result)
            else:
                messages.append(result)

        if not messages:
            return None

        # Title fallback: first user message content[:80]
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


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


class BaseWriter(ABC):
    """Shared JSONL writing boilerplate for session writers."""

    @abstractmethod
    def to_record(self, msg: JorMessage, session_id: str) -> dict | list[dict]:
        """Convert one JorMessage to native record(s)."""
        ...

    @abstractmethod
    def resume_command(self, session_file: Path) -> str:
        """Shell command to resume this session in the target tool."""
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


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------


class BaseLauncher(ABC):
    """Shared launch boilerplate: resume existing or write + launch new."""

    RESUME_CMD: str  # e.g. "claude --resume {session_id}"

    def __init__(self, home_path: Path) -> None:
        self._home = home_path

    @abstractmethod
    def _write_session(self, messages: list[JorMessage], project: str | None) -> tuple[str, str, Path]:
        """Write a new session file. Returns (session_id, resume_command, path)."""
        ...

    def launch(self, messages: list[JorMessage], session_id: str | None = None, project: str | None = None) -> None:
        if session_id:
            cmd = self.RESUME_CMD.format(session_id=session_id)
        else:
            _, cmd, _ = self._write_session(messages, project)

        cwd = project if project and Path(project).is_dir() else None
        subprocess.run(cmd, shell=True, cwd=cwd)
