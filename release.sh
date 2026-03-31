#!/bin/bash
# release.sh - Automation script for the release process.
#
# This script automates versioning, changelog generation, and pushing
# changes and tags to the remote repository.
#
# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Script to automate the release process for the project.
# It performs the following steps:
# 1. Checks for uncommitted changes.
# 2. Checks if the version tag already exists.
# 3. Updates the version in VERSION and requirements.txt.
# 4. Generates a changelog entry from git commits.
# 5. Commits the changes and creates a new git tag.
# 6. Pushes the changes and the tag to the remote repository.
#
# Usage: ./release.sh [-d|--dry-run] <version>
# Example: ./release.sh 3.0.1

# Ensure the script stops on errors
set -e

DRY_RUN=false
VERSION_INPUT=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -d|--dry-run) DRY_RUN=true ;;
        -h|--help) echo "Usage: ./release.sh [-d|--dry-run] <version>"; exit 0 ;;
        *)
            if [ -z "$VERSION_INPUT" ]; then
                VERSION_INPUT=$1
            else
                echo "Error: Multiple versions provided or unknown argument: $1"
                exit 1
            fi
            ;;
    esac
    shift
done

# Check if a version argument is provided
if [ -z "$VERSION_INPUT" ]; then
  echo "Usage: ./release.sh [-d|--dry-run] <version>"
  exit 1
fi

# Normalize version: strip 'v' prefix if present
NEW_VERSION=${VERSION_INPUT#v}

# Validate version format (simple SemVer: X.Y.Z)
if [[ ! $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in the format X.Y.Z (e.g., 3.0.1). Provided: $VERSION_INPUT"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo "Dry run enabled. No changes will be committed or pushed."
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Error: You have uncommitted changes. Please commit or stash them before releasing."
    exit 1
fi

# Check if tag already exists
if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
    echo "Error: Tag v$NEW_VERSION already exists."
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Branch check: Warning if not on main/master
if [[ "$CURRENT_BRANCH" != "main" && "$CURRENT_BRANCH" != "master" ]]; then
    echo "Warning: You are on branch '$CURRENT_BRANCH'. Standard releases usually happen from 'main' or 'master'."
    if [[ -z "$GITHUB_ACTIONS" ]]; then
        read -p "Continue anyway? [y/N] " response
        if [[ ! "$response" =~ ^[yY]$ ]]; then
            echo "Release aborted."
            exit 1
        fi
    fi
fi

# Update VERSION file
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Update VERSION to $NEW_VERSION"
else
    echo "$NEW_VERSION" > VERSION
fi

# Update requirements.txt
# Sync the MinerU pipeline dependency used by the project runtime.
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Update requirements.txt to mineru[pipeline]==$NEW_VERSION"
else
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/mineru\[pipeline\]==.*/mineru\[pipeline\]==$NEW_VERSION/" requirements.txt
    else
        sed -i "s/mineru\[pipeline\]==.*/mineru\[pipeline\]==$NEW_VERSION/" requirements.txt
    fi
fi

# Generate CHANGELOG entry
CHANGELOG_FILE="CHANGELOG.md"
TEMP_ENTRY="CHANGELOG_ENTRY.tmp"
TEMP_FULL="CHANGELOG_FULL.tmp"

# Create the new entry
{
    echo "## $NEW_VERSION - $(date +%Y-%m-%d)"
    echo ""
} > "$TEMP_ENTRY"

# Get commits since the last tag, or all commits if no tags exist
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -z "$LAST_TAG" ]; then
    git log --pretty=format:"- %s" >> "$TEMP_ENTRY"
else
    # Correct range syntax for git log
    git log --pretty=format:"- %s" "${LAST_TAG}..HEAD" >> "$TEMP_ENTRY"
fi
echo "" >> "$TEMP_ENTRY"
echo "" >> "$TEMP_ENTRY"

# Combine with existing changelog
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Generate CHANGELOG.md entry for $NEW_VERSION"
    rm -f "$TEMP_ENTRY"
else
    if [ -f "$CHANGELOG_FILE" ]; then
        # Check if the file starts with "# Changelog"
        if grep -q "^# Changelog" "$CHANGELOG_FILE"; then
            echo "# Changelog" > "$TEMP_FULL"
            echo "" >> "$TEMP_FULL"
            cat "$TEMP_ENTRY" >> "$TEMP_FULL"
            # Append existing content skipping the first line (header)
            tail -n +2 "$CHANGELOG_FILE" >> "$TEMP_FULL"
        else
            # No header found, just prepend
            cat "$TEMP_ENTRY" "$CHANGELOG_FILE" > "$TEMP_FULL"
        fi
    else
        # New file
        echo "# Changelog" > "$TEMP_FULL"
        echo "" >> "$TEMP_FULL"
        cat "$TEMP_ENTRY" >> "$TEMP_FULL"
    fi

    mv "$TEMP_FULL" "$CHANGELOG_FILE"
    rm -f "$TEMP_ENTRY"
fi

# Commit changes
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] git add VERSION requirements.txt CHANGELOG.md"
    echo "[DRY RUN] git commit -m \"Bump version to $NEW_VERSION\""
else
    git add VERSION requirements.txt CHANGELOG.md
    git commit -m "Bump version to $NEW_VERSION"
fi

# Create a tag
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] git tag -a \"v$NEW_VERSION\" -m \"Release v$NEW_VERSION\""
else
    git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
fi

# Push changes and tags
if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] git push origin \"$CURRENT_BRANCH\""
    echo "[DRY RUN] git push origin \"v$NEW_VERSION\""
    echo "Dry run complete. No changes were made."
else
    echo "Pushing changes to $CURRENT_BRANCH..."
    git push origin "$CURRENT_BRANCH"
    git push origin "v$NEW_VERSION"
    echo "Release v$NEW_VERSION prepared and pushed."
fi
