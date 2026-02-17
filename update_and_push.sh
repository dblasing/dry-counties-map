#!/bin/bash
# ============================================================================
# update_and_push.sh — Monthly cron job to regenerate the dry counties map
#                       and push changes to GitHub
#
# Install as cron job (runs 1st of every month at 8am):
#   crontab -e
#   0 8 1 * * /Users/dblasing/dry-counties-map/update_and_push.sh >> /Users/dblasing/dry-counties-map/cron.log 2>&1
#
# Prerequisites:
#   pip3 install plotly pandas geopandas plotly-geo shapely requests beautifulsoup4
#   gh auth login
# ============================================================================

set -euo pipefail

REPO_DIR="$HOME/dry-counties-map"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

echo "=== Dry Counties Map Update: ${TIMESTAMP} ==="

# Sanity check
if [ ! -d "${REPO_DIR}/.git" ]; then
    echo "ERROR: ${REPO_DIR} is not a git repo. Clone it first:"
    echo "  git clone https://github.com/dblasing/dry-counties-map.git ~/dry-counties-map"
    exit 1
fi

cd "${REPO_DIR}"

# Pull latest in case of manual edits on GitHub
echo "Pulling latest from GitHub..."
git pull --rebase origin main

# Regenerate the map (--update tries Wikipedia scrape first)
echo "Regenerating map..."
python3 dry_counties_map.py --update

# Check if anything changed
if git diff --quiet dry_counties_map.html; then
    echo "No changes detected. Map is up to date."
    exit 0
fi

# Commit and push
echo "Changes detected — committing and pushing..."
git add dry_counties_map.html
git commit -m "Auto-update dry counties map (${TIMESTAMP})"
git push origin main

echo "=== Update complete ==="
