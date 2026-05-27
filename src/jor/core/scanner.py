"""Scanner — runs all connectors and builds the session index.

The scanner is the orchestrator for `jor discover`. It iterates over
registered connectors (Claude, Codex, etc.), asks each to scan
for sessions, and upserts the results into the shared index.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from jor.core.index import IndexEntry, load_index, save_index, upsert_session


class Connector(Protocol):
    """Interface that every tool connector must implement."""

    def name(self) -> str: ...
    def detect(self) -> bool: ...
    def scan(self, jor_home: Path) -> list[IndexEntry]: ...


class Scanner:
    """Runs all detected connectors and updates the index."""

    def __init__(self, connectors: list[Connector], jor_home: Path) -> None:
        self._connectors = connectors
        self._jor_home = jor_home

    def run(self) -> dict[str, int]:
        index_path = self._jor_home / "index.json"
        index = load_index(index_path)
        counts: dict[str, int] = {}

        for connector in self._connectors:
            if not connector.detect():
                continue
            entries = connector.scan(jor_home=self._jor_home)
            for entry in entries:
                upsert_session(index, entry)
            counts[connector.name()] = len(entries)

        index.last_scan = datetime.now(timezone.utc).isoformat()
        save_index(index, index_path)
        return counts
