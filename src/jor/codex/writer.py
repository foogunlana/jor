"""Writer: Jor → Codex native JSONL format (OpenAI chat completion)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from jor.core.schema import JorMessage


class CodexWriter:
    def write(self, messages: list[JorMessage], target_dir: Path) -> tuple[str, Path]:
        """Write messages to target_dir. Returns (session_id, path)."""
        target_dir.mkdir(parents=True, exist_ok=True)
        session_id = str(uuid.uuid4())
        out = target_dir / f"rollout-{session_id}.jsonl"
        records = [self._to_record(msg) for msg in messages]
        out.write_text("\n".join(json.dumps(r) for r in records) + "\n")
        return session_id, out

    def resume_command(self, session_file: Path) -> str:
        stem = session_file.stem
        session_id = stem[len("rollout-"):] if stem.startswith("rollout-") else stem
        return f"codex resume {session_id}"

    def _to_record(self, msg: JorMessage) -> dict:
        if msg.role == "tool_result":
            return {
                "role": "tool",
                "tool_call_id": msg.tool_result.tool_call_id if msg.tool_result else "",
                "content": msg.content,
            }

        record: dict = {"role": msg.role, "content": msg.content}

        if msg.role == "assistant" and msg.tool_calls:
            record["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input),
                    },
                }
                for tc in msg.tool_calls
            ]

        return record
