---
name: review-plan-implementation
description: Checks whether the implementation of the plan after execution of its tasks aligns to the plan. Furthermore, the changes are analyzed and bugs are spotted and fixed. The test execution is checked and broken tests are fixed.
---

# Review Plan Implementation

Use this skill when the user requests `/review-plan-implementation <plan>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `plan`: the name of the plan (e.g., `migrate-to-minerU`).

## Preconditions

- Plan directory (e.g., `plans/<plan>/`) exists and contains task files.
- `plans/<plan>/IMPLEMENTED.md` exists (optional, but helpful to understand the state of implementation).
- If verification requires Docker, Docker is available locally and the review can create plan-scoped test artifacts inside the repository.

## Procedure

1. **Read the plan definition**:
   - Explore `plans/<plan>/` to understand the intended changes and requirements.
   - Read `plans/<plan>/design.md`, `plans/<plan>/requirements.md`, and all task files (e.g., `01-*.md`, `02-*.md`, etc.).
2. **Assess alignment with the plan**:
   - Check if the current codebase implementation matches the steps and requirements defined in the plan.
   - Identify any missing parts or deviations not documented in `IMPLEMENTED.md`.
3. **Analyze changes and fix bugs**:
   - Perform a focused code review of all files modified as part of the plan.
   - Identify bugs, security issues, performance regressions, or quality concerns introduced during implementation.
   - Implement fixes directly for any identified issues.
4. **Verify test execution**:
   - Identify all tests and checks related to the plan (as specified in the task files or `IMPLEMENTED.md`) before starting any Docker-based verification.
   - If Docker is needed for verification, create a dedicated test Dockerfile that installs all required dependencies and packages during image build so the resulting test image is built once and then reused for the entire review.
   - For Docker-based verification, write a single execution script that runs all required in-container tests and checks in the planned order instead of invoking one `docker run` per command.
   - Mount the execution script and a results output file into the container so the script can be updated easily and the aggregated results can be inspected after the container stops.
   - Reuse the same running container or single container execution for the grouped checks whenever the same environment is sufficient; do not repeatedly start fresh containers just to run individual commands against the same image.
   - Identify and execute all tests related to the plan.
   - If tests fail, diagnose the root cause and fix the broken tests or the underlying code.
   - Ensure the full test suite passes if the plan is considered fully implemented.
5. **Update documentation**:
   - Ensure `plans/<plan>/IMPLEMENTED.md` is accurate and reflects any additional fixes or changes made during this review.
   - Update `README.md` if the review resulted in behavioral or configuration changes.

## Outputs/Artifacts

- Code/test/doc updates.
- Updated `plans/<plan>/IMPLEMENTED.md`.
- When Docker-based verification is used: a plan-scoped test Dockerfile, the mounted execution script, and the results output file.

## Validation

- Full suite of tests relevant to the plan passes.
- Code changes are verified to be aligned with the plan's requirements.
- No new bugs or regressions are introduced.
- When Docker-based verification is used, dependency installation happens during image build rather than repeated runtime installs, and grouped checks reuse that built image/container workflow.

## Failure Handling

- If the implementation is fundamentally flawed and requires a redesign, pause and present options to the user.
- If specific tests cannot be fixed without external dependencies or decisions, report them clearly to the user.
