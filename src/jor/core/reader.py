"""Session reader — load Jor sessions and format for output."""

from __future__ import annotations

from pathlib import Path

from jor.core.index import IndexEntry
from jor.core.schema import JorMessage


def read_session(path: Path) -> list[JorMessage]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [
        JorMessage.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def format_summary(messages: list[JorMessage], entry: IndexEntry) -> str:
    date = entry.started_at[:10] if entry.started_at else ""
    lines = [
        f"# Session: {entry.title}",
        f"Tool: {entry.tool}",
        f"Model: {entry.model}",
        f"Project: {entry.project}",
        f"Date: {date}",
        "",
    ]

    total = len(messages)
    if total > 50:
        omitted = total - 50
        lines.append(f"*[{omitted} messages omitted — showing last 50]*\n")
        shown = messages[-50:]
    else:
        shown = messages

    for msg in shown:
        if msg.role == "user":
            lines.append(f"User: {msg.content}")
        elif msg.role == "assistant":
            if msg.content:
                lines.append(f"Assistant: {msg.content}")
            for tc in msg.tool_calls or []:
                lines.append(f"  [Tool: {tc.name}]")

    all_files: list[str] = []
    for msg in messages:
        if msg.files:
            all_files.extend(msg.files)

    if all_files:
        lines.append("")
        lines.append("## Files")
        for f in all_files:
            lines.append(f"- {f}")

    return "\n".join(lines)


def format_full(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text()
