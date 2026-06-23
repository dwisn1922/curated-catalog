#!/bin/bash
# Wrapper: add products from CSV → auto-deploy
# Usage: ./add_from_csv.sh products.csv
#        ./add_from_csv.sh --dry-run products.csv
set -e
cd "$(dirname "$0")"

# Use hermes venv python (has patchright + Pillow)
PY=/home/ubuntu/.hermes/hermes-agent/venv/bin/python3

if [ ! -f "$PY" ]; then
  echo "Error: hermes venv not found at $PY"
  exit 1
fi

if [ -z "$1" ]; then
  echo "Usage: $0 [--dry-run] <products.csv>"
  echo ""
  echo "CSV format (UTF-8, header required):"
  echo "  link,category,name_hint"
  echo "  https://s.shopee.co.id/xxxxx,skincare,"
  echo "  https://s.shopee.co.id/yyyyy,,Vitamin C serum"
  echo ""
  echo "Columns:"
  echo "  link       (required) Shopee affiliate short link"
  echo "  category   (optional) Default 'general'"
  echo "  name_hint  (optional) Override search query"
  exit 1
fi

exec "$PY" "$PWD/add_from_csv.py" "$@"
