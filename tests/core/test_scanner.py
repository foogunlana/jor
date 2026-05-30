"""Tests for the session scanner."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jor.core.index import IndexEntry, load_index
from jor.core.scanner import Scanner


def _make_entry(tool: str, n: int) -> IndexEntry:
    return IndexEntry(
        id=f"id-{n}",
        tool=tool,
        source_id=f"src-{n}",
        source_path=f"/fake/{n}.jsonl",
        title=f"Session {n}",
        project="/fake/project",
        started_at="2026-04-20T10:00:00Z",
        message_count=5,
    )


@pytest.fixture()
def jor_home(tmp_path: Path) -> Path:
    h = tmp_path / ".jor"
    h.mkdir()
    (h / "sessions").mkdir()
    return h


def test_scanner_runs_detected_connectors(jor_home: Path) -> None:
    c1 = MagicMock()
    c1.detect.return_value = True
    c1.scan.return_value = [_make_entry("tool1", 1)]
    c1.name.return_value = "tool1"

    c2 = MagicMock()
    c2.detect.return_value = False
    c2.name.return_value = "tool2"

    scanner = Scanner(connectors=[c1, c2], jor_home=jor_home)
    counts = scanner.run()

    c1.scan.assert_called_once()
    c2.scan.assert_not_called()
    assert counts["tool1"] == 1


def test_scanner_updates_index(jor_home: Path) -> None:
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = [_make_entry("claude", 1), _make_entry("claude", 2)]
    c.name.return_value = "claude"

    Scanner(connectors=[c], jor_home=jor_home).run()

    index = load_index(jor_home / "index.json")
    assert len(index.sessions) == 2


def test_scanner_upserts_on_rescan(jor_home: Path) -> None:
    entry = _make_entry("claude", 1)
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = [entry]
    c.name.return_value = "claude"

    Scanner(connectors=[c], jor_home=jor_home).run()
    Scanner(connectors=[c], jor_home=jor_home).run()

    index = load_index(jor_home / "index.json")
    assert len(index.sessions) == 1  # upserted, not duplicated


def test_scanner_sets_last_scan(jor_home: Path) -> None:
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = []
    c.name.return_value = "any"

    Scanner(connectors=[c], jor_home=jor_home).run()

    index = load_index(jor_home / "index.json")
    assert index.last_scan is not None


def test_scanner_no_connectors(jor_home: Path) -> None:
    counts = Scanner(connectors=[], jor_home=jor_home).run()
    assert counts == {}


# ---------------------------------------------------------------------------
# run_incremental
# ---------------------------------------------------------------------------


def test_run_incremental_passes_since_to_connectors(jor_home: Path) -> None:
    """run_incremental should pass the last_scan timestamp to connectors."""
    from jor.core.index import SessionIndex, save_index
    idx = SessionIndex(last_scan="2026-05-01T00:00:00+00:00")
    save_index(idx, jor_home / "index.json")

    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = []
    c.name.return_value = "claude"

    scanner = Scanner(connectors=[c], jor_home=jor_home)
    scanner.run_incremental()

    c.scan.assert_called_once()
    _, kwargs = c.scan.call_args
    assert "since" in kwargs
    assert isinstance(kwargs["since"], float)


def test_run_incremental_no_last_scan_does_full(jor_home: Path) -> None:
    """First run (no last_scan) should pass since=None for full scan."""
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = []
    c.name.return_value = "claude"

    scanner = Scanner(connectors=[c], jor_home=jor_home)
    scanner.run_incremental()

    c.scan.assert_called_once()
    _, kwargs = c.scan.call_args
    assert kwargs["since"] is None


def test_run_incremental_updates_last_scan(jor_home: Path) -> None:
    """run_incremental should update last_scan in the index."""
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = []
    c.name.return_value = "claude"

    scanner = Scanner(connectors=[c], jor_home=jor_home)
    scanner.run_incremental()

    index = load_index(jor_home / "index.json")
    assert index.last_scan is not None


def test_run_incremental_returns_counts(jor_home: Path) -> None:
    """run_incremental should return counts like run()."""
    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = [_make_entry("claude", 1)]
    c.name.return_value = "claude"

    scanner = Scanner(connectors=[c], jor_home=jor_home)
    counts = scanner.run_incremental()

    assert counts["claude"] == 1
