"""Category classifier for CURATED catalog.
Returns one of: clothing, bags, shoes, beauty, sleepwear, hijab, occasion,
                beauty_storage, home, gadget, automotive, kids, baby, accessories
"""
import re

VALID_CATEGORIES = {
    "clothing", "bags", "shoes", "beauty", "sleepwear", "hijab", "occasion",
    "beauty_storage", "home", "gadget", "automotive", "kids", "baby", "accessories",
}


def classify(p: dict) -> str:
    """Classify a product by name keyword matching.
    
    Priority order: automotive > gadget > beauty > hijab > baby > kids >
                    shoes > bags > sleepwear > occasion > home > accessories > default
    """
    name = p.get("name", "").lower()

    # 1. Automotive
    if any(kw in name for kw in [
        "oli ", "oli mesin", "oli gardan", "mesin motor", "mesin mobil",
        "scooter gear", "scooter power", "ban motor", "ban mobil",
        " aki ", " aki,", " aki.", " aki/",
        "accu ", "velg ", "knalpot", "jet cleaner", "alat cuci motor", "steam ac mobil",
    ]):
        return "automotive"

    # 2. Gadget — checked first (before home, before beauty)
    # Phone brands + model keywords (case-insensitive)
    if any(kw in name for kw in [
        "smartband", "smart band", " mi band", "fitness band",
        "smartwatch", "smart watch", " mi watch", "amazfit",
        "tablet ", " ipad", "kindle",
        "tws ", "earbuds", "earphone", "headphone", "airpods",
        "speaker bluetooth", "speaker aktif",
        "power bank", "powerbank", "kabel data", "kabel charger", "charger ",
        "mouse wireless", "mouse gaming", "keyboard mekanik",
        "stand holder phone", "phone stand", "phone holder",
    ]):
        return "gadget"
    # Phone brand/model names — word-boundary regex to avoid false positives
    if re.search(r"\b(iphone|ip\s?\d+\s?(pro|plus|max|mini)?|ipad|ipados)\b", name):
        return "gadget"
    if re.search(r"\b(samsung|galaxy\s?(s|a|z|note|m|f)?\d*|xiaomi|redmi|poco|huawei|honor|oppo|realme|vivo|infinix|tecno|lenovo\s?(motopad|tab|legion)?|asus(?:\s+(?:zenfone|rog|tuf))?)\b", name):
        return "gadget"
    if re.search(r"\b(garmin|fitbit|apple\s+watch|amazfit|g-shock|casio\s+(ga|gm|mts|dw|mtv))\b", name):
        return "gadget"
    if re.search(r"\b(macbook|ideapad|vivobook|thinkpad|surface\s+(pro|go|laptop))\b", name):
        return "gadget"
    if re.search(r"\b(kipas\s+(senter|portabel|mini|rechargeable|angin|genggam|tangan|usb)|kipas\s+angin\s+(mini|portabel|usb)|fan\s+(mini|portable|usb|rechargeable))\b", name):
        return "gadget"
    if re.search(r"\b(gps\s+(mobil|motor|tracker|tracking))\b", name):
        return "automotive"  # GPS tracker for vehicle
    if re.search(r"\b(hair\s+dryer|hairdryer|pengering\s+rambut)\b", name):
        return "home"  # personal care appliance
    if re.search(r"\b(speaker\s+(portable|wireless|bt|jbl|harman|sony|bose))\b", name):
        return "gadget"

    # 3. Beauty (incl perfume)
    if any(kw in name for kw in [
        "facial wash", "facial foam", "face wash", "sabun muka", "sabun cuci muka",
        "pembersih muka", "pembersih wajah", "cleanser",
        "parfum", "perfume", "eau de parfum", "edp", "cologne",
        "skincare", "serum", "toner", "moisturizer", "sunscreen",
        "lipstik", "lip cream", "lip tint", "lip matte", "lip gloss",
        "foundation", "cushion", "bb cream", "cc cream", "concealer",
        "bedak", "powder", "blush", "eyeshadow", "eyeliner", "mascara",
        "masker wajah", "masker hidung",
        "shampoo", "conditioner", "hair mask", "hair oil", "minyak kemiri",
        "kuteks", "nail art", "nail polish", "cat kuku",
        "henna", "inai",
    ]):
        return "beauty"

    # 4. Hijab
    if any(kw in name for kw in [
        "hijab", "pashmina", "bergo", "jilbab", "kerudung", "mukena", "khimar",
    ]):
        return "hijab"

    # 4b. Beauty storage (rak/organizer kosmetik) — checked before clothing
    if any(kw in name for kw in [
        "rak kosmetik", "rak makeup", "makeup organizer", "beauty organizer",
        "cosmetic organizer", "rak lipstick", "tempat kosmetik", "kotak kosmetik",
        "tas kosmetik", "pouch kosmetik", "case kosmetik",
    ]):
        return "beauty_storage"

    # 5. Baby (incl ASI, breast pump)
    if any(kw in name for kw in [
        "bayi", "baby ", "paseo baby", "tisu bayi", "popok", "diaper", "dot bayi",
        "botol susu", "asi ", "pompa asi", "pompa air susu", "breast pump",
        "baby bottle", "baby bottle", "sterilizer bayi", "baby walker", "stroller",
    ]):
        return "baby"

    # 6. Kids (incl pakaian anak, mainan)
    if any(kw in name for kw in [
        "mainan", "toys", "pesawat terbang", "remote control", "mobil-mobilan",
        "boneka", "puzzle", " anak ", "baju anak", "pakaian anak",
        "kids ", "kid ", "children ", "bayi laki", "bayi perempuan",
    ]):
        return "kids"

    # 7. Shoes (only at start)
    if re.match(r"^\W*(sepatu|sneaker|sneakers|boots|sandal|flat shoes|heels|loafer|pantofel)", name):
        return "shoes"

    # 8. Bags — also catches English "BAGS" brand prefix
    if any(kw in name for kw in [
        "tas ransel", "ransel", "selempang", "sling bag", "tote bag",
        "backpack", "dompet", "wallet", "pouch", "koper", "luggage",
        "tas tangan", "tas bahu", "tas pesta", "tas wanita", "tas pria",
        "tas selempang", "tas sekolah", "tas laptop",
    ]):
        return "bags"
    if re.match(r"^\W*tas\b", name):
        return "bags"
    if re.search(r"\bbags?\s*[-–—:]", name) or " bags " in name:
        return "bags"

    # 9. Sleepwear
    if any(kw in name for kw in [
        "piyama", "pajama", "sleepwear", "nightgown", "daster", "kimono tidur",
    ]):
        return "sleepwear"

    # 10. Occasion
    if any(kw in name for kw in [
        "kebaya", "gaun pengantin", "wedding dress", "bridesmaid", "party dress", "gaun pesta",
    ]):
        return "occasion"

    # 11. Home (incl small appliances, furniture, lighting)
    # Use regex word-boundary to avoid false positives (e.g. "meja" inside "kemeja")
    def _has_word(name: str, kw: str) -> bool:
        """Match kw as a whole word in name (case-insensitive)."""
        return bool(re.search(r"\b" + re.escape(kw) + r"\b", name))

    HOME_KW_BARE = [
        "kursi", "chair", "furnitur", "furniture", "meja",
        "lampu tidur", "lampu led", "lampu meja", "lampu dinding",
        "kipas", "fan mini", "setrika",
        "deterjen", "sabun cuci piring", "sabun lantai",
        "botol minum", "tumbler", "thermos", "tempat minum",
        "rak piring", "rak buku", "shelf",
        "kasur", "bantal", "sprei", "bed cover",
        "ember", "gayung", "tempat sampah",
    ]
    HOME_KW_SUBSTR = [
        "jemuran", "gantungan baju", "rak sepatu", "lemari pakaian",
        "meja lipat", "kursi lipat",
    ]
    if any(kw in name for kw in HOME_KW_SUBSTR):
        return "home"
    if any(_has_word(name, kw) for kw in HOME_KW_BARE):
        return "home"
    # "rak " (with space) — only match as separate word "rak"
    if _has_word(name, "rak"):
        return "home"

    # 12. Accessories
    if any(kw in name for kw in [
        "topi", "cap ", "caps ", "beanie", "bucket hat",
        "kacamata hitam", "sunglasses",
        "ikat pinggang", "belt ", "sabuk",
        "kaus kaki", "kaos kaki", "sock",
        "bros", "hair clip", "ikat rambut", "scrunchie",
    ]):
        return "accessories"

    # 13. Default — keep current if valid
    cur = p.get("category", "")
    return cur if cur in VALID_CATEGORIES else "clothing"
