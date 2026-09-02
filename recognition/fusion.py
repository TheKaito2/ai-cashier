"""Combining what the camera, the scale and the ruler each think.

Appearance alone cannot separate Lay's Flat Original from Lay's Ridged Original -
the packets differ mainly in one word of Thai text.  Grams and millimetres can.

Each modality contributes a log-likelihood and they are summed.  A modality that
is unavailable - no scale connected, no marker in frame, no reference value for
that SKU - contributes exactly zero, so it never tilts the ranking and never
penalises a SKU for having incomplete data.

Identification (`fuse`) and fraud checking (`verify_basket`) are deliberately
separate: the first decides what an item is, the second decides whether the
basket on the pan matches the basket on the screen.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum

from recognition.gallery import Match


class Status(str, Enum):
    ACCEPTED = "accepted"
    UNKNOWN = "unknown"        # nothing in the gallery is close enough
    AMBIGUOUS = "ambiguous"    # two candidates too close to call


@dataclass(frozen=True)
class SkuPrior:
    """What we know about a SKU besides its appearance."""
    sku_id: str
    weight_g: float | None = None
    size_mm: tuple[float, float] | None = None      # (longer, shorter)
    weight_is_estimated: bool = False               # parsed from a label, not weighed


@dataclass(frozen=True)
class FusedCandidate:
    sku_id: str
    total: float
    appearance: float
    weight: float
    size: float

    @property
    def used_weight(self) -> bool:
        return self.weight != 0.0

    @property
    def used_size(self) -> bool:
        return self.size != 0.0


@dataclass(frozen=True)
class Decision:
    status: Status
    sku_id: str | None
    candidates: list[FusedCandidate]
    margin: float                    # gap between the top two, 0 if only one

    @property
    def top(self) -> FusedCandidate | None:
        return self.candidates[0] if self.candidates else None


@dataclass
class FusionConfig:
    #: cosine -> logit.  Small values sharpen the appearance term; 0.07 is the
    #: CLIP contrastive temperature and is a reasonable starting point.
    appearance_temperature: float = 0.07
    #: a 5 kg bar cell settles to about a gram; the slack is mostly product
    #: variation (fill weight, moisture) rather than the sensor
    weight_sigma_g: float = 6.0
    #: measured on the mat plane, so this is repeatability not accuracy
    size_sigma_mm: float = 6.0

    w_appearance: float = 1.0
    w_weight: float = 1.0
    w_size: float = 0.6

    #: Below this cosine, say "unknown" rather than name the nearest thing.
    #:
    #: This default is the value calibrated on the synthetic set (tests/synthetic.py)
    #: and it is a placeholder.  The right number depends on the backbone, the
    #: lighting and how many products are enrolled, so it MUST be recalibrated on
    #: real photographs before the till takes anyone's money -
    #: recognition.calibration.pick_threshold does it, research/exp5_openset.py
    #: runs it and reports the curve.
    reject_below_cosine: float = 0.38
    #: if the top two are closer than this, ask the operator instead of guessing
    ambiguous_margin: float = 0.35


def _gaussian_ll(delta: float, sigma: float) -> float:
    """Log-density of a zero-mean gaussian, dropping the constant term."""
    return -0.5 * (delta / sigma) ** 2


def fuse(matches: list[Match],
         priors: dict[str, SkuPrior],
         measured_weight_g: float | None = None,
         measured_size_mm: tuple[float, float] | None = None,
         cfg: FusionConfig | None = None) -> Decision:
    """Rank the gallery's candidates using every modality that is available."""
    cfg = cfg or FusionConfig()
    if not matches:
        return Decision(Status.UNKNOWN, None, [], 0.0)

    candidates: list[FusedCandidate] = []
    for m in matches:
        prior = priors.get(m.sku_id)
        appearance = cfg.w_appearance * (m.score / cfg.appearance_temperature)

        weight = 0.0
        if measured_weight_g is not None and prior and prior.weight_g:
            weight = cfg.w_weight * _gaussian_ll(
                measured_weight_g - prior.weight_g, cfg.weight_sigma_g)

        size = 0.0
        if measured_size_mm is not None and prior and prior.size_mm:
            d_long = measured_size_mm[0] - prior.size_mm[0]
            d_short = measured_size_mm[1] - prior.size_mm[1]
            size = cfg.w_size * (_gaussian_ll(d_long, cfg.size_sigma_mm)
                                 + _gaussian_ll(d_short, cfg.size_sigma_mm))

        candidates.append(FusedCandidate(
            sku_id=m.sku_id, total=appearance + weight + size,
            appearance=appearance, weight=weight, size=size))

    candidates.sort(key=lambda c: c.total, reverse=True)
    margin = candidates[0].total - candidates[1].total if len(candidates) > 1 else 0.0

    # abstention is an appearance decision: if nothing in the gallery looks like
    # this, no amount of weight agreement should make us name a product
    best_cosine = max(m.score for m in matches)
    if best_cosine < cfg.reject_below_cosine:
        return Decision(Status.UNKNOWN, None, candidates, margin)

    if len(candidates) > 1 and margin < cfg.ambiguous_margin:
        return Decision(Status.AMBIGUOUS, candidates[0].sku_id, candidates, margin)

    return Decision(Status.ACCEPTED, candidates[0].sku_id, candidates, margin)


@dataclass(frozen=True)
class BasketCheck:
    ok: bool
    expected_g: float
    measured_g: float
    tolerance_g: float

    @property
    def delta_g(self) -> float:
        return self.measured_g - self.expected_g

    @property
    def reason(self) -> str:
        if self.ok:
            return "weight matches the basket"
        heavier = self.delta_g > 0
        return (f"the pan is {abs(self.delta_g):.0f} g "
                f"{'heavier' if heavier else 'lighter'} than the basket - "
                f"{'an unscanned item' if heavier else 'an item was removed'}")


#: settled noise of a 5 kg bar cell plus tare drift, in grams
CELL_SIGMA_G = 2.0
#: how much one unit of a product varies from its nominal mass - fill weight and
#: moisture, not sensor error.  The dominant term for a multi-item basket.
ITEM_SIGMA_G = 4.0


def basket_tolerance_g(n_items: int, k_sigma: float = 3.0,
                       cell_sigma_g: float = CELL_SIGMA_G,
                       item_sigma_g: float = ITEM_SIGMA_G) -> float:
    """How far the pan may legitimately differ from the till.

    Independent errors add in quadrature, not linearly - summing them linearly
    gives a band so wide it swallows the swaps this check exists to catch.

    `k_sigma` is the security/nuisance dial: raising it lets more swaps through,
    lowering it makes the till accuse honest customers.  It is not guessed - it
    is swept in research/exp6_fusion.py and set from the measured curve.
    """
    variance = cell_sigma_g ** 2 + max(n_items, 1) * item_sigma_g ** 2
    return k_sigma * math.sqrt(variance)


def verify_basket(priors: dict[str, SkuPrior],
                  cart: dict[str, int],
                  measured_total_g: float,
                  k_sigma: float = 3.0) -> BasketCheck | None:
    """Does the mass on the pan match what the till thinks it is selling?

    This is what catches an item being swapped after it was scanned.

    Blind spot worth stating plainly: swapping one product for another of nearly
    the same mass is invisible here.  That case is the camera's job, and the two
    modalities cover each other - appearance struggles with same-brand variants
    that differ in mass, mass struggles with different products that do not.

    Returns None when any item in the cart has no reference weight, because a
    check that cannot actually be performed must not report itself as passing.
    """
    expected = 0.0
    for sku_id, qty in cart.items():
        prior = priors.get(sku_id)
        if not prior or not prior.weight_g:
            return None
        expected += prior.weight_g * qty

    tolerance = basket_tolerance_g(sum(cart.values()), k_sigma)
    return BasketCheck(ok=abs(measured_total_g - expected) <= tolerance,
                       expected_g=expected, measured_g=measured_total_g,
                       tolerance_g=tolerance)


#: below this much added mass the pan is treated as unchanged
MIN_ITEM_DELTA_G = 5.0


def item_weight_for_scan(pan_g: float | None, baseline_g: float | None,
                         n_new_items: int, min_delta_g: float = MIN_ITEM_DELTA_G) -> float | None:
    """The mass one newly placed item added to the pan, or None.

    `fuse` wants the mass of *one* item.  The pan reports the mass of
    everything on it.  The two agree only when exactly one item was put down
    since the cart last changed, so that is the only case in which a number is
    returned: the difference between the pan now and the pan then.  With two
    items on the mat, or a pan that went down (the customer bagged something),
    the answer is None and appearance and size decide alone; the basket check
    at PAY still verifies the total (docs/research/09, D6).
    """
    if pan_g is None or n_new_items != 1:
        return None
    delta = pan_g - (baseline_g or 0.0)
    return delta if delta >= min_delta_g else None


_SIZE = re.compile(r"([\d.]+)\s*(g|ml|l|kg)\b", re.I)
#: rough container mass by category, for the provisional estimate only
_CONTAINER_G = {"can": 15.0, "bottle": 22.0}


def estimate_weight_g(size_label: str | None, name: str = "") -> float | None:
    """Provisional mass from a pack label like '75g' or '325ml'.

    Only a starting point: the real number is whatever the scale reads when the
    product is enrolled, and `SkuPrior.weight_is_estimated` marks which is which.
    Liquids are counted at 1 g/ml plus a nominal container mass.
    """
    if not size_label:
        return None
    m = _SIZE.search(size_label)
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2).lower()
    if unit == "g":
        return value
    if unit == "kg":
        return value * 1000.0
    volume_ml = value * 1000.0 if unit == "l" else value
    lowered = f"{name} {size_label}".lower()
    container = next((g for k, g in _CONTAINER_G.items() if k in lowered), 18.0)
    return volume_ml + container
