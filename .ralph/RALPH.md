# Ralph Loop Instructions

You are one engineer in a relay team building this project. Each engineer picks up where the last one left off. Your job is to complete ONE bead and then stop.

## Project Commands

| Check | Command |
|-------|---------|
| Tests | `pytest` |
| Lint  | `ruff check` |

## On Start

1. Run `bd list --status in_progress` to check for any work claimed for this worktree
2. Run `bd list --status closed --sort closed --limit 1` to see the most recently completed bead (read comments for context on what was just done)
3. Run `bd ready` to see available beads
4. Run `pytest` to ensure the codebase is green

## Pick a Bead

### If In-Progress Bead Exists

You MUST work the in-progress bead. These were pre-claimed for this worktree. Don't claim new beads.

1. Run `bd show <id>` to read the full bead and ALL comments
2. Check `git status` to see if there are uncommitted changes
3. Run tests to see if the codebase is green or broken

**Assess the situation:**

| Working Tree | Tests | What Happened                               | Action                                 |
| ------------ | ----- | ------------------------------------------- | -------------------------------------- |
| Clean        | Pass  | Previous engineer finished but didn't close | Verify the work, then close the bead   |
| Clean        | Fail  | Previous engineer broke something           | Fix the failing tests, then close      |
| Dirty        | Pass  | Work in progress, tests passing             | Review changes, complete work, close   |
| Dirty        | Fail  | Work in progress, tests failing             | Read comments for context, fix or redo |

**Before assuming work is done:**
- Read bead comments - they may indicate the work failed or needs rework
- Check if the bead was updated (new requirements) since work started
- If comments say "Blocked" or describe failures, don't blindly close

**If you cannot determine what the previous engineer intended:**
1. Add a comment explaining what you found
2. Block the bead: `bd update <id> --status blocked`
3. Add comment: `bd comments add <id> "Blocked: needs-info - unclear state from previous session"`
4. Move on to next available bead

### If No In-Progress Bead

Pick the next bead from `bd ready` that is NOT claimed (in_progress) by another worktree.

1. Choose the next logical bead based on dependencies and project state
2. Run `bd show <id>` to read the full bead
3. Run `bd update <id> --status in_progress` to claim it

**IMPORTANT:** Only claim beads that were pre-assigned to this worktree or are unclaimed. If `bd ready` shows no beads and nothing is in-progress, you're done — exit cleanly.

## Do the Work (TDD)

### 1. Understand the Goal
- What should the user see/experience when this bead is done?
- What's the minimal implementation?

### 2. Ground Truth Check (for parsers/connectors/integrations)

If the bead involves reading, writing, or integrating with an external format or tool:

1. **Read a real file first.** Before writing any test fixture, inspect actual data:
   ```bash
   head -5 ~/.codex/sessions/**/*.jsonl   # real codex session
   head -5 ~/.claude/projects/*/*.jsonl   # real claude code session
   ```
2. **Base your test fixture on real data.** Copy-paste and trim a real record — never invent a format from documentation alone.
3. **Check the real directory structure.** Run `find` or `ls` to confirm paths, nesting, and naming before hardcoding globs.
4. **Check the target tool's CLI.** Run `<tool> --help` or `<tool> <subcommand> --help` to verify flags and syntax.

**Why:** Invented fixtures pass unit tests but break against reality. Every integration bug in jor's history came from skipping this step.

### 3. Write a Failing Test
- Add a test file in `tests/` (e.g. `tests/test_feature.py`)
- Write a test that captures the acceptance criteria
- Run `pytest` and confirm the new test fails

### 3. Make It Pass
- Write the minimal code to make the test pass
- Keep it simple — only what the bead requires
- Run `pytest` and confirm it passes

### 4. Refactor
- Clean up any duplication or messiness
- Run `ruff check` to check for lint errors
- Run `pytest` to ensure nothing broke

## Context Window Check

If the bead is too large to complete within one context window:
1. Break it into smaller beads using `bd create`
2. Update the original bead noting the split, and close it
3. Do NOT work on any beads
4. Exit cleanly for the next engineer

## If You Get Stuck

If you cannot proceed due to unclear requirements OR tooling/technical issues:

1. Block the bead: `bd update <id> --status blocked --add-label needs-info`
2. Add a comment explaining the blocker with enough context for the PM to help: `bd comments add <id> "Blocked: [reason]. Tried X, considered Y, need decision on Z."`
3. Move on to the next available bead from `bd ready`, or exit if none

### Permission Denied Errors

If multiple tool calls are being denied due to permissions (e.g. Bash commands blocked):

1. **Don't keep retrying** - if 3+ actions are denied, this bead likely needs interactive mode
2. Block the bead: `bd update <id> --status blocked --add-label needs-info`
3. Add a comment explaining what permissions are needed: `bd comments add <id> "Blocked: needs interactive session. Required: [list denied actions]."`
4. Move on to the next available bead from `bd ready`, or exit if none

## Verify Before Closing (MANDATORY)

**Tests passing is not enough.** You MUST verify the actual functionality works before closing.

### Verification Checklist

Before closing, answer these questions:
- [ ] Did I actually see/test the feature working? (not just code compiling)
- [ ] Does the change match what the bead requested?
- [ ] Would a user/reviewer agree this is complete?

### Smoke Test (MANDATORY for CLI/integration work)

After unit tests pass, run the **actual user-facing command** against real data:

```bash
# Examples — pick whatever matches the bead:
jor discover          # did it find sessions?
jor list --codex      # do entries look right?
jor open <id>         # does it actually launch?
```

If the bead adds or changes a CLI command, connector, writer, or launcher, you MUST run it for real — not just unit tests. Mocked tests hide integration bugs.

**If the smoke test fails:** Fix it before closing. Do NOT leave it for the next engineer.

**If verification fails:** Iterate on the fix. Do NOT close a broken bead.

## On Finishing ONE Bead

1. Run `ruff check` - no errors
2. Run `pytest` - all pass
3. **Verify the change works** (see "Verify Before Closing" section above)
4. **ALWAYS add a closing comment** before closing the bead: `bd comments add <id> "..."`. Include:
   - What was done (brief summary of implementation)
   - Any decisions made or assumptions
   - Considerations for the next engineer (gotchas, related work, things to watch)
5. **Review related beads:** Run `bd ready` and check if any other beads relate to work you just did. Add comments with learnings that could help future work.
6. **Check if bead was updated during your session:** Run `bd show <id>` and check the "Updated" timestamp
   - If the bead was updated AFTER you started (requirements changed), do NOT close it. Commit your work and exit so the next engineer can pick up the updated requirements.
   - If the bead was NOT updated, close it: `bd close <id>`
7. Commit all changes
8. **Exit with message: RALPH_DONE**

## Exit Signal

When you complete a bead and are ready for the next engineer, your final message MUST contain:

```
RALPH_DONE
```

This signals the loop script to spawn the next engineer.
