#!/usr/bin/env python3
"""Compare the two version-2 product files against the merged one.

usage: compare_databases.py <path/to/v2/checkout>

The v2 build kept products in two places with two different shapes.  This is the
script that found the price disagreements, kept so the comparison can be redone.
"""
import json
import sys
from pathlib import Path

v2 = Path(sys.argv[1])
web = {p["name"]: p for p in json.loads((v2 / "smart-checkout-optimized/products.json").read_text())["products"]}
scanner = json.loads((v2 / "self-checkout-system/database/products.json").read_text())["products"]
merged = {p["name"]: p for p in json.loads(
    (Path(__file__).resolve().parents[2] / "data/products.json").read_text())["products"]}


def thb(v):
    return f"THB {v:.0f}"


print("$ python docs/tools/compare_databases.py   # the two product files, before the merge")
print()
print(f"  {'product':<32}{'server':>10}{'scanner':>10}{'merged':>10}   verdict")
print("  " + "-" * 76)

disagreed = 0
total = 0
for items in scanner.values():
    for p in items.values():
        total += 1
        w, m = web.get(p["name"]), merged.get(p["name"])
        if not w:
            verdict = "scanner-only: recovered into the merged file"
            disagreed += 1
        elif w["price"] != p["price"]:
            verdict = "PRICE MISMATCH -> server price kept"
            disagreed += 1
        else:
            verdict = "agrees"
        print(f"  {p['name'][:32]:<32}{thb(w['price']) if w else '-':>10}"
              f"{thb(p['price']):>10}{thb(m['price']) if m else '-':>10}   {verdict}")

print("  " + "-" * 76)
print(f"  {disagreed} of {total} products disagreed between the two files.")
print("  After the merge there is one file: data/products.json")
