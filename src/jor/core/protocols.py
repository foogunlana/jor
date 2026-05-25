"""Shared protocols for writers.

Writers convert JorMessage lists back into a tool's native session format.
Each tool module (claude_code/, codex/) provides its own Writer implementation.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from jor.core.schema import JorMessage


@runtime_checkable
class Writer(Protocol):
    """Interface for converting jor sessions to a tool's native format."""

    def write(self, messages: list[JorMessage], target: Path) -> tuple[str, Path]: ...
    def resume_command(self, session_file: Path) -> str: ...
