#!/usr/bin/env python3
"""
Backfill missing product images for curated.my.id
- Fetch shortlink via facebook UA → og:square_image
- Download @resize_w800 (800x800)
- Save as images/{id}.jpg + .webp + -400w.webp
- Update data.json with image_url, image_webp, image_srcset
"""
import asyncio
import json
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
import requests
from PIL import Image

ROOT = Path('/home/ubuntu/shopee-web/shopee-affiliate')
IMG_DIR = ROOT / 'images'
DATA_FILE = ROOT / 'data.json'
IMG_DIR.mkdir(exist_ok=True)

HEADERS_FB = {'User-Agent': 'facebookexternalhit/1.1', 'Accept': 'text/html,application/xhtml+xml'}
HEADERS_DL = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}

def fetch_shortlink(short_url, retries=2):
    """Resolve shortlink to get og:square_image URL. Returns (shopee_image_url, redirect_url)"""
    for attempt in range(retries):
        try:
            r = requests.get(short_url, headers=HEADERS_FB, timeout=10, allow_redirects=True)
            if r.status_code != 200:
                continue
            m = re.search(r'<meta[^>]+property="og:square_image"[^>]+content="([^"]+)"', r.text)
            if m:
                return m.group(1)
        except Exception as e:
            if attempt == retries - 1:
                print(f'  retry fail {short_url[-12:]}: {e}')
            time.sleep(0.5)
    return None

def download_image(url, retries=2):
    """Download image and return PIL Image"""
    # Use @resize_w800 for 800x800 (smaller download)
    if '@' in url:
        img_url = url.split('@')[0] + '@resize_w800'
    else:
        img_url = url
    for attempt in range(retries):
        try:
            r = requests.get(img_url, headers=HEADERS_DL, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                img = Image.open(BytesIO(r.content))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                return img, len(r.content)
        except Exception as e:
            if attempt == retries - 1:
                print(f'  dl fail {url[-30:]}: {e}')
            time.sleep(0.3)
    return None, 0

def save_image_variants(img, prod_id):
    """Save jpg + webp (800) + webp (400w). Returns the 3 paths."""
    jpg_path = IMG_DIR / f'{prod_id}.jpg'
    webp_path = IMG_DIR / f'{prod_id}.webp'
    webp_400 = IMG_DIR / f'{prod_id}-400w.webp'

    # Save JPG
    img.save(jpg_path, 'JPEG', quality=85, optimize=True)

    # Save WebP 800
    img.save(webp_path, 'WEBP', quality=85, method=6)

    # Save WebP 400 (downscaled)
    img_400 = img.copy()
    img_400.thumbnail((400, 400), Image.LANCZOS)
    img_400.save(webp_400, 'WEBP', quality=85, method=6)

    return jpg_path, webp_path, webp_400

def process_product(prod):
    """Process a single product. Returns (id, success, info)."""
    prod_id = prod['id']
    aff = prod.get('affiliate', {})
    short_url = aff.get('link', '')

    if not short_url or 's.shopee.co.id' not in short_url:
        return (prod_id, False, 'no-shortlink')

    # Step 1: Get og:square_image from shortlink
    og_url = fetch_shortlink(short_url)
    if not og_url:
        return (prod_id, False, 'no-og-image')

    # Step 2: Download image
    img, size = download_image(og_url)
    if not img:
        return (prod_id, False, 'download-fail')

    # Step 3: Save variants
    jpg_path, webp_path, webp_400 = save_image_variants(img, prod_id)

    return (prod_id, True, {
        'jpg': jpg_path.name,
        'webp': webp_path.name,
        'webp_400': webp_400.name,
        'image_url': f'images/{prod_id}.jpg',
        'image_webp': f'images/{prod_id}.webp',
        'image_srcset': f'images/{prod_id}-400w.webp 400w, images/{prod_id}.webp 800w',
        'orig_size': img.size,
        'bytes': size,
    })

def main():
    data = json.loads(DATA_FILE.read_text())
    print(f'Total products: {len(data)}')

    # Find missing
    missing = []
    for p in data:
        if not (IMG_DIR / f'{p["id"]}.jpg').exists():
            missing.append(p)
    print(f'Missing images: {len(missing)}')

    if not missing:
        print('Nothing to do.')
        return

    # Process with thread pool
    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(process_product, p): p for p in missing}
        done_count = 0
        for fut in as_completed(futures):
            done_count += 1
            prod_id, ok, info = fut.result()
            status = '✓' if ok else '✗'
            print(f'  [{done_count}/{len(missing)}] {status} {prod_id} | {info if not ok else info["bytes"]}')
            results.append((prod_id, ok, info))
            if done_count % 50 == 0:
                print(f'\n=== Progress: {done_count}/{len(missing)} | elapsed: {time.time()-start:.1f}s ===\n')

    # Update data.json
    success_ids = {r[0]: r[2] for r in results if r[1]}
    fail_ids = [r[0] for r in results if not r[1]]

    print(f'\n=== Summary ===')
    print(f'Success: {len(success_ids)}')
    print(f'Failed: {len(fail_ids)}')
    if fail_ids:
        print(f'Failed IDs: {fail_ids[:10]}...' if len(fail_ids) > 10 else f'Failed IDs: {fail_ids}')

    # Update data.json
    for p in data:
        if p['id'] in success_ids:
            info = success_ids[p['id']]
            p['image_url'] = info['image_url']
            p['image_webp'] = info['image_webp']
            p['image_srcset'] = info['image_srcset']

    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f'\n✓ data.json updated with {len(success_ids)} new images')

    # Save failed IDs for retry
    if fail_ids:
        Path('/tmp/img_failed_ids.json').write_text(json.dumps(fail_ids, indent=2))
        print(f'Failed IDs saved to /tmp/img_failed_ids.json')

    print(f'Total time: {time.time()-start:.1f}s')

if __name__ == '__main__':
    main()