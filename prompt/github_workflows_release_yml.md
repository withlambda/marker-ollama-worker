# Context
This GitHub Actions workflow, located at `.github/workflows/release.yml`, automates the project's release process. It provides a manual trigger (`workflow_dispatch`) to bump the version, generate a changelog, and tag the repository using the `release.sh` script.

# Interface

## Inputs
- `version` (string, required): The target version for the release (e.g., `1.10.3`).
- `dry_run` (boolean, default: `false`): If true, simulates the release without committing or pushing changes.

# Logic
1.  **Checkout**: Uses `actions/checkout@v4` with full history and a `GITHUB_TOKEN` for write permissions.
2.  **Git Config**: Configures the `github-actions[bot]` user and email for commits.
3.  **Execution**: Calls `./release.sh` with the provided version and optional `--dry-run` flag.
4.  **Chained Workflow**: If it's not a dry run, it triggers the `docker-publish.yml` workflow to build and push the new container image to GHCR.

# Goal
The prompt file captures the CI/CD orchestration for releases, enabling the exact regeneration of the GitHub Actions workflow and its integration with the local release script.
