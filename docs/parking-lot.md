# Jor — Parking Lot

Ideas to revisit after Phase 1.

---

## Auto-discovery on session start

When a new Claude Code (or other tool) session opens, Jor should automatically discover and index sessions without the user needing to call `jor_discover` manually. Options to explore:

- MCP server `onConnect` hook — run discovery when the MCP client connects
- File watcher on known session directories (e.g. `~/.claude/projects/`)
- Lightweight background scan on a timer (e.g. every 5 minutes)
- Hook into Claude Code's session lifecycle if the SDK exposes it

The goal: `jor_list` just works from the first message without needing to call `jor_discover` first. Discovery should feel invisible.
