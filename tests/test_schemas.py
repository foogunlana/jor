"""Validate test fixtures against their connector's schema.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import jsonschema


FIXTURES_DIR = Path(__file__).parent / "fixtures"
CONNECTORS_DIR = Path(__file__).parent.parent / "src" / "jor" / "connectors"


def _load_schema(connector_name: str) -> dict:
    schema_path = CONNECTORS_DIR / connector_name / "schema.json"
    return json.loads(schema_path.read_text())


def _load_fixture_lines(filename: str) -> list[dict]:
    fixture = FIXTURES_DIR / filename
    return [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Claude fixture vs schema
# ---------------------------------------------------------------------------


class TestClaudeSchema:
    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("claude")

    @pytest.fixture()
    def records(self) -> list[dict]:
        return _load_fixture_lines("claude_session.jsonl")

    def test_all_lines_valid(self, schema: dict, records: list[dict]) -> None:
        for i, record in enumerate(records):
            jsonschema.validate(record, schema)

    def test_schema_requires_type(self, schema: dict) -> None:
        assert "type" in schema.get("required", [])

    def test_schema_requires_session_id(self, schema: dict) -> None:
        assert "sessionId" in schema.get("required", [])

    def test_schema_requires_timestamp(self, schema: dict) -> None:
        assert "timestamp" in schema.get("required", [])

    def test_schema_requires_message(self, schema: dict) -> None:
        assert "message" in schema.get("required", [])


# ---------------------------------------------------------------------------
# Codex fixture vs schema
# ---------------------------------------------------------------------------


class TestCodexSchema:
    @pytest.fixture()
    def schema(self) -> dict:
        return _load_schema("codex")

    @pytest.fixture()
    def records(self) -> list[dict]:
        return _load_fixture_lines("codex_session.jsonl")

    def test_all_lines_valid(self, schema: dict, records: list[dict]) -> None:
        for i, record in enumerate(records):
            jsonschema.validate(record, schema)

    def test_schema_requires_type(self, schema: dict) -> None:
        assert "type" in schema.get("required", [])

    def test_schema_requires_timestamp(self, schema: dict) -> None:
        assert "timestamp" in schema.get("required", [])

    def test_schema_type_enum_includes_expected_values(self, schema: dict) -> None:
        type_enum = schema["properties"]["type"]["enum"]
        assert "session_meta" in type_enum
        assert "response_item" in type_enum
