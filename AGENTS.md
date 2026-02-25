# Agent Instructions

This file controls the general behavior of the agent for this project.

## User Changes and Persistence

1.  **Respect Manual Changes**:
    - The agent MUST NOT overwrite or undo manual changes made by the user unless explicitly instructed to do so.
    - Treat user edits as the new "ground truth" or baseline for all subsequent actions.
    - If a user modifies a file, the agent should analyze and understand the intent of those changes before proposing further modifications.

2.  **Conflict Resolution**:
    - If manual changes introduce errors, inconsistencies, or conflicts with established project rules (e.g., compilation errors, formatting violations):
        - Do NOT automatically fix them.
        - **First, inform the user** of the specific issue.
        - **Ask the user** if they wish for the agent to resolve the problem.
    - Only proceed with corrective actions after receiving explicit confirmation.

## Code Quality and Documentation

When generating or modifying code, the agent must ensure that:
1.  **Documentation**: All functions, classes, and complex logic blocks are well-documented with comments explaining their purpose and behavior.
2.  **Clarity**: Variable and function names should be descriptive and follow standard naming conventions for the language being used.
3.  **Maintainability**: Code should be structured logically to facilitate future updates and debugging.
4.  **Project Documentation**:
    - The `README.md` file must be kept up-to-date with every significant change.
    - It should clearly state the project's purpose, installation steps, usage instructions, and deployment details.
    - When executing prompts that modify the system's behavior or configuration, the agent must review and update `README.md` to reflect these changes.

## Custom Commands

### `/exec-prompt <prompt_name>`
When the user issues the command `/exec-prompt <prompt_name>`, the agent must:
1.  Locate the file `prompt/<prompt_name>.md` in the project.
2.  Read the content of that file.
3.  Execute the instructions contained within that file as if they were sent directly in the chat.

### `/refine-prompt <prompt_name>`
When the user issues the command `/refine-prompt <prompt_name>`, the agent must:
1.  Locate the file `prompt/<prompt_name>.md` in the project.
2.  Read the content of that file.
3.  Analyze the prompt for clarity, consistency, and effectiveness.
4.  Rewrite the content of `prompt/<prompt_name>.md` with a refined version that is optimized for execution by an LLM agent.

### `/refine-prompts`
When the user issues the command `/refine-prompts`, the agent must:
1.  List all files in the `prompt` directory.
2.  Iterate through each file (excluding `README.md` or other non-prompt files).
3.  Perform the actions defined in `/refine-prompt` for each file.

### `/review-prompt <prompt_name>`
When the user issues the command `/review-prompt <prompt_name>`, the agent must:
1.  Locate the file `prompt/<prompt_name>.md` in the project.
2.  Read the content of that file.
3.  Analyze the prompt to identify ambiguities, missing information, or potential issues.
4.  Report these findings to the user as a list of open questions or suggestions for improvement, without modifying the file itself.

### `/execute-prompts`
When the user issues the command `/execute-prompts`, the agent must:
1.  List all files in the `prompt` directory.
2.  Determine the optimal execution order based on dependencies (e.g., source code must exist before tests can be run).
3.  Iterate through the ordered list of files (excluding `README.md`).
4.  Perform the actions defined in `/exec-prompt` for each file.
