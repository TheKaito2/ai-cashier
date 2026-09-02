#!/usr/bin/env python3
"""Two-point calibration for the load cell.

An HX711 returns raw counts. Two readings turn those into grams: one with the pan
empty (the offset) and one with a known mass (the slope).

    python tools/calibrate_scale.py --known-mass 500

Use a mass you can trust. A 500 g bag of sugar is close enough for a school
project; a calibration weight is better. Whatever you use, weigh it on a shop
scale first and type that number, not what the packet claims.

Redo this if the cell is remounted, if the mat is changed, or if readings drift.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import paths                                          # noqa: E402

SETTINGS = paths.settings_path()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--known-mass", type=float, required=True, help="grams")
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="use a simulated cell, to rehearse the procedure")
    args = ap.parse_args()

    settings = json.loads(SETTINGS.read_text())
    cfg = settings.setdefault("scale", {})

    if args.dry_run:
        state = {"mass": 0.0}
        print("DRY RUN - no hardware is being read.\n")

        def read_raw():
            return 120000 + 412.0 * state["mass"]

        import builtins
        original_input = builtins.input

        def prompt(msg=""):
            original_input(msg)
            # only the second prompt means "the mass is now on the pan"; the
            # first is "the pan is empty", and loading it there would make the
            # two readings identical
            if "reference mass" in str(msg):
                state["mass"] = args.known_mass
            return ""

        builtins.input = prompt
    else:
        from recognition.scale import HX711Scale
        cell = HX711Scale(cfg.get("dout_pin", 5), cfg.get("sck_pin", 6), 1.0, 0.0)
        read_raw = cell.read_raw

    from recognition.scale import calibrate

    print(f"Calibrating against {args.known_mass:g} g.")
    print("Take everything off the pan and let it settle, then press Enter.")
    input()
    counts_per_gram, offset = calibrate(read_raw, args.known_mass, args.samples)

    print(f"\n  counts per gram : {counts_per_gram:.3f}")
    print(f"  offset counts   : {offset:.1f}")
    print(f"  resolution      : {1.0 / abs(counts_per_gram) * 1000:.2f} mg per count")

    if args.dry_run:
        print("\nDry run - settings not written.")
        return 0

    cfg["counts_per_gram"] = round(counts_per_gram, 4)
    cfg["offset_counts"] = round(offset, 1)
    SETTINGS.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
    print(f"\nWritten to {SETTINGS}.")
    print("Check it: put a different known mass on the pan and run")
    print("  python -c \"from recognition.scale import HX711Scale; ...\"")
    print("If it reads more than a couple of grams out, calibrate again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
