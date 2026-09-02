"""Turning a crop of a product into a vector.

This is what replaces the closed-set classifier.  The classifier could only
answer "which of my twelve classes is this"; an embedding answers "what does
this look like", and the answer stays meaningful for products the model has
never seen.  That is the whole reason a new SKU can be enrolled in seconds
instead of retrained overnight.

Two implementations: torch for development and for the reference backbones, and
ONNX Runtime for the Raspberry Pi, where torch is far too heavy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

#: ImageNet statistics - every backbone here was pretrained with them
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
INPUT = 224


class Embedder(Protocol):
    dim: int
    def embed(self, crops: list[np.ndarray]) -> np.ndarray: ...


def preprocess(crops: list[np.ndarray], size: int = INPUT,
               mean: np.ndarray = MEAN, std: np.ndarray = STD) -> np.ndarray:
    """BGR uint8 crops -> NCHW float32 batch, normalised (ImageNet by default)."""
    batch = np.empty((len(crops), size, size, 3), dtype=np.float32)
    for i, crop in enumerate(crops):
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        batch[i] = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_AREA)
    batch = (batch / 255.0 - mean) / std
    return np.ascontiguousarray(batch.transpose(0, 3, 1, 2))


class TorchEmbedder:
    """Development and reference backbones.

    `mobilenet_v3_small` is the one that ships; the larger backbones exist to
    measure how much accuracy is being traded away for speed (research/exp3).
    """

    BACKBONES = {
        "mobilenet_v3_small": 576,
        "mobilenet_v3_large": 960,
        "resnet18": 512,
    }

    #: research-only encoders (requirements-research.txt: open_clip_torch).
    #: The 2026 grocery-retrieval study found small, well-trained CLIP-class
    #: encoders competitive with far larger models (docs/research/05, P27),
    #: so they are the E3 rows worth adding.  DINOv3 distilled weights are
    #: gated at time of writing; DINOv2-S/14 is the public stand-in.
    #: name -> (open_clip model, pretrained tag, dim, mean, std)
    CLIP_BACKBONES = {
        "mobileclip_b":  ("MobileCLIP-B",       "datacompdr",  512,
                          (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        "mobileclip_s1": ("MobileCLIP-S1",      "datacompdr",  512,
                          (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        "siglip_b16":    ("ViT-B-16-SigLIP",    "webli",       768,
                          (0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    }
    HUB_BACKBONES = {
        "dinov2_vits14": ("facebookresearch/dinov2", "dinov2_vits14", 384),
    }

    def __init__(self, backbone: str = "mobilenet_v3_small", weights: str = "DEFAULT"):
        import torch
        import torchvision.models as tv

        self.name = backbone
        self._torch = torch
        self.mean, self.std = MEAN, STD

        if backbone in self.CLIP_BACKBONES:
            self._load_open_clip(backbone)
            return
        if backbone in self.HUB_BACKBONES:
            self._load_hub(backbone)
            return
        if backbone not in self.BACKBONES:
            raise ValueError(f"unknown backbone {backbone!r}; try one of "
                             f"{sorted(self.BACKBONES) + sorted(self.CLIP_BACKBONES) + sorted(self.HUB_BACKBONES)}")
        self.dim = self.BACKBONES[backbone]

        model = getattr(tv, backbone)(weights=weights)
        # keep the trunk, drop the 1000-class head: we want the representation,
        # not an ImageNet label
        if backbone.startswith("mobilenet"):
            self.net = torch.nn.Sequential(model.features, model.avgpool, torch.nn.Flatten())
        else:
            self.net = torch.nn.Sequential(*list(model.children())[:-1], torch.nn.Flatten())
        self.net.eval()

    def _load_open_clip(self, backbone: str) -> None:
        import open_clip
        arch, tag, self.dim, mean, std = self.CLIP_BACKBONES[backbone]
        model, _, _ = open_clip.create_model_and_transforms(arch, pretrained=tag)
        self.mean, self.std = np.array(mean, np.float32), np.array(std, np.float32)

        class ImageOnly(self._torch.nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m
            def forward(self, x):
                return self.m.encode_image(x)
        self.net = ImageOnly(model).eval()

    def _load_hub(self, backbone: str) -> None:
        repo, name, self.dim = self.HUB_BACKBONES[backbone]
        self.net = self._torch.hub.load(repo, name).eval()

    @property
    def device(self):
        return next(self.net.parameters()).device

    def to(self, device):
        self.net.to(device)
        return self

    def embed(self, crops: list[np.ndarray]) -> np.ndarray:
        if not crops:
            return np.zeros((0, self.dim), dtype=np.float32)
        x = self._torch.from_numpy(preprocess(crops, mean=self.mean, std=self.std)).to(self.device)
        with self._torch.no_grad():
            out = self.net(x)
        return out.detach().cpu().numpy().astype(np.float32)

    def export_onnx(self, path: str | Path) -> Path:
        """Freeze to ONNX so the Pi never has to import torch."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        dummy = self._torch.zeros(1, 3, INPUT, INPUT, device=self.device)
        self._torch.onnx.export(
            self.net, dummy, str(path),
            input_names=["images"], output_names=["embedding"],
            dynamic_axes={"images": {0: "batch"}, "embedding": {0: "batch"}},
            opset_version=17)
        return path


class OnnxEmbedder:
    """What actually runs on the till."""

    def __init__(self, path: str | Path, providers: list[str] | None = None):
        import onnxruntime as ort
        self.session = ort.InferenceSession(
            str(path), providers=providers or ["CPUExecutionProvider"])
        self._input = self.session.get_inputs()[0].name
        dim = self.session.get_outputs()[0].shape[-1]
        if not isinstance(dim, int):          # quantised graphs carry a symbolic dim
            probe = np.zeros((1, 3, INPUT, INPUT), np.float32)
            dim = self.session.run(None, {self._input: probe})[0].shape[-1]
        self.dim = int(dim)
        self.name = Path(path).stem

    def embed(self, crops: list[np.ndarray]) -> np.ndarray:
        if not crops:
            return np.zeros((0, self.dim), dtype=np.float32)
        out = self.session.run(None, {self._input: preprocess(crops)})[0]
        return np.asarray(out, dtype=np.float32)
