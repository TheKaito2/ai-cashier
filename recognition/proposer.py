"""Finding *where* the products are, without caring what they are.

This is the part that has to work for a product the system has never seen, so it
cannot be a classifier.  On a fixed rig with a light ring, subtracting the empty
mat is both the simplest and the most general answer: it proposes anything that
was not there before, which is exactly the requirement.

The YOLO proposer is kept for comparison (research/exp3) and because it still
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
                 shadow_ratio: tuple[float, float] = (0.55, 0.95)):
        self.min_area_px = min_area_px
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

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        proposals = []
        for c in contours:
            area = int(cv2.contourArea(c))
            if area * self.downscale ** 2 < self.min_area_px:
                continue
            x, y, w, h = cv2.boundingRect(c)
            d = self.downscale
            proposals.append(Proposal(box=(x * d, y * d, (x + w) * d, (y + h) * d),
                                      area_px=area * d * d))

        proposals.sort(key=lambda p: p.area_px, reverse=True)
        return proposals[:self.max_proposals]


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

    def propose(self, frame: np.ndarray) -> list[Proposal]:
        result = self.model(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        proposals = []
        if result.boxes is not None:
            for x1, y1, x2, y2, score, _cls in result.boxes.data.tolist():
                box = (int(x1), int(y1), int(x2), int(y2))
                proposals.append(Proposal(
                    box=box, area_px=int((x2 - x1) * (y2 - y1)), confidence=float(score)))
        return proposals
