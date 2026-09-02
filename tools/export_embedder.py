#!/usr/bin/env python3
"""Freeze the embedding backbone to ONNX.

The till runs on a Raspberry Pi, where importing torch costs seconds of start-up
and hundreds of megabytes of memory for a model that never trains.  ONNX Runtime
loads the same network in milliseconds.

    python tools/export_embedder.py [backbone] [--int8]
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.embedder import INPUT, OnnxEmbedder, TorchEmbedder   # noqa: E402


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:                      # --out somewhere outside the repo
        return str(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("backbone", nargs="?", default="mobilenet_v3_small",
                    choices=sorted(TorchEmbedder.BACKBONES))
    ap.add_argument("--out", default=None)
    ap.add_argument("--int8", action="store_true",
                    help="also write a dynamically quantised copy")
    ap.add_argument("--int8-static", action="store_true",
                    help="also write a statically quantised copy, calibrated on synthetic crops")
    args = ap.parse_args()

    out = Path(args.out or ROOT / "models" / f"{args.backbone}.onnx")
    torch_model = TorchEmbedder(args.backbone)
    torch_model.export_onnx(out)
    print(f"  {rel(out)}  {out.stat().st_size / 1e6:.1f} MB  dim={torch_model.dim}")

    if args.int8:
        from onnxruntime.quantization import QuantType, quantize_dynamic
        q = out.with_name(out.stem + "-int8.onnx")
        quantize_dynamic(str(out), str(q), weight_type=QuantType.QInt8)
        print(f"  {rel(q)}  {q.stat().st_size / 1e6:.1f} MB")

    extra = [q] if args.int8 else []
    if args.int8_static:
        # Dynamic INT8 quantises weights only and re-quantises activations per
        # call, which on a tiny convnet cost 2.2x speed for nothing (measured).
        # Static quantisation fixes activation ranges from calibration data,
        # so every conv runs in integer arithmetic end to end.
        from onnxruntime.quantization import (CalibrationDataReader, QuantFormat, QuantType,
                                              quantize_static)
        from onnxruntime.quantization.shape_inference import quant_pre_process
        from recognition.embedder import preprocess
        from tests.synthetic import CATALOGUE, scene
        from recognition.proposer import BackgroundSubtractionProposer
        from tests.synthetic import empty_mat

        prop = BackgroundSubtractionProposer()
        prop.calibrate(empty_mat())
        cal = []
        for i, sku in enumerate(CATALOGUE):
            for j in range(4):
                f = scene([sku], seed=300 + 10 * i + j)
                cal.append(max(prop.propose(f), key=lambda p: p.area_px).crop(f))

        class Reader(CalibrationDataReader):
            def __init__(self):
                self.batches = iter([{"images": preprocess([c])} for c in cal])
            def get_next(self):
                return next(self.batches, None)

        pre = out.with_name(out.stem + "-pre.onnx")
        quant_pre_process(str(out), str(pre))
        qs = out.with_name(out.stem + "-int8s.onnx")
        quantize_static(str(pre), str(qs), Reader(), quant_format=QuantFormat.QDQ,
                        activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                        per_channel=True)
        pre.unlink(missing_ok=True)
        pre.with_suffix(".onnx.data").unlink(missing_ok=True)
        print(f"  {rel(qs)}  {qs.stat().st_size / 1e6:.1f} MB  (static INT8, "
              f"{len(cal)} calibration crops)")
        extra.append(qs)

    # the export is worthless if it does not agree with the model it came from.
    # Checked on product-like crops (held-out synthetic seeds), not on noise: a
    # quantised model is calibrated for packets and is allowed to be wrong on
    # static, and noise would make every INT8 export look broken.
    from tests.synthetic import CATALOGUE as _CAT, empty_mat as _mat, scene as _scene
    from recognition.proposer import BackgroundSubtractionProposer as _BSP
    _prop = _BSP()
    _prop.calibrate(_mat())
    crops = []
    for i, sku in enumerate(_CAT):
        f = _scene([sku], seed=900 + i)
        crops.append(max(_prop.propose(f), key=lambda p: p.area_px).crop(f))
    reference = torch_model.embed(crops)
    for path in [out] + extra:
        onnx_model = OnnxEmbedder(path)
        got = onnx_model.embed(crops)
        cos = float((reference * got).sum(1).mean()
                    / (np.linalg.norm(reference, axis=1) * np.linalg.norm(got, axis=1)).mean())
        t0 = time.perf_counter()
        for _ in range(10):
            onnx_model.embed(crops[:1])
        ms = (time.perf_counter() - t0) / 10 * 1000
        print(f"    {path.name:<34} agrees with torch at cos={cos:.5f}   {ms:5.1f} ms/crop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
