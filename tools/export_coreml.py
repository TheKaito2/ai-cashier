#!/usr/bin/env python3
"""Freeze the embedding backbone for the iPhone.

Core ML cannot read the ONNX file the till uses (coremltools dropped its ONNX
converter), so the same torchvision trunk is traced again here, with the
ImageNet normalisation folded into the graph so the Swift side passes plain
pixels.  Run it in the conversion venv (torch 2.7, coremltools 9.0):

    uv venv .venv-coreml --python 3.12
    uv pip install --python .venv-coreml/bin/python "torch==2.7.*" "torchvision==0.22.*" \\
        "coremltools==9.0" opencv-contrib-python onnxruntime pillow
    .venv-coreml/bin/python tools/export_coreml.py

Writes ios/AICashier/Resources/MobileNetV3Small.mlpackage and prints the cosine
between the Core ML output and the ONNX output on synthetic product crops.
Anything under 0.98 fails: the phone would then not share the till's gallery.
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.embedder import INPUT, MEAN, STD, OnnxEmbedder, TorchEmbedder   # noqa: E402

OUT = ROOT / "ios" / "AICashier" / "Resources" / "MobileNetV3Small.mlpackage"


def main() -> int:
    import coremltools as ct
    import torch
    from PIL import Image

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--min-cosine", type=float, default=0.98)
    args = ap.parse_args()

    class Normalised(torch.nn.Module):
        """Pixels in 0..1 -> ImageNet-normalised -> 576-d trunk output."""
        def __init__(self, net):
            super().__init__()
            self.net = net
            self.register_buffer("mean", torch.tensor(MEAN).view(1, 3, 1, 1))
            self.register_buffer("std", torch.tensor(STD).view(1, 3, 1, 1))

        def forward(self, x):
            return self.net((x - self.mean) / self.std)

    trunk = TorchEmbedder("mobilenet_v3_small")
    model = Normalised(trunk.net).eval()
    traced = torch.jit.trace(model, torch.rand(1, 3, INPUT, INPUT))
    ml = ct.convert(
        traced,
        convert_to="mlprogram",
        inputs=[ct.ImageType(name="image", shape=(1, 3, INPUT, INPUT), scale=1 / 255.0,
                             color_layout=ct.colorlayout.RGB)],
        outputs=[ct.TensorType(name="embedding")],
        minimum_deployment_target=ct.target.iOS17,
        # FLOAT32: 4 MB instead of 2, and no half-precision surprises on any compute unit
        compute_precision=ct.precision.FLOAT32,
    )
    ml.short_description = "AI Cashier product embedder: MobileNetV3-Small trunk, 576-d"
    ml.author = "Group 3, Assumption College Sriracha"
    ml.version = (ROOT / "VERSION").read_text().strip()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ml.save(str(out))
    print(f"  {out}  ({sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) / 1e6:.1f} MB)")

    # fidelity against the till's ONNX embedder on product-like crops
    import cv2
    from recognition.proposer import BackgroundSubtractionProposer
    from tests.synthetic import CATALOGUE, empty_mat, views

    onnx = OnnxEmbedder(ROOT / "models" / "mobilenet_v3_small.onnx")
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(empty_mat())
    worst = 1.0
    for sku in CATALOGUE:
        for frame in views(sku, 2, seed=100):
            crop = max(proposer.propose(frame), key=lambda p: p.area_px).crop(frame)
            a = onnx.embed([crop])[0]
            rgb = cv2.cvtColor(cv2.resize(crop, (INPUT, INPUT), interpolation=cv2.INTER_AREA),
                               cv2.COLOR_BGR2RGB)
            b = np.asarray(ml.predict({"image": Image.fromarray(rgb)})["embedding"], np.float32).ravel()
            cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
            worst = min(worst, cos)
    print(f"  Core ML vs ONNX: worst cosine {worst:.4f} over {2 * len(CATALOGUE)} crops")
    if worst < args.min_cosine:
        print(f"  FAILED: below {args.min_cosine}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
