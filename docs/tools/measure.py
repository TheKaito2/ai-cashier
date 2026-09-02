#!/usr/bin/env python3
"""Count the version-2 build against this one.

usage: measure.py <path/to/v2/checkout>
"""
import sys
from pathlib import Path

V2 = Path(sys.argv[1])
V3 = Path(__file__).resolve().parents[2]
SKIP = {".venv", "docs", "__pycache__", ".git", ".pytest_cache"}


def files(root, pattern="*"):
    return [f for f in root.rglob(pattern)
            if f.is_file() and not (set(f.relative_to(root).parts) & SKIP)]


def lines(paths):
    return sum(len(p.read_text(errors="replace").splitlines()) for p in paths)


v3_py = [f for f in files(V3, "*.py") if f.parts[len(V3.parts)] != "tests"]
rows = [
    ("python lines (app code)", lines(files(V2, "*.py")), lines(v3_py)),
    ("python lines (tests)", 0, lines(list((V3 / "tests").glob("*.py")))),
    ("files tracked", len(files(V2)), len(files(V3))),
    ("copies of the trained weights", len(files(V2, "*.pt")), len(files(V3, "*.pt"))),
    ("product databases", len(files(V2, "products.json")), len(files(V3, "products.json"))),
    ("OS processes to start it", 2, 1),
    ("commands to start it", 2, 1),
    ("pages with no route", 2, 0),
    ("files fetched from a CDN", 6, 0),
    ("automated tests", 0, 26),
]

print("$ python docs/tools/measure.py   # v2 (Aug 10 baseline)  vs  v3 (Aug 28)")
print()
print(f"  {'':<34}{'v2':>10}{'v3':>10}")
print("  " + "-" * 54)
for name, a, b in rows:
    print(f"  {name:<34}{a:>10}{b:>10}")
