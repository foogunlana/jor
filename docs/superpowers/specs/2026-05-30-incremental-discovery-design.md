# Incremental Discovery Design

**Date:** 2026-05-30
**Status:** Approved

## Problem

`jor list` requires a prior `jor discover` to have fresh data. Full discovery scans ~379 session files, parsing each one — taking ~6 seconds. Users expect `jor list` to show current sessions without a manual discovery step.

## Solution

Add mtime-based incremental discovery that runs automatically before `jor list`. Only session files modified since the last scan are processed. A threaded braille-dot spinner provides visual feedback during the scan.

## Design

### Incremental Scan in BaseConnector

`BaseConnector.scan()` accepts an optional `since: float | None` parameter (unix timestamp).

- When `since` is provided: skip files where `stat().st_mtime <= since`
- When `since` is None: process all files (full scan, same as today)

The `_process()` method is unchanged — it only runs on files that pass the mtime filter.

### Scanner.run_incremental()

New method on `Scanner`:

1. Load the index and read `last_scan`
2. Convert `last_scan` ISO string to unix timestamp
3. Pass as `since` to each connector's `scan()`
4. Upsert any new/updated entries into the index
5. Update `last_scan` and save

First run (no `last_scan`): falls back to full scan automatically by passing `since=None`.

### CLI Integration

`jor list` calls `Scanner.run_incremental()` before loading the index for display. `jor discover` is unchanged — always runs a full scan (`since=None`), useful for cleaning up deleted/stale sessions.

### Spinner

A threaded braille-dot spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) with the message "Discovering new sessions...":

- Runs in a daemon thread, stopped when scan completes
- Only shown when incremental scan actually runs
- If new sessions found: prints a brief line like "Found 3 new sessions" before list output
- If no new sessions: spinner disappears silently

Implementation uses stdlib `threading` and `sys.stderr` — no new dependencies.

### Edge Cases

- **Deleted sessions:** Remain in the index until a full `jor discover` is run. Acceptable — stale entries are harmless (convert/open will fail with a clear error if the source file is gone).
- **Append-only files:** Both Claude Code and Codex only append to session files, so mtime always updates on changes. In-place edits that preserve mtime are not a realistic scenario.

## Files Changed

| File | Change |
|------|--------|
| `src/jor/connectors/base.py` | Add `since` parameter to `scan()`, filter by mtime |
| `src/jor/core/scanner.py` | Add `run_incremental()` method |
| `src/jor/cli.py` | Call `run_incremental()` in `list_sessions`, add spinner |

## Not in Scope

- Background/async discovery
- File hash caching
- Filesystem watchers
- Cleaning up deleted sessions from incremental scan (use `jor discover` for that)
