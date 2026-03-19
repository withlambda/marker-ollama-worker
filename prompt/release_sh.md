# Context
This file, `release.sh`, is a Bash script designed to automate the project's release process. It handles version bumping, updating dependencies (specifically `marker-pdf` in `requirements.txt`), generating a changelog from git commits, tagging the repository, and pushing changes to the remote.

# Interface

## Arguments
- `[version]` (Required): The new version number in `X.Y.Z` format.
- `-d | --dry-run`: Performs all checks and shows what would happen, but does not commit or push any changes.
- `-h | --help`: Displays usage information.

## Input Files
- `VERSION`: Stores the current project version.
- `requirements.txt`: Contains the pinned version of `marker-pdf`.
- `CHANGELOG.md`: The history of changes.

# Logic

### 1. Validation and Setup
- Strips any 'v' prefix from the input version to normalize it.
- Validates the version matches `^[0-9]+\.[0-9]+\.[0-9]+$`.
- Checks if the current working directory has uncommitted changes using `git diff-index`.
- Verifies that the proposed version tag (`vX.Y.Z`) does not already exist.
- Warns the user if they are not on the `main` or `master` branch.

### 2. Version and Dependency Update
- Overwrites the `VERSION` file with the new version string.
- Uses `sed` to update the `marker-pdf==X.Y.Z` line in `requirements.txt`. It handles OS-specific differences between macOS (`sed -i ''`) and Linux.

### 3. Changelog Generation
- Identifies the last tag using `git describe --tags --abbrev=0`.
- Retrieves all commit messages since that tag (or all commits if no tag exists) using `git log --pretty=format:"- %s"`.
- Creates a new entry with the version and current date.
- Prepends this entry to `CHANGELOG.md`. If the file starts with a "# Changelog" header, it preserves the header and inserts the new entry immediately below it.

### 4. Git Operations
- Stages `VERSION`, `requirements.txt`, and `CHANGELOG.md`.
- Commits with the message "Bump version to X.Y.Z".
- Creates an annotated tag: `git tag -a "vX.Y.Z" -m "Release vX.Y.Z"`.
- Pushes the current branch and the new tag to `origin`.

# Goal
The prompt file provides the full automation logic and string manipulation rules (like `sed` patterns and `git` commands) required to regenerate `release.sh` exactly.
