"""The product gallery: k reference vectors per SKU, matched by cosine similarity.

Enrolling a product is appending rows to this table.  That is the whole
mechanism - there is no retraining step anywhere in the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

#: with fewer products than this the mean is mostly one product's own
#: direction, and pinning it would do more harm than good.  research/E5
#: refuses to calibrate a threshold below the same count.
MIN_SKUS_TO_FREEZE = 4


@dataclass(frozen=True)
class Match:
    sku_id: str
    score: float          # cosine similarity, -1..1
    n_views: int          # how many reference views this SKU has


def l2_normalise(v: np.ndarray) -> np.ndarray:
    """Row-wise unit length, so a dot product is a cosine similarity."""
    v = np.atleast_2d(np.asarray(v, dtype=np.float32))
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    # a zero vector has no direction; leave it at zero rather than dividing by 0
    return v / np.maximum(norms, 1e-12)


class PcaWhitening:
    """Centre, decorrelate and equalise the embedding space (Jégou & Chum, ECCV
    2012).  Mean-centring removes the direction every image shares; whitening
    also removes the co-occurring directions that dominate an ImageNet trunk's
    features.  Fitted on products that are *not* the ones being recognised, so
    the reference frame is independent of what the shop enrols - the long-term
    answer to the moving-centre problem (docs/research/09, D7).  Research only
    until E3 says otherwise."""

    def __init__(self, mean: np.ndarray, components: np.ndarray, scale: np.ndarray):
        self.mean, self.components, self.scale = mean, components, scale

    @classmethod
    def fit(cls, vectors: np.ndarray, n_components: int | None = None,
            eps: float = 1e-6) -> "PcaWhitening":
        x = l2_normalise(vectors)
        mean = x.mean(axis=0)
        u, s, vt = np.linalg.svd(x - mean, full_matrices=False)
        n = n_components or len(s)
        var = (s[:n] ** 2) / max(1, len(x) - 1)
        return cls(mean.astype(np.float32), vt[:n].astype(np.float32),
                   (1.0 / np.sqrt(var + eps)).astype(np.float32))

    def transform(self, vectors: np.ndarray) -> np.ndarray:
        x = l2_normalise(vectors) - self.mean
        return l2_normalise((x @ self.components.T) * self.scale)


class SkuGallery:
    """Reference vectors for every enrolled SKU.

    Small enough that an exact search is a single matmul - a few hundred SKUs at
    k=5 is a couple of thousand rows, which is microseconds.  No index needed.

    Matching happens on *centred* vectors.  An ImageNet trunk was never trained
    to make its features contrastive, so every pair of natural images already
    points in roughly the same direction: measured on the synthetic set, two
    completely different products still scored 0.81 cosine, which leaves no
    room for a rejection threshold.  Subtracting the gallery mean removes that
    shared component and drops the same figure to -0.18, while views of one
    product stay near 0.88.

    The centre can be **frozen**.  While it floats with the gallery mean, every
    enrolment moves every existing score, and a rejection threshold calibrated
    last week was calibrated in a coordinate system that no longer exists
    (docs/research/09, D7).  Once there are enough products to centre on, the
    till pins the centre; enrolling more products then adds rows and nothing
    else.  Re-centring is an explicit act, done together with recalibrating the
    threshold.  Raw vectors are what is stored, so that is always possible.
    """

    def __init__(self, dim: int):
        self.dim = int(dim)
        self.vectors = np.zeros((0, self.dim), dtype=np.float32)
        self.sku_ids: list[str] = []
        self.centre: np.ndarray | None = None        # frozen reference, or None
        self._centred: np.ndarray | None = None      # cache, rebuilt on change
        self._mean: np.ndarray | None = None

    # ------------------------------------------------------------- enrolment

    def enrol(self, sku_id: str, vectors: np.ndarray) -> int:
        """Add reference views for a SKU. Returns the SKU's total view count."""
        v = l2_normalise(vectors)
        if v.shape[1] != self.dim:
            raise ValueError(f"expected {self.dim}-d vectors, got {v.shape[1]}")
        self.vectors = np.vstack([self.vectors, v])
        self.sku_ids.extend([sku_id] * len(v))
        self._invalidate()
        return self.count(sku_id)

    def remove(self, sku_id: str) -> int:
        """Drop every view of a SKU. Returns how many were removed."""
        keep = [i for i, s in enumerate(self.sku_ids) if s != sku_id]
        removed = len(self.sku_ids) - len(keep)
        self.vectors = self.vectors[keep]
        self.sku_ids = [self.sku_ids[i] for i in keep]
        self._invalidate()
        return removed

    def count(self, sku_id: str) -> int:
        return self.sku_ids.count(sku_id)

    @property
    def skus(self) -> list[str]:
        return sorted(set(self.sku_ids))

    def __len__(self) -> int:
        return len(self.sku_ids)

    # -------------------------------------------------------------- matching

    def _invalidate(self) -> None:
        self._centred = None
        self._mean = None

    @property
    def mean(self) -> np.ndarray:
        """The direction every product's features share, which carries no
        information about which product it is."""
        if self._mean is None:
            self._mean = (self.vectors.mean(axis=0) if len(self.vectors)
                          else np.zeros(self.dim, dtype=np.float32))
        return self._mean

    @property
    def frozen(self) -> bool:
        return self.centre is not None

    def freeze_centre(self) -> None:
        """Pin the current mean as the centring reference from now on."""
        self.centre = self.mean.astype(np.float32).copy()
        self._centred = None

    def thaw_centre(self) -> None:
        """Let the centre float again - only together with recalibrating the threshold."""
        self.centre = None
        self._centred = None

    def reference(self) -> np.ndarray:
        return self.centre if self.centre is not None else self.mean

    def centred(self) -> np.ndarray:
        if self._centred is None:
            self._centred = l2_normalise(self.vectors - self.reference())
        return self._centred

    def project(self, vector: np.ndarray) -> np.ndarray:
        """Put a query into the same centred space as the gallery."""
        return l2_normalise(np.asarray(vector, dtype=np.float32) - self.reference())[0]

    def match(self, vector: np.ndarray, top_k: int = 3) -> list[Match]:
        """Rank SKUs by their best-matching reference view."""
        if not len(self):
            return []
        sims = self.centred() @ self.project(vector)   # cosine in the centred space

        best: dict[str, float] = {}
        for sku, s in zip(self.sku_ids, sims):
            # a SKU is scored by its closest view, not its average: one good
            # angle should be enough to recognise it
            if s > best.get(sku, -2.0):
                best[sku] = float(s)

        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [Match(sku, score, self.count(sku)) for sku, score in ranked]

    def match_prototypes(self, vector: np.ndarray, top_k: int = 3) -> list[Match]:
        """The alternative scoring: each SKU is its mean view (a prototype).

        Kept for research/E2, which reports both.  Not what the till uses: with
        five views a mean is easily pulled off by one bad angle, whereas the
        nearest view only needs one good one.
        """
        if not len(self):
            return []
        q = self.project(vector)
        c = self.centred()
        protos = {}
        for sku in self.skus:
            rows = [i for i, s in enumerate(self.sku_ids) if s == sku]
            protos[sku] = float(l2_normalise(c[rows].mean(axis=0))[0] @ q)
        ranked = sorted(protos.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [Match(sku, score, self.count(sku)) for sku, score in ranked]

    # ------------------------------------------------------------ persistence

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, vectors=self.vectors,
                            sku_ids=np.array(self.sku_ids, dtype=object),
                            dim=self.dim,
                            centre=(self.centre if self.centre is not None
                                    else np.zeros(0, dtype=np.float32)))

    @classmethod
    def load(cls, path: str | Path) -> "SkuGallery":
        data = np.load(path, allow_pickle=True)
        g = cls(int(data["dim"]))
        g.vectors = data["vectors"].astype(np.float32)
        g.sku_ids = [str(s) for s in data["sku_ids"]]
        if "centre" in data and data["centre"].size:
            g.centre = data["centre"].astype(np.float32)
        return g
