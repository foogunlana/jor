# Jor Research: Session Formats, Competitors, and Reading List

Compiled 2026-04-25.

---

## Session Storage Across Major AI Tools

| Tool | Location | Format | Shareable? |
|------|----------|--------|------------|
| Claude Code | `~/.claude/projects/<hash>/sessions/<uuid>.jsonl` | JSONL (typed messages, linked by parentUuid) | No |
| Claude Desktop (Cowork) | `~/Library/Application Support/Claude/` | Unknown (likely SQLite) | No ("team sharing coming") |
| ChatGPT | Server-side | JSON tree (mapping of message nodes) | Read-only link |
| Cursor | `~/Library/Application Support/Cursor/` | SQLite (closed-source) | No |
| Windsurf | `~/Library/Application Support/Windsurf/` | SQLite (closed-source) | No |
| GitHub Copilot Chat | VS Code extension state | Ephemeral (not persisted) | No |
| Codex (OpenAI) | In-memory during sessions | OpenAI chat completion format | No |
| Aider | `.aider.chat.history.md` | Markdown | No |
| Continue.dev | `~/.continue/sessions/` | JSON per session | No |
| Goose | `{data_dir}/sessions/sessions.db` | SQLite (sessions + messages tables) | No |
| Cline | VS Code extension state | TypeScript objects | No |

---

## Existing Standards / Interchange Attempts

- **OpenAI Chat Completion Format** — de facto standard but lacks timestamps, file refs, costs, branching
- **Anthropic Messages Format** — content block arrays, different from OpenAI's
- **ShareGPT Format** — `[{from, value}]` turns. Deprecated but became training data standard (Vicuna). 1.8k stars.
- **CCMF (ContextSwitchAI)** — Compressed Chat Memory Format, up to 70% smaller, designed for AI-to-AI interchange
- **LangChain BaseMessage** — normalizes across providers but LangChain-specific
- **Jupyter nbformat** — THE playbook. Open JSON + formal schema + semantic versioning + ecosystem of tools
- **No RFC, W3C spec, or IETF draft exists for AI conversation interchange**

---

## Competitors and Adjacent Projects

### Direct
- **Nessie Labs** (YC F25) — "Perplexity for your mind." Imports from ChatGPT/Claude, auto-organizes into knowledge. 1,200+ users, 300K+ conversations in 3 weeks. Positioned as knowledge extraction, not session sharing.
- **CASS** — Unified search across 19+ agent session formats. Normalized SQLite + Tantivy index. Their RESEARCH_FINDINGS.md is essential reading for format differences.
- **ContextSwitchAI** — Browser extension exporting across ChatGPT/Claude/Gemini/Grok. Introduces CCMF format.
- **Plurality Network** — Browser extension creating universal memory layer across AI platforms.

### Adjacent
- **claude-squad** (6.6k stars) — manages multiple Claude Code/Codex agents in parallel. Local only.
- **tradchenko/claude-sessions** — cross-agent shared memory via MCP. Validates agent-agnostic sessions.
- **mem0-mcp** — memory-as-a-service via MCP. Session-level equivalent is what Jor would be.
- **LibreChat** — multi-format export/import, but sharing within single instance only.
- **Open WebUI** — multi-user with S3/GCS backends, but self-contained platform.
- **Plandex** — version control for AI plans. Closest to "git for AI" but single-tool.

### What Nobody Has
1. Universal AI conversation interchange format
2. Fork-and-continue for sessions
3. Cross-tool session portability
4. Shareable context bundles (files + conversation + tool state)

---

## Where Anthropic and OpenAI Are Heading

### Anthropic
- **Managed Agents** treats sessions as append-only event logs (separate from execution)
- Sessions API (beta): `POST /v1/sessions`, `GET /v1/sessions/{id}/stream`
- Claude Code Agent SDK exposes `listSessions()`, `getSessionMessages()`
- **Cowork cannot share sessions.** "Team sharing is coming" — no timeline.
- Memory for agents: agent-to-agent, not human-to-human sharing

### OpenAI
- **Conversations API** — durable session IDs, no 30-day TTL. Sessions becoming first-class.
- ChatGPT shared links — read-only, no forking, link dies with original
- **Group Chats** — up to 20 people in shared conversation. ChatGPT-only, not exportable.
- Codex: resume/fork primitives, sticky environments, remote thread plumbing
- Assistants API deprecating Aug 2026 → Responses API + Conversations API

**Key signal:** Both labs are making sessions first-class primitives but neither is solving cross-platform interchange or fork-and-continue.

---

## Essential Reading List

### Must Read (before building)
1. [CASS RESEARCH_FINDINGS.md](https://github.com/Dicklesworthstone/coding_agent_session_search/blob/main/RESEARCH_FINDINGS.md) — documents session format differences across 19+ agents
2. [Jupyter nbformat spec](https://nbformat.readthedocs.io/en/latest/format_description.html) — the playbook for building an interchange format
3. [Inside Claude Code Session Format](https://databunny.medium.com/inside-claude-code-the-session-file-format-and-how-to-inspect-it-b9998e66d56b) — detailed JSONL schema
4. [Anthropic Managed Agents Engineering](https://www.anthropic.com/engineering/managed-agents) — session architecture (append-only event log)
5. [AI Conversation Portability Does Not Exist Yet](https://dev.to/isabelsmith/standard-ai-conversation-portability-does-not-exist-yet-here-is-why-that-should-bother-you-p34) — the manifesto

### Should Read (for positioning)
6. [Nessie Labs YC Launch](https://www.ycombinator.com/launches/Omc-nessie-perplexity-for-your-mind?uw=31) — closest competitor
7. [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — how to structure context for re-ingestion
8. [OpenAI Conversation State Guide](https://developers.openai.com/api/docs/guides/conversation-state) — OpenAI's session persistence API
9. [Claude Code Sessions SDK](https://code.claude.com/docs/en/agent-sdk/sessions) — programmatic session access
10. [Building agent-sessions: Universal Session Manager](https://dev.to/vineethnkrishnan/building-agent-sessions-a-universal-session-manager-for-the-ai-cli-era-2i04) — practical challenges

### Worth Scanning (for context)
11. [ContextSwitchAI / CCMF](https://contextswitchai.github.io/ContextSwitchAI/) — compressed interchange format
12. [ChatGPT Group Chats](https://openai.com/index/group-chats-in-chatgpt/) — most advanced collaborative AI sessions
13. [Bessemer AI Infrastructure Roadmap](https://www.bvp.com/atlas/ai-infrastructure-roadmap-five-frontiers-for-2026) — VC perspective on session infrastructure
14. [Plurality Network AI Context Flow](https://plurality.network/ai-context-flow/) — browser extension for cross-platform context
15. [nbformat GitHub](https://github.com/jupyter/nbformat) — reference implementation for format ecosystem
