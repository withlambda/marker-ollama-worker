---
name: update-readme
description: Synchronizes README.md with current implementation, setup, usage, testing, and operational details.
---

# Update README

Use this skill when the user requests `/update-readme`.

## Guardrail Binding

- Follow all Global Guardrails in `AGENTS.md`.

## Inputs

- Current source code and current `README.md`.

## Preconditions

- Re-read existing `README.md` content before edits to preserve manual changes.

## Procedure

1. Review source code to understand current functionality.
2. Compare implementation to `README.md`.
3. Update `README.md` to match project behavior/status.
4. Ensure README covers:
   - Repository purpose
   - How to install/test/use
   - Other critical operational information

## Outputs/Artifacts

- Updated `README.md`.

## Validation

- README is accurate, complete for key workflows, and free of contradictions.

## Failure Handling

- If intended behavior is uncertain, ask user before documenting assumptions.
