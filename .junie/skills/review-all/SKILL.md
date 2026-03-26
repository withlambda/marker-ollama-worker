---
name: review-all
description: Executes full-project review-and-implement workflow across code, tests, docs, and configs with direct remediation.
---

# Review All

Use this skill when the user requests `/review-all`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- Entire project (source, tests, docs, configs).

## Preconditions

- Confirm full-scope audit is desired.

## Procedure

1. Perform comprehensive review for bugs, security issues, performance, architecture, maintainability, and best practices.
2. Directly implement all justified improvements.
3. Update all related docs:
   - Sync inline docs (`/update-src-docs` intent)
   - Add missing inline docs (`/add-src-docs` intent)
   - Update tests for behavior/signature changes
   - Update config documentation when needed
4. Update `README.md` (`/update-readme` intent).
5. Verify internal consistency and backward compatibility unless explicit breakage is intended.

## Outputs/Artifacts

- Code improvements, documentation updates, and synchronized tests.

## Validation

- No contradictions across code/tests/docs.
- Implemented changes are coherent and operationally sound.

## Failure Handling

- If full implementation is blocked, provide a precise blocked-items list with reasons and required decisions.

## Key Principle

- This is a review-and-implement workflow, not review-only. Identified improvements must be applied directly.
