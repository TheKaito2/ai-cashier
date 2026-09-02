"""Where the experiments get their images.

Two sources, one interface:

  synthetic  - tests/synthetic.py.  Runs today, on any machine, with no rig and
               no products.  Proves the harness itself works and that every
               table regenerates.  Not evidence about real crisps.
  captures   - photographs taken on the actual rig by research/capture.py.
               This is what the paper reports.

Keeping both behind one interface means the experiment code is written, run and
debugged before the capture session, so the session produces numbers instead of
discovering bugs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "research" / "data" / "captures"
MANIFEST = ROOT / "research" / "data" / "manifest.json"
MAT = ROOT / "research" / "data" / "mat_background.png"


@dataclass(frozen=True)
class Sku:
    sku_id: str
    name: str
    price: float
    weight_g: float | None
    category: str = "other"
    #: True for the products the surviving v1 detector was trained on, so the
    #: closed-set baseline can be evaluated on exactly its own classes
    in_legacy_model: bool = False


class Source:
    """A set of products and, for each, several photographs of it on the mat."""

    def skus(self) -> list[Sku]: ...
    def frames(self, sku_id: str) -> list[np.ndarray]: ...
    def background(self) -> np.ndarray: ...
    name: str = "source"


class SyntheticSource(Source):
    name = "synthetic"

    def __init__(self, views_per_sku: int = 14):
        from tests.synthetic import CATALOGUE, empty_mat
        self._catalogue = CATALOGUE
        self._empty = empty_mat
        self.views_per_sku = views_per_sku

    def skus(self) -> list[Sku]:
        prices = {"lays-flat-original": 20.0, "lays-ridged-original": 22.0,
                  "tasto-seaweed": 24.0, "pepsi": 14.0, "crystal-water": 7.0,
                  "never-enrolled-snack": 18.0}
        return [Sku(sku_id=s, name=s.replace("-", " ").title(),
                    price=prices.get(s, 20.0), weight_g=spec[4],
                    category="drinks" if s in ("pepsi", "crystal-water") else "chips")
                for s, spec in self._catalogue.items()]

    def frames(self, sku_id: str) -> list[np.ndarray]:
        from tests.synthetic import scene
        # a fixed offset per sku so gallery and probe frames never coincide
        return [scene([sku_id], seed=1000 + i) for i in range(self.views_per_sku)]

    def background(self) -> np.ndarray:
        return self._empty()


class CaptureSource(Source):
    name = "captures"

    def __init__(self, root: Path = CAPTURES, manifest: Path = MANIFEST):
        if not manifest.exists():
            raise SystemExit(
                f"{manifest} not found.\n"
                "Photograph the products first:  python research/capture.py --help")
        self.root = root
        self.manifest = json.loads(manifest.read_text())

    def skus(self) -> list[Sku]:
        return [Sku(sku_id=k, name=v["name"], price=v["price"],
                    weight_g=v.get("weight_g"), category=v.get("category", "other"),
                    in_legacy_model=v.get("in_legacy_model", False))
                for k, v in sorted(self.manifest.items())]

    def frames(self, sku_id: str) -> list[np.ndarray]:
        paths = sorted((self.root / sku_id).glob("*.jpg"))
        frames = [cv2.imread(str(p)) for p in paths]
        return [f for f in frames if f is not None]

    def background(self) -> np.ndarray:
        img = cv2.imread(str(MAT))
        if img is None:
            raise SystemExit(f"{MAT} not found - capture the empty mat first")
        return img


class ImageFolderSource(Source):
    """A public benchmark laid out as one folder per SKU of pre-cropped images.

        root/
          <sku_id>/  *.jpg | *.png        (product photographs, already cropped)
          meta.json                        optional: {"<sku_id>": {"name":..,
                                           "price":.., "weight_g":..}}

    This is how RPC's single-product training images (one folder per category),
    GroceryVision's MPR gallery images and MIMEX all fit with a few lines of
    shell.  There is no mat to subtract, so experiment E9 pairs this source with
    `WholeFrameProposer`.  Only the first `max_skus` folders are used when set,
    so a 200-SKU benchmark can be smoke-tested on a laptop.
    """
    name = "folder"

    def __init__(self, root: Path, max_skus: int | None = None, max_views: int = 14):
        self.root = Path(root)
        if not self.root.is_dir():
            raise SystemExit(f"{self.root} is not a directory")
        meta_path = self.root / "meta.json"
        self.meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        dirs = sorted(d for d in self.root.iterdir() if d.is_dir())
        self._dirs = dirs[:max_skus] if max_skus else dirs
        self.max_views = max_views
        self.name = f"folder:{self.root.name}"

    def skus(self) -> list[Sku]:
        out = []
        for d in self._dirs:
            m = self.meta.get(d.name, {})
            out.append(Sku(sku_id=d.name, name=m.get("name", d.name),
                           price=float(m.get("price", 1.0)), weight_g=m.get("weight_g"),
                           category=m.get("category", "other")))
        return out

    def frames(self, sku_id: str) -> list[np.ndarray]:
        paths = sorted(p for p in (self.root / sku_id).iterdir()
                       if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:self.max_views]
        frames = [cv2.imread(str(p)) for p in paths]
        return [f for f in frames if f is not None]

    def background(self) -> np.ndarray:
        return np.zeros((8, 8, 3), np.uint8)      # nothing to subtract


def get_source(name: str, root: Path | None = None, max_skus: int | None = None) -> Source:
    if name == "synthetic":
        return SyntheticSource()
    if name == "folder":
        if root is None:
            raise SystemExit("--source folder needs --root <dir with one folder per SKU>")
        return ImageFolderSource(root, max_skus=max_skus)
    return CaptureSource()


@dataclass(frozen=True)
class Split:
    """Which products the embedding may learn from, and which test it.

    The distinction the whole claim rests on: few-shot enrolment is only
    interesting if it works on products the representation has never seen.
    Evaluating on SKUs that were in the embedding's training set would measure
    nothing and a reviewer would say so.
    """
    seen: list[str]        # available for fine-tuning a representation
    unseen: list[str]      # only ever enrolled from k views, never trained on

    def to_dict(self) -> dict:
        return {"seen": self.seen, "unseen": self.unseen}


def make_split(skus: list[Sku], unseen_fraction: float = 0.5, seed: int = 0) -> Split:
    ids = sorted(s.sku_id for s in skus)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(ids))
    n_unseen = max(1, int(round(len(ids) * unseen_fraction)))
    unseen = sorted(ids[i] for i in order[:n_unseen])
    return Split(seen=sorted(set(ids) - set(unseen)), unseen=unseen)
