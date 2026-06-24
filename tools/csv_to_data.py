#!/usr/bin/env python3
"""
csv_to_data.py — Convert Shopee Affiliate "LinkProdukSekaligus" CSV ke data.json entries.

Bypass add_from_csv.py (Tokopedia-search based, sering crash) dengan cara:
- Build entries langsung dari CSV (ID, Nama, Harga, Toko, Link Komisi Ekstra)
- image_url/image_local kosong dulu (di-scrape terpisah via Shopee HTTP API)
- category auto-classify via classifier.classify(name)

Usage:
  python3 tools/csv_to_data.py --csv products.csv [--dry-run]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
DATA_JSON = REPO_DIR / "data.json"
sys.path.insert(0, str(REPO_DIR / "tools"))
from classifier import classify  # type: ignore


def log(msg: str):
    print(f"[csv2data] {msg}", flush=True)


def parse_price(price_str: str) -> int:
    """'Rp125.000' -> 125000"""
    if not price_str:
        return 0
    digits = re.sub(r"[^\d]", "", price_str)
    return int(digits) if digits else 0


def parse_commission(comm_str: str) -> float:
    """'Rp10.000' -> 10.0 (in 'rb'/'K' format)"""
    if not comm_str:
        return 0.0
    digits = re.sub(r"[^\d]", "", comm_str)
    val = int(digits) if digits else 0
    return val / 1000.0


def build_entry(csv_row: dict) -> dict:
    """Build one data.json entry from one Shopee CSV row."""
    item_id = csv_row["ID Produk"].strip()
    name = csv_row["Nama Produk"].strip()
    price = parse_price(csv_row.get("Harga", ""))
    shop = csv_row.get("Nama Toko", "").strip()
    sales = csv_row.get("Penjualan", "0").strip()
    commission_pct = parse_commission(csv_row.get("Komisi hingga", ""))
    affiliate_link = csv_row.get("Link Komisi Ekstra", "").strip() or csv_row.get("Link Produk", "").strip()
    # classifier expects dict with 'name' key
    category = classify({"name": name})

    # slug from name (light)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]

    entry = {
        "id": item_id,
        "name": name,
        "slug": slug,
        "price": price,
        "category": category,
        "image_url": "",   # to be filled by separate scraper
        "image_local": None,
        "affiliate_link": affiliate_link,
        "shop": shop,
        "sales": sales,
        "commission_pct": commission_pct,
        "commission_rate": commission_pct / 100.0,
        "source": "shopee_csv_import",
    }
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file", help="Path to products.csv (link,category,name_hint)")
    ap.add_argument("--csv-source", required=True, action="append",
                    help="Path to Shopee LinkProdukSekaligus CSV (repeat for multiple files)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Load products.csv (link, category, name_hint) — primary key = link
    products_csv = []
    with open(args.csv_file, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            products_csv.append(row)
    log(f"products.csv loaded: {len(products_csv)} rows")

    # Load source Shopee CSV (ID, Nama, ...) — primary key = ID Produk
    # Use utf-8-sig to strip BOM if present
    # Accept multiple --csv-source flags (one per Shopee export file)
    source_csv = []
    for src_path in args.csv_source:
        with open(src_path, newline="", encoding="utf-8-sig") as f:
            rdr = csv.DictReader(f)
            file_rows = list(rdr)
            source_csv.extend(file_rows)
            log(f"  source: {src_path.split('/')[-1]} → {len(file_rows)} rows")
    log(f"source CSV total: {len(source_csv)} rows")

    # Load existing data.json
    existing = []
    if DATA_JSON.exists():
        with open(DATA_JSON, encoding="utf-8") as f:
            existing = json.load(f)
    log(f"existing data.json: {len(existing)} entries")
    existing_ids = {p["id"] for p in existing}

    # Process each products.csv row
    new_entries = []
    skipped = 0
    for row in products_csv:
        link = row["link"].strip()
        # Extract ID from Shopee link via resolve... actually we just look up by link match
        # Find matching source row by affiliate link
        match_src = None
        for src in source_csv:
            if src.get("Link Komisi Ekstra", "").strip() == link or src.get("Link Produk", "").strip() == link:
                match_src = src
                break
        if not match_src:
            log(f"  WARN: no source match for {link[:60]}")
            continue
        item_id = match_src["ID Produk"].strip()
        if item_id in existing_ids:
            skipped += 1
            continue
        entry = build_entry(match_src)
        new_entries.append(entry)
        existing_ids.add(item_id)

    log(f"new: {len(new_entries)}, skipped (dupe): {skipped}")

    if args.dry_run:
        log("[dry-run] preview:")
        for e in new_entries[:5]:
            log(f"  {e['id']} | {e['category']:12s} | {e['name'][:60]}")
        cat_count = {}
        for e in new_entries:
            cat_count[e["category"]] = cat_count.get(e["category"], 0) + 1
        log("category distribution:")
        for c, n in sorted(cat_count.items(), key=lambda x: -x[1]):
            log(f"  {c:15s}: {n}")
        return

    # Write
    merged = existing + new_entries
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    log(f"data.json updated: {len(merged)} entries (+{len(new_entries)})")


if __name__ == "__main__":
    main()
