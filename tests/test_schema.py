"""Failing tests for Jor session schema models — RED phase."""

import json

import pytest


def test_tool_call_model_has_required_fields() -> None:
    from jor.core.schema import ToolCall

    tc = ToolCall(id="tc1", name="read_file", input={"path": "/foo"})
    assert tc.id == "tc1"
    assert tc.name == "read_file"
    assert tc.input == {"path": "/foo"}


def test_tool_result_model_has_required_fields() -> None:
    from jor.core.schema import ToolResult

    tr = ToolResult(tool_call_id="tc1", content="file contents")
    assert tr.tool_call_id == "tc1"
    assert tr.content == "file contents"
    assert tr.is_error is False


def test_tool_result_is_error_optional() -> None:
    from jor.core.schema import ToolResult

    tr = ToolResult(tool_call_id="tc1", content="oops", is_error=True)
    assert tr.is_error is True


def test_jor_message_basic_fields() -> None:
    from jor.core.schema import JorMessage

    msg = JorMessage(id="m1", role="user", content="hello")
    assert msg.id == "m1"
    assert msg.role == "user"
    assert msg.content == "hello"


def test_jor_message_all_roles_valid() -> None:
    from jor.core.schema import JorMessage

    for role in ("user", "assistant", "system", "tool_result"):
        msg = JorMessage(id="m1", role=role, content="x")
        assert msg.role == role


def test_jor_message_invalid_role_rejected() -> None:
    from jor.core.schema import JorMessage
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        JorMessage(id="m1", role="invalid_role", content="x")


def test_jor_message_optional_fields_default_none() -> None:
    from jor.core.schema import JorMessage

    msg = JorMessage(id="m1", role="user", content="hi")
    assert msg.tool_calls is None
    assert msg.tool_result is None
    assert msg.files is None
    assert msg.model is None
    assert msg.provider is None
    assert msg.timestamp is None
    assert msg.metadata is None
    assert msg.source_tool is None
    assert msg.source_id is None


def test_jor_message_serialize_to_json_line() -> None:
    from jor.core.schema import JorMessage

    msg = JorMessage(id="m1", role="assistant", content="hi")
    line = msg.model_dump_json()
    assert "\n" not in line
    data = json.loads(line)
    assert data["id"] == "m1"
    assert data["role"] == "assistant"


def test_jor_message_round_trip() -> None:
    from jor.core.schema import JorMessage, ToolCall

    tc = ToolCall(id="tc1", name="bash", input={"cmd": "ls"})
    msg = JorMessage(
        id="m2",
        role="assistant",
        content="running ls",
        tool_calls=[tc],
        model="claude-sonnet-4-6",
        provider="anthropic",
        source_tool="claude_code",
        source_id="orig-abc",
        metadata={"extra": "data"},
    )
    line = msg.model_dump_json()
    restored = JorMessage.model_validate_json(line)
    assert restored == msg
