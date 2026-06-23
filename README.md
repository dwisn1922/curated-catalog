# Curated — Shopee Affiliate Web

Static editorial web, 151 produk fashion/beauty dari Shopee. Built as showcase — **bukan** production deploy.

## Isi
- `index.html` — markup
- `style.css` — palette cream + ink + forest green, 3-tier typography (serif display + sans body + tracked micro-sans)
- `script.js` — load data.json, render featured + grid, filter/search/sort
- `data.json` — 151 produk ter-parse dari CSV (name, price, store, category, url, dll)

## Cara jalanin lokal
Buka terminal di folder ini, terus:
```bash
python3 -m http.server 3212
```
Terus buka `http://localhost:3212/` di browser.

Atau pake Node:
```bash
npx http-server -p 3212
```

## Cara deploy production

### Vercel (paling gampang, gratis)
1. Push folder ini ke GitHub repo baru
2. Buka vercel.com → New Project → Import repo
3. Klik Deploy. Otomatis dapet URL `https://xxx.vercel.app`
4. Custom domain: Project Settings → Domains

### Netlify
1. Drag & drop folder ini ke app.netlify.com/drop
2. Otomatis live. Custom domain di Site Settings → Domain Management

### Cloudflare Pages
1. Push ke GitHub
2. Cloudflare Dashboard → Pages → Connect to Git → pilih repo
3. Build command: (kosong), Build output: `./`
4. Deploy

### VPS sendiri (kalau udah ada nginx)
1. Copy folder ke `/var/www/curated/`
2. Nginx server block: root ke path itu
3. `sudo nginx -s reload`

## Notes
- **151 product images** ada di `images/` (resized ke max 800x800, optimized JPEG quality 82, total 9.6 MB) — same photo dengan yang dipake di Pinterest pin, matching by product ID
- Affiliate link udah pake shortlink `s.shopee.co.id` (otomatis nyantol komisi)
- Mobile responsive udah ada
- Filter kategori + search + sort jalan
- Hero section: 3 highest-priced products dengan photo, rotated polaroid-style
- Featured section: 7 picks (1 tertinggi + 1 per kategori), asymmetric grid
- Grid section: 3-column responsive grid, semua 151 produk dengan real photo

## Image matching logic
Foto produk diambil dari `/home/ubuntu/pin_images/` (sumber Pinterest pin) dan di-resize ke `images/{product_id}.jpg`. Matching: tokenize nama produk, cari token yang sama dengan nama file. 151/151 matched.

```python
# Re-extract images from updated pin_images/
python3 << 'EOF'
import os, json, re
from PIL import Image
files = sorted([f for f in os.listdir('/home/ubuntu/pin_images/') if f.endswith(('.jpg','.png'))])
data = json.load(open('data.json'))
def norm(s): s=s.lower(); return re.sub(r'[^a-z0-9]+','',s)
name2file = {norm(f.split('_',1)[1].rsplit('.',1)[0]): f for f in files}
for p in data:
    parts = re.sub(r'[^a-z0-9]+',' ',p['name'].lower()).split()[:5]
    for token in parts:
        if len(token)<4: continue
        for k,v in name2file.items():
            if token in k:
                img = Image.open(f'/home/ubuntu/pin_images/{v}')
                img.thumbnail((800,800), Image.LANCZOS)
                img.save(f'images/{p["id"]}.jpg', 'JPEG', quality=82)
                p['image_url'] = f'images/{p["id"]}.jpg'
                break
        if p.get('image_url'): break
json.dump(data, open('data.json','w'), indent=2, ensure_ascii=False)
EOF
```

## Customization cepet

**Ganti hero copy** → edit di `index.html`, cari section `.hero-headline`
**Ganti palet warna** → edit di `style.css` bagian `:root { --bg, --ink, --accent }`
**Ganti featured picks** → edit `script.js`, function `getFeatured()`, ubah logic sort
**Tambah product image** → di `script.js` function `cardHtml()`, tambah `<img src="${p.image_url}">` di `.card-media`
