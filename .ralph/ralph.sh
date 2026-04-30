#!/bin/bash

# Ralph Loop - Autonomous engineer relay
#
# Usage:
#   ./ralph.sh [iterations]    Single mode: one bead per iteration, no worktrees
#   ./ralph.sh -p N            Parallel: N beads at a time, loops until no ready beads
#   ./ralph.sh -p N --once     Parallel: N beads, one round only
#
# Parallel mode:
#   1. Claims up to N ready beads on main, commits .beads/
#   2. Creates one worktree per bead in .ralph/worktrees/<bead-id>
#   3. Launches one ralph loop per worktree (1 iteration each)
#   4. Logs to .ralph/logs/<bead-id>.log
#   5. Waits for all to finish
#   6. Merges branches back to main, closes completed beads
#   7. Repeats until no ready beads remain (unless --once)

set -e

# ANSI colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ─── Parse arguments ────────────────────────────────────────────────────────

PARALLEL=0
MAX_ITERATIONS=5
ONCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--parallel)
            PARALLEL="$2"
            shift 2
            ;;
        --once)
            ONCE=true
            shift
            ;;
        *)
            MAX_ITERATIONS="$1"
            shift
            ;;
    esac
done

# ─── Parallel mode ──────────────────────────────────────────────────────────

if [ "$PARALLEL" -gt 0 ]; then
    cd "$PROJECT_DIR"

    # Kill all worker processes on interrupt
    ALL_PIDS=()
    cleanup_parallel() {
        echo -e "\n${RED}✗${NC} Interrupted — killing workers..."
        for pid in "${ALL_PIDS[@]}"; do
            kill "$pid" 2>/dev/null
        done
        # Kill any claude processes we spawned in worktrees
        pkill -P $$ 2>/dev/null || true
        exit 130
    }
    trap cleanup_parallel INT TERM

    WORKTREE_DIR="$PROJECT_DIR/.ralph/worktrees"
    LOG_DIR="$PROJECT_DIR/.ralph/logs"
    ROUND=0
    TOTAL_FAILURES=0
    ALL_BEADS_WORKED=()

    while true; do
        ROUND=$((ROUND + 1))

        # Get ready beads, take up to N
        READY_BEADS=($(bd ready 2>/dev/null | grep -oE 'jor-[a-z0-9]+' || true))

        if [ ${#READY_BEADS[@]} -eq 0 ]; then
            if [ $ROUND -eq 1 ]; then
                echo -e "${YELLOW}No ready beads to work on.${NC}"
            else
                echo -e "${GREEN}■${NC} No more ready beads."
            fi
            break
        fi

        # Cap at requested parallelism
        BEADS=("${READY_BEADS[@]:0:$PARALLEL}")
        ALL_BEADS_WORKED+=("${BEADS[@]}")

        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${CYAN}▶${NC} Ralph Parallel — Round ${GREEN}$ROUND${NC}: ${#BEADS[@]} beads"
        echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${BLUE}▸${NC} Working: ${BEADS[*]}"
        echo ""

        # Claim all beads on main
        for BEAD in "${BEADS[@]}"; do
            echo -e "${DIM}› Claiming $BEAD${NC}"
            bd update "$BEAD" --claim 2>/dev/null
        done
        echo ""

        # Commit .beads/ state so worktrees inherit it
        echo -e "${DIM}› Committing bead claims...${NC}"
        git add .beads/
        git commit -m "ralph: claim beads for round $ROUND" --quiet 2>/dev/null || true

        # Create worktrees and launch one ralph loop per bead
        mkdir -p "$WORKTREE_DIR" "$LOG_DIR"

        PIDS=()
        for BEAD in "${BEADS[@]}"; do
            WT_PATH="$WORKTREE_DIR/$BEAD"
            BRANCH="ralph/$BEAD"
            LOG_FILE="$LOG_DIR/$BEAD.log"

            # Clean up stale worktree if it exists
            if [ -d "$WT_PATH" ]; then
                echo -e "${YELLOW}› Removing stale worktree $BEAD${NC}"
                git worktree remove "$WT_PATH" --force 2>/dev/null || rm -rf "$WT_PATH"
                git worktree prune 2>/dev/null || true
                git branch -D "$BRANCH" 2>/dev/null || true
            fi

            echo -e "${BLUE}› Creating worktree $BEAD on branch $BRANCH${NC}"
            git worktree add "$WT_PATH" -b "$BRANCH" --quiet

            echo -e "${GREEN}› Launching ralph for $BEAD (log: .ralph/logs/$BEAD.log)${NC}"
            # Strip ANSI escape codes so log files are plain text
            # --line-buffered ensures logs stream in real-time
            (cd "$WT_PATH" && bash .ralph/ralph.sh 1) 2>&1 | sed -l 's/\x1b\[[0-9;]*m//g' > "$LOG_FILE" &
            PIDS+=($!)
            ALL_PIDS+=($!)
        done

        echo ""
        echo -e "${CYAN}▶${NC} Waiting for round $ROUND..."
        echo ""

        # Poll for completion with progress display
        # Use indexed array for bash 3 compatibility (no associative arrays)
        TOTAL=${#BEADS[@]}
        FAILURES=0
        DONE=()  # indexed same as BEADS: "" = running, "ok" = success, "fail" = failed

        while true; do
            COMPLETED=0
            STATUS_LINE=""

            for i in "${!BEADS[@]}"; do
                BEAD=${BEADS[$i]}
                if [ "${DONE[$i]}" = "ok" ]; then
                    # Already finished successfully
                    COMPLETED=$((COMPLETED + 1))
                    STATUS_LINE+=" ${GREEN}✓${NC} $BEAD"
                elif [ "${DONE[$i]}" = "fail" ]; then
                    # Already finished with error
                    COMPLETED=$((COMPLETED + 1))
                    STATUS_LINE+=" ${RED}✗${NC} $BEAD"
                elif ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
                    # Just finished — check exit status
                    if wait "${PIDS[$i]}" 2>/dev/null; then
                        DONE[$i]="ok"
                    else
                        DONE[$i]="fail"
                        FAILURES=$((FAILURES + 1))
                    fi
                    COMPLETED=$((COMPLETED + 1))
                    if [ "${DONE[$i]}" = "ok" ]; then
                        STATUS_LINE+=" ${GREEN}✓${NC} $BEAD"
                    else
                        STATUS_LINE+=" ${RED}✗${NC} $BEAD"
                    fi
                else
                    # Still running
                    STATUS_LINE+=" ${YELLOW}◐${NC} $BEAD"
                fi
            done

            # Build progress bar
            BAR_WIDTH=20
            FILLED=$((COMPLETED * BAR_WIDTH / TOTAL))
            EMPTY=$((BAR_WIDTH - FILLED))
            BAR=$(printf "%${FILLED}s" | tr ' ' '█')$(printf "%${EMPTY}s" | tr ' ' '░')

            # Print on single line, overwriting previous
            printf "\r\033[K  ${CYAN}[${BAR}]${NC} ${GREEN}${COMPLETED}${NC}/${TOTAL} ${STATUS_LINE} "

            # Done?
            if [ "$COMPLETED" -eq "$TOTAL" ]; then
                echo ""
                break
            fi

            sleep 3
        done
        echo ""

        TOTAL_FAILURES=$((TOTAL_FAILURES + FAILURES))

        # Merge branches back to main
        echo -e "${DIM}› Merging branches back to main...${NC}"
        git checkout main --quiet

        for BEAD in "${BEADS[@]}"; do
            BRANCH="ralph/$BEAD"
            echo -e "${BLUE}› Merging $BRANCH${NC}"
            # Accept main's .beads/ on conflicts — we'll close beads manually
            if ! git merge "$BRANCH" --no-edit --quiet 2>/dev/null; then
                echo -e "${YELLOW}  Conflict — keeping main's .beads/, merging code${NC}"
                git checkout --ours .beads/ 2>/dev/null || true
                git add .beads/
                git commit --no-edit --quiet 2>/dev/null || true
            fi
        done

        # Clean up worktrees and branches
        echo -e "${DIM}› Cleaning up worktrees...${NC}"
        for BEAD in "${BEADS[@]}"; do
            git worktree remove "$WORKTREE_DIR/$BEAD" --force 2>/dev/null || true
            git branch -D "ralph/$BEAD" --quiet 2>/dev/null || true
        done
        echo ""

        # Stop after one round if --once
        if [ "$ONCE" = true ]; then
            break
        fi
    done

    # Final report
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}■${NC} Ralph parallel run complete — $ROUND round(s), ${#ALL_BEADS_WORKED[@]} bead(s)"
    echo ""
    if [ ${#ALL_BEADS_WORKED[@]} -gt 0 ]; then
        echo -e "${YELLOW}▸${NC} Review the work, then close completed beads on main:"
        echo ""
        echo "  bd close ${ALL_BEADS_WORKED[*]}"
        echo ""
    fi
    echo -e "${BLUE}▸${NC} Logs: .ralph/logs/"
    echo -e "${BLUE}▸${NC} Current status:"
    bd list --status in_progress 2>/dev/null || true
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    exit $TOTAL_FAILURES
fi

# ─── Single track mode ──────────────────────────────────────────────────────

# Track claude PID so we can kill it on Ctrl-C
CLAUDE_PID=""
cleanup() {
    echo -e "\n${RED}✗${NC} Interrupted"
    [ -n "$CLAUDE_PID" ] && kill "$CLAUDE_PID" 2>/dev/null
    exit 130
}
trap cleanup INT TERM

ITERATION=0

cd "$PROJECT_DIR"

echo -e "${CYAN}→${NC} Starting Ralph Loop in $PROJECT_DIR"
echo "   Max iterations: $MAX_ITERATIONS"
echo ""

# Check beads are ready
if ! command -v bd &> /dev/null; then
    echo -e "${RED}✗${NC} bd (beads) not found. Install it first."
    exit 1
fi

# Show initial state
echo -e "${BLUE}▸${NC} Current beads status:"
bd ready 2>/dev/null || echo "   No beads ready or bd not initialised"
echo ""

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    # Check for dirty state - if dirty, skip fetch/pull (we're mid-work)
    if git diff --quiet && git diff --cached --quiet; then
        echo -e "${DIM}› Syncing...${NC}"
        git fetch --quiet 2>/dev/null || true
        git pull --rebase --quiet 2>/dev/null || true
    else
        echo -e "${YELLOW}› Dirty working tree detected - resuming previous work...${NC}"
    fi

    # Check if there are any beads to work on
    READY_COUNT=$(bd count --status open 2>/dev/null || echo "0")
    IN_PROGRESS=$(bd count --status in_progress 2>/dev/null || echo "0")

    if [ "$READY_COUNT" = "0" ] && [ "$IN_PROGRESS" = "0" ]; then
        echo -e "${GREEN}■${NC} No beads available — this track is done."
        break
    fi

    ITERATION=$((ITERATION + 1))
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}▶${NC} Ralph iteration ${GREEN}$ITERATION${NC} of $MAX_ITERATIONS"
    echo "   Started: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    echo -e "${BLUE}› Spawning Claude engineer...${NC}"
    echo ""

    # Stream output with clean formatting.
    # Uses a FIFO so claude runs as a tracked background process. This lets
    # the trap handler kill it on Ctrl-C (bash's `read` builtin blocks signals
    # but the cleanup trap fires between reads when claude is killed).
    FIFO=$(mktemp -u /tmp/ralph-fifo-XXXXXX)
    mkfifo "$FIFO"

    claude --chrome --model sonnet --effort medium --permission-mode acceptEdits --verbose \
      --allowedTools 'Bash(bd *)' 'Bash(pytest*)' 'Bash(ruff *)' \
      --allowedTools 'Bash(uv *)' 'Bash(git *)' \
      --print "Read @RALPH.md and follow the instructions. Pick up where the last engineer left off. Complete ONE bead." \
      --output-format stream-json > "$FIFO" 2>/dev/null &
    CLAUDE_PID=$!

    while read -r line; do
        type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)
        if [ "$type" = "assistant" ]; then
            # Show text
            echo "$line" | jq -r '.message.content[]? | select(.type == "text") | .text' 2>/dev/null | while IFS= read -r text; do
                [ -z "$text" ] && continue
                echo -e "${BLUE}▸${NC} $text"
            done
            # Show tool calls concisely: → tool_name { inputs }
            echo "$line" | jq -c '.message.content[]? | select(.type == "tool_use")' 2>/dev/null | while read -r tool; do
                [ -z "$tool" ] && continue
                name=$(echo "$tool" | jq -r '.name' 2>/dev/null)
                input=$(echo "$tool" | jq -c '.input' 2>/dev/null)
                echo -e "${YELLOW}→${NC} ${CYAN}$name${NC} ${DIM}$input${NC}"
            done
        elif [ "$type" = "user" ]; then
            # Show tool results cleanly
            echo "$line" | jq -c '.message.content[]? | select(.type == "tool_result")' 2>/dev/null | while read -r result; do
                [ -z "$result" ] && continue
                is_error=$(echo "$result" | jq -r '.is_error // false' 2>/dev/null)
                # Extract and clean content
                content=$(echo "$result" | jq -r '
                    .content |
                    if type == "array" then
                        map(select(.type == "text") | .text) | join("\n")
                    elif type == "string" then
                        .
                    else
                        "..."
                    end
                ' 2>/dev/null | tr -d '\r' | head -n 20)
                # Truncate if contains base64 image data
                if echo "$content" | grep -q '/9j/4AAQ\|data:image'; then
                    content="[image captured]"
                fi
                # Format line numbers: replace → with spaces, dim the line numbers
                formatted=$(echo "$content" | sed -E "s/^([[:space:]]*[0-9]+)→/\x1b[2m\1\x1b[0m  /")
                if [ "$is_error" = "true" ]; then
                    echo ""
                    echo -e "${RED}✗${NC}"
                    echo -e "$formatted"
                else
                    echo ""
                    echo -e "${DIM}○${NC}"
                    echo -e "$formatted"
                fi
            done
        elif [ "$type" = "result" ]; then
            # Handle final result from Claude CLI
            subtype=$(echo "$line" | jq -r '.subtype // empty' 2>/dev/null)
            result_text=$(echo "$line" | jq -r '.result // empty' 2>/dev/null)
            if [ "$subtype" = "success" ] && [ -n "$result_text" ]; then
                echo ""
                echo -e "${GREEN}✓${NC} $result_text"
            elif [ "$subtype" = "error" ]; then
                echo ""
                echo -e "${RED}✗${NC} $result_text"
            else
                echo -e "${DIM}? $line${NC}"
            fi
        elif [ "$type" != "system" ]; then
            echo -e "${DIM}? $line${NC}"
        fi
    done < "$FIFO"

    rm -f "$FIFO"
    wait "$CLAUDE_PID" 2>/dev/null || true
    CLAUDE_PID=""

    echo ""
    echo -e "${GREEN}✓${NC} Iteration $ITERATION complete"
    echo ""
    sleep 2
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}■${NC} Ralph loop finished"
echo "   Total iterations: $ITERATION"
echo "   Ended: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo -e "${BLUE}▸${NC} Final beads status:"
bd ready 2>/dev/null || echo "   No beads ready"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
