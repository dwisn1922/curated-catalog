# CURATED. Product Update Pipeline

One-shot automation to add products and re-categorize the catalog.

## Quick start

```bash
# 1. Drop your new products into products.csv
# CSV format: link,category,name_hint
#   - link:       required, Shopee short URL (https://s.shopee.co.id/xxxxxxxx)
#   - category:   optional, auto-classified from name if blank
#   - name_hint:  optional, used to query Shopee when the short URL is opaque
$ nano products.csv

# 2. Run the pipeline
$ ./tools/auto_update.sh --csv products.csv

# 3. Wait ~1-2 min for CF Pages to deploy, then verify
$ curl -s https://curated.my.id/ | grep -oE "[0-9]+ barang" | head -1
```

## Pipeline stages

| Stage | Tool | What it does |
|-------|------|--------------|
| Import | `tools/add_from_csv.sh products.csv` | Resolves Shopee short URL → scrape TKP API → fetch product details + image → add to `data.json` with auto-categorization |
| Re-categorize | `tools/recategorize.py --apply` | Audits all 154 products, applies classifier + hand-curated rules, shows diff before write |
| Deploy | `git push origin main` | CF Pages auto-deploys in 1-2 min |

## CSV format

```csv
link,category,name_hint
https://s.shopee.co.id/abc12345,,Rak Kosmetik Acrylic
https://s.shopee.co.id/def67890,clothing,Daster Batik
https://s.shopee.co.id/ghi11112,,
```

- `link` — Shopee affiliate short URL (resolved via `curl -sLI`)
- `category` — leave empty for auto-classify, or set explicitly (one of: `beauty`, `clothing`, `bags`, `shoes`, `hijab`, `sleepwear`, `gadget`, `home`, `automotive`, `kids`, `baby`, `beauty_storage`, `accessories`)
- `name_hint` — only used when Shopee short URL doesn't carry the product name in redirect

## Cron (optional)

Run weekly:

```cron
0 9 * * 1  cd /home/ubuntu/shopee-web/shopee-affiliate && ./tools/auto_update.sh --csv products.csv 2>&1 | tee -a logs/auto_update.log
```

## Available categories (13)

`beauty` (32) · `clothing` (23) · `bags` (54) · `shoes` (18) · `hijab` (6) · `kids` (6) · `gadget` (4) · `sleepwear` (3) · `automotive` (3) · `home` (2) · `baby` (1) · `beauty_storage` (1) · `accessories` (1)

## Tools

| Script | Purpose |
|--------|---------|
| `tools/auto_update.sh` | One-shot pipeline (this folder) |
| `tools/add_from_csv.sh` | Wrapper for `add_from_csv.py` |
| `tools/add_from_csv.py` | CSV importer (uses patchright browser) |
| `tools/recategorize.py` | Audit + re-categorize existing data (idempotent) |
| `tools/classifier.py` | Rule-based name → category classifier |