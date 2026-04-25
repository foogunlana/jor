# Jor — Go to Market Plan

## Vision

Your AI context is fragmented. Claude Code sessions on your laptop. ChatGPT threads in the cloud. Aider histories in project folders. Cursor conversations locked in a closed database. None of them talk to each other, none of them are shareable, and switching between tools means starting from scratch.

Jor is the missing session layer for AI. It discovers, indexes, and unifies your AI conversations across every tool — then lets you continue any session in any tool, share your work with anyone, and build on what others have done.

**Jor is to AI sessions what Jupyter Notebooks are to data science: an open, portable, shareable format that an ecosystem grows around.**

Three layers, shipped in order:

1. **Jor MCP** — the open-source tool. Discovers and indexes all your AI sessions locally. Continue any session in any MCP-compatible tool.
2. **JorHub** — the platform. Hosted storage, sharing, and discovery. GitHub-to-git relationship.
3. **JorHub Social** — the experience. Session visualization, public profiles, forking, remixing, community.

---

## MVP Scope (Phase 1 — 1 week)

**"All your AI sessions, one place."**

A local-only MCP server that discovers AI sessions across tools on your machine and lets you continue any of them in Claude Code.

### What ships

- **Jor MCP server** (npm package, installable in Claude Code)
- **Session discovery engine** — scans known paths for sessions from:
  - Claude Code (`~/.claude/projects/*/sessions/*.jsonl`)
  - Continue.dev (`~/.continue/sessions/`)
  - Aider (`.aider.chat.history.md` files)
  - Others as accessible (Goose SQLite, Cline VS Code state)
- **Jor session format** — JSONL schema that captures the superset: role, content, tool calls/results, file references (relative paths), model, provider, timestamps, metadata
- **Session translators** — converters from each tool's native format into Jor JSONL
- **Local session index** — browseable catalogue of all discovered sessions
- **MCP tools:**
  - `jor_discover` — scan machine, find all sessions, return summary
  - `jor_list` — list indexed sessions (filter by tool, date, project, keyword)
  - `jor_open` — load a session into the current conversation context to continue it

### What doesn't ship

- No remote storage, no sync, no auth
- No web UI
- No git integration
- No push/pull/share
- No real-time session capture (sessions are discovered after the fact)

### Success criteria

- Install the MCP, run `jor_discover`, see sessions from 2+ different AI tools
- Pick a session from a different tool and meaningfully continue it in Claude Code
- The whole thing works offline with zero configuration beyond installing the MCP

---

## First GTM Milestone: The Demo

**Target:** Community event presentation (May 2026)

**Demo script (3-5 minutes):**

1. "I use Claude Code, Aider, and Continue.dev. My conversations are scattered."
2. Install the Jor MCP — one line in Claude Code config.
3. "Jor, discover my sessions." → Shows a catalogue: 15 Claude Code, 8 Aider, 4 Continue sessions across projects.
4. "Show me the Aider session where I was working on the auth refactor." → Session details with conversation summary.
5. "Open it." → Session context loads. Continue the conversation in Claude Code, picking up where Aider left off.
6. "This is session portability. No lock-in. Your work is yours."

**What makes this demo land:**
- It's real — running on your actual laptop with your actual sessions
- The "aha moment" is immediate — people didn't know they had 50+ AI sessions scattered across tools
- It solves a pain point they feel but haven't articulated
- It's open source — they can install it and try it themselves right after the talk

**Audience:** AI Mavericks, developer communities, anyone using 2+ AI tools

**Call to action:** "Install it. Star the repo. Tell me what sessions you want to be able to share."

---

## Roadmap (Post-Demo)

### Phase 2: Share — "Give your session to anyone"

- **Git-backed storage** — Jor folders are git repos with a `.jor/` convention. Push to GitHub, share the URL.
- `jor_init` — initialize `.jor/` in a project folder
- `jor_push` — convert and commit sessions + files to git, push to remote
- `jor_pull` — clone/pull a shared Jor repo, index the sessions locally
- `jor_share` — return the remote URL
- **Session + files together** — not just the conversation but the files referenced, with relative paths preserved
- **Works with any git host** — GitHub, GitLab, self-hosted

### Phase 3: JorHub — "GitHub for AI sessions"

- **Hosted platform** — `jorhub.com` (or equivalent)
- `jor_push` just works without configuring git — push to your JorHub account
- **Web UI** — browse your session library in the browser, view folder structures, read sessions
- **Auth and permissions** — share with specific people, teams, or publicly
- **Persistent shareable links** — no expiry, no git knowledge required for recipients
- **Fork and continue** — clone someone else's session, branch from any point, continue with your own model

### Phase 4: Visualize — "See the conversation"

- **Session renderer** — beautiful web-based visualization of conversation history
- **Embeddable** — share a session visualization like you'd share a Gist
- **Diff view** — compare two sessions or two branches of a session
- **Timeline view** — see all sessions in a project chronologically
- **Tool usage analytics** — which models, how many tokens, cost breakdown

### Phase 5: Social — "Discover what others are building"

- **Public profiles** — your session portfolio (opt-in)
- **Discovery feed** — trending sessions, curated collections
- **Remix** — fork a public session, modify the approach, publish your version
- **Teams** — shared session libraries for organizations
- **Comments and annotations** — discuss specific points in a session

### Phase 6: Ecosystem — "Jor everywhere"

- **More translators** — Cursor, Windsurf, Copilot Chat, Codex, ChatGPT export, Goose, Cline
- **Oya integration** — Oya desktop app becomes a Jor client with native session browsing
- **Mobile client** — browse and read sessions from your phone
- **Real-time session capture** — MCP auto-records sessions as they happen, not just after
- **Browser extension** — capture ChatGPT/Claude web sessions directly
- **API** — programmatic access to session data for building tools on top
- **Session search** — semantic search across all your sessions ("find the session where I debugged the memory leak")

---

## Positioning

**Tagline options:**
- "Your AI sessions. Unified. Shareable. Yours."
- "The session layer for AI."
- "Jupyter Notebooks for AI conversations."

**What Jor is NOT:**
- Not another AI chat app (use Claude, ChatGPT, Cursor — Jor works with all of them)
- Not a memory/RAG tool (Mem0, Khoj do that — Jor preserves full sessions, not extracted facts)
- Not a knowledge base (Nessie Labs does that — Jor is about session portability and sharing)

**Key differentiators:**
- Open source, open format
- Tool-agnostic (works with any AI tool, any model)
- Session-level (full conversations with tool calls, not just text)
- Lossless (nothing is stripped or summarized — the full session is preserved)
- Local-first (your data stays on your machine unless you choose to share)

---

## Competitive Landscape

| | Jor | Nessie Labs | CASS | ShareGPT | ChatGPT Share |
|---|---|---|---|---|---|
| Multi-tool import | Yes | ChatGPT + Claude | 19+ agents | ChatGPT only | ChatGPT only |
| Session format | Open JSONL | Proprietary | Normalized SQLite | Simple JSON | None (link) |
| Fork & continue | Yes | No | No | No | Copy only |
| Cross-tool portability | Yes | No | Search only | No | No |
| Sharing | Git → JorHub | Within platform | No | Public link | Public link |
| Open source | Yes | No | Yes | Deprecated | No |
| Local-first | Yes | No | Yes | No | No |

---

## Naming

Jor. Short, memorable, easy to type.

Yoruba connection to explore: "Jor" could reference collaboration/sharing in Yoruba. JorHub follows the GitHub naming convention.

For the session format: `.jor` file extension (actually JSONL under the hood).

---

## Key Risks

1. **Session formats change** — AI tools update their storage formats. Mitigation: translators are modular, community can contribute.
2. **Tools lock down access** — Cursor/Windsurf could encrypt or move their session storage. Mitigation: start with open tools (Claude Code, Aider, Continue.dev).
3. **Nessie Labs moves into session sharing** — they have YC backing and users. Mitigation: Jor is open source and local-first; different positioning.
4. **"Why not just copy-paste?"** — works for text but loses tool calls, file context, and continuity. Jor preserves the full graph.
5. **Adoption** — MCP is still early. Mitigation: Phase 1 is useful standalone; MCP is growing fast.
