# Context
This file, `AGENTS.md`, contains the comprehensive governing instructions for AI agents working on the `marker-vllm-worker` project. it defines custom commands, code quality standards, and protocols for respecting user changes and maintaining documentation.

# Interface

## Custom Commands
- `/exec-prompt <name>`: Loads and executes a specific instruction file from `prompt/`.
- `/refine-prompt <name>` / `/refine-prompts`: Analyzes and optimizes prompt files for LLM execution.
- `/review-prompt <name>`: Identifies ambiguities in a prompt without modifying it.
- `/execute-prompts`: Runs all prompts in the optimal dependency order.
- `/review-code`: Comprehensive bug-hunting and quality improvement sweep across all source files.
- `/sync-prompts`: Synchronizes the `prompt/` directory with the current source code state (this process).
- `/add-src-docs` / `/update-src-docs`: Manages inline code documentation (docstrings).
- `/update-readme`: Synchronizes `README.md` with project functionality.
- `/review-all`: A complete review-and-implement cycle covering code, tests, and documentation.

## Guidelines
- **User Preference**: Agents must never revert manual user changes.
- **Documentation**: All new logic must be documented. `README.md` must be updated for significant changes.
- **Code Standards**: Descriptive naming, logical structure, and maintainability are required.

# Logic
The file serves as a system prompt extension that defines the "Skillset" of a Junie agent within this repository. It acts as the operational manual for any automated task or refactoring cycle.

# Goal
The prompt file captures the behavioral and functional requirements for AI agents, enabling the regeneration of the project's governance framework.
