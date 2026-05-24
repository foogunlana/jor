"""Launcher protocol — converts session and launches the target tool."""

from typing import Protocol

from jor.session.schema import JorMessage


class Launcher(Protocol):
    def launch(self, messages: list[JorMessage], session_id: str) -> None: ...
