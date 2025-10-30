#!/bin/bash

# Script to bump version in VERSION file
# Usage:
#   ./bump-version.sh           # Bumps patch version (1.0.0 -> 1.0.1)
#   ./bump-version.sh patch     # Bumps patch version (1.0.0 -> 1.0.1)
#   ./bump-version.sh minor     # Bumps minor version (1.0.0 -> 1.1.0)
#   ./bump-version.sh major     # Bumps major version (1.0.0 -> 2.0.0)
#   ./bump-version.sh 2.0.0     # Sets specific version

set -e

VERSION_FILE="VERSION"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: VERSION file not found"
    exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE")
IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"

if [ -z "$1" ] || [ "$1" == "patch" ]; then
    # Auto-increment patch version
    NEW_VERSION="$major.$minor.$((patch + 1))"
    echo "Bumping PATCH version: $CURRENT_VERSION -> $NEW_VERSION"
elif [ "$1" == "minor" ]; then
    # Increment minor version, reset patch
    NEW_VERSION="$major.$((minor + 1)).0"
    echo "Bumping MINOR version: $CURRENT_VERSION -> $NEW_VERSION"
elif [ "$1" == "major" ]; then
    # Increment major version, reset minor and patch
    NEW_VERSION="$((major + 1)).0.0"
    echo "Bumping MAJOR version: $CURRENT_VERSION -> $NEW_VERSION"
else
    # Set specific version
    NEW_VERSION="$1"
    echo "Setting version: $CURRENT_VERSION -> $NEW_VERSION"

    # Validate version format
    if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Error: Version must be in format X.Y.Z"
        exit 1
    fi
fi

echo "$NEW_VERSION" > "$VERSION_FILE"
echo "Version updated to $NEW_VERSION"
