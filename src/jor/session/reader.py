"""Session reader — load Jor sessions and format for output."""

from __future__ import annotations

from pathlib import Path

from jor.session.schema import JorMessage


def read_session(path: Path) -> list[JorMessage]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        JorMessage.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def format_summary(messages: list[JorMessage], title: str, source_tool: str) -> str:
    lines = [
        f"# Continuing session: {title}",
        f"# Originally in: {source_tool}",
        f"# Messages: {len(messages)}",
        "",
    ]
    shown = messages[-50:] if len(messages) > 50 else messages
    if len(messages) > 50:
        lines.append(f"*[Showing last 50 of {len(messages)} messages]*\n")

    for msg in shown:
        if msg.role == "user":
            lines.append(f"**User:** {msg.content}")
        elif msg.role == "assistant":
            if msg.content:
                lines.append(f"**Assistant:** {msg.content}")
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    lines.append(f"  *[Tool call: {tc.name}]*")
        elif msg.role == "tool_result":
            lines.append(f"  *[Tool result]*")
        elif msg.role == "system":
            lines.append(f"*[System: {msg.content}]*")

    return "\n".join(lines)
