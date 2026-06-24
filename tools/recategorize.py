#!/usr/bin/env python3
"""
Recategorize existing data.json products.

Strategy:
1. Run classifier on each product's name
2. Apply hand-curated overrides for known edge cases
3. Apply name-pattern rules (e.g. "anak"/"bayi" in name + current bag/hijab → kids)
4. Show diff before write, optionally commit+push

Usage:
    ./recategorize.py               # show diff only
    ./recategorize.py --apply       # apply changes
    ./recategorize.py --apply --push  # apply + commit + push to git
"""
import json
import re
import sys
import subprocess
import argparse
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
REPO_DIR = TOOLS_DIR.parent
DATA_JSON = REPO_DIR / "data.json"

# Make tools importable
sys.path.insert(0, str(REPO_DIR))
from tools.classifier import classify

# Hand-curated overrides (id → new category)
# Used for edge cases where the name doesn't follow clean patterns.
OVERRIDES = {
    # e.g. "44065673820": "clothing",   # Setelan Vest+Celana misclassified as bags
}

# Name patterns that should trigger a category change
# (regex, current_cats_to_apply_to, new_category)
NAME_PATTERN_RULES = [
    (re.compile(r"\b(anak|bayi|kids?|children)\b", re.I), {"bags", "hijab"}, "kids"),
    (re.compile(r"(setelan|celana|kemeja|blouse|kaos|jaket|outer|vest)\b", re.I), {"bags"}, "clothing"),
    (re.compile(r"(pompa asi|breast pump|botol susu|popok bayi|diaper)\b", re.I),
     {"bags", "clothing", "home"}, "baby"),
    (re.compile(r"(rak kosmetik|rak makeup|organizer kosmetik|makeup organizer|kotak kosmetik)\b", re.I),
     {"bags", "clothing", "home", "beauty"}, "beauty_storage"),
]


def suggest_changes(products: list) -> list[tuple[dict, str, str]]:
    """Return list of (product, current_cat, suggested_cat) tuples."""
    changes = []
    for p in products:
        cur = p.get("category", "")
        new = None

        # 1. Hand-curated override wins
        if p["id"] in OVERRIDES:
            new = OVERRIDES[p["id"]]
        else:
            # 2. Name-pattern rules
            for pat, applicable_cats, target in NAME_PATTERN_RULES:
                if cur in applicable_cats and pat.search(p["name"]):
                    new = target
                    break
            # 3. Classifier (only if name-pattern didn't match)
            if not new:
                classifier_sug = classify({"name": p["name"]})
                # Don't override clothing with classifier if classifier says clothing
                # (clothing is the default fallback, low signal)
                if classifier_sug != "clothing" and classifier_sug != cur:
                    # Skip: don't auto-reverse out of narrow explicit categories
                    if cur in ("kids", "baby"):
                        continue
                    new = classifier_sug

        if new and new != cur:
            changes.append((p, cur, new))
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Apply changes to data.json (default: dry-run)")
    ap.add_argument("--push", action="store_true",
                    help="After applying, git commit + push")
    args = ap.parse_args()

    with open(DATA_JSON, "r", encoding="utf-8") as f:
        products = json.load(f)

    print(f"Loaded {len(products)} products from data.json\n")

    changes = suggest_changes(products)

    if not changes:
        print("✓ No miscategorizations detected.")
        return

    print(f"{'ID':>11} | {'FROM':<14} | {'TO':<14} | NAME")
    print("-" * 100)
    for p, cur, new in changes:
        print(f"{p['id']:>11} | {cur:<14} | {new:<14} | {p['name'][:60]}")

    print(f"\nTotal: {len(changes)} changes")

    if not args.apply:
        print("\n[dry-run] Use --apply to write changes. Add --push to commit+push.")
        return

    # Apply
    by_id = {p["id"]: p for p in products}
    for p, cur, new in changes:
        by_id[p["id"]]["category"] = new

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Wrote {len(products)} products to data.json")

    if args.push:
        summary = f"fix: recategorize {len(changes)} produk"
        subprocess.run(["git", "add", "-A"], cwd=REPO_DIR, check=True)
        r = subprocess.run(["git", "commit", "-m", summary], cwd=REPO_DIR,
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            print(f"commit failed: {r.returncode}")
            sys.exit(1)
        r = subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR,
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            print(f"push failed: {r.returncode}")
            sys.exit(1)
        print("\n✓ DEPLOYED — auto-deploy triggered")


if __name__ == "__main__":
    main()