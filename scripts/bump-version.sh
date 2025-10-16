#!/bin/bash

# Script to bump version in VERSION file
# Usage:
#   ./bump-version.sh           # Bumps minor version (1.0.0 -> 1.1.0)
#   ./bump-version.sh 2.0.0     # Sets specific version

set -e

VERSION_FILE="VERSION"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: VERSION file not found"
    exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE")

if [ -z "$1" ]; then
    # Auto-increment minor version
    IFS='.' read -r major minor patch <<< "$CURRENT_VERSION"
    NEW_VERSION="$major.$((minor + 1)).$patch"
    echo "Auto-bumping version: $CURRENT_VERSION -> $NEW_VERSION"
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
