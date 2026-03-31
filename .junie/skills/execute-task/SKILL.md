---
name: execute-task
description: Executes a single task from a feature plan, validates outcomes, and creates IMPLEMENTED.md if it's the last task.
---

# Execute Task

Use this skill when the user requests `/execute-task <plan>/<task>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `plan`: The name of the plan directory under `plans/`.
- `task`: The file name of the specific task (e.g., `01-task-name.md`) within the plan directory.

## Preconditions

- The task file exists at `plans/<plan>/<task>`.
- `requirements.md` exists in the `plans/<plan>/` directory.
- Dependencies listed in the task file have been executed (if applicable).

## Procedure

1. Read the task file `plans/<plan>/<task>` to understand the task description, ordering, dependencies, and test requirements.
2. Verify that dependencies are already implemented (e.g., by checking codebase or previous `IMPLEMENTED.md` in `plans/<plan>/` if any).
3. Execute the implementation steps defined in the task file.
4. Implement and run task-level tests as specified.
5. If the task is the last one in the plan (based on ordering numbers of all task files in the `plans/<plan>/` directory):
   - Run the full test suite after implementation.
   - Create `IMPLEMENTED.md` in the `plans/<plan>/` directory with:
     - Implementation summary
     - New/modified file list
     - Deviations and rationale
   - Update `README.md` when behavior/configuration changed.
6. Report the task execution results.

## Outputs/Artifacts

- Code/test/doc updates.
- `plans/<plan>/IMPLEMENTED.md` (only if the last task).

## Validation

- Task-level tests pass.
- If it's the last task, the full suite passes.
- Success criteria in `requirements.md` for this task are satisfied.

## Failure Handling

- On blocker, pause and report root cause, impact, and proposed resolution path.
- If dependencies are not met, notify the user.
