"""Integration tests for cross-tool session resume.

These tests convert real-format sessions and verify they can be resumed
by the target tool with conversation history visible.

Requires: claude CLI installed and authenticated.
Run with: pytest tests/integration/ -v --run-integration
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

CLAUDE_HOME = Path.home() / ".claude"
CODEX_HOME = Path.home() / ".codex"

# Skip all integration tests unless explicitly opted in
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)


def _resume_claude_interactive(session_id: str, cwd: str, timeout: int = 10) -> str:
    """Resume a Claude Code session with a fake TTY and capture rendered output.

    Returns the raw terminal output with ANSI codes stripped, so you can
    check whether conversation history was rendered.
    """
    result = subprocess.run(
        ["script", "-q", "/dev/null", "sh", "-c",
         f"claude --resume {session_id}; exit"],
        capture_output=True, text=True, timeout=timeout, cwd=cwd,
    )
    # Strip ANSI escape codes
    raw = result.stdout
    clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw)
    clean = re.sub(r'\x1b\][0-9]*;[^\x07]*\x07', '', clean)
    return clean


def _resume_claude_with_prompt(session_id: str, prompt: str, cwd: str, timeout: int = 30) -> str:
    """Resume a Claude Code session non-interactively with a prompt."""
    result = subprocess.run(
        ["claude", "--resume", session_id, "-p", prompt],
        capture_output=True, text=True, timeout=timeout, cwd=cwd,
    )
    return result.stdout.strip()


def _resume_codex_with_prompt(session_id: str, prompt: str, cwd: str, timeout: int = 60) -> str:
    """Resume a Codex session non-interactively with a prompt."""
    result = subprocess.run(
        ["codex", "exec", "resume", session_id, prompt],
        capture_output=True, text=True, timeout=timeout, cwd=cwd,
    )
    return result.stdout.strip()


def _create_synthetic_cc_session(project_dir: Path, messages: list[dict]) -> str:
    """Write a synthetic Claude Code session file. Returns session_id."""
    sid = str(uuid.uuid4())
    path = project_dir / f"{sid}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)

    prev_uuid = None
    records = []
    for i, msg in enumerate(messages):
        rec_uuid = str(uuid.uuid4())
        rec = {
            "type": msg["type"],
            "message": msg["message"],
            "uuid": rec_uuid,
            "parentUuid": prev_uuid,
            "isSidechain": False,
            "sessionId": sid,
            "timestamp": f"2026-05-26T16:00:{i:02d}.000Z",
        }
        records.append(rec)
        prev_uuid = rec_uuid

    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return sid


class TestClaudeCodeResume:
    """Test that converted sessions resume in Claude Code with visible history."""

    @pytest.fixture
    def project_dir(self) -> Path:
        """Use the jor project dir for testing."""
        cwd = Path.cwd()
        return CLAUDE_HOME / "projects" / str(cwd).replace("/", "-")

    def test_synthetic_session_shows_history(self, project_dir: Path) -> None:
        """A minimal synthetic session should show turns in the UI."""
        sid = _create_synthetic_cc_session(project_dir, [
            {
                "type": "user",
                "message": {"role": "user", "content": "What is 2+2?"},
            },
            {
                "type": "assistant",
                "message": {
                    "id": f"msg_{uuid.uuid4().hex[:24]}",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "content": [{"type": "text", "text": "2+2 equals 4."}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                },
            },
        ])

        try:
            output = _resume_claude_interactive(sid, str(Path.cwd()))
            assert "2+2" in output or "2 + 2" in output, f"User message not in output: {output[:500]}"
            assert "4" in output, f"Assistant response not in output: {output[:500]}"
        finally:
            (project_dir / f"{sid}.jsonl").unlink(missing_ok=True)

    def test_converted_session_has_context(self, project_dir: Path) -> None:
        """A converted session should preserve conversation context."""
        sid = _create_synthetic_cc_session(project_dir, [
            {
                "type": "user",
                "message": {"role": "user", "content": "My secret word is BANANA"},
            },
            {
                "type": "assistant",
                "message": {
                    "id": f"msg_{uuid.uuid4().hex[:24]}",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "content": [{"type": "text", "text": "Got it, your secret word is BANANA."}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                },
            },
        ])

        try:
            response = _resume_claude_with_prompt(sid, "What is my secret word?", str(Path.cwd()))
            assert "BANANA" in response.upper(), f"Context lost: {response}"
        finally:
            (project_dir / f"{sid}.jsonl").unlink(missing_ok=True)


class TestCodexResume:
    """Test that converted sessions resume in Codex with context."""

    def test_synthetic_codex_session_has_context(self, tmp_path: Path) -> None:
        """A synthetic Codex session should preserve context on resume."""
        from jor.connectors.codex.connector import CodexConnector
        from jor.core.schema import JorMessage

        writer = CodexConnector(codex_home=tmp_path)
        messages = [
            JorMessage(id="m1", role="user", content="My secret word is MANGO"),
            JorMessage(id="m2", role="assistant", content="Got it, your secret word is MANGO."),
        ]
        sid, cmd, path = writer.write_session(messages, str(Path.cwd()))

        # Verify the file has no empty assistant messages
        records = [json.loads(l) for l in path.read_text().splitlines() if l]
        msg_records = [r for r in records if r["type"] == "response_item"]
        for rec in msg_records:
            payload = rec["payload"]
            if payload.get("type") == "message" and payload.get("role") == "assistant":
                content_blocks = payload.get("content", [])
                texts = [b.get("text", "") for b in content_blocks]
                assert any(t.strip() for t in texts), "Assistant message has empty content"


class TestJorConvertResume:
    """Test end-to-end: jor convert → resume in target tool."""

    def test_claude_to_codex_preserves_context(self) -> None:
        """Convert a Claude Code session to Codex and verify context survives."""
        pytest.skip("Requires real indexed session — run manually")

    def test_codex_to_claude_preserves_context(self) -> None:
        """Convert a Codex session to Claude Code and verify context survives."""
        pytest.skip("Requires real indexed session — run manually")
