#!/usr/bin/env python3
"""Measure how much the load cell wanders when nothing changes.

    python tools/scale_drift.py --minutes 30 --known-mass 500
    python tools/scale_drift.py --dry-run                # simulated cell

Leave a known mass on the pan and log the reading every few seconds.  The
result is the number docs/HARDWARE.md tells you to report: creep over the first
minutes and drift with temperature over a shift.  If the spread exceeds the
item tolerance in recognition/fusion.py, the basket check cannot be trusted
without re-taring between baskets (which the till does anyway).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=30.0)
    ap.add_argument("--every", type=float, default=5.0, help="seconds between samples")
    ap.add_argument("--known-mass", type=float, default=None, help="grams on the pan")
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "results" / "scale_drift.csv")
    ap.add_argument("--dry-run", action="store_true", help="simulated cell, 20 fast samples")
    args = ap.parse_args()

    if args.dry_run:
        from recognition.scale import SimulatedScale
        scale = SimulatedScale(noise_g=0.8, drift_g_per_min=0.5)
        if args.known_mass:
            scale.place(args.known_mass)
        n, every = 20, 0.05
    else:
        import json
        from recognition.scale import HX711Scale
        import paths
        cfg = json.loads(paths.settings_path().read_text())["scale"]
        scale = HX711Scale(cfg["dout_pin"], cfg["sck_pin"], cfg["counts_per_gram"], cfg["offset_counts"])
        n, every = int(args.minutes * 60 / args.every), args.every

    args.out.parent.mkdir(parents=True, exist_ok=True)
    readings = []
    with args.out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "grams", "known_mass_g"])
        for i in range(n):
            grams = scale.read_grams()
            readings.append(grams)
            w.writerow([datetime.now().isoformat(), f"{grams:.2f}", args.known_mass or ""])
            f.flush()
            if i % 12 == 0 or args.dry_run:
                print(f"  {i * every / 60:6.1f} min  {grams:8.2f} g")
            time.sleep(every)

    lo, hi = min(readings), max(readings)
    print(f"\n  {len(readings)} samples over {n * every / 60:.1f} min: "
          f"min {lo:.2f} g  max {hi:.2f} g  spread {hi - lo:.2f} g")
    if args.known_mass:
        print(f"  mean error vs {args.known_mass:.0f} g: "
              f"{sum(readings) / len(readings) - args.known_mass:+.2f} g")
    print(f"  written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
