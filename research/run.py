#!/usr/bin/env python3
"""Run the experiments and write the results.

    python research/run.py --source synthetic      # works today, on any machine
    python research/run.py --source captures       # the real thing, after a capture session
    python research/run.py --only E5 E6

Results land in research/results/<experiment>.json.  Nothing is printed into the
paper by hand - report.py turns these files into the tables and figures.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.proposer import BackgroundSubtractionProposer   # noqa: E402
from research import experiments as X                            # noqa: E402
from research.dataset import get_source, make_split              # noqa: E402

RESULTS = ROOT / "research" / "results"


def environment() -> dict:
    """Recorded with every result, because "which machine" changes the answer."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = None
    return {"python": platform.python_version(), "machine": platform.machine(),
            "platform": platform.platform(), "commit": commit}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="synthetic", choices=("synthetic", "captures", "folder"))
    ap.add_argument("--root", type=Path, default=None,
                    help="with --source folder: a directory with one sub-folder per SKU")
    ap.add_argument("--max-skus", type=int, default=None, help="with --source folder")
    ap.add_argument("--backbone", default="mobilenet_v3_small")
    ap.add_argument("--backbones", nargs="*", default=None,
                    help="E3 rows, e.g. mobilenet_v3_small mobileclip_b dinov2_vits14")
    ap.add_argument("--k", type=int, default=X.DEFAULT_K)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--retrain-hours", type=float, default=None,
                    help="measured hours the team spent building the v1 closed-set model")
    ap.add_argument("--tag", default=None,
                    help="suffix for the results file, e.g. --tag packages -> E9-packages.json")
    ap.add_argument("--only", nargs="*", default=None,
                    help="experiment ids, e.g. E2 E5")
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    source = get_source(args.source, root=args.root, max_skus=args.max_skus)
    skus = source.skus()
    split = make_split(skus, seed=args.seed)
    if args.source == "folder":
        from recognition.proposer import WholeFrameProposer
        proposer = WholeFrameProposer()               # pre-cropped: no mat to subtract
    else:
        proposer = BackgroundSubtractionProposer()
        proposer.calibrate(source.background())
    embedder = X.make_embedder(args.backbone)

    print(f"source {source.name}: {len(skus)} products")
    print(f"  seen   {split.seen}")
    print(f"  unseen {split.unseen}   <- everything is scored on these\n")

    jobs = {
        "E2": lambda: X.e2_fewshot_vs_k(source, embedder, proposer, split),
        "E3": lambda: X.e3_backbones(source, proposer, split, k=args.k,
                                     **({"backbones": args.backbones} if args.backbones else {})),
        "E4": lambda: X.e4_temporal_voting(source, embedder, proposer, split, k=args.k),
        "E5": lambda: X.e5_open_set(source, embedder, proposer, split, k=args.k),
        "E6": lambda: X.e6_fusion(source, embedder, proposer, split, k=args.k),
        "E7": lambda: X.e7_basket_error(source, embedder, proposer, split, k=args.k,
                                        seed=args.seed),
        "E8": lambda: X.e8_enrolment_cost(source, embedder, proposer, k=args.k,
                                          retrain_hours=args.retrain_hours),
        "E9": lambda: X.e9_public_benchmark(source, embedder, split, k=args.k),
    }
    # E9 is the public-benchmark run: only meaningful on a folder source, and
    # E6-E8 need weights and prices a benchmark does not have
    default_jobs = ["E9"] if args.source == "folder" else [j for j in jobs if j != "E9"]
    chosen = args.only or default_jobs

    for name in chosen:
        if name not in jobs:
            print(f"  {name}: no such experiment")
            continue
        print(f"  running {name} ...", end="", flush=True)
        try:
            result = jobs[name]()
        except Exception as e:
            print(f" FAILED: {e}")
            continue
        result["environment"] = environment()
        result["split"] = split.to_dict()
        stem = f"{name}-{args.tag}" if args.tag else name
        (RESULTS / f"{stem}.json").write_text(json.dumps(result, indent=2))
        print(f" -> results/{stem}.json")

    print("\nnow:  python research/report.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
