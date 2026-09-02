#!/usr/bin/env python3
"""Numbers the Swift port must reproduce.

The iOS app re-implements the proposer, the embedder (Core ML), the gallery,
the PromptPay payload and the checkout arithmetic.  Without a shared set of
inputs and expected outputs, "it works on the phone" would mean nothing.  This
writes them from the same synthetic products the Python tests use:

    ios/AICashier/Tests/Fixtures/
      crops/<sku>-<n>.png     what the Python proposer cut out and embedded
      mat.png, scene.png      an empty mat and a two-product scene
      fixtures.json           embeddings, gallery centre, expected matches,
                              expected boxes, PromptPay vectors

    python tools/export_fixtures.py
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paths                                                    # noqa: E402
from recognition.embedder import OnnxEmbedder                   # noqa: E402
from recognition.fusion import FusionConfig                     # noqa: E402
from recognition.gallery import SkuGallery                      # noqa: E402
from recognition.proposer import BackgroundSubtractionProposer  # noqa: E402
from server.services.promptpay import build_payload, crc16_ccitt  # noqa: E402
from tests.synthetic import CATALOGUE, empty_mat, scene, views    # noqa: E402

OUT = ROOT / "ios" / "AICashier" / "Tests" / "Fixtures"
ENROLLED = ["lays-flat-original", "lays-ridged-original", "tasto-seaweed", "pepsi", "crystal-water"]
STRANGER = "never-enrolled-snack"
K = 2                                                           # views per enrolled product


def largest_crop(proposer, frame):
    props = proposer.propose(frame)
    best = max(props, key=lambda p: p.area_px)
    return best.crop(frame), best.box


def main() -> int:
    (OUT / "crops").mkdir(parents=True, exist_ok=True)
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(empty_mat())
    embedder = OnnxEmbedder(paths.EMBEDDER)

    crops, embeddings = {}, {}
    for sku in ENROLLED + [STRANGER]:
        for n, frame in enumerate(views(sku, K, seed=100) + views(sku, 1, seed=900)):
            crop, _ = largest_crop(proposer, frame)
            name = f"{sku}-{n}"
            cv2.imwrite(str(OUT / "crops" / f"{name}.png"), crop)
            crops[name] = {"sku": sku, "role": "enrol" if n < K else "query"}
            embeddings[name] = embedder.embed([crop])[0].round(6).tolist()

    gallery = SkuGallery(embedder.dim)
    for sku in ENROLLED:
        gallery.enrol(sku, np.array([embeddings[f"{sku}-{n}"] for n in range(K)], np.float32))
    gallery.freeze_centre()

    cfg = FusionConfig()
    expected = {}
    for name, meta in crops.items():
        if meta["role"] != "query":
            continue
        matches = gallery.match(np.array(embeddings[name], np.float32), top_k=3)
        expected[name] = {"top1": matches[0].sku_id, "score": round(matches[0].score, 5),
                          "accepted": matches[0].score >= cfg.reject_below_cosine,
                          "ranking": [[m.sku_id, round(m.score, 5)] for m in matches]}

    mat, two = empty_mat(), scene(["pepsi", "tasto-seaweed"], seed=930)
    cv2.imwrite(str(OUT / "mat.png"), mat)
    cv2.imwrite(str(OUT / "scene.png"), two)
    boxes = [list(p.box) for p in proposer.propose(two)]

    promptpay = [
        {"target": "081-234-5678", "amount": 68.48, "payload": build_payload("081-234-5678", 68.48)},
        {"target": "0812345678", "amount": None, "payload": build_payload("0812345678")},
        {"target": "0812345678", "amount": 1234.56, "payload": build_payload("0812345678", 1234.56)},
        {"target": "1234567890123", "amount": 20.0, "payload": build_payload("1234567890123", 20.0)},
        {"target": "123456789012345", "amount": 5.0, "payload": build_payload("123456789012345", 5.0)},
    ]

    fixtures = {
        "embedder": {"dim": embedder.dim, "input": 224,
                     "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        "thresholds": {"reject_below_cosine": cfg.reject_below_cosine,
                       "ambiguous_margin": cfg.ambiguous_margin,
                       "appearance_temperature": cfg.appearance_temperature},
        "proposer": {"min_area_px": proposer.min_area_px, "diff_threshold": proposer.diff_threshold,
                     "blur": proposer.blur, "downscale": proposer.downscale,
                     "shadow_chroma_eps": proposer.shadow_chroma_eps,
                     "shadow_ratio": list(proposer.shadow_ratio)},
        "crops": crops,
        "embeddings": embeddings,
        "gallery": {"enrolled": ENROLLED, "k": K, "centre": gallery.centre.round(6).tolist()},
        "expected_matches": expected,
        "scene_boxes": boxes,
        "catalogue_weights_g": {sku: CATALOGUE[sku][4] for sku in CATALOGUE},
        "promptpay": promptpay,
        "crc16_check": {"input": "123456789", "value": crc16_ccitt("123456789")},
    }
    (OUT / "fixtures.json").write_text(json.dumps(fixtures, indent=1))
    n_ok = sum(1 for n, e in expected.items() if e["top1"] == crops[n]["sku"])
    print(f"  {len(crops)} crops, {len(expected)} queries, {n_ok} top-1 correct among enrolled, "
          f"stranger best score {expected[f'{STRANGER}-{K}']['score']:.3f} "
          f"(accepted={expected[f'{STRANGER}-{K}']['accepted']}), {len(boxes)} scene boxes")
    print(f"  written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
