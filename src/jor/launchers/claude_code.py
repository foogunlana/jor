"""Launcher: write Claude Code session file and run claude --resume."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jor.session.schema import JorMessage
from jor.session.writers.claude_code import ClaudeCodeWriter


class ClaudeCodeLauncher:
    def __init__(self, claude_home: Path | None = None) -> None:
        self._home = claude_home or Path.home() / ".claude"

    def launch(self, messages: list[JorMessage], session_id: str) -> None:
        writer = ClaudeCodeWriter()
        target_dir = self._home / "projects" / "jor-imported" / "sessions"
        out = writer.write(messages, target_dir, session_id)
        cmd = writer.resume_command(out)
        subprocess.run(cmd, shell=True)
