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

    # 2. Gadget
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

    # 5. Baby
    if any(kw in name for kw in [
        "bayi", "baby ", "paseo baby", "tisu bayi", "popok", "diaper", "dot bayi", "botol susu",
    ]):
        return "baby"

    # 6. Kids (toys)
    if any(kw in name for kw in [
        "mainan", "toys", "pesawat terbang", "remote control", "mobil-mobilan", "boneka", "puzzle",
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

    # 11. Home (incl small appliances)
    if any(kw in name for kw in [
        "jemuran", "gantungan baju", "rak sepatu", "lemari pakaian",
        "meja lipat", "kursi lipat", "lampu led",
        "kipas", "fan mini", "setrika",
        "deterjen", "sabun cuci piring", "sabun lantai",
    ]):
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
