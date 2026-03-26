---
name: execute-plan
description: Executes an approved feature plan from plans/<feature-name>/tasks.md, validates outcomes, and records implementation results.
---

# Execute Plan

Use this skill when the user requests `/execute-plan <feature-name>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `feature-name`

## Preconditions

- `plans/<feature-name>/tasks.md` and `requirements.md` exist.
- Check for `plans/<feature-name>/IMPLEMENTED.md`.

## Procedure

1. If `IMPLEMENTED.md` exists, inform user and abort execution.
2. Execute tasks sequentially from `tasks.md`.
3. Implement and run task-level tests as specified.
4. Run full test suite after implementation.
5. Create `IMPLEMENTED.md` with:
   - Implementation summary
   - New/modified file list
   - Deviations and rationale
6. Update `README.md` when behavior/configuration changed.

## Outputs/Artifacts

- Code/test/doc updates.
- `plans/<feature-name>/IMPLEMENTED.md`.

## Validation

- Full suite passes.
- Success criteria in `requirements.md` are satisfied.
- Final implementation is consistent with design or documented deviations.

## Failure Handling

- On blocker, pause and report root cause, impact, and proposed resolution path.
