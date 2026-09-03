#!/usr/bin/env python3
"""Put the measured rejection threshold into the till.

E5 (research/run.py) picks the lowest cosine that still accepts 95 % of the
enrolled products' held-out views, and reports how many strangers slip past
it.  This writes that number where the till reads it - the `reject_below_cosine`
setting in the shop database (scanner/ui/main_window.py) - and prints the line
to paste into the iPhone app, which carries its own copy.

    python tools/set_threshold.py                      # research/results/E5.json
    python tools/set_threshold.py results/E5.json --dry-run

Refuses a result that says `insufficient_data`: a threshold from two products
is a guess with a decimal point.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.calibration import ThresholdReport   # noqa: E402

DEFAULT = ROOT / "research" / "results" / "E5.json"
SWIFT = ROOT / "ios" / "AICashier" / "Sources" / "Recognition" / "Fusion.swift"


def report_from(result: dict) -> ThresholdReport:
    if result.get("experiment") != "E5":
        raise ValueError(f"not an E5 result: {result.get('experiment')!r}")
    if result.get("insufficient_data"):
        raise ValueError(result.get("error", "E5 did not run: insufficient data"))
    return ThresholdReport(threshold=float(result["threshold"]), tpr=float(result["tpr"]),
                           fpr=float(result["fpr"]), auroc=float(result["auroc"]),
                           fpr_at_95_tpr=float(result["fpr_at_95_tpr"]))


def apply(result: dict, db) -> ThresholdReport:
    """Validate the E5 result and write its threshold to the shop database."""
    r = report_from(result)
    db.set_setting("reject_below_cosine", round(r.threshold, 4))
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result", nargs="?", type=Path, default=DEFAULT)
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()
    if not args.result.exists():
        print(f"{args.result} not found - run:  python research/run.py --source captures --only E5")
        return 1
    result = json.loads(args.result.read_text())
    try:
        r = report_from(result)
    except ValueError as e:
        print(f"refusing: {e}")
        return 1
    print(f"  {args.result.name}  source={result.get('source')}  backbone={result.get('backbone')}")
    print(f"  {r}")
    if not args.dry_run:
        from server.services.database import Database
        apply(result, Database())
        print("  written: settings.reject_below_cosine")
    print(f"  iPhone ({SWIFT.relative_to(ROOT)}):  var rejectBelowCosine: Float = {r.threshold:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
