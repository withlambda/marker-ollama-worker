# Agent Instructions

This file controls the general behavior of the agent for this project.

## User Changes and Persistence

1.  **Respect Manual Changes**:
    - The agent MUST NOT overwrite or undo manual changes made by the user unless explicitly instructed to do so.
    - Treat user edits as the new "ground truth" or baseline for all subsequent actions.
    - If a user modifies a file, the agent should analyze and understand the intent of those changes before proposing further modifications.
    - **Never revert content**: Before modifying a file (especially documentation like `README.md`), the agent must check the existing content to ensure it does not accidentally delete or revert recent user additions. When updating a file, merge new information with existing content rather than replacing sections wholesale.

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
    - **Verification**: Before writing to `README.md`, re-read the current file content to ensure no manual edits (e.g., specific configuration values, notes, or section removals) are lost in the update.

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

### `/review-code`
When the user issues the command `/review-code`, the agent must:
1.  Analyze all source code files in the project (e.g., `.py`, `.sh`, `Dockerfile`, `.yml`, `.env`).
2.  Identify potential bugs, security vulnerabilities, performance issues, and code quality improvements.
3.  Apply fixes and improvements directly to the files, ensuring that the changes are well-documented and follow the project's coding standards.
4.  Update `README.md` if any changes affect the usage or configuration of the project.

### `/sync-prompts`
When the user issues the command `/sync-prompts`, the agent must:
1.  **Inventory**: Identify all source code files (e.g., `.py`, `.sh`, `Dockerfile`, `.yml`, `.env`) in the project, excluding `.git`, `__pycache__`, and `build` directories.
2.  **Cleanup**: Identify any files in the `prompt/` directory that no longer have a corresponding source file and delete them.
3.  **Generate/Update**: For each source file, create or update its corresponding prompt file (naming convention: `prompt/<path_to_file_with_underscores>.md`).
4.  **Content Requirements**:
    -   **Do not** simply copy-paste the source code as the primary instruction.
    -   **Context**: Describe the file's purpose and location.
    -   **Interface**: Define classes, functions, inputs, outputs, and environment variables.
    -   **Logic**: Describe the internal logic, algorithms, and error handling in detailed Natural Language or Pseudocode.
    -   **Exceptions**: You MAY include code blocks for critical constants, complex regex, or configuration file content (like `Dockerfile`) if exact reproduction is impossible via description alone.
5.  **Goal**: The content of the prompt file must be sufficient for an LLM to regenerate the source file exactly as it behaves now.

### `/add-src-docs`
When the user issues the command `/add-src-docs`, the agent must:
1.  Review all source code files in the project.
2.  Identify functions, classes, and modules that lack documentation (e.g., docstrings, comments).
3.  Add appropriate documentation to these elements, explaining their purpose, parameters, and return values.

### `/update-src-docs`
When the user issues the command `/update-src-docs`, the agent must:
1.  Review all source code files in the project.
2.  Compare the existing documentation with the actual code implementation.
3.  Update the documentation where it no longer accurately describes the code (e.g., after changes to logic, parameters, or return values).

### `/update-readme`
When the user issues the command `/update-readme`, the agent must:
1.  Review all source code files to understand the current functionality of the project.
2.  Read the current content of `README.md`.
3.  Determine if the `README.md` content accurately reflects the source code and project status.
4.  Update `README.md` to ensure it is in sync with the source code.
5.  Ensure the `README.md` describes:
    - What the repository does.
    - How to test the code.
    - Any other important information for using the repository.

## License

[GNU General Public License v3.0](LICENSE)
