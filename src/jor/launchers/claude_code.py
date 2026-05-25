"""Launcher: resume or create a Claude Code session."""

from __future__ import annotations

import subprocess
from pathlib import Path

from jor.session.schema import JorMessage
from jor.session.writers.claude_code import ClaudeCodeWriter


class ClaudeCodeLauncher:
    def __init__(self, claude_home: Path | None = None) -> None:
        self._home = claude_home or Path.home() / ".claude"

    def launch(self, messages: list[JorMessage], session_id: str | None = None, project: str | None = None) -> None:
        if session_id:
            cmd = f"claude --resume {session_id}"
        else:
            writer = ClaudeCodeWriter()
            target_dir = self._home / "projects" / "jor-imported" / "sessions"
            target_dir.mkdir(parents=True, exist_ok=True)
            _, out = writer.write(messages, target_dir / "imported.jsonl")
            cmd = writer.resume_command(out)

        cwd = project if project and Path(project).is_dir() else None
        subprocess.run(cmd, shell=True, cwd=cwd)
