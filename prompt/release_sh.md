# `release.sh`

## Context
This script automates the release process for the project. It handles version bumping, changelog updates, and git tagging/pushing.

## Logic
1.  **Arguments**:
    *   Takes one argument: `<version>`.
    *   Exits if argument is missing.
2.  **Checks**:
    *   Checks for uncommitted changes using `git diff-index`. Exits if present.
    *   Checks if the tag `v<version>` already exists. Exits if so.
3.  **Update Files**:
    *   Writes `<version>` to `VERSION` file.
    *   Updates `marker-pdf` version in `requirements.txt` using `sed`. Handles MacOS vs. Linux syntax differences.
4.  **Changelog**:
    *   Generates a new entry in `CHANGELOG.md`.
    *   Gets commits since the last tag (or all if no tags exist).
    *   Formats as `- <commit_message>`.
    *   Prepends new entry to existing `CHANGELOG.md` or creates new file.
5.  **Git Operations**:
    *   Adds `VERSION`, `requirements.txt`, and `CHANGELOG.md` to git.
    *   Commits with message "Bump version to <version>".
    *   Creates annotated tag `v<version>`.
    *   Pushes changes and tag to remote repository.

## Environment Variables
*   None required.
