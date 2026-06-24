# CURATED. Product Update Pipeline

One-shot automation to add products and re-categorize the catalog.

## Quick start (NEW: csv_to_data — no browser needed)

```bash
# 1. Drop your new products into products.csv (auto-generated from Shopee exports)
# CSV format: link,category,name_hint
#   - link:       required, Shopee short URL (https://s.shopee.co.id/xxxxxxxx)
#   - category:   optional, auto-classified from name if blank
#   - name_hint:  optional
$ nano products.csv

# 2. Run the lightweight pipeline (no browser, no TKP scraping, fast)
$ python3 tools/csv_to_data.py products.csv \
    --csv-source /path/to/Shopee_Export_1.csv \
    --csv-source /path/to/Shopee_Export_2.csv \
    [...repeat --csv-source per file...]
$ python3 tools/normalize_entries.py
$ python3 tools/recategorize.py

# 3. Commit + push
$ git add -A && git commit -m "feat: import N new products"
$ git push origin main

# 4. Wait ~1-2 min for CF Pages to deploy, then verify
$ curl -s https://curated.my.id/ | grep -oE "[0-9]+ barang" | head -1
```

## Legacy pipeline (browser-based — has OOM issues)

The legacy `add_from_csv.py` uses Tokopedia web search + Shopee via browser. It works for
small batches but crashes after ~50-100 products due to Chromium OOM. `csv_to_data.py` is
the new default; it's pure Python and reads from your existing Shopee export CSVs.

```bash
# Legacy path — only use if you need image scraping
$ ./tools/auto_update.sh --csv products.csv
```

## Pipeline stages

| Stage | Tool | What it does |
|-------|------|--------------|
| Import | `tools/csv_to_data.py products.csv --csv-source ...` | Reads Shopee export CSVs, builds data.json entries (no browser, no image scraping — images stay empty until separate pipeline adds them) |
| Normalize | `tools/normalize_entries.py` | Converts raw Shopee fields (price, sales, shop) to frontend-friendly format (price_label, sold_label, image_url, etc.) |
| Re-categorize | `tools/recategorize.py` | Audits all products, applies classifier + hand-curated rules |
| Deploy | `git push origin main` | CF Pages auto-deploys in 1-2 min |

## CSV format

```csv
link,category,name_hint
https://s.shopee.co.id/abc12345,,Rak Kosmetik Acrylic
https://s.shopee.co.id/def67890,clothing,Daster Batik
https://s.shopee.co.id/ghi11112,,
```

- `link` — Shopee affiliate short URL
- `category` — leave empty for auto-classify, or set explicitly (one of: `beauty`, `clothing`, `bags`, `shoes`, `hijab`, `sleepwear`, `gadget`, `home`, `automotive`, `kids`, `baby`, `beauty_storage`, `accessories`)
- `name_hint` — optional hint for ambiguous names

## Available categories (13)

`beauty` · `clothing` · `bags` · `shoes` · `hijab` · `kids` · `gadget` · `sleepwear` · `automotive` · `home` · `baby` · `beauty_storage` · `accessories`

## Tools

| Script | Purpose |
|--------|---------|
| `tools/auto_update.sh` | One-shot pipeline (legacy browser path) |
| `tools/csv_to_data.py` | **NEW** — pure Python importer, reads Shopee export CSVs directly |
| `tools/normalize_entries.py` | **NEW** — converts new imports to frontend schema |
| `tools/add_from_csv.py` | Legacy CSV importer (uses patchright browser, OOM-prone) |
| `tools/recategorize.py` | Audit + re-categorize existing data (idempotent) |
| `tools/classifier.py` | Rule-based name → category classifier |