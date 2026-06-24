#!/usr/bin/env python3
"""
normalize_entries.py — Normalize new CSV-imported entries to match old entry schema.

Why: csv_to_data.py imports with raw Shopee CSV fields (price, sales, shop, ...)
but frontend (rendered via data.json) expects fully serialized fields
(price_label, sold_label, image_url, image_webp, image_srcset, editorial_note, ...).

Run this after csv_to_data.py import. Idempotent.
"""

import json
import re
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
DATA_JSON = REPO_DIR / "data.json"


def _price_label(price_int: int) -> str:
    """89700 → '89,7RB' (Indonesian formatting)"""
    if price_int >= 1_000_000_000:
        return f"{price_int/1_000_000_000:.1f}M".replace(".0M", "M").replace(".", ",")
    if price_int >= 1_000_000:
        return f"{price_int/1_000_000:.1f}JT".replace(".0JT", "JT").replace(".", ",")
    if price_int >= 1_000:
        return f"{price_int/1_000:.1f}RB".replace(".0RB", "RB").replace(".", ",")
    return str(price_int)


def _sold_from_label(sales_label: str) -> tuple[int, str]:
    """'4RB+' → (4000, '4RB+'), '100+' → (100, '100+')"""
    s = (sales_label or "").strip().replace(" ", "")
    m = re.match(r"(\d+)([A-Z]*)(\+?)", s.upper())
    if not m:
        return 0, sales_label or "0"
    num, unit, plus = m.groups()
    n = int(num)
    if unit == "RB":
        n *= 1000
    elif unit == "JT":
        n *= 1_000_000
    elif unit == "M":
        n *= 1_000_000_000
    return n, sales_label


def _commission_idr(price: int, pct: float) -> int:
    """89700 * 7% → 6279"""
    return int(price * pct)


def _derive_raw_url(affiliate_link: str, item_id: str) -> str:
    """https://s.shopee.co.id/2LWAx9JTER + 40567309551 → https://shopee.co.id/product/0/40567309551

    We don't know shop_id from CSV, so we use 0 (Shopee still loads the product page).
    """
    return f"https://shopee.co.id/product/0/{item_id}"


def normalize(entry: dict) -> dict:
    """Convert new-format entry to old-format. Returns the same dict (in-place)."""
    # Skip if already normalized (has price_label = old format indicator)
    if "price_label" in entry and "image_webp" in entry:
        return entry

    item_id = entry["id"]
    name = entry["name"]
    price = entry.get("price", 0)
    sales_label = entry.get("sales", "0")
    shop = entry.get("shop", "")
    affiliate_link = entry.get("affiliate_link", "")
    pct = entry.get("commission_pct", 0)

    sold_num, sold_lbl = _sold_from_label(sales_label)

    # Image fields — new entries have no image yet (image scraping is phase 2)
    image_url = entry.get("image_url", "") or ""
    image_webp = entry.get("image_webp", "") or image_url.replace(".jpg", ".webp") if image_url else ""
    image_srcset = (
        f"{image_webp} 400w, {image_webp.replace('-400w.webp', '.webp')} 800w"
        if image_webp and "-400w" in image_webp
        else f"{image_webp} 800w" if image_webp else ""
    )

    # Slug from name (for permalink)
    slug = entry.get("slug") or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80]

    normalized = {
        "id": item_id,
        "name": name,
        "slug": slug,
        "price": price,
        "price_label": _price_label(price),
        "original_price": price,
        "discount": 0,
        "sold": sold_num,
        "sold_label": sold_lbl,
        "rating": 0,
        "store": shop,
        "shop_name": shop,
        "is_official_shop": False,
        "category": entry.get("category", "clothing"),
        "subcategory": "",
        "tags": [],
        "description": "",
        "url": affiliate_link,
        "raw_url": _derive_raw_url(affiliate_link, item_id),
        "affiliate": {
            "link": affiliate_link,
            "commission_pct": pct,
            "commission_rate": entry.get("commission_rate", 0),
            "commission_idr": _commission_idr(price, pct),
        },
        "commission_pct": pct,
        "commission_idr": _commission_idr(price, pct),
        "image_url": image_url,
        "image_webp": image_webp,
        "image_srcset": image_srcset,
        "image": image_url,
        "thumb": image_url,
        "cod": True,  # Shopee default — most products have COD
        "free_shipping": False,
        "editorial_note": "",  # can be filled in via editorial pass
        "meta_title": name[:60],
        "meta_description": (name[:155] if name else ""),
        "created_at": datetime.now().isoformat(),
        "source": entry.get("source", "shopee_csv_import"),
    }
    return normalized


def main():
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    new_count = 0
    skipped = 0
    for entry in data:
        if entry.get("source") == "shopee_csv_import" and "price_label" not in entry:
            normalized = normalize(entry)
            entry.clear()
            entry.update(normalized)
            new_count += 1
        elif entry.get("source") == "shopee_csv_import":
            skipped += 1
    DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[normalize] normalized {new_count}, skipped (already normalized) {skipped}")
    print(f"[normalize] total entries: {len(data)}")


if __name__ == "__main__":
    main()
