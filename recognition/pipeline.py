"""Frame in, priced items out.

    frame -> proposals -> crops -> vectors -> gallery match -> fusion -> tracks

Every stage is swappable, which is what makes the ablation tables in research/
possible without a second implementation of anything.

Privacy property (docs/PRIVACY.md): nothing in this module writes a frame or a
crop to disk.  The only thing that persists is the gallery of embedding vectors,
and an embedding cannot be turned back into a picture of the customer.
tests/test_privacy.py fails if anyone adds a file write here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from recognition.fusion import Decision, FusionConfig, SkuPrior, Status, estimate_weight_g, fuse
from recognition.gallery import SkuGallery
from recognition.metrology import MatMetrology
from recognition.proposer import Proposal
from recognition.tracker import CentroidTracker, Track


@dataclass
class RecognisedItem:
    track_id: int
    box: tuple[int, int, int, int]
    decision: Decision
    agreement: float                    # share of frames that agreed
    size_mm: tuple[float, float] | None
    hits: int

    @property
    def sku_id(self) -> str | None:
        return self.decision.sku_id

    @property
    def status(self) -> Status:
        return self.decision.status


def priors_from_products(products: list[dict]) -> dict[str, SkuPrior]:
    """Build fusion priors from the product database.

    `weight_g` is used when a product has actually been weighed at enrolment.
    Otherwise it falls back to parsing the pack label, and marks the value as an
    estimate so the till can say so rather than implying it was measured.
    """
    priors: dict[str, SkuPrior] = {}
    for p in products:
        weighed = p.get("weight_g")
        weight = float(weighed) if weighed else estimate_weight_g(p.get("size"), p.get("name", ""))
        size = p.get("size_mm")
        priors[p["id"]] = SkuPrior(
            sku_id=p["id"],
            weight_g=weight,
            size_mm=tuple(size) if size else None,
            weight_is_estimated=not weighed and weight is not None,
        )
    return priors


class RecognitionPipeline:
    def __init__(self, proposer, embedder, gallery: SkuGallery,
                 priors: dict[str, SkuPrior] | None = None,
                 metrology: MatMetrology | None = None,
                 cfg: FusionConfig | None = None,
                 tracker: CentroidTracker | None = None,
                 settled_hits: int = 4):
        self.proposer = proposer
        self.embedder = embedder
        self.gallery = gallery
        self.priors = priors or {}
        self.metrology = metrology
        self.cfg = cfg or FusionConfig()
        self.tracker = tracker or CentroidTracker()
        #: once a track has agreed with itself this many times, stop re-embedding
        #: it.  This is the difference between a usable frame rate on a Pi and a
        #: slideshow - the expensive stage runs on new objects, not on every
        #: object in every frame.
        self.settled_hits = settled_hits
        self._settled: dict[int, Decision] = {}

    # ------------------------------------------------------------ calibration

    def calibrate(self, empty_mat_frame: np.ndarray, marker_mm: float | None = None,
                  marker_layout_mm: dict | None = None) -> None:
        if hasattr(self.proposer, "calibrate"):
            self.proposer.calibrate(empty_mat_frame)
        if marker_mm:
            self.metrology = MatMetrology.from_frame(empty_mat_frame, marker_mm,
                                                     layout_mm=marker_layout_mm)

    def reset(self) -> None:
        self.tracker.reset()
        self._settled.clear()

    # --------------------------------------------------------------- per frame

    def process(self, frame: np.ndarray,
                weight_delta_g: float | None = None) -> list[RecognisedItem]:
        """Run one frame. `weight_delta_g` is the mass the pan gained, when the
        caller knows a single item was just placed."""
        proposals = self.proposer.propose(frame)
        tracks = self.tracker.update([p.box for p in proposals])
        by_id = {t.track_id: t for t in tracks}

        # only embed tracks we have not already made up our mind about
        pending: list[tuple[Track, Proposal]] = []
        for prop in proposals:
            track = self._track_for(by_id, prop.box)
            if track is None:
                continue
            if track.track_id in self._settled:
                continue
            pending.append((track, prop))

        if pending:
            vectors = self.embedder.embed([p.crop(frame) for _, p in pending])
            for (track, prop), vector in zip(pending, vectors):
                self._observe(track, prop, vector, frame, weight_delta_g)

        items = []
        for track in self.tracker.confirmed:
            decision = self._settled.get(track.track_id) or self._decide(track)
            if track.hits >= self.settled_hits and track.track_id not in self._settled:
                self._settled[track.track_id] = decision
            _, _, agreement = track.decision
            items.append(RecognisedItem(
                track_id=track.track_id, box=track.box, decision=decision,
                agreement=agreement, size_mm=self._size_mm(track.box), hits=track.hits))
        return items

    def _track_for(self, by_id: dict[int, Track], box) -> Track | None:
        for t in by_id.values():
            if t.box == box:
                return t
        return None

    def _size_mm(self, box) -> tuple[float, float] | None:
        return self.metrology.box_mm(box) if self.metrology else None

    def _observe(self, track: Track, prop: Proposal, vector: np.ndarray,
                 frame: np.ndarray, weight_delta_g: float | None) -> None:
        matches = self.gallery.match(vector, top_k=3)
        decision = fuse(matches, self.priors,
                        measured_weight_g=weight_delta_g,
                        measured_size_mm=self._size_mm(prop.box),
                        cfg=self.cfg)
        best = max((m.score for m in matches), default=0.0)
        track.observe(decision.sku_id, best)
        track._last_decision = decision           # noqa: SLF001 - carried for _decide

    def _decide(self, track: Track) -> Decision:
        """The track's verdict: the SKU most frames agreed on."""
        sku, score, _ = track.decision
        last: Decision | None = getattr(track, "_last_decision", None)
        if last is None:
            return Decision(Status.UNKNOWN, None, [], 0.0)
        if sku == last.sku_id:
            return last
        # frames disagreed with the most recent one; trust the vote
        status = Status.UNKNOWN if sku is None else Status.ACCEPTED
        return Decision(status, sku, last.candidates, last.margin)

    # -------------------------------------------------------------- enrolment

    def enrol(self, sku_id: str, frames: list[np.ndarray],
              weight_g: float | None = None) -> int:
        """Teach the system a product from k views of it on the mat.

        This is the entire "add a new product" path.  No labelling, no training,
        no restart - the till can sell it on the next frame.
        """
        crops = []
        sizes = []
        for frame in frames:
            proposals = self.proposer.propose(frame)
            if not proposals:
                continue
            best = max(proposals, key=lambda p: p.area_px)
            crops.append(best.crop(frame))
            if self.metrology:
                sizes.append(self.metrology.box_mm(best.box))

        if not crops:
            raise ValueError("nothing found on the mat in any of those frames")

        self.gallery.enrol(sku_id, self.embedder.embed(crops))
        self.priors[sku_id] = SkuPrior(
            sku_id=sku_id,
            weight_g=weight_g,
            size_mm=tuple(np.median(np.array(sizes), axis=0)) if sizes else None,
            weight_is_estimated=weight_g is None,
        )
        return self.gallery.count(sku_id)
