"""Writer protocol — all target writers implement this interface."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from jor.session.schema import JorMessage


@runtime_checkable
class Writer(Protocol):
    def write(self, messages: list[JorMessage], target: Path) -> tuple[str, Path]: ...
    def resume_command(self, session_file: Path) -> str: ...
