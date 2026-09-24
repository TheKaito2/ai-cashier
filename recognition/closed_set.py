"""Version 1's detector, kept as a fallback the till can switch to.

This is the approach the whole project exists to replace, and it is here on
purpose.  It names products by classifying them, so it knows exactly the twelve
things it was trained on and cannot be taught a thirteenth without retraining.
The retrieval pipeline next door learns a new product from five photographs and
no gradients.  Having both on one machine, one button apart, is the clearest
demonstration of the difference there is.

Three things to be honest about before using it:

* **Licence.**  `ultralytics` is AGPL-3.0 and so are the weights trained with
  it.  While this module is on the till's path the Apache-2.0 licence on the
  repository does not describe the whole program - see `NOTICE`.  Nothing is
  imported until the mode is actually selected, so a till that never switches
  to it never loads it.
* **Enrolment is impossible here.**  A closed-set detector proposes nothing for
  a product it was not trained on.  The till disables Add product in this mode
  rather than appearing to accept one.
* **It cannot abstain usefully.**  Confidence below the threshold means "no
  box", not "something is there and I do not know it" - so an unknown product
  is invisible rather than flagged, which is the failure the retrieval path was
  built to avoid.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from recognition.fusion import Decision, FusedCandidate, Status
from recognition.pipeline import RecognisedItem

logger = logging.getLogger(__name__)

#: the version 1 detectors, six classes each
DEFAULT_WEIGHTS = ("chips_model.pt", "drinks_model.pt")


class _AlwaysReady:
    """Stands in for the background-subtraction proposer's mat calibration.

    A detector has no empty-mat photograph to take, but the till gates Scan on
    `proposer.calibrated` and paints the live preview from `proposer.propose`,
    so the mode has to answer both.
    """

    calibrated = True

    def __init__(self, detectors):
        self._detectors = detectors

    def calibrate(self, *_a, **_k) -> None:
        """Nothing to learn: the detector's world is fixed at training time."""

    def propose(self, frame: np.ndarray):
        out = []
        for d in self._detectors:
            out.extend(d.propose(frame))
        return out


class ClosedSetRecogniser:
    """Drop-in for `recognition.pipeline.RecognitionPipeline`, one mode over.

    Same surface the till already uses - `proposer`, `reset`, `process`,
    `calibrate` - so switching modes is swapping the object, not rewriting the
    window.
    """

    #: the same shape RecognitionPipeline exposes, so the till's enrolment and
    #: gallery code can see at a glance that neither applies here
    gallery = None
    metrology = None
    priors: dict = {}

    def __init__(self, weights: list[Path], class_to_sku: dict[str, str],
                 conf: float = 0.25, imgsz: int = 416):
        # imported here, not at module scope: this is the only line in the till
        # that reaches for an AGPL dependency, and it must not run for a user
        # who never selects this mode (tests/test_no_ultralytics.py)
        from recognition.proposer import YoloProposer

        missing = [p for p in weights if not Path(p).exists()]
        if missing:
            raise FileNotFoundError(
                f"{', '.join(str(p) for p in missing)} - the version 1 weights are "
                "not in this checkout.  They are gitignored because they are "
                "AGPL-derived; copy them from a machine that has them.")

        self.detectors = [YoloProposer(str(p), conf=conf, imgsz=imgsz) for p in weights]
        self.class_to_sku = class_to_sku
        self.proposer = _AlwaysReady(self.detectors)
        self._unmapped: set[str] = set()

    @property
    def classes(self) -> list[str]:
        """Everything this mode can ever name."""
        names: list[str] = []
        for d in self.detectors:
            names.extend(d.class_names.values())
        return sorted(set(names))

    def calibrate(self, *_a, **_k) -> None:
        """Accepted and ignored, so Calibrate mat does not error in this mode."""

    def reset(self) -> None:
        """No tracks to clear: every frame is judged on its own."""

    def process(self, frame: np.ndarray, weight_delta_g: float | None = None
                ) -> list[RecognisedItem]:
        items: list[RecognisedItem] = []
        for track_id, prop in enumerate(self.proposer.propose(frame)):
            sku = self.class_to_sku.get(prop.label or "")
            if sku is None and prop.label and prop.label not in self._unmapped:
                self._unmapped.add(prop.label)
                logger.warning("detector class %r has no product row - add a "
                               "yolo_class to data/products.json", prop.label)
            # the detector's confidence is not a cosine, and nothing downstream
            # should read it as one; it is carried so the chip can show it
            candidate = FusedCandidate(sku or prop.label or "unknown",
                                       prop.confidence, prop.confidence, 0.0, 0.0)
            decision = Decision(Status.ACCEPTED if sku else Status.UNKNOWN,
                                sku, [candidate], 0.0)
            items.append(RecognisedItem(track_id=track_id, box=prop.box,
                                        decision=decision, agreement=1.0,
                                        size_mm=None, hits=1))
        return items


def class_to_sku(products: list[dict]) -> dict[str, str]:
    """Map a detector's class name to the shop's product id.

    The column is `yolo_class` in `data/products.json` and the database; it is
    version 1's vocabulary, kept precisely so this mode and experiment E1 can
    both still speak it.
    """
    return {p["yolo_class"]: p["id"] for p in products if p.get("yolo_class")}
