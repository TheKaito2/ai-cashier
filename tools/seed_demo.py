#!/usr/bin/env python3
"""Set up a till that can be demonstrated without a camera or a shelf of crisps.

Builds a mat background, enrols the synthetic products from tests/synthetic.py,
and leaves one product deliberately *not* enrolled so the "unknown item" path
and live enrolment can both be shown.

    python tools/seed_demo.py
"""
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.calibration import pick_threshold          # noqa: E402
from recognition.embedder import OnnxEmbedder               # noqa: E402
from recognition.gallery import SkuGallery                  # noqa: E402
from recognition.pipeline import RecognitionPipeline        # noqa: E402
from recognition.proposer import BackgroundSubtractionProposer  # noqa: E402
from server.services.database import Database               # noqa: E402
from tests.synthetic import CATALOGUE, empty_mat, scene, true_mass, views  # noqa: E402

#: left out on purpose - this is the one a judge is handed to enrol live
HOLD_BACK = "never-enrolled-snack"

PRICES = {"lays-flat-original": 20.0, "lays-ridged-original": 22.0,
          "tasto-seaweed": 24.0, "pepsi": 14.0, "crystal-water": 7.0,
          "never-enrolled-snack": 18.0}
CATEGORY = {"pepsi": "drinks", "crystal-water": "drinks"}


def main() -> int:
    data = ROOT / "data"
    data.mkdir(exist_ok=True)

    mat = empty_mat()
    cv2.imwrite(str(data / "mat_background.png"), mat)
    cv2.imwrite(str(ROOT / "docs" / "assets" / "demo_frame.jpg"),
                scene(["lays-flat-original", "pepsi"], seed=42))

    embedder = OnnxEmbedder(ROOT / "models" / "mobilenet_v3_small.onnx")
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(mat)
    pipe = RecognitionPipeline(proposer, embedder, SkuGallery(embedder.dim))

    db = Database()
    enrolled = [s for s in CATALOGUE if s != HOLD_BACK]
    for sku in enrolled:
        n = pipe.enrol(sku, views(sku, 5, seed=100), weight_g=true_mass(sku))
        prior = pipe.priors[sku]
        db.upsert_product({
            "id": sku, "name": sku.replace("-", " ").title(),
            "price": PRICES[sku], "category": CATEGORY.get(sku, "chips"),
            "stock": 40, "min_stock": 10, "weight_g": true_mass(sku),
            "size_mm": list(prior.size_mm) if prior.size_mm else None,
        })
        print(f"  enrolled {sku:<22} {n} views   {true_mass(sku):5.0f} g")

    # the threshold is measured, never guessed - same routine the real rig uses
    def top_score(sku, seed):
        frame = scene([sku], seed=seed)
        prop = max(pipe.proposer.propose(frame), key=lambda p: p.area_px)
        m = pipe.gallery.match(pipe.embedder.embed([prop.crop(frame)])[0])
        return m[0].score if m else 0.0

    known = [top_score(s, 700 + i) for s in enrolled for i in range(4)]
    unknown = [top_score(HOLD_BACK, 700 + i) for i in range(8)]
    report = pick_threshold(known, unknown)
    db.set_setting("reject_below_cosine", round(report.threshold, 4))

    pipe.gallery.save(data / "gallery.npz")
    print(f"\n  gallery  {len(pipe.gallery.skus)} products, {len(pipe.gallery)} views")
    print(f"  threshold {report}")
    print(f"  held back for the live-enrolment demo: {HOLD_BACK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
