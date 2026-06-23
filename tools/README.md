# Curated Catalog Tools

## `add_from_csv.py` — Add products from CSV → auto-deploy

Takes a CSV of Shopee affiliate links and adds them to the catalog with images sourced from Tokopedia. Pushes to GitHub → GitHub Actions → auto-deploys to Cloudflare Pages.

### Quick start

```bash
# 1. Create CSV
cat > products.csv << 'CSV'
link,category,name_hint
https://s.shopee.co.id/XXXXX,skincare,
https://s.shopee.co.id/YYYYY,fashion,Vitamin C serum
CSV

# 2. Dry-run first to see what would happen
./add_from_csv.sh --dry-run products.csv

# 3. Run for real (commits + pushes → auto-deploy in ~30s)
./add_from_csv.sh products.csv
```

### CSV columns

| Column | Required | Default | Description |
|--------|----------|---------|-------------|
| `link` | ✅ | — | Shopee affiliate short link (`s.shopee.co.id/xxxxx`) |
| `category` | ❌ | `general` | Product category (skincare, fashion, dll) |
| `name_hint` | ❌ | (extracted from URL slug) | Override search query for Tokopedia |

### What it does

1. Resolves Shopee short link → extracts item ID + slug
2. Searches Tokopedia with cleaned query
3. Picks best match (name similarity ≥ 0.25)
4. Downloads thumbnail (200×200) → upscales to 800×800 (`jpg` + `webp` + 400w webp)
5. Builds product entry (price, sold, store, etc. from Tokopedia)
6. Deduplicates against existing `data.json`
7. Updates `data.json`, `index.html` count, `sitemap.xml` lastmod
8. Git commits + pushes → GitHub Actions → Cloudflare Pages (≈ 30s)

### Requirements

- `/home/ubuntu/.hermes/hermes-agent/venv/bin/python3` (has `patchright` + `Pillow`)
- Git repo with `workflow` scope PAT configured

### Notes

- TKP image CDN signs URLs to the IP — image download goes through the browser context.
- Uses `patchright` (anti-detection fork of Playwright).
- Server IP may be flagged at Tokopedia; rate limit naturally via search.
