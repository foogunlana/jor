"""Protocol definitions for writers."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from jor.core.schema import JorMessage


@runtime_checkable
class Writer(Protocol):
    def write(self, messages: list[JorMessage], target: Path) -> tuple[str, Path]: ...
    def resume_command(self, session_file: Path) -> str: ...
