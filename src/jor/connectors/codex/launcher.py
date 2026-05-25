"""Launch a session in Codex.

For same-tool resume: runs `codex resume <session-id>` from the project dir.
For cross-tool: writes a new session file to ~/.codex/sessions/ then resumes.
Note: cross-tool resume doesn't work yet because Codex tracks sessions in its
own SQLite database, not by scanning files. See bead jor-2qn.
"""

from __future__ import annotations

from pathlib import Path

from jor.connectors.base import BaseLauncher
from jor.connectors.codex.writer import CodexWriter
from jor.core.schema import JorMessage


class CodexLauncher(BaseLauncher):
    """Write a session file and launch `codex resume`."""

    RESUME_CMD = "codex resume {session_id}"

    def __init__(self, codex_home: Path | None = None) -> None:
        super().__init__(home_path=codex_home or Path.home() / ".codex")

    def _write_session(self, messages: list[JorMessage], project: str | None) -> tuple[str, str, Path]:
        writer = CodexWriter()
        target_dir = self._home / "sessions"
        sid, out = writer.write(messages, target_dir)
        return sid, writer.resume_command(out), out
