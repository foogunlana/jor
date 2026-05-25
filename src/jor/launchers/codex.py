"""Launcher: resume or create a Codex session."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jor.session.schema import JorMessage
from jor.session.writers.codex import CodexWriter


class CodexLauncher:
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
