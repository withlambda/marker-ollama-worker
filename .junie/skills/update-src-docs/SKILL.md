---
name: update-src-docs
description: Synchronizes outdated inline source documentation with current implementation behavior and signatures.
---

# Update Source Docs

Use this skill when the user requests `/update-src-docs`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- All relevant source files and existing inline documentation.

## Preconditions

- Determine where implementation and documentation diverge.

## Procedure

1. Compare current implementation with existing docs.
2. Update outdated docstrings/comments to reflect real behavior and signatures.

## Outputs/Artifacts

- Source files with synchronized documentation.

## Validation

- No stale or contradictory inline documentation remains in touched areas.

## Failure Handling

- If undocumented behavior appears unintended, flag it and ask whether code or docs should be authoritative.
