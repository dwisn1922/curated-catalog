#!/usr/bin/env python3
"""
Curated Catalog — Product Importer from CSV

Input: CSV with at least `link` column (Shopee affiliate short link, e.g. s.shopee.co.id/xxxxx)
Optional columns: category, name_hint

Pipeline per row:
1. Resolve Shopee short link → extract item ID + slug
2. Clean slug → search query → Tokopedia search
3. Best match by name similarity → extract name, price, store, sold, image
4. Download image (200x200 thumb) → upscale to 800x800 (jpg + webp)
5. Build product entry, dedupe vs existing data.json
6. Commit + push to trigger auto-deploy

Usage:
    ./add_from_csv.py products.csv
    ./add_from_csv.py --dry-run products.csv   # show what would happen
"""
import sys
import os
import csv
import re
import json
import time
import shutil
import subprocess
import argparse
import requests
from pathlib import Path
from io import BytesIO
from datetime import datetime
from PIL import Image
from patchright.sync_api import sync_playwright

REPO_DIR = Path(__file__).parent
DATA_JSON = REPO_DIR / "data.json"
IMAGES_DIR = REPO_DIR / "images"
CATEGORY = "general"
EDITORIAL_PLACEHOLDER = "Pilihan menarik di katalog CURATED. Cek halaman produk untuk detail harga, rating, dan review."

# Classifier integration — auto-categorize when CSV has no hint
TOOLS_DIR = REPO_DIR / "tools"
try:
    sys.path.insert(0, str(REPO_DIR))
    from tools.classifier import classify as _classify_raw
    def _classify(name: str) -> str:
        return _classify_raw({"name": name or ""})
    HAS_CLASSIFIER = True
except Exception as _e:
    HAS_CLASSIFIER = False
    def _classify(name: str) -> str:  # type: ignore
        return "general"

# Categories that should be replaced by auto-classification
_NON_USER_CATEGORIES = {"", "general", "auto", "?"}

# ---------- helpers ----------

def log(*a):
    print("[add]", *a, flush=True)

def slug_to_query(slug: str) -> str:
    """Convert Shopee slug like 'minyak-goreng-kunci-mas-2l-i.880.12345' to clean search query."""
    # Strip trailing -i.<shop_id>.<item_id>
    s = re.sub(r'-i\.\d+\.\d+$', '', slug)
    # Remove common noise tokens
    NOISE = ['official', 'terbaru', 'terlaris', 'best', 'seller', 'free',
             'murah', 'original', 'ori', 'bpom', 'halal', 'ready', 'stock',
             'cod', 'grosir', 'resmi', 'preorder', 'limited', 'promo', 'diskon']
    parts = []
    for w in s.split('-'):
        if w.lower() in NOISE:
            continue
        if re.match(r'^\d+$', w):  # pure numbers (sizes, etc.)
            parts.append(w)
        elif len(w) > 1:
            parts.append(w)
    return ' '.join(parts[:8])  # cap at 8 words

def name_similarity(a: str, b: str) -> float:
    a_words = set(re.findall(r'\w+', a.lower()))
    b_words = set(re.findall(r'\w+', b.lower()))
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / max(len(a_words), len(b_words))

def safe_filename(name: str) -> str:
    s = re.sub(r'[^a-z0-9-]', '-', name.lower())
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:60] or 'product'

def price_label(price: int) -> str:
    """Format 89700 → '89,7RB'"""
    if price >= 1_000_000:
        juta = price / 1_000_000
        return f"{juta:.1f}JT".replace('.0JT', 'JT')
    elif price >= 1000:
        ribu = price / 1000
        s = f"{ribu:.1f}".replace('.0', '')
        return f"{s}RB"
    return str(price)

def sold_label(sold: int) -> str:
    if sold >= 1000:
        rb = sold / 1000
        s = f"{rb:.1f}".replace('.0', '')
        return f"{s}RB+"
    return f"{sold}+"

# ---------- pipeline ----------

def resolve_shopee_link(url: str) -> dict | None:
    """Follow Shopee short link redirects, extract item ID + slug."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        final = r.url
    except Exception:
        try:
            r = requests.get(url, allow_redirects=True, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            final = r.url
        except Exception as e:
            log(f"  resolve fail: {e}")
            return None

    # Shopee URL patterns (try all):
    #   shopee.co.id/{slug}-i.{shop_id}.{item_id}
    #   shopee.co.id/{store-slug}/{shop_id}/{item_id}
    #   shopee.co.id/product/{shop_id}/{item_id}
    item_id = None
    slug = ''

    m = re.search(r'-i\.\d+\.(\d+)', final)
    if m:
        item_id = m.group(1)
        # slug is everything before -i.
        slug_m = re.search(r'shopee\.co\.id/([^/?]+?)-i\.', final)
        if slug_m:
            slug = slug_m.group(1)
    if not item_id:
        m = re.search(r'/product/\d+/(\d+)', final)
        if m:
            item_id = m.group(1)
            slug_m = re.search(r'shopee\.co\.id/[^/]+/([^/?]+?)/\d+/\d+', final)
            if slug_m:
                slug = slug_m.group(1)
    if not item_id:
        # Last fallback: /{store-slug}/{shop_id}/{item_id}
        m = re.search(r'shopee\.co\.id/[^/]+/\d+/(\d+)', final)
        if m:
            item_id = m.group(1)
            slug_m = re.search(r'shopee\.co\.id/([^/?]+)/', final)
            if slug_m:
                slug = slug_m.group(1)

    if not item_id:
        log(f"  could not parse item_id from: {final[:120]}")
        return None

    return {"item_id": item_id, "slug": slug, "raw_url": final, "original_link": url}


def tkp_search_and_download(page, query: str, item_id: str) -> dict | None:
    """Search Tokopedia, pick best match, download image."""
    log(f"  TKP search: {query!r}")
    try:
        page.goto(f"https://www.tokopedia.com/search?q={requests.utils.quote(query)}",
                  wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        log(f"  TKP goto fail: {e}")
        return None
    time.sleep(4)

    products = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href*="tokopedia.com/"]');
            const results = [];
            for (const link of links) {
                const href = link.getAttribute('href');
                if (!href || href.length < 50) continue;
                if (href.includes('pixel') || href.includes('metrics-log')) continue;

                // Get whole text content of the card
                const fullText = (link.textContent || '').replace(/\\s+/g, ' ').trim();

                // Extract price: first Rp...
                let price = '';
                const pm = fullText.match(/Rp\\s*([\\d.]+(?:\\.\\d{3})?)/);
                if (pm) price = 'Rp' + pm[1];

                // Extract sold: '40+ terjual' or '1rb+ terjual' or '4.540+ terjual'
                let sold = '';
                const sm = fullText.match(/(\\d+(?:\\.\\d+)?)(rb|rb\\+)?\\s*\\+?\\s*terjual/i);
                if (sm) sold = sm[0];

                // Extract name: longest meaningful span
                const spans = link.querySelectorAll('span');
                let name = '';
                let maxLen = 0;
                for (const span of spans) {
                    const t = span.textContent.trim();
                    if (!t) continue;
                    if (t.match(/^(Rp[\\d.,]+|\\d+(?:\\.\\d+)?\\s*(rb)?\\s*\\+?\\s*terjual|Habis|COD|Official|Resmi|Pakai Bonus|Hemat s\\.d)$/i)) continue;
                    if (t.length >= 15 && t.length < 200 && /[a-zA-Z]/.test(t) && t.length > maxLen) {
                        name = t;
                        maxLen = t.length;
                    }
                }
                if (!name) continue;

                const img = link.querySelector('img[src*="tokopedia-static.net"]');
                results.push({
                    name: name.substring(0, 200),
                    price: price,
                    sold: sold,
                    href: href.split('?')[0].replace('&amp;', '&'),
                    img: img ? img.src.replace('&amp;', '&') : null
                });
                if (results.length >= 8) break;
            }
            return results;
        }
    """)

    if not products:
        log("  no TKP results")
        return None

    # Best match by name similarity to query
    best = max(products, key=lambda p: name_similarity(query, p['name']))
    sim = name_similarity(query, best['name'])
    log(f"  best match (sim={sim:.2f}): {best['name'][:60]}")
    if sim < 0.25:
        log(f"  similarity too low, skip")
        return None
    if not best.get('img'):
        log(f"  no image URL")
        return None

    # Download image
    try:
        r = page.context.request.get(best['img'], headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
            "Referer": "https://www.tokopedia.com/"
        })
        if r.status != 200 or len(r.body()) < 1000:
            log(f"  image download fail status={r.status} size={len(r.body())}")
            return None
        img = Image.open(BytesIO(r.body()))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # Upscale to 800x800
        if img.size != (800, 800):
            img = img.resize((800, 800), Image.LANCZOS)

        jpg_path = IMAGES_DIR / f"{item_id}.jpg"
        webp_path = IMAGES_DIR / f"{item_id}.webp"
        webp_400 = IMAGES_DIR / f"{item_id}-400w.webp"

        img.save(jpg_path, 'JPEG', quality=88, optimize=True)
        img.save(webp_path, 'WEBP', quality=85, method=6)
        # 400w version
        img_400 = img.resize((400, 400), Image.LANCZOS)
        img_400.save(webp_400, 'WEBP', quality=82, method=6)

        log(f"  saved images: {jpg_path.name} {webp_path.name} {webp_400.name}")
    except Exception as e:
        log(f"  image save fail: {e}")
        return None

    # Parse price (e.g. "Rp35.000" → 35000, or "Rp1.250.000" → 1250000)
    price_num = 0
    pm = re.search(r'(\d[\d.]+)', best.get('price', ''))
    if pm:
        # Remove dots (thousand separators)
        price_num = int(pm.group(1).replace('.', ''))

    # Parse sold (e.g. "4.540+ terjual" → 4540, "1rb+ terjual" → 1000, "40+ terjual" → 40)
    sold_num = 0
    sold_text = best.get('sold', '').lower()
    if 'rb' in sold_text:
        # e.g. "1rb+ terjual" or "2.5rb+ terjual"
        rm = re.search(r'([\d.,]+)\s*rb', sold_text)
        if rm:
            sold_num = int(float(rm.group(1).replace(',', '.')) * 1000)
    else:
        # e.g. "4.540+ terjual" or "40+ terjual"
        rm = re.search(r'([\d.,]+)\s*\+?\s*terjual', sold_text)
        if rm:
            sold_num = int(rm.group(1).replace('.', '').replace(',', ''))

    # Store name from URL
    store_match = re.search(r'tokopedia\.com/([^/]+)/', best['href'])
    store = store_match.group(1).replace('-', ' ').title() if store_match else 'Tokopedia'

    return {
        "name": best['name'],
        "price": price_num,
        "price_label": price_label(price_num) if price_num else "?",
        "sold": sold_num,
        "sold_label": sold_label(sold_num) if sold_num else "?",
        "store": store,
        "raw_url": best['href'],
    }


def build_product_entry(item_id: str, shopee: dict, tkp: dict, category: str, link: str) -> dict:
    name = tkp['name']
    price = tkp['price']
    # Auto-classify when CSV left it blank/general
    final_category = category
    if (not final_category) or final_category.lower() in _NON_USER_CATEGORIES:
        final_category = _classify(name)
        log(f"  auto-classify: '{name[:50]}' → {final_category}")
    return {
        "id": item_id,
        "name": name,
        "price": price,
        "price_label": tkp['price_label'],
        "sold": tkp['sold'],
        "sold_label": tkp['sold_label'],
        "store": tkp['store'],
        "category": final_category or "general",
        "commission_pct": "5%",
        "commission_idr": f"Rp{int(price * 0.05):,}".replace(',', '.'),
        "url": link,
        "raw_url": shopee['raw_url'],
        "image_url": f"images/{item_id}.jpg",
        "image_webp": f"images/{item_id}.webp",
        "image_srcset": f"images/{item_id}-400w.webp 400w, images/{item_id}.webp 800w",
        "editorial_note": EDITORIAL_PLACEHOLDER,
        "meta_title": f"{name} — Rp {price:,} | Curated Shopee".replace(',', '.'),
        "meta_description": f"{name} tersedia di katalog CURATED. Harga Rp {price:,}".replace(',', '.'),
    }


def git_commit_push(summary: str):
    """Commit and push all changes."""
    log("git add...")
    subprocess.run(["git", "add", "-A"], cwd=REPO_DIR, check=True)
    log("git commit...")
    r = subprocess.run(
        ["git", "commit", "-m", summary],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    log(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
        log(f"commit fail: {r.returncode}")
        return False
    log("git push...")
    r = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    log(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        log(f"push fail: {r.returncode}")
        return False
    return True


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--limit", type=int, default=999, help="max products to process")
    args = ap.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        log(f"CSV not found: {csv_path}")
        sys.exit(1)

    # Load existing data
    with open(DATA_JSON, 'r') as f:
        existing = json.load(f)
    existing_ids = {p['id'] for p in existing}
    log(f"Existing products: {len(existing)}")

    # Parse CSV
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            link = (r.get('link') or r.get('url') or '').strip()
            if not link:
                continue
            cat = (r.get('category') or r.get('cat') or 'general').strip()
            name_hint = (r.get('name') or r.get('name_hint') or '').strip()
            rows.append({"link": link, "category": cat, "name_hint": name_hint})
    log(f"CSV rows: {len(rows)}")

    new_products = []
    skipped = 0
    failed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chromium")
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            locale="id-ID"
        )
        page = ctx.new_page()

        for i, row in enumerate(rows[:args.limit]):
            log(f"\n[{i+1}/{min(len(rows), args.limit)}] {row['link'][:80]}")
            shopee = resolve_shopee_link(row['link'])
            if not shopee:
                log("  resolve fail, skip")
                failed += 1
                continue
            item_id = shopee['item_id']
            if item_id in existing_ids:
                log(f"  already exists (id={item_id}), skip")
                skipped += 1
                continue

            query = slug_to_query(shopee['slug']) if shopee['slug'] else ''
            if row['name_hint']:
                query = row['name_hint']
            if not query:
                log("  no query, skip")
                failed += 1
                continue
            log(f"  item_id={item_id}, query='{query}'")

            tkp = tkp_search_and_download(page, query, item_id)
            if not tkp:
                log("  TKP fail, skip")
                failed += 1
                continue

            entry = build_product_entry(item_id, shopee, tkp, row['category'], row['link'])
            new_products.append(entry)
            existing_ids.add(item_id)
            log(f"  OK: {entry['name'][:60]}")

            if args.dry_run:
                log("  [dry-run] not writing")
                # Clean up downloaded images
                for f in [f"{item_id}.jpg", f"{item_id}.webp", f"{item_id}-400w.webp"]:
                    p = IMAGES_DIR / f
                    if p.exists():
                        p.unlink()
                new_products.pop()

        browser.close()

    log(f"\n=== Summary ===")
    log(f"new:     {len(new_products)}")
    log(f"skipped: {skipped}")
    log(f"failed:  {failed}")

    if not new_products:
        log("nothing to add")
        return

    if args.dry_run:
        log("[dry-run] would add:")
        for p in new_products:
            log(f"  {p['id']}  {p['name'][:60]}")
        return

    # Update data.json
    all_products = existing + new_products
    with open(DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)
    log(f"data.json updated: {len(all_products)} products")

    # Update count in index.html if present
    idx_html = REPO_DIR / "index.html"
    if idx_html.exists():
        with open(idx_html, 'r', encoding='utf-8') as f:
            html = f.read()
        today = datetime.now().strftime("%-d %B %Y").upper() if hasattr(datetime, 'strftime') else \
                datetime.now().strftime("%d %B %Y").upper()
        new_count = len(all_products)
        html_new = re.sub(
            r'\d+\s*BARANG',
            f"{new_count} BARANG",
            html, count=1
        )
        if html_new != html:
            with open(idx_html, 'w', encoding='utf-8') as f:
                f.write(html_new)
            log(f"index.html count updated to {new_count}")

    # Update sitemap lastmod
    sitemap = REPO_DIR / "sitemap.xml"
    if sitemap.exists():
        with open(sitemap, 'r', encoding='utf-8') as f:
            s = f.read()
        today_iso = datetime.now().strftime("%Y-%m-%d")
        s_new = re.sub(r'<lastmod>\d{4}-\d{2}-\d{2}</lastmod>',
                       f'<lastmod>{today_iso}</lastmod>', s)
        if s_new != s:
            with open(sitemap, 'w', encoding='utf-8') as f:
                f.write(s_new)
            log("sitemap.xml updated")

    # Commit + push
    if args.no_push:
        log("--no-push, not pushing")
        return

    summary = f"add: {len(new_products)} produk baru via CSV import"
    if git_commit_push(summary):
        log("\nDEPLOYED! Auto-deploy triggered via GitHub Actions.")
    else:
        log("\ncommit/push failed, please run manually")


if __name__ == "__main__":
    main()
