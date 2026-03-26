---
name: add-src-docs
description: Adds missing inline source documentation for modules, classes, and functions while keeping docs accurate and concise.
---

# Add Source Docs

Use this skill when the user requests `/add-src-docs`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- All relevant source files.

## Preconditions

- Identify modules/functions/classes with missing documentation.

## Procedure

1. Scan source files for undocumented modules/classes/functions.
2. Add docstrings/comments describing purpose, parameters, return values, and important behavior.

## Outputs/Artifacts

- Source files updated with new documentation.

## Validation

- Documentation is accurate, concise, and consistent with code behavior.

## Failure Handling

- If behavior is unclear, inspect call sites/tests before documenting; ask user when ambiguity remains.
