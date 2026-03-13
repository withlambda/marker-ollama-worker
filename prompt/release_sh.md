# `release.sh`

## Context
This script automates the release process for the project. It handles version bumping, changelog updates, and git tagging/pushing. It supports both local and CI (GitHub Actions) execution.

## Logic
1.  **Arguments**:
    *   `[-d|--dry-run]`: Optional flag to simulate the release without committing or pushing changes.
    *   `<version>`: The target version (e.g., `1.10.3` or `v1.10.3`).
2.  **Normalization & Validation**:
    *   Strips the leading `v` from the version if present.
    *   Validates the version format against `^[0-9]+\.[0-9]+\.[0-9]+$`.
3.  **Checks**:
    *   Checks for uncommitted changes using `git diff-index`. Exits if present.
    *   Checks if the tag `v<version>` already exists. Exits if so.
    *   Warns if not on `main` or `master` branch (non-interactive in CI).
4.  **Update Files**:
    *   Writes `<version>` to `VERSION` file.
    *   Updates `marker-pdf` version in `requirements.txt` using `sed`. Handles MacOS vs. Linux syntax differences.
5.  **Changelog**:
    *   Generates a new entry in `CHANGELOG.md` with current date.
    *   Gets commits since the last tag (or all if no tags exist).
    *   Formats as `- <commit_message>`.
    *   Prepends new entry to existing `CHANGELOG.md` (skipping header) or creates new file.
6.  **Git Operations**:
    *   Adds `VERSION`, `requirements.txt`, and `CHANGELOG.md` to git.
    *   Commits with message "Bump version to <version>".
    *   Creates annotated tag `v<version>`.
    *   Pushes changes and tag to remote repository.
7.  **Dry-Run Support**:
    *   If dry-run is enabled, all file modifications and git operations are logged as `[DRY RUN]` and not executed.

## Environment Variables
*   `GITHUB_ACTIONS`: Used to detect CI environment for non-interactive behavior.
