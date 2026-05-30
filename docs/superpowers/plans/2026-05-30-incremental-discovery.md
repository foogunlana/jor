# Incremental Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `jor list` automatically discover new/changed sessions via mtime-based incremental scan, with a delightful braille-dot spinner.

**Architecture:** Add a `since` parameter to `BaseConnector.scan()` for mtime filtering. Add `Scanner.run_incremental()` that reads `last_scan` from the index and passes it as `since`. Wire it into `jor list` with a threaded spinner for visual feedback.

**Tech Stack:** Python stdlib (`threading`, `sys`, `time`, `datetime`), click, existing connector infrastructure.

---

### Task 1: Add `since` parameter to `BaseConnector.scan()`

**Files:**
- Modify: `src/jor/connectors/base.py:55-61`
- Test: `tests/connectors/claude/test_connector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/connectors/claude/test_connector.py`:

```python
import os
import time


def test_scan_since_skips_old_files(claude_home: Path, jor_home: Path):
    """Files older than `since` are skipped."""
    c = ClaudeConnector(claude_home=claude_home)
    # Set all session files to an old mtime
    for f in claude_home.rglob("*.jsonl"):
        os.utime(f, (0, 1000))
    entries = c.scan(jor_home, since=2000.0)
    assert entries == []


def test_scan_since_includes_new_files(claude_home: Path, jor_home: Path):
    """Files newer than `since` are processed."""
    c = ClaudeConnector(claude_home=claude_home)
    entries = c.scan(jor_home, since=0.0)
    assert len(entries) == 1


def test_scan_since_none_processes_all(claude_home: Path, jor_home: Path):
    """since=None processes all files (backwards compatible)."""
    c = ClaudeConnector(claude_home=claude_home)
    entries = c.scan(jor_home, since=None)
    assert len(entries) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/connectors/claude/test_connector.py::test_scan_since_skips_old_files tests/connectors/claude/test_connector.py::test_scan_since_includes_new_files tests/connectors/claude/test_connector.py::test_scan_since_none_processes_all -v`
Expected: FAIL — `scan()` doesn't accept `since` parameter

- [ ] **Step 3: Add `since` parameter to `BaseConnector.scan()`**

In `src/jor/connectors/base.py`, modify the `scan` method:

```python
def scan(self, jor_home: Path, since: float | None = None) -> list[IndexEntry]:
    entries: list[IndexEntry] = []
    for session_path in self._home.glob(self.GLOB_PATTERN):
        if since is not None and session_path.stat().st_mtime <= since:
            continue
        entry = self._process(session_path, jor_home)
        if entry is not None:
            entries.append(entry)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/connectors/claude/test_connector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest -q`
Expected: All pass (existing tests still call `scan(jor_home)` without `since`, which defaults to `None`)

- [ ] **Step 6: Commit**

```bash
git add src/jor/connectors/base.py tests/connectors/claude/test_connector.py
git commit -m "feat: add since parameter to BaseConnector.scan() for mtime filtering"
```

---

### Task 2: Add `Scanner.run_incremental()`

**Files:**
- Modify: `src/jor/core/scanner.py`
- Test: `tests/core/test_scanner.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_scanner.py`:

```python
from datetime import datetime, timezone


def test_run_incremental_passes_since_to_connectors(jor_home: Path) -> None:
    """run_incremental should pass the last_scan timestamp to connectors."""
    # Pre-seed an index with a last_scan timestamp
    from jor.core.index import SessionIndex, save_index
    idx = SessionIndex(last_scan="2026-05-01T00:00:00+00:00")
    save_index(idx, jor_home / "index.json")

    c = MagicMock()
    c.detect.return_value = True
    c.scan.return_value = []
    c.name.return_value = "claude"

    scanner = Scanner(connectors=[c], jor_home=jor_home)
    scanner.run_incremental()

    # scan should be called with since= as a float timestamp
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

    from jor.core.index import load_index
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_scanner.py::test_run_incremental_passes_since_to_connectors tests/core/test_scanner.py::test_run_incremental_no_last_scan_does_full tests/core/test_scanner.py::test_run_incremental_updates_last_scan tests/core/test_scanner.py::test_run_incremental_returns_counts -v`
Expected: FAIL — `Scanner` has no `run_incremental` method

- [ ] **Step 3: Implement `run_incremental()`**

In `src/jor/core/scanner.py`, add the method:

```python
def run_incremental(self) -> dict[str, int]:
    """Run discovery only on files changed since last scan."""
    index_path = self._jor_home / "index.json"
    index = load_index(index_path)

    since: float | None = None
    if index.last_scan:
        since = datetime.fromisoformat(index.last_scan).timestamp()

    counts: dict[str, int] = {}
    for connector in self._connectors:
        if not connector.detect():
            continue
        entries = connector.scan(jor_home=self._jor_home, since=since)
        for entry in entries:
            upsert_session(index, entry)
        counts[connector.name()] = len(entries)

    index.last_scan = datetime.now(timezone.utc).isoformat()
    save_index(index, index_path)
    return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scanner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/jor/core/scanner.py tests/core/test_scanner.py
git commit -m "feat: add Scanner.run_incremental() for mtime-based discovery"
```

---

### Task 3: Add spinner utility

**Files:**
- Create: `src/jor/spinner.py`
- Test: `tests/test_spinner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_spinner.py`:

```python
"""Tests for the braille-dot spinner."""

import io
import time

from jor.spinner import Spinner


def test_spinner_context_manager():
    """Spinner starts and stops cleanly as a context manager."""
    output = io.StringIO()
    with Spinner("Working...", stream=output):
        time.sleep(0.15)  # let at least one frame render

    text = output.getvalue()
    assert "Working..." in text


def test_spinner_clears_on_exit():
    """Spinner clears its line on exit."""
    output = io.StringIO()
    with Spinner("Working...", stream=output):
        time.sleep(0.05)

    # Last write should contain \r to clear the line
    text = output.getvalue()
    assert "\r" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spinner.py -v`
Expected: FAIL — `jor.spinner` module doesn't exist

- [ ] **Step 3: Implement the spinner**

Create `src/jor/spinner.py`:

```python
"""Threaded braille-dot spinner for visual feedback."""

from __future__ import annotations

import sys
import threading
import time
from typing import IO

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    """A context-manager spinner that runs in a daemon thread."""

    def __init__(self, message: str, stream: IO[str] | None = None, interval: float = 0.08) -> None:
        self._message = message
        self._stream = stream or sys.stderr
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Spinner:
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line
        self._stream.write("\r" + " " * (len(self._message) + 4) + "\r")
        self._stream.flush()

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = BRAILLE[i % len(BRAILLE)]
            self._stream.write(f"\r{frame} {self._message}")
            self._stream.flush()
            i += 1
            self._stop.wait(self._interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spinner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/jor/spinner.py tests/test_spinner.py
git commit -m "feat: add braille-dot spinner utility"
```

---

### Task 4: Wire incremental discovery + spinner into `jor list`

**Files:**
- Modify: `src/jor/cli.py:57-67`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_list_runs_incremental_discovery(tmp_path: Path) -> None:
    """jor list should run incremental discovery before listing."""
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"):
        MockScanner.return_value.run_incremental.return_value = {}
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    MockScanner.return_value.run_incremental.assert_called_once()


def test_list_shows_new_session_count(tmp_path: Path) -> None:
    """jor list should print count when new sessions are found."""
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"):
        MockScanner.return_value.run_incremental.return_value = {"claude": 3}
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "Found 3 new sessions" in result.output


def test_list_no_new_sessions_no_extra_output(tmp_path: Path) -> None:
    """jor list should print nothing extra when no new sessions found."""
    runner = CliRunner()
    index = SessionIndex(sessions=[_entry()])
    with patch("jor.cli.load_index", return_value=index), \
         patch("jor.cli.Scanner") as MockScanner, \
         patch("jor.cli.ClaudeConnector"), \
         patch("jor.cli.CodexConnector"):
        MockScanner.return_value.run_incremental.return_value = {"claude": 0, "codex": 0}
        result = runner.invoke(main, ["list"])

    assert result.exit_code == 0
    assert "new sessions" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_list_runs_incremental_discovery tests/test_cli.py::test_list_shows_new_session_count tests/test_cli.py::test_list_no_new_sessions_no_extra_output -v`
Expected: FAIL — `jor list` doesn't call `Scanner.run_incremental()`

- [ ] **Step 3: Wire incremental discovery into `list_sessions`**

In `src/jor/cli.py`, modify `list_sessions`:

```python
from jor.spinner import Spinner

@main.command(name="list")
@click.option("--codex", is_flag=True, help="Show only Codex sessions")
@click.option("--claude", "claude", is_flag=True, help="Show only Claude sessions")
@click.option("--query", "-q", default=None, help="Search titles")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results")
@click.option("--path", default=None, help="Filter by workspace path")
def list_sessions(codex: bool, claude: bool, query: str | None, limit: int, path: str | None) -> None:
    """List indexed sessions."""
    jor_home = _jor_home()

    # Incremental discovery
    connectors = [ClaudeConnector(), CodexConnector()]
    scanner = Scanner(connectors=connectors, jor_home=jor_home)
    with Spinner("Discovering new sessions..."):
        counts = scanner.run_incremental()
    total_new = sum(counts.values())
    if total_new > 0:
        click.echo(f"Found {total_new} new sessions")

    index = load_index(jor_home / "index.json")
    sessions = index.sessions

    # ... rest unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -q`
Expected: All pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add src/jor/cli.py tests/test_cli.py
git commit -m "feat: wire incremental discovery + spinner into jor list"
```

---

### Task 5: Manual smoke test

- [ ] **Step 1: Run a full discover to establish baseline**

```bash
uv run jor discover
```

- [ ] **Step 2: Run `jor list` — should be fast with spinner, no new sessions**

```bash
uv run jor list
```

Expected: Spinner appears briefly, no "Found N new sessions" line, list displays instantly.

- [ ] **Step 3: Start a new AI session to create a new session file, then run `jor list` again**

Expected: Spinner appears, "Found 1 new sessions" line, new session appears in list.

- [ ] **Step 4: Commit and push**

```bash
git push
```
