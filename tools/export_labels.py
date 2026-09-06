#!/usr/bin/env python3
"""Turn the capture session into a training set for the closed-set baseline.

The proposed system does not need this.  Enrolment takes five photographs and
appends vectors to a gallery; nothing is trained.  A YOLO detector cannot do
that - it needs a labelled dataset, meaning every photograph paired with a
rectangle and a class.

Drawing those rectangles is normally the expensive part: three hundred-odd
photographs, ten to twenty seconds of dragging each, and boxes that vary with
whoever drew them.  None of that is necessary here, because the capture protocol
already contains both halves of every label:

  the class   `capture.py --sku pepsi` filed the photograph under `pepsi/`
  the box     the empty mat was photographed first, so subtracting it leaves
              exactly the product, and `BackgroundSubtractionProposer` returns
              its rectangle

So the labels are computed, not drawn, by the same proposer the till runs.  That
also makes experiment E1 fair in a way a reviewer can check: the detector is
trained on precisely the crops the retrieval system enrols from, so neither
system is handicapped by how somebody dragged a mouse.

    python tools/export_labels.py                 # research/data/yolo
    python tools/export_labels.py --k 5           # views 0-4 train, the rest val

The split is deliberate.  Views 0 to k-1 are the ones enrolment uses, so
training the detector on exactly those and validating on the rest puts both
systems on the same footing - the same examples to learn from, the same held-out
views to be scored on.

**Limitation, and it belongs in the paper.**  These boxes come from mat
subtraction, so the detector learns to find products the way the mat presents
them.  It will do well on the rig and poorly on a cluttered shelf.  For this
project that is the deployment condition rather than a shortcut, but it is not a
general-purpose detector and must not be described as one.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.proposer import BackgroundSubtractionProposer   # noqa: E402
from research.capture import load_manifest                       # noqa: E402
from research.dataset import CAPTURES, MAT                       # noqa: E402

#: enrolment takes five views; the detector trains on the same five
DEFAULT_K = 5


def to_yolo(box, width: int, height: int) -> tuple[float, float, float, float]:
    """Pixel corners to the fractions YOLO wants: centre, then size."""
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2 / width, (y1 + y2) / 2 / height,
            (x2 - x1) / width, (y2 - y1) / height)


def export(captures: Path, mat_path: Path, out: Path,
           k: int = DEFAULT_K) -> dict:
    """Write a YOLO dataset.  Returns what happened, per product."""
    mat = cv2.imread(str(mat_path))
    if mat is None:
        raise SystemExit(f"{mat_path} not found - photograph the empty mat first: "
                         "python research/capture.py --mat")

    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(mat)

    skus = sorted(d.name for d in captures.iterdir()
                  if d.is_dir() and any(d.glob("*.jpg")))
    if not skus:
        raise SystemExit(f"no captures in {captures} - "
                         "python research/capture.py --help")

    for split in ("train", "val"):
        for kind in ("images", "labels"):
            (out / kind / split).mkdir(parents=True, exist_ok=True)

    report = {"classes": skus, "train": 0, "val": 0, "skipped": {}, "per_sku": {}}
    for index, sku in enumerate(skus):
        photos = sorted((captures / sku).glob("*.jpg"))
        kept = {"train": 0, "val": 0}
        for n, photo in enumerate(photos):
            frame = cv2.imread(str(photo))
            if frame is None:
                report["skipped"].setdefault(sku, []).append(f"{photo.name}: unreadable")
                continue
            proposals = proposer.propose(frame)
            if not proposals:
                # the product is in the photograph, so an empty label would be a
                # lie that teaches the detector this frame contains nothing
                report["skipped"].setdefault(sku, []).append(
                    f"{photo.name}: nothing found against the mat")
                continue
            best = max(proposals, key=lambda p: p.area_px)
            h, w = frame.shape[:2]
            cx, cy, bw, bh = to_yolo(best.box, w, h)

            split = "train" if n < k else "val"
            stem = f"{sku}-{n:03d}"
            shutil.copy(photo, out / "images" / split / f"{stem}.jpg")
            (out / "labels" / split / f"{stem}.txt").write_text(
                f"{index} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
            kept[split] += 1

        report["per_sku"][sku] = kept
        report["train"] += kept["train"]
        report["val"] += kept["val"]

    names = "\n".join(f"  {i}: {s}" for i, s in enumerate(skus))
    (out / "data.yaml").write_text(
        f"# GENERATED by tools/export_labels.py - do not edit\n"
        f"# boxes computed by BackgroundSubtractionProposer against "
        f"{mat_path.name}, never drawn by hand\n"
        f"path: {out.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n{names}\n")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", type=Path, default=CAPTURES)
    ap.add_argument("--mat", type=Path, default=MAT)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "data" / "yolo")
    ap.add_argument("--k", type=int, default=DEFAULT_K,
                    help="views per product used for training; the rest validate")
    args = ap.parse_args()

    report = export(args.captures, args.mat, args.out, args.k)

    manifest = load_manifest()
    print(f"{len(report['classes'])} classes, {report['train']} training "
          f"and {report['val']} validation images -> {args.out}")
    for sku, counts in report["per_sku"].items():
        note = "" if sku in manifest else "   (not in the manifest)"
        print(f"  {sku:<26}{counts['train']:>4} train {counts['val']:>4} val{note}")

    if report["skipped"]:
        total = sum(len(v) for v in report["skipped"].values())
        print(f"\n  {total} photograph(s) left out - the mat subtraction found nothing "
              f"in them.\n  They are not labelled as empty, because the product is "
              f"there and saying\n  otherwise would teach the detector to miss it:")
        for sku, reasons in report["skipped"].items():
            for reason in reasons[:4]:
                print(f"    {sku}/{reason}")
        print("  Check the mat photograph is current and the light has not moved.")

    print(f"\n  train:  yolo detect train data={args.out}/data.yaml model=yolov8n.pt")
    print("  Time it. E8 compares those hours against enrolment, and the number "
          "has to be\n  measured rather than remembered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
