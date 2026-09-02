"""Choosing the rejection threshold from data instead of taste.

`FusionConfig.reject_below_cosine` decides when the till says "I do not know"
rather than naming the nearest product.  Set it too low and an unseen packet is
charged as whatever it resembles; too high and the till refuses things it
actually knows.  The right value depends on the backbone, the rig and the
lighting, so it is measured on a validation split - never hardcoded and hoped for.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ThresholdReport:
    threshold: float
    tpr: float                 # enrolled products correctly accepted
    fpr: float                 # unenrolled products wrongly accepted
    auroc: float
    fpr_at_95_tpr: float

    def __str__(self) -> str:
        return (f"tau={self.threshold:.3f}  accepts {self.tpr:.1%} of known, "
                f"{self.fpr:.1%} of unknown  (AUROC {self.auroc:.3f}, "
                f"FPR@95TPR {self.fpr_at_95_tpr:.1%})")


def energy_score(similarities: np.ndarray, temperature: float = 0.07) -> float:
    """Free energy over the similarity vector to every enrolled SKU (Liu et al.,
    NeurIPS 2020, ported to cosine retrieval).  Higher = more in-distribution.
    A second abstention rule for E5 beside the plain max-cosine."""
    s = np.asarray(similarities, dtype=np.float64) / temperature
    if s.size == 0:
        return float("-inf")
    m = s.max()
    return float(temperature * (m + np.log(np.exp(s - m).sum())))


def msp_score(similarities: np.ndarray, temperature: float = 0.07) -> float:
    """Maximum softmax probability (Hendrycks & Gimpel, ICLR 2017) over the same
    similarity vector - the closed-set baseline's own confidence."""
    s = np.asarray(similarities, dtype=np.float64) / temperature
    if s.size == 0:
        return 0.0
    s = s - s.max()
    return float(np.exp(s).max() / np.exp(s).sum())


def auroc(known: np.ndarray, unknown: np.ndarray) -> float:
    """Probability a known product outscores an unknown one.

    Computed by rank rather than by sweeping, so ties are handled correctly.
    """
    known, unknown = np.asarray(known), np.asarray(unknown)
    if not len(known) or not len(unknown):
        return float("nan")
    order = np.argsort(np.concatenate([known, unknown]), kind="mergesort")
    ranks = np.empty(len(order), dtype=np.float64)
    ranks[order] = np.arange(1, len(order) + 1)
    # average the ranks of tied scores
    scores = np.concatenate([known, unknown])
    for value in np.unique(scores):
        tied = scores == value
        if tied.sum() > 1:
            ranks[tied] = ranks[tied].mean()
    n1, n2 = len(known), len(unknown)
    return float((ranks[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2))


def fpr_at_tpr(known: np.ndarray, unknown: np.ndarray, target_tpr: float = 0.95) -> float:
    """How many unknown products slip through when we insist on catching
    `target_tpr` of the known ones. The number that matters operationally."""
    if not len(known) or not len(unknown):
        return float("nan")
    tau = float(np.quantile(known, 1.0 - target_tpr))
    return float((np.asarray(unknown) >= tau).mean())


def pick_threshold(known: np.ndarray, unknown: np.ndarray,
                   target_tpr: float = 0.95) -> ThresholdReport:
    """Lowest threshold that still accepts `target_tpr` of enrolled products.

    Anchored on the true-positive rate rather than on accuracy, because the
    costs are not symmetric: refusing a product the shop stocks annoys a queue,
    while charging an unknown item as something else takes the wrong money.
    """
    known, unknown = np.asarray(known, float), np.asarray(unknown, float)
    tau = float(np.quantile(known, 1.0 - target_tpr)) if len(known) else 0.0
    return ThresholdReport(
        threshold=tau,
        tpr=float((known >= tau).mean()) if len(known) else float("nan"),
        fpr=float((unknown >= tau).mean()) if len(unknown) else float("nan"),
        auroc=auroc(known, unknown),
        fpr_at_95_tpr=fpr_at_tpr(known, unknown, 0.95),
    )
