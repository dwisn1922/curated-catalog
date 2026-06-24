#!/usr/bin/env bash
# Wrapper for add_from_csv.py — sets up Python venv & runs importer.
# Use this from cron or manual.
#
# Usage:
#   ./add_from_csv.sh products.csv              # add + commit + push
#   ./add_from_csv.sh products.csv --dry-run    # show what would happen
#   ./add_from_csv.sh products.csv --no-push    # add but don't push
#
# CSV format (header row required):
#   link,category,name_hint
#   https://s.shopee.co.id/xxxxx,,Rak Kosmetik Lipat
#
# Required columns: link
# Optional: category (auto-classified if empty), name_hint (override slug query)

set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$TOOLS_DIR")"

# Use Hermes venv python (cron-friendly)
PY="${HERMES_PY:-/home/ubuntu/.hermes/hermes-agent/venv/bin/python3}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

cd "$TOOLS_DIR"
exec "$PY" add_from_csv.py "$@"