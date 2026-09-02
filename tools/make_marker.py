#!/usr/bin/env python3
"""Print the markers that turn pixels into millimetres.

    python tools/make_marker.py             # four corner markers, docs/assets/markers.png
    python tools/make_marker.py --single    # one 60 mm marker, docs/assets/marker.png

Print at 100% scale - "fit to page" silently rescales it and every size
measurement is then wrong by that factor. Measure a printed black square with a
ruler before gluing anything down, and if it is not the size you asked for, put
the real figure in config/settings.json under rig.marker_mm.

Four markers: cut them out, glue one flat in each corner of the mat where
products will not cover them, then measure each marker's top-left black corner
from the mat's top-left corner and write the four positions into
config/settings.json under rig.marker_positions_mm, e.g.

    "marker_positions_mm": {"0": [20, 20], "1": [340, 20], "2": [340, 240], "3": [20, 240]}

With no positions the till uses whichever single marker it sees, as before.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.metrology import write_corner_markers_sheet, write_marker_sheet   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mm", type=float, default=60.0)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--single", action="store_true", help="one marker (id 0) instead of four")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.single:
        out = args.out or str(ROOT / "docs" / "assets" / "marker.png")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        path = write_marker_sheet(out, marker_mm=args.mm, dpi=args.dpi, marker_id=0)
    else:
        out = args.out or str(ROOT / "docs" / "assets" / "markers.png")
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        path = write_corner_markers_sheet(out, marker_mm=args.mm, dpi=args.dpi)
    print(f"  {path}")
    print(f"  each black square should measure {args.mm:g} mm on the printed page")
    print("  print at 100% scale, then set rig.marker_mm"
          + ("" if args.single else " and rig.marker_positions_mm") + " in config/settings.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
