#!/usr/bin/env python3
"""Photograph the products, on the rig, for the experiments.

The version 1 training images are gone; only the trained weights survived.  That
turns out to matter less than it sounds, because the method needs a handful of
views per product rather than a labelled dataset - but those views have to be
taken on the rig that will be doing the recognising, under its lighting.

    python research/capture.py --mat                  photograph the empty mat first
    python research/capture.py --sku pepsi --name "Pepsi" --price 14 --views 14
    python research/capture.py --import photos/       bring in pictures taken elsewhere
    python research/capture.py --verify               is the dataset complete?

Take more views than you will enrol.  Enrolment uses the first k; everything
after that is the test set, and a product with no held-out views cannot be
scored on.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.dataset import CAPTURES, MANIFEST, MAT   # noqa: E402

#: enrolment takes 5; the rest are held out for scoring
MIN_VIEWS = 8
RECOMMENDED_VIEWS = 14


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def open_camera(index: int):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit(f"camera {index} did not open")
    return cap


def capture_mat(camera: int) -> int:
    cap = open_camera(camera)
    print("Clear the mat completely, then press SPACE. Q to abort.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue
            cv2.imshow("empty mat - SPACE to save", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                MAT.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(MAT), frame)
                print(f"  saved {MAT}")
                return 0
            if key in (ord("q"), 27):
                return 1
    finally:
        cap.release()
        cv2.destroyAllWindows()


def capture_sku(args) -> int:
    if not MAT.exists():
        raise SystemExit("photograph the empty mat first:  python research/capture.py --mat")

    out = CAPTURES / args.sku
    out.mkdir(parents=True, exist_ok=True)
    existing = sorted(out.glob("*.jpg"))
    cap = open_camera(args.camera)

    print(f"{args.name or args.sku}: {args.views} views. "
          "SPACE captures, U undoes the last one, Q finishes.")
    print("Turn the product a little between shots - five photographs of the same "
          "angle are worth about as much as one.")
    taken = len(existing)
    try:
        while taken < args.views:
            ok, frame = cap.read()
            if not ok:
                continue
            preview = frame.copy()
            cv2.putText(preview, f"{taken}/{args.views}", (20, 44),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 255), 3)
            cv2.imshow(f"capture {args.sku}", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(" "):
                cv2.imwrite(str(out / f"{taken:03d}.jpg"), frame)
                taken += 1
            elif key == ord("u") and taken:
                taken -= 1
                (out / f"{taken:03d}.jpg").unlink(missing_ok=True)
            elif key in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    manifest = load_manifest()
    manifest[args.sku] = {
        "rig_note": args.rig_note,
        "name": args.name or args.sku, "price": args.price,
        "weight_g": args.weight, "category": args.category,
        "in_legacy_model": args.in_legacy_model, "views": taken,
    }
    save_manifest(manifest)
    print(f"  {taken} views in {out}")
    return 0


def import_folder(folder: Path) -> int:
    """Bring in photographs taken elsewhere.

    Expects one sub-folder per product, named with the product id.
    """
    manifest = load_manifest()
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        images = sorted(q for q in sub.iterdir()
                        if q.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if not images:
            continue
        out = CAPTURES / sub.name
        out.mkdir(parents=True, exist_ok=True)
        for i, src in enumerate(images):
            shutil.copy(src, out / f"{i:03d}.jpg")
        entry = manifest.setdefault(sub.name, {"name": sub.name, "price": 0.0,
                                               "weight_g": None, "category": "other",
                                               "in_legacy_model": False})
        entry["views"] = len(images)
        print(f"  {sub.name:<24} {len(images)} views")
    save_manifest(manifest)
    print("\nSet each product's price and weight in research/data/manifest.json.")
    return 0


def verify() -> int:
    """Say plainly whether the dataset can support the experiments."""
    manifest = load_manifest()
    if not manifest:
        print("nothing captured yet")
        return 1

    problems = []
    if not MAT.exists():
        problems.append("no photograph of the empty mat")

    print(f"{'product':<26}{'views':>7}{'price':>9}{'weight':>9}   status")
    print("-" * 68)
    for sku, meta in sorted(manifest.items()):
        n = len(list((CAPTURES / sku).glob("*.jpg")))
        issues = []
        if n < MIN_VIEWS:
            issues.append(f"only {n} views, need {MIN_VIEWS}")
        if not meta.get("price"):
            issues.append("no price")
        if meta.get("weight_g") is None:
            issues.append("no weight")
        problems += [f"{sku}: {i}" for i in issues]
        print(f"{sku:<26}{n:>7}{meta.get('price') or 0:>9.2f}"
              f"{meta.get('weight_g') or 0:>9.0f}   "
              f"{'ok' if not issues else '; '.join(issues)}")

    n_skus = len(manifest)
    print()
    if n_skus < 10:
        problems.append(f"only {n_skus} products - the open-set experiment needs at "
                        f"least 7 and reads as noise below about 10")
    if problems:
        print("not ready:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"ready: {n_skus} products.  Next:  python research/run.py --source captures")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mat", action="store_true", help="photograph the empty mat")
    ap.add_argument("--sku", help="product id, e.g. lays-nori-seaweed")
    ap.add_argument("--name", help="product name as the customer sees it")
    ap.add_argument("--price", type=float, default=0.0)
    ap.add_argument("--weight", type=float, default=None, help="grams, from the scale")
    ap.add_argument("--category", default="other")
    ap.add_argument("--views", type=int, default=RECOMMENDED_VIEWS)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--in-legacy-model", action="store_true",
                    help="the surviving v1 detector was trained on this product")
    ap.add_argument("--import", dest="import_dir", type=Path)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--rig-note", default="",
                    help="camera, exposure lock, light, mat, marker size, date, where bought "
                         "(research/PROTOCOL.md 0b) - stored with the product")
    args = ap.parse_args()

    if args.mat:
        return capture_mat(args.camera)
    if args.import_dir:
        return import_folder(args.import_dir)
    if args.verify:
        return verify()
    if args.sku:
        return capture_sku(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
