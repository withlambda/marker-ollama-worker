---
name: plan-feature
description: Creates structured feature plans with requirements, design, and executable tasks under plans/<feature-name>/.
---

# Plan Feature

Use this skill when the user requests `/plan <feature-name> <feature-description>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `feature-name`
- `feature-description`

## Preconditions

- Confirm target path `plans/<feature-name>/` is available.
- Analyze relevant code paths for feasibility and integration impact.

## Procedure

1. Create `plans/<feature-name>/`.
2. Create `requirements.md` with:
   - Functional requirements
   - Non-functional requirements
   - Edge cases/pitfalls
   - Definition of Done (measurable success criteria)
3. Create `design.md` with:
   - High-level architecture/data flow
   - List of new/modified files
   - API/schema/dependency changes
4. Create `tasks.md` with:
   - Structured numbered tasks
   - Explicit test requirements per task

## Outputs/Artifacts

- `plans/<feature-name>/requirements.md`
- `plans/<feature-name>/design.md`
- `plans/<feature-name>/tasks.md`

## Validation

- Requirements are testable and unambiguous.
- Each task traces to at least one requirement.
- Design references concrete components/files.

## Failure Handling

- If requirements are unclear or conflicting, ask user clarifying questions before finalizing artifacts.
