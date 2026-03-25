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
    - The `README.md` file must be kept up to date with every significant change.
    - It should clearly state the project's purpose, installation steps, usage instructions, and deployment details.
    - When implementing changes that modify the system's behavior or configuration, the agent must review and update `README.md` to reflect these changes.
    - **Verification**: Before writing to `README.md`, re-read the current file content to ensure no manual edits (e.g., specific configuration values, notes, or section removals) are lost in the update.

## Dependencies in Source Code and Tests

1. **Required dependencies are mandatory**:
   - In source code files, required dependencies MUST be imported directly.
   - Do NOT use `try/except` import patterns for required packages.
   - If a required package is not installed, execution should fail fast with the normal import error.

2. **No dummy dependency classes/modules in tests for required packages**:
   - Tests MUST NOT simulate required third-party packages via dummy classes, `sys.modules` injection, or equivalent module-level shims.
   - For local testing, install the real dependencies instead.

3. **Local testing dependency setup**:
   - Before running tests locally, install project dependencies from `requirements.txt`.
   - Preferred command: `python -m pip install -r requirements.txt`.

## Custom Commands

### `/plan <feature-name> <feature-description>`
When the user issues the command `/plan <feature-name> <feature-description>`, the agent must:
1.  **Initialization**: Create a directory `plans/<feature-name>/`.
2.  **Analysis**: Analyze the current codebase to identify the files and logic relevant to the `<feature-description>`.
3.  **Requirements**: Create `plans/<feature-name>/requirements.md` that details:
    -   All functional and non-functional requirements.
    -   Edge cases and potential pitfalls.
    -   Definition of Done (success criteria).
4.  **Design**: Create `plans/<feature-name>/design.md` that describes:
    -   High-level architecture and data flow.
    -   List of modified and new files.
    -   Required changes to APIs, schemas, or dependencies.
5.  **Tasks**: Create `plans/<feature-name>/tasks.md` with a structured, numbered list of implementation tasks, including specific testing requirements for each.

### `/review-plan <feature-name>`
When the user issues the command `/review-plan <feature-name>`, the agent must:
1.  **Validation**: Read all files in the `plans/<feature-name>/` directory.
2.  **Evaluation**: Analyze the plan for ambiguities, inconsistencies, and alignment with project standards.
3.  **Feasibility**: Cross-reference the plan with the current codebase to ensure technical feasibility.
4.  **Critique**: Provide a detailed list of suggestions, missing details, or potential improvements.
5.  **Refinement**: If the user provides feedback or instructions, update the planning files accordingly.

### `/execute-plan <feature-name>`
When the user issues the command `/execute-plan <feature-name>`, the agent must:
1.  **Verification**: Check if the feature is already implemented by looking for `plans/<feature-name>/IMPLEMENTED.md`. If it exists, inform the user and abort.
2.  **Execution**: Follow the tasks in `plans/<feature-name>/tasks.md` sequentially.
3.  **Testing**: Implement and run tests for each task as specified in the plan.
4.  **Final Validation**: Once all tasks are complete, run the full test suite to ensure everything works correctly and meets the success criteria in `requirements.md`.
5.  **Completion**: Create a file `plans/<feature-name>/IMPLEMENTED.md` that includes:
    -   A summary of the final implementation.
    -   A list of all new and modified files.
    -   Any deviations from the original plan and why they occurred.
6.  **Cleanup**: Update `README.md` to reflect the new feature if applicable.

### `/review-code`
When the user issues the command `/review-code`, the agent must:
1.  Analyze all source code files in the project (e.g., `.py`, `.sh`, `Dockerfile`, `.yml`, `.env`).
2.  Identify potential bugs, security vulnerabilities, performance issues, and code quality improvements.
3.  Apply fixes and improvements directly to the files, ensuring that the changes are well-documented and follow the project's coding standards.
4.  Update `README.md` if any changes affect the usage or configuration of the project.


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

### `/review-all`
When the user issues the command `/review-all`, the agent must:
1.  Execute a comprehensive project audit, code review, and implementation cycle.
2.  **Perform comprehensive code review**:
    -   Analyze all source code files in the project (Python, shell scripts, Dockerfiles, YAML, etc.)
    -   Identify bugs, security vulnerabilities, performance issues, code quality problems, and potential improvements
    -   Review architecture, design patterns, error handling, resource management, and best practices
    -   Check for code smells, anti-patterns, and maintainability issues
3.  **Directly implement all suggested improvements**:
    -   **IMPORTANT**: The agent MUST NOT just list suggestions - it must implement all identified fixes and improvements
    -   Apply bug fixes, security patches, and performance optimizations
    -   Refactor code to improve quality, readability, and maintainability
    -   Update patterns and practices to follow modern standards
    -   Fix any identified issues with error handling, logging, or resource management
4.  **Update all related documentation**:
    -   `/update-src-docs`: Synchronize inline documentation (docstrings, comments) with updated code logic
    -   `/add-src-docs`: Ensure all new or modified functions, classes, and modules have complete documentation
    -   Update test files to match any changes in function signatures or behavior
    -   Update configuration documentation if settings changed
5.  **Update project documentation**:
    -   `/update-readme`: Ensure README.md reflects all implemented changes, new features, or configuration options
    -   Update any relevant sections (usage, configuration, environment variables, troubleshooting)
6.  **Verification**:
    -   Ensure all changes are cohesive and internally consistent
    -   Verify that no documentation contradicts the updated source code
    -   Confirm that all fixes maintain backward compatibility unless explicitly intended otherwise

**Key principle**: This command performs a complete review-and-implement cycle, not just a review-and-report cycle. All identified improvements must be implemented directly.

## License

[GNU General Public License v3.0](LICENSE)
