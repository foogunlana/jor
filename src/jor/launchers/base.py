"""Launcher protocol — converts session and launches the target tool."""

from pathlib import Path
from typing import Protocol

from jor.session.schema import JorMessage


class Launcher(Protocol):
    def launch(self, messages: list[JorMessage], session_id: str) -> None: ...
