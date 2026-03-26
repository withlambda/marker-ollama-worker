---
name: review-plan
description: Reviews plan artifacts under plans/<feature-name>/ for ambiguity, consistency, feasibility, and actionable improvements.
---

# Review Plan

Use this skill when the user requests `/review-plan <feature-name>`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- `feature-name`

## Preconditions

- `plans/<feature-name>/` exists and contains planning documents.

## Procedure

1. Read all planning files in `plans/<feature-name>/`.
2. Evaluate for ambiguity, inconsistency, and standards alignment.
3. Cross-check feasibility against current codebase constraints.
4. Provide detailed critique: gaps, risks, and improvements.
5. If user requests, update plan files to incorporate feedback.

## Outputs/Artifacts

- Review report (and updated plan files if refinement is requested).

## Validation

- Findings are actionable and prioritized.
- Proposed changes preserve requirement-task-design consistency.

## Failure Handling

- If key planning files are missing, report exact missing files and ask whether to generate them first.
