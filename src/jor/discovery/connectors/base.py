"""Connector protocol — all source connectors implement this interface."""

from pathlib import Path
from typing import Protocol

from jor.discovery.index import IndexEntry


class Connector(Protocol):
    def name(self) -> str: ...
    def detect(self) -> bool: ...
    def scan(self, jor_home: Path) -> list[IndexEntry]: ...
