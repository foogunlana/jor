"""Launcher: write Claude Code session file and run claude --resume."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from jor.session.schema import JorMessage
from jor.session.writers.claude_code import ClaudeCodeWriter


class ClaudeCodeLauncher:
    def __init__(self, claude_home: Path | None = None) -> None:
        self._home = claude_home or Path.home() / ".claude"

    def launch(self, messages: list[JorMessage], session_id: str | None = None) -> None:
        writer = ClaudeCodeWriter()
        target_dir = self._home / "projects" / "jor-imported" / "sessions"
        target_dir.mkdir(parents=True, exist_ok=True)
        sid = session_id or str(uuid.uuid4())
        _, out = writer.write(messages, target_dir / f"{sid}.jsonl")
        cmd = writer.resume_command(out)
        subprocess.run(cmd, shell=True)
