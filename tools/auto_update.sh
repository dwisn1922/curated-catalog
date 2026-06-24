#!/usr/bin/env bash
# One-shot pipeline: import new products from CSV → re-categorize → commit → push → auto-deploy.
#
# Use this from cron or manual. Idempotent — safe to re-run.
#
# Usage:
#   ./auto_update.sh                              # run full pipeline with existing CSV
#   ./auto_update.sh --csv products.csv           # add from specific CSV first
#   ./auto_update.sh --dry-run                    # show what would happen, no changes
#   ./auto_update.sh --no-push                    # apply + commit, but don't push
#
# Default CSV: <repo>/products.csv
# Deploy: triggers CF Pages auto-deploy via git push (1-2 min)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
PY="${HERMES_PY:-/home/ubuntu/.hermes/hermes-agent/venv/bin/python3}"
[ -x "$PY" ] || PY="$(command -v python3)"

CSV_FILE=""
DRY_RUN=0
PUSH=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv)    CSV_FILE="$2"; shift 2;;
    --dry-run) DRY_RUN=1; PUSH=0; shift;;
    --no-push) PUSH=0; shift;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

cd "$REPO_DIR"
echo "📁 Working dir: $REPO_DIR"
echo "🐍 Python: $PY"
echo ""

# Step 1: Import from CSV (if provided)
if [ -n "$CSV_FILE" ] && [ -f "$CSV_FILE" ]; then
  echo "📥 [1/3] Importing products from $CSV_FILE"
  if [ "$DRY_RUN" = "1" ]; then
    "$PY" tools/add_from_csv.py "$CSV_FILE" --dry-run
  else
    "$PY" tools/add_from_csv.py "$CSV_FILE" --no-push
  fi
  echo ""
fi

# Step 2: Re-categorize existing data (always safe — idempotent)
echo "🔄 [2/3] Auditing + re-categorizing"
if [ "$DRY_RUN" = "1" ]; then
  "$PY" tools/recategorize.py
else
  "$PY" tools/recategorize.py --apply
fi
echo ""

# Step 3: Commit + push (if not dry-run)
if [ "$PUSH" = "1" ]; then
  echo "🚀 [3/3] Commit + push → CF Pages auto-deploy"
  if git diff --quiet data.json tools/ index.html 2>/dev/null; then
    echo "  No changes to commit."
  else
    git add data.json tools/ index.html 2>/dev/null || git add -A
    MSG="chore: auto-update $(date -u +'%Y-%m-%d %H:%M UTC')"
    git commit -m "$MSG"
    git push origin main
    echo "  ✓ Pushed. CF Pages deploying now (1-2 min)."
  fi
else
  echo "⏭  [3/3] Skipped push (--dry-run or --no-push)"
fi

echo ""
echo "✅ Done"