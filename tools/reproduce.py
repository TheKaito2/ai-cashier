#!/usr/bin/env python3
"""Regenerate every table and figure in the paper from a clean checkout.

A reviewer should be able to run one command and get the same artefacts we did,
without reading the harness first.  This is that command.

    python tools/reproduce.py            # synthetic experiments, then the tables
    python tools/reproduce.py --list     # say what exists, change nothing

It will not overwrite results that came from photographs.  Synthetic runs exist
to prove the harness works; quietly replacing a measured result with a rendered
one would be the single most damaging thing this script could do, so it refuses
and says which files stopped it.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "research" / "results"

#: a result from these sources was measured on photographs and is not ours to
#: regenerate: `captures` is the rig, `folder:...` is a public benchmark whose
#: dataset a fresh checkout does not have
MEASURED = ("captures", "folder:")


def existing() -> list[tuple[Path, str]]:
    out = []
    for path in sorted(RESULTS.glob("*.json")):
        try:
            out.append((path, json.loads(path.read_text()).get("source", "?")))
        except json.JSONDecodeError:
            out.append((path, "unreadable"))
    return out


def measured(source: str) -> bool:
    return any(source.startswith(m) for m in MEASURED)


def report(rows: list[tuple[Path, str]]) -> None:
    if not rows:
        print("  no results yet")
        return
    print(f"  {'file':<34}{"source":<32}provenance")
    print("  " + "-" * 82)
    for path, source in rows:
        kind = "measured - not regenerated" if measured(source) else "synthetic"
        print(f"  {path.name:<34}{source:<32}{kind}")


def run(*command: str) -> int:
    print(f"\n$ {' '.join(command)}")
    return subprocess.call([sys.executable, *command], cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="show provenance and exit")
    args = ap.parse_args()

    rows = existing()
    print("results already present:")
    report(rows)
    if args.list:
        return 0

    blocking = [p.name for p, s in rows if s == "captures"]
    if blocking:
        print("\nrefusing to run: these came from photographs, and a synthetic run "
              "would overwrite them --")
        for name in blocking:
            print(f"  research/results/{name}")
        print("\nMove them aside first if you really mean to regenerate from "
              "rendered images.")
        return 1

    if run("research/run.py", "--source", "synthetic") != 0:
        return 1
    if run("research/report.py") != 0:
        return 1

    print("\nprovenance of what the paper will now contain:")
    report(existing())
    print("\n  Synthetic rows verify that the harness runs. They are not evidence "
          "about real products,\n  and every generated table says so at the top. "
          "The public-benchmark rows are photographs,\n  taken by somebody else "
          "(docs/kb/05-research.md).")
    print("\n  Build the paper:  cd paper && make")
    return 0


if __name__ == "__main__":
    sys.exit(main())
