#!/bin/bash
# ============================================================================
# publish.sh — Create a GitHub repo and push the dry-counties-map project
#
# Prerequisites:
#   brew install gh        # macOS
#   # or: https://cli.github.com/  for other platforms
#   gh auth login          # authenticate once
#
# Usage:
#   cd dry-counties-map
#   chmod +x publish.sh
#   ./publish.sh
# ============================================================================

set -euo pipefail

REPO_NAME="dry-counties-map"
DESCRIPTION="Interactive map of US counties that still prohibit alcohol sales (2026). Python/Plotly replacement for the 2019 SAS map."

echo "=== Publishing ${REPO_NAME} to GitHub ==="

# Check for gh CLI
if ! command -v gh &>/dev/null; then
    echo "ERROR: GitHub CLI (gh) not found."
    echo "Install it: brew install gh  (macOS) or see https://cli.github.com/"
    exit 1
fi

# Check auth
if ! gh auth status &>/dev/null; then
    echo "ERROR: Not authenticated. Run: gh auth login"
    exit 1
fi

# Initialize git if needed
if [ ! -d .git ]; then
    echo "Initializing git repo..."
    git init
    git add .
    git commit -m "Initial commit: US Dry Counties Map (2026)

Modern open-source replacement for the SAS-based dry counties map.
Uses Python, Plotly, and GeoPandas with data compiled from state ABC
boards as of February 2026.

Key corrections vs the 2019 map:
- Hot Spring County, AR: now WET (voted Nov 2022)
- Kansas: zero dry counties remain
- Texas: down to 3 dry counties
- Virginia: zero dry counties since 2020

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
fi

# Create the GitHub repo
echo "Creating GitHub repo: ${REPO_NAME} ..."
gh repo create "${REPO_NAME}" \
    --public \
    --description "${DESCRIPTION}" \
    --source . \
    --remote origin \
    --push

echo ""
echo "=== Done! ==="
OWNER=$(gh api user --jq '.login')
echo "Repo:  https://github.com/${OWNER}/${REPO_NAME}"
echo ""
echo "To enable GitHub Pages (so people can view the map online):"
echo "  gh repo edit ${REPO_NAME} --enable-pages --branch main --path /"
echo ""
echo "Then the live map will be at:"
echo "  https://${OWNER}.github.io/${REPO_NAME}/dry_counties_map.html"
