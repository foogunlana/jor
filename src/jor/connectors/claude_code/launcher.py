"""Launch a session in Claude Code.

For same-tool resume: runs `claude --resume <session-id>` from the project dir.
For cross-tool: writes a new session file to the correct Claude Code project
directory (~/.claude/projects/<project-name>/<uuid>.jsonl) then resumes it.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from jor.connectors.base import BaseLauncher
from jor.connectors.claude_code.writer import ClaudeCodeWriter
from jor.core.schema import JorMessage


class ClaudeCodeLauncher(BaseLauncher):
    """Write a session file and launch `claude --resume`."""

    RESUME_CMD = "claude --resume {session_id}"

    def __init__(self, claude_home: Path | None = None) -> None:
        super().__init__(home_path=claude_home or Path.home() / ".claude")

    def _write_session(self, messages: list[JorMessage], project: str | None) -> tuple[str, str, Path]:
        project_dir = _project_dir_name(project) if project else "jor-imported"
        target_dir = self._home / "projects" / project_dir
        sid = str(uuid.uuid4())
        writer = ClaudeCodeWriter()
        _, out = writer.write(messages, target_dir / f"{sid}.jsonl")
        return sid, writer.resume_command(out), out


def _project_dir_name(project_path: str) -> str:
    """Convert a project path to Claude Code's project directory name.

    /Users/foo/code/bar -> -Users-foo-code-bar
    """
    return project_path.replace("/", "-")
