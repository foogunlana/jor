"""Launch a session in Codex.

For same-tool resume: runs `codex resume <session-id>` from the project dir.
For cross-tool: writes a new session file to ~/.codex/sessions/ then resumes.
Note: cross-tool resume doesn't work yet because Codex tracks sessions in its
own SQLite database, not by scanning files. See bead jor-4yo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from jor.core.schema import JorMessage
from jor.connectors.codex.writer import CodexWriter


class CodexLauncher:
    """Write a session file and launch `codex resume`."""

    def __init__(self, codex_home: Path | None = None) -> None:
        self._home = codex_home or Path.home() / ".codex"

    def launch(self, messages: list[JorMessage], session_id: str | None = None, project: str | None = None) -> None:
        if session_id:
            cmd = f"codex resume {session_id}"
        else:
            writer = CodexWriter()
            target_dir = self._home / "sessions"
            _, out = writer.write(messages, target_dir)
            cmd = writer.resume_command(out)

        cwd = project if project and Path(project).is_dir() else None
        subprocess.run(cmd, shell=True, cwd=cwd)
