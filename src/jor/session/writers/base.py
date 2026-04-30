"""Writer protocol — all target writers implement this interface."""

from pathlib import Path
from typing import Protocol

from jor.session.schema import JorMessage


class Writer(Protocol):
    def write(self, messages: list[JorMessage], target_dir: Path, session_id: str) -> Path: ...
    def resume_command(self, session_file: Path) -> str: ...
