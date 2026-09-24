"""Finding *where* the products are, without caring what they are.

This is the part that has to work for a product the system has never seen, so it
cannot be a classifier.  On a fixed rig with a light ring, subtracting the empty
mat is both the simplest and the most general answer: it proposes anything that
was not there before, which is exactly the requirement.

The YOLO proposer is kept for comparison (the E1 baseline) and because it still
helps on a cluttered background - but it can only propose what it was trained
on, which is the limitation this whole package exists to remove.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Proposal:
    box: Box
    area_px: int
    confidence: float = 1.0
    #: What a *classifying* proposer called it, when it has an opinion.  The
    #: class-agnostic proposers leave it None by construction - they find things
    #: without naming them, which is the whole point.  Only the closed-set
    #: baseline (research/experiments.py:e1_closed_set_baseline) reads it.
    label: str | None = None

    def crop(self, frame: np.ndarray, pad: int = 6) -> np.ndarray:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = self.box
        return frame[max(0, y1 - pad):min(h, y2 + pad),
                     max(0, x1 - pad):min(w, x2 + pad)]


class Proposer(Protocol):
    def propose(self, frame: np.ndarray) -> list[Proposal]: ...


class BackgroundSubtractionProposer:
    """Whatever is on the mat that was not there when we calibrated.

    Class-agnostic by construction, about a millisecond per frame, and no
    training data - which is what makes same-day enrolment of an unknown product
    possible at all.
    """

    def __init__(self, min_area_px: int = 4000, diff_threshold: int = 28,
                 blur: int = 5, max_proposals: int = 12, downscale: int = 2,
                 shadow_chroma_eps: float = 0.04,
                 shadow_ratio: tuple[float, float] = (0.55, 0.95),
                 max_area_frac: float = 0.35, min_fill_ratio: float = 0.45,
                 max_aspect: float = 6.0, reject_border_px: int = 8,
                 roi: Box | None = None):
        self.min_area_px = min_area_px
        #: Everything below is an objectness test, and the proposer had none
        #: until a real rig was switched on.  "Differs from the empty mat and is
        #: bigger than 4000 px" was the whole definition of a product, so on a
        #: white table the table's own edges, a cable and a moving shadow all
        #: qualified and the till narrated products that were not there.
        #:
        #: An upper bound.  A packet occupies a part of the mat; a contour
        #: covering a third of it is the lighting changing, or the mat photograph
        #: no longer matching the mat.
        self.max_area_frac = max_area_frac
        #: The gate measures `contourArea` but the box that gets emitted is the
        #: bounding rectangle.  A diagonal sliver or a ring of shadow around a
        #: region passes the area test and then hands the embedder a box many
        #: times its own size, full of mat.  Requiring the contour to fill its
        #: own box throws those away and keeps solid things.
        self.min_fill_ratio = min_fill_ratio
        #: Long and thin is a table edge, a cable or the seam of a shadow.  No
        #: packet the till is meant to price is six times longer than it is wide.
        self.max_aspect = max_aspect
        #: A product sits on the mat, inside the frame.  Anything reaching the
        #: boundary is the world beyond the mat leaking in - and if the camera is
        #: aimed so tightly that real products touch the edge, the fix is the
        #: aim, not a proposal for the floor.
        self.reject_border_px = reject_border_px
        #: Where the mat is, in full-frame pixels, or None for the whole frame.
        #: Set it from `rig.mat_roi`.  The mask outside is zeroed rather than the
        #: frame being cropped, so every box stays in full-frame coordinates and
        #: the tracker, the crops, metrology and the overlay need no adjustment.
        self.roi = roi
        self.diff_threshold = diff_threshold
        #: A shadow darkens the mat without changing its colour: same
        #: chromaticity (RGB / sum), lower intensity.  Pixels that fit that
        #: description are dropped from the mask so a product's shadow, or a
        #: hand's, does not become part of its box (docs/research/09, D10).
        #: ponytail: an achromatic packet whose intensity ratio to the mat
        #: falls inside `shadow_ratio` is invisible to this test; on the matte
        #: black mat HARDWARE.md prescribes, shadows barely register anyway.
        #: Set shadow_chroma_eps=0 to switch it off.
        self.shadow_chroma_eps = shadow_chroma_eps
        self.shadow_ratio = shadow_ratio
        self.blur = blur | 1                      # cv2 needs an odd kernel
        self.max_proposals = max_proposals
        #: The mask is computed at 1/downscale resolution and the boxes scaled
        #: back up.  Benchmarking showed this stage, not the neural network, was
        #: the frame budget once tracks settle - and a product occupying a
        #: quarter of the frame does not need full resolution to be *located*.
        #: The crop that reaches the embedder is still cut from the full frame.
        self.downscale = max(1, int(downscale))
        self._background: np.ndarray | None = None

    def calibrate(self, empty_mat_frame: np.ndarray) -> None:
        """Record the empty mat. Re-run whenever the rig or the lighting moves."""
        self._background = self._prepare(empty_mat_frame)

    @property
    def calibrated(self) -> bool:
        return self._background is not None

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        # kept in colour on purpose.  A greyscale difference is blind to any
        # product whose brightness happens to match the mat - a red-and-blue
        # can over a dark mat has almost the same luminance and simply vanishes.
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if self.downscale > 1:
            frame = cv2.resize(frame, None, fx=1 / self.downscale, fy=1 / self.downscale,
                               interpolation=cv2.INTER_AREA)
        return cv2.GaussianBlur(frame, (self.blur, self.blur), 0)

    def _shadow(self, prepared: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Boolean map of masked pixels that are only the mat, darker."""
        ys, xs = np.nonzero(mask)
        out = np.zeros(mask.shape, dtype=bool)
        if not len(ys):
            return out
        bg = self._background[ys, xs].astype(np.float32)
        cur = prepared[ys, xs].astype(np.float32)
        bg_i = bg.sum(axis=1) + 1.0
        cur_i = cur.sum(axis=1) + 1.0
        chroma = np.abs(bg / bg_i[:, None] - cur / cur_i[:, None]).max(axis=1)
        ratio = cur_i / bg_i
        lo, hi = self.shadow_ratio
        shadow = (chroma < self.shadow_chroma_eps) & (ratio > lo) & (ratio < hi)
        out[ys[shadow], xs[shadow]] = True
        return out

    def propose(self, frame: np.ndarray) -> list[Proposal]:
        if self._background is None:
            raise RuntimeError("calibrate() with a photo of the empty mat first")

        # the strongest disagreeing colour channel, so a change in hue counts
        # even when brightness does not change at all
        prepared = self._prepare(frame)
        diff = cv2.absdiff(self._background, prepared).max(axis=2)
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        if self.shadow_chroma_eps > 0:
            mask[self._shadow(prepared, mask)] = 0
        # close the packet's printed graphics into one blob, then drop speckle
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        if self.roi is not None:
            x0, y0, x1, y1 = self._search_area(mask.shape)
            outside = np.ones(mask.shape, dtype=bool)
            outside[y0:y1, x0:x1] = False
            mask[outside] = 0

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        d = self.downscale
        search = self._search_area(mask.shape)          # in mask pixels
        sx0, sy0, sx1, sy1 = search
        search_px = max(1, (sx1 - sx0) * (sy1 - sy0))

        proposals = []
        for c in contours:
            area = int(cv2.contourArea(c))
            if area * d ** 2 < self.min_area_px:
                continue
            if area / search_px > self.max_area_frac:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if w == 0 or h == 0:
                continue
            if area / float(w * h) < self.min_fill_ratio:
                continue
            if max(w, h) / float(min(w, h)) > self.max_aspect:
                continue
            if self.reject_border_px:
                edge = self.reject_border_px / d
                if (x - sx0 < edge or y - sy0 < edge
                        or sx1 - (x + w) < edge or sy1 - (y + h) < edge):
                    continue
            proposals.append(Proposal(box=(x * d, y * d, (x + w) * d, (y + h) * d),
                                      area_px=area * d * d))

        proposals.sort(key=lambda p: p.area_px, reverse=True)
        return proposals[:self.max_proposals]

    def _search_area(self, shape: tuple[int, ...]) -> Box:
        """The region the proposer is allowed to find things in, in mask pixels."""
        h, w = shape[:2]
        if self.roi is None:
            return (0, 0, w, h)
        d = self.downscale
        x0, y0, x1, y1 = (v // d for v in self.roi)
        return (max(0, x0), max(0, y0), min(w, x1), min(h, y1))


class WholeFrameProposer:
    """The image *is* the crop.

    Public benchmarks (RPC single-product images, GroceryVision, MIMEX) ship
    pre-cropped product photographs with no mat to subtract, so the proposer
    has nothing to find.  Returning the whole frame lets the same experiments
    run unchanged on them (research/dataset.py ImageFolderSource, experiment E9).
    """

    calibrated = True

    def calibrate(self, empty_mat_frame: np.ndarray) -> None:      # nothing to learn
        pass

    def propose(self, frame: np.ndarray) -> list[Proposal]:
        h, w = frame.shape[:2]
        return [Proposal(box=(0, 0, w, h), area_px=int(w * h))]


def mask_above_mat(frame: np.ndarray, horizon_px: int) -> np.ndarray:
    """Black out everything above the mat plane in a side-camera frame.

    The planned front camera looks across the mat at product height, so a
    shopper's hands or torso can enter the top of its frame.  Nothing above
    `horizon_px` is ever processed or stored (docs/PRIVACY.md).  Returns a copy;
    the original frame is untouched.
    """
    out = frame.copy()
    out[:max(0, min(horizon_px, out.shape[0]))] = 0
    return out


class YoloProposer:
    """The trained detector, used only for its boxes.

    Comparison baseline.  Note the ceiling: it proposes nothing for a product it
    was not trained on, so it cannot support enrolment.
    """

    def __init__(self, model_path: str, conf: float = 0.25, imgsz: int = 416):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.conf = conf
        self.imgsz = imgsz

    @property
    def class_names(self) -> dict[int, str]:
        """The classes this detector was trained on - its whole world."""
        return dict(self.model.names)

    def propose(self, frame: np.ndarray) -> list[Proposal]:
        result = self.model(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        names = result.names
        proposals = []
        if result.boxes is not None:
            for x1, y1, x2, y2, score, cls in result.boxes.data.tolist():
                box = (int(x1), int(y1), int(x2), int(y2))
                proposals.append(Proposal(
                    box=box, area_px=int((x2 - x1) * (y2 - y1)), confidence=float(score),
                    label=names.get(int(cls))))
        return proposals
