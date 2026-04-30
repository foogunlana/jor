"""Jor session schema — canonical message format."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False


class JorMessage(BaseModel):
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
