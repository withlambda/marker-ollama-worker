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
