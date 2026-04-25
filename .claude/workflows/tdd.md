# TDD Bead Workflow

A workflow for structuring implementation work as TDD bead pairs using beads + Ralph.

## The Pattern

Every implementable unit of work becomes **two beads** — a test bead and an implementation bead:

1. **Test bead** — Write failing tests that encode the acceptance criteria
2. **Implementation bead** — Write code to make the tests pass (and pass linters)

Both beads share identical acceptance criteria. The test bead says "write tests for these criteria." The implementation bead says "make these criteria pass, all tests green, linters clean."

The implementation bead **depends on** the test bead (`bd dep add <impl> <test>`), so Ralph picks them up in the right order.

## Bead Structure

### Test Bead Template

```
Title: "Tests: <feature name>"
Type: task
Description: |
  Write failing tests for <feature name>.

  ## Acceptance Criteria
  <shared criteria — paste identically into both beads>

  ## Test Guidance
  - Tests MUST fail before implementation (red phase)
  - One test per criterion minimum
  - Use fixtures in tests/fixtures/ for sample data
  - Test file: tests/test_<module>.py
```

### Implementation Bead Template

```
Title: "Impl: <feature name>"
Type: task
Description: |
  Implement <feature name> to satisfy acceptance criteria. All tests and linters must pass.

  ## Acceptance Criteria
  <shared criteria — identical to test bead>

  ## Implementation Guidance
  - Minimal code to make tests pass (green phase)
  - Refactor only if needed for clarity (refactor phase)
  - All tests pass: <test command>
  - Linters pass: <lint command>
```

## Creating TDD Pairs

When creating beads for a feature:

```bash
# 1. Create the test bead
bd create --title="Tests: session schema" \
  --description="Write failing tests for session schema.\n\n## Acceptance Criteria\n- JorMessage validates required fields\n- Round-trip JSONL serialization\n- Rejects invalid roles\n\n## Test Guidance\n- Tests MUST fail before implementation\n- Test file: tests/test_schema.py" \
  --type=task --priority=2

# 2. Create the implementation bead
bd create --title="Impl: session schema" \
  --description="Implement session schema. All tests and linters must pass.\n\n## Acceptance Criteria\n- JorMessage validates required fields\n- Round-trip JSONL serialization\n- Rejects invalid roles\n\n## Implementation Guidance\n- Minimal code to make tests pass\n- All tests pass: pytest\n- Linters pass: ruff check" \
  --type=task --priority=2

# 3. Set dependency (impl depends on tests)
bd dep add <impl-id> <test-id>
```

## Layering with Dependencies

For multi-layer projects, chain the TDD pairs:

```
Tests: schema ──→ Impl: schema ──→ Tests: connectors ──→ Impl: connectors ──→ ...
```

Each layer's test bead depends on the previous layer's implementation bead. This ensures:
- Ralph builds bottom-up
- Each layer has passing tests before the next begins
- A broken layer blocks downstream work (good — catches issues early)

## Scaffolding & Non-TDD Beads

Not everything needs a TDD pair. Use a single bead for:
- **Project scaffolding** — pyproject.toml, directory structure, config files
- **Documentation** — README, skills, packaging
- **Integration tests** — end-to-end tests that span multiple layers (created after all layers ship)

These are regular beads, not TDD pairs.

## Epics

Group related TDD pairs under an epic for visibility:

```bash
bd create --title="Session Schema" --type=epic --description="Core Pydantic models for Jor session format"
# Then create TDD pairs and add the epic as a parent or tag
```

## Ralph Integration

This workflow is designed for Ralph (`ralph.sh`). Ralph's RALPH.md already has TDD instructions (write failing test → make it pass → refactor). The bead structure reinforces this:

- **Test beads** — Ralph writes tests, confirms they fail, commits
- **Impl beads** — Ralph writes code, confirms tests pass + linters clean, commits

The dependency chain ensures Ralph processes them in order without human intervention.

## Quality Gates

Acceptance criteria on implementation beads should always include:
- All tests pass (`pytest` / `npm test` / etc.)
- Linters pass (`ruff check` / `eslint` / etc.)
- Type checking passes (if applicable)

These are verified by Ralph before closing each bead.
