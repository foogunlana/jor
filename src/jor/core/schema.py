"""Canonical message format for jor sessions.

All connectors convert tool-native messages into JorMessage objects.
All writers convert JorMessage objects back into tool-native formats.
This is the intermediate representation that makes cross-tool conversion possible.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ToolCall(BaseModel):
    """A tool invocation made by the assistant (e.g. Read, Bash, exec_command)."""

    id: str
    name: str
    input: dict[str, Any]


class ToolResult(BaseModel):
    """The output returned by a tool after execution."""

    tool_call_id: str
    content: str
    is_error: bool = False


class JorMessage(BaseModel):
    """One message in a jor session.

    Every message from every tool (Claude, Codex, etc.) is normalized
    into this format. The source_tool and source_id fields track where the
    message originally came from.
    """

    id: str
    role: Literal["user", "assistant", "system", "tool_result"]
    content: str
    tool_calls: Optional[list[ToolCall]] = None
    tool_result: Optional[ToolResult] = None
    files: Optional[list[str]] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    source_tool: Optional[str] = None
    source_id: Optional[str] = None
