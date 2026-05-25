"""Launcher: resume or create a Claude Code session."""

from __future__ import annotations

import subprocess
import uuid
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
            project_dir = _project_dir_name(project) if project else "jor-imported"
            target_dir = self._home / "projects" / project_dir / "sessions"
            target_dir.mkdir(parents=True, exist_ok=True)
            sid = str(uuid.uuid4())
            writer = ClaudeCodeWriter()
            _, out = writer.write(messages, target_dir / f"{sid}.jsonl")
            cmd = writer.resume_command(out)

        cwd = project if project and Path(project).is_dir() else None
        subprocess.run(cmd, shell=True, cwd=cwd)


def _project_dir_name(project_path: str) -> str:
    """Convert a project path to Claude Code's project directory name.

    /Users/foo/code/bar -> -Users-foo-code-bar
    """
    return project_path.replace("/", "-")
