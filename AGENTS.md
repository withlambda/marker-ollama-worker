# Agent Instructions

This file defines how the agent should operate in this project.

## Instruction Model

This document is intentionally split into two layers:

1. **Global Guardrails (always-on)**
   - Mandatory rules that apply to all tasks and all skills.
2. **Skill Registry (external skill files)**
   - Reusable, structured procedures triggered by specific user commands, stored under `.junie/skills/`.

**Global rule**: Every skill under `.junie/skills/` MUST comply with all Global Guardrails in this file.

## Global Guardrails (Always-On)

### 1) User Changes and Persistence

1. **Respect manual changes**:
   - The agent MUST NOT overwrite or undo manual user edits unless explicitly instructed.
   - Treat user edits as the current ground truth.
   - If a user modifies a file, first understand intent before proposing or applying additional changes.
   - **Never revert content unintentionally**: before editing a file (especially `README.md`), read current content and merge updates carefully.

2. **Conflict resolution for user-introduced issues**:
   - If user edits introduce errors or inconsistencies, do NOT auto-fix.
   - First report the specific issue to the user.
   - Ask whether the user wants the agent to resolve it.
   - Only proceed after explicit confirmation.

### 2) Code Quality and Documentation Standards

When generating or modifying code, the agent must ensure:

1. **Documentation quality**:
   - Functions, classes, and complex logic blocks are documented with clear purpose/behavior descriptions.
2. **Clarity**:
   - Variable and function names are descriptive and follow language conventions.
3. **Maintainability**:
   - Code remains logically structured for future updates/debugging.
4. **Project documentation synchronization**:
   - Keep `README.md` current for significant behavioral or configuration changes.
   - Ensure `README.md` includes project purpose, installation, usage/testing, and deployment-relevant details where applicable.
   - Before editing `README.md`, re-read its latest content to preserve manual user additions/removals.
5. **Functional Style**:
   - Follow an immutable functional style when possible, ensuring it does not increase code complexity.
6. **Error Handling**:
   - Avoid useless `except: pass` blocks.
   - Catch specific exceptions instead of a general `Exception` whenever they can be inferred.
   - All caught exceptions MUST be logged with the appropriate context.
7. **Import Management**:
   - Regularly check and remove unused imports.
8. **Formatting**:
   - Code formatting MUST strictly obey the rules defined in `.editorconfig`.

### 3) Dependencies in Source Code and Tests

1. **Required dependencies are mandatory**:
   - In source code, required dependencies MUST be imported directly.
   - Do NOT use `try/except` import patterns for required packages.
   - Missing required packages should fail fast with normal import errors.

2. **No dummy dependency shims for required packages in tests**:
   - Do NOT simulate required third-party modules using dummy classes, `sys.modules` injection, or equivalent shims.
   - Use real dependencies for local test execution.

3. **Local dependency setup before testing**:
   - Install dependencies from `requirements.txt` before running tests.
   - Preferred command: `python -m pip install -r requirements.txt`.

## Skill Registry (`.junie/skills`)

Reusable workflows are defined as skill folders under `.junie/skills/`, each with a required `SKILL.md` file.

Each skill file uses the same structure:
- **Trigger**
- **Inputs**
- **Preconditions**
- **Procedure**
- **Outputs/Artifacts**
- **Validation**
- **Failure Handling**

Registered skills:

1. `/plan <feature-name> <feature-description>` → `.junie/skills/plan/SKILL.md`
2. `/review-plan <feature-name>` → `.junie/skills/review-plan/SKILL.md`
3. `/execute-task <plan>/<task>` → `.junie/skills/execute-task/SKILL.md`
4. `/execute-plan <feature-name>` → `.junie/skills/execute-plan/SKILL.md`
5. `/review-code` → `.junie/skills/review-code/SKILL.md`
6. `/add-src-docs` → `.junie/skills/add-src-docs/SKILL.md`
7. `/update-src-docs` → `.junie/skills/update-src-docs/SKILL.md`
8. `/update-readme` → `.junie/skills/update-readme/SKILL.md`
9. `/review-all` → `.junie/skills/review-all/SKILL.md`

**Key principle for `/review-all`**: It is a review-and-implement workflow, not review-only. Identified improvements must be applied directly.

## License

[GNU General Public License v3.0](LICENSE)
