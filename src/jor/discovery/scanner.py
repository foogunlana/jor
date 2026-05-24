"""Scanner — orchestrates connectors, builds session index."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jor.discovery.connectors.base import Connector
from jor.discovery.index import load_index, save_index, upsert_session


class Scanner:
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
