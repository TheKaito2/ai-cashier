#!/usr/bin/env python3
"""Measure the pipeline where it actually runs.

    python research/bench.py                    # on the Raspberry Pi
    python research/bench.py --json results/bench-pi5.json

Every latency figure in the paper must come from this script run on the Pi. A
laptop number is not a Pi number, and the difference is the whole point of
choosing a small backbone. The output records which machine produced it so a
laptop run can never be quoted as a Pi run by mistake.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.embedder import OnnxEmbedder                    # noqa: E402
from recognition.gallery import SkuGallery                       # noqa: E402
from recognition.metrology import MatMetrology                   # noqa: E402
from recognition.pipeline import RecognitionPipeline             # noqa: E402
from recognition.proposer import BackgroundSubtractionProposer   # noqa: E402


def cpu_temperature_c() -> float | None:
    """Pi 5 throttles when it gets hot, and a benchmark that ignores that
    reports a speed the till will not sustain."""
    for path in ("/sys/class/thermal/thermal_zone0/temp",):
        p = Path(path)
        if p.exists():
            try:
                return int(p.read_text().strip()) / 1000.0
            except Exception:
                return None
    return None


def timed(fn, n: int) -> dict:
    fn()                                   # warm up: the first call is not typical
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    return {"mean_ms": statistics.fmean(samples),
            "median_ms": statistics.median(samples),
            "p95_ms": samples[int(0.95 * (len(samples) - 1))],
            "n": n}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", default="mobilenet_v3_small")
    ap.add_argument("--items", type=int, default=3, help="products on the mat")
    ap.add_argument("--reps", type=int, default=50)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    from tests.synthetic import CATALOGUE, empty_mat, scene
    skus = list(CATALOGUE)[:args.items]
    background = empty_mat()
    frame = scene(skus, seed=7)

    embedder = OnnxEmbedder(ROOT / "models" / f"{args.backbone}.onnx")
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(background)
    gallery = SkuGallery(embedder.dim)
    rng = np.random.default_rng(0)
    for s in skus:
        gallery.enrol(s, rng.normal(size=(5, embedder.dim)))

    proposals = proposer.propose(frame)
    crops = [p.crop(frame) for p in proposals]
    pipeline = RecognitionPipeline(proposer, embedder, gallery)

    def full_frame():
        pipeline.reset()
        pipeline.process(frame)

    stages = {
        "propose": timed(lambda: proposer.propose(frame), args.reps),
        "embed_one_crop": timed(lambda: embedder.embed(crops[:1]), args.reps),
        f"embed_{len(crops)}_crops": timed(lambda: embedder.embed(crops), args.reps),
        "gallery_match": timed(lambda: gallery.match(rng.normal(size=embedder.dim)), 200),
        "metrology": timed(lambda: MatMetrology.from_frame(frame, 60.0), 20),
        "full_frame_cold": timed(full_frame, max(10, args.reps // 5)),
    }

    # the till's SCAN button: reset, then five frames on the UI thread.  If this
    # exceeds ~200 ms on the Pi the scan moves to a worker thread (docs/research/09, D4)
    def scan_five():
        pipeline.reset()
        for _ in range(5):
            pipeline.process(frame)
    stages["scan_5_frames"] = timed(scan_five, max(10, args.reps // 5))

    # a settled track is not re-embedded, which is the steady state during a scan
    pipeline.reset()
    for _ in range(8):
        pipeline.process(frame)
    stages["full_frame_settled"] = timed(lambda: pipeline.process(frame), args.reps)

    fps = 1000.0 / stages["full_frame_settled"]["mean_ms"]
    out = {
        "backbone": args.backbone, "items_on_mat": len(crops),
        "frame_size": list(frame.shape[:2]),
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "processor": platform.processor(), "python": platform.python_version()},
        "cpu_temperature_c_start": cpu_temperature_c(),
        "stages": stages,
        "sustained_fps_settled": fps,
    }
    out["cpu_temperature_c_end"] = cpu_temperature_c()

    print(f"{args.backbone} - {len(crops)} products on the mat")
    print(f"machine: {platform.platform()}\n")
    print(f"  {'stage':<24}{'mean':>9}{'median':>9}{'p95':>9}")
    print("  " + "-" * 51)
    for name, s in stages.items():
        print(f"  {name:<24}{s['mean_ms']:>8.1f}{s['median_ms']:>9.1f}{s['p95_ms']:>9.1f}   ms")
    print(f"\n  sustained: {fps:.1f} FPS once tracks have settled")
    if out["cpu_temperature_c_start"] is None:
        print("\n  NOTE: no CPU temperature available - this is not a Raspberry Pi. "
              "Do not quote these numbers as Pi figures.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(out, indent=2))
        print(f"\n  written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
