#!/bin/bash
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

# Ensure the script stops on errors
set -e

# Check if a version argument is provided
if [ -z "$1" ]; then
  echo "Usage: ./release.sh <version>"
  exit 1
fi

NEW_VERSION=$1

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

# Update VERSION file
echo "$NEW_VERSION" > VERSION

# Update requirements.txt
# Assuming marker-pdf is the library we want to sync with
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/marker-pdf==.*/marker-pdf==$NEW_VERSION/" requirements.txt
else
  sed -i "s/marker-pdf==.*/marker-pdf==$NEW_VERSION/" requirements.txt
fi

# Generate CHANGELOG entry
CHANGELOG_FILE="CHANGELOG.md"
TEMP_ENTRY="CHANGELOG_ENTRY.tmp"
TEMP_FULL="CHANGELOG_FULL.tmp"

# Create the new entry
echo "## $NEW_VERSION - $(date +%Y-%m-%d)" > "$TEMP_ENTRY"
echo "" >> "$TEMP_ENTRY"

# Get commits since the last tag, or all commits if no tags exist
LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -z "$LAST_TAG" ]; then
    git log --pretty=format:"- %s" >> "$TEMP_ENTRY"
else
    git log --pretty=format:"- %s" "$LAST_TAG"..HEAD >> "$TEMP_ENTRY"
fi
echo "" >> "$TEMP_ENTRY"
echo "" >> "$TEMP_ENTRY"

# Combine with existing changelog
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

# Commit changes
git add VERSION requirements.txt CHANGELOG.md
git commit -m "Bump version to $NEW_VERSION"

# Create a tag
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

# Push changes and tags
echo "Pushing changes to $CURRENT_BRANCH..."
git push origin "$CURRENT_BRANCH"
git push origin "v$NEW_VERSION"

echo "Release v$NEW_VERSION prepared and pushed."
