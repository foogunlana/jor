"""Convert jor sessions to Claude Code's native JSONL format.

Output format: one JSON record per line with {sessionId, timestamp, type, message}.
The session file is written to a specific path (not a directory) because Claude Code
identifies sessions by filename (the UUID stem).
"""

from __future__ import annotations

import json
from pathlib import Path

from jor.core.schema import JorMessage


class ClaudeCodeWriter:
    """Write jor messages as Claude Code JSONL."""

    def write(self, messages: list[JorMessage], target_path: Path) -> tuple[str, Path]:
        """Write messages to target_path (full file path). Returns (session_id, path)."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        session_id = target_path.stem
        records = [self._to_record(msg, session_id) for msg in messages]
        target_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return session_id, target_path

    def resume_command(self, session_file: Path) -> str:
        session_id = session_file.stem
        return f"claude --resume {session_id}"

    def _to_record(self, msg: JorMessage, session_id: str) -> dict:
        base = {
            "sessionId": session_id,
            "timestamp": msg.timestamp or "",
        }
        if msg.role == "user":
            return {**base, "type": "user", "message": {"role": "user", "content": msg.content}}

        elif msg.role == "assistant":
            content_blocks = []
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.input,
                    })
            return {**base, "type": "assistant", "message": {"role": "assistant", "content": content_blocks}}

        elif msg.role == "tool_result":
            tool_call_id = msg.tool_result.tool_call_id if msg.tool_result else ""
            return {
                **base,
                "type": "tool_result",
                "message": {
                    "role": "tool_result",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": msg.content,
                    }],
                },
            }

        else:
            return {**base, "type": msg.role, "message": {"role": msg.role, "content": msg.content}}
