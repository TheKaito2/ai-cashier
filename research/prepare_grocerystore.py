#!/usr/bin/env python3
"""Lay the Grocery Store dataset out for experiment E9.

Klasson, Zhang and Kjellstrom (WACV 2019) photographed 81 fruit, vegetable and
carton products on Swedish shop shelves with a phone, 5,125 natural images plus
one manufacturer ("iconic") image per class.  MIT licence.  It is the public
set that fits this project best: the reference-vs-query setup is exactly the
gallery-vs-till problem, it is small enough to clone, and it needs no login
(RPC is 15 GB behind Kaggle; GroceryVision is a Kaggle challenge).

    git clone --depth 1 https://github.com/marcusklasson/GroceryStoreDataset \\
        research/data/public/GroceryStoreDataset
    python research/prepare_grocerystore.py
    python research/run.py --source folder --root research/data/public/grocerystore-packages --tag packages

Writes three `ImageFolderSource` roots of symlinks under research/data/public/:

    grocerystore-packages   the 30 carton classes (milk, juice, yoghurt): a till's domain
    grocerystore-all        all 81 classes
    grocerystore-iconic     all 81, with the manufacturer image as view 000, so the
                            k=1 row is enrolment from a pack shot with no capture at all

Per class the files sort as 0-iconic, a-train-001..005, b-test-001..009: the
enrolment views come from the training photographs and the k=5 probes are all
test photographs.  Fourteen files per class, the `ImageFolderSource` cap.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "research" / "data" / "public"
DATASET = PUBLIC / "GroceryStoreDataset" / "dataset"

N_TRAIN, N_TEST = 5, 9


def _listed(dataset: Path, name: str) -> dict[str, list[Path]]:
    """`train.txt` lines are `path, fine_id, coarse_id`; group paths by fine class."""
    out: dict[str, list[Path]] = defaultdict(list)
    for line in (dataset / name).read_text().splitlines():
        if not line.strip():
            continue
        rel = line.split(",")[0].strip()
        out[Path(rel).parent.name].append(dataset / rel)
    return {k: sorted(v) for k, v in out.items()}


def _classes(dataset: Path) -> dict[str, dict]:
    with (dataset / "classes.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["Class Name (str)"]: {
        "coarse": r["Coarse Class Name (str)"],
        "iconic": dataset / r["Iconic Image Path (str)"].lstrip("/"),
    } for r in rows}


def _link(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(src.resolve(), dst)


def prepare(dataset: Path = DATASET, out: Path = PUBLIC,
            n_train: int = N_TRAIN, n_test: int = N_TEST) -> dict[str, int]:
    """Build the three roots; return {root name: number of classes}."""
    train, test, classes = _listed(dataset, "train.txt"), _listed(dataset, "test.txt"), _classes(dataset)
    groups = {
        "grocerystore-packages": [c for c in classes if "/Packages/" in str(train[c][0])],
        "grocerystore-all": list(classes),
        "grocerystore-iconic": list(classes),
    }
    counts = {}
    for name, members in groups.items():
        root = out / name
        root.mkdir(parents=True, exist_ok=True)
        meta = {}
        for cls in members:
            d = root / cls
            d.mkdir(exist_ok=True)
            for old in d.iterdir():
                old.unlink()
            if name.endswith("iconic"):
                _link(classes[cls]["iconic"], d / "0-iconic.jpg")
            for i, src in enumerate(train[cls][:n_train], 1):
                _link(src, d / f"a-train-{i:03d}.jpg")
            for i, src in enumerate(test[cls][:n_test], 1):
                _link(src, d / f"b-test-{i:03d}.jpg")
            meta[cls] = {"name": cls.replace("-", " "), "category": classes[cls]["coarse"]}
        (root / "meta.json").write_text(json.dumps(meta, indent=1))
        counts[name] = len(members)
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--out", type=Path, default=PUBLIC)
    args = ap.parse_args()
    if not (args.dataset / "classes.csv").exists():
        print(f"{args.dataset} has no classes.csv - clone the dataset first (see --help)")
        return 1
    for name, n in prepare(args.dataset, args.out).items():
        print(f"  {name:<24} {n} classes  -> {args.out / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
