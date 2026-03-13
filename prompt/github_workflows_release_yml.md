# `.github/workflows/release.yml`

## Context
This GitHub Workflow automates the release process using the `release.sh` script. It allows triggering a new release directly from the GitHub Actions UI.

## Logic
1.  **Trigger**:
    *   `workflow_dispatch`: Manually triggered with input parameters `version` and `dry_run`.
2.  **Jobs**:
    *   **release**:
        *   Requires `contents: write` permissions.
        *   Checks out the repository with full history.
        *   Configures git for the GitHub Actions bot.
        *   Executes `./release.sh` with the provided version and `dry_run` flag if applicable.
    *   **publish**:
        *   Depends on the `release` job.
        *   Runs only if `dry_run` is false.
        *   Calls the Docker publish workflow (`.github/workflows/docker-publish.yml`).
3.  **Security and Integration**:
    *   Uses `GITHUB_TOKEN` for repository operations.
    *   The explicit call to the Docker publish workflow ensures the image is built even though `GITHUB_TOKEN` pushes don't trigger subsequent workflows by default.

## Inputs
*   `version`: The target version for the new release (e.g., `1.10.3`).
*   `dry_run`: Boolean flag to simulate the release process without making changes.
