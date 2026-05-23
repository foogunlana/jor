# jor

Transfer AI sessions between tools. Start a conversation in Claude Code, continue it in Codex — or vice versa.

Jor discovers sessions across AI tools on your machine, converts them to a common format, and writes them back in the target tool's native format so you can resume seamlessly.

## Supported Tools

- **Claude Code** — reads and writes `.jsonl` sessions
- **Codex** — reads and writes `.jsonl` sessions

## Install

```bash
pip install jor
```

## Usage

```bash
# Discover all AI sessions on your machine
jor discover

# List indexed sessions
jor list

# Convert a session to another tool's format
jor convert <session-id> --codex     # Claude Code → Codex
jor convert <session-id>             # anything → Claude Code (default)

# Convert and launch the target tool
jor open <session-id> --codex
```

## How It Works

1. **Discover** scans known session directories for each supported tool
2. **Convert** translates messages, tool calls, and tool results into a common schema (JSONL)
3. **Write** outputs the session in the target tool's native format
4. **Open** writes + launches the tool with a resume command

Sessions are portable — file paths are stored relative, and source provenance is preserved.

## License

MIT
