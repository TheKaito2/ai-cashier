"""End-to-end: enrol a product by showing it, then recognise it.

These use synthetic packaging (tests/synthetic.py) because the rig and the
photographs do not exist yet.  They prove the machinery is correct, not that
recognition is accurate on real crisps - that number comes from research/exp2
after the capture session, and is deliberately not claimed here.
"""

import numpy as np
import pytest

from recognition.embedder import TorchEmbedder
from recognition.fusion import FusionConfig, SkuPrior, Status
from recognition.gallery import SkuGallery
from recognition.pipeline import RecognitionPipeline
from recognition.calibration import pick_threshold
from recognition.proposer import BackgroundSubtractionProposer
from tests.synthetic import CATALOGUE, empty_mat, scene, true_mass, views

EASY = ["pepsi", "tasto-seaweed", "crystal-water"]
HARD_PAIR = ["lays-flat-original", "lays-ridged-original"]


@pytest.fixture(scope="module")
def embedder():
    return TorchEmbedder("mobilenet_v3_small")


def build(embedder, skus, k=5, cfg=None, calibrate=True):
    """A till that has been taught `skus` from k views each.

    The rejection threshold is calibrated from held-out views rather than left
    at its default, which is exactly what research/exp5_openset.py does on real
    photographs.  A hardcoded threshold would make these tests pass or fail for
    reasons that have nothing to do with the code.
    """
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(empty_mat())
    pipe = RecognitionPipeline(proposer, embedder, SkuGallery(embedder.dim),
                               cfg=cfg or FusionConfig())
    for sku in skus:
        pipe.enrol(sku, views(sku, k, seed=100), weight_g=true_mass(sku))
    if skus:
        pipe.gallery.freeze_centre()          # tau is only valid for one centre

    if calibrate and skus:
        known = [_top_score(pipe, s, 700 + i) for s in skus for i in range(4)]
        unseen = [s for s in CATALOGUE if s not in skus]
        unknown = [_top_score(pipe, s, 700 + i) for s in unseen for i in range(4)]
        if unknown:
            pipe.cfg.reject_below_cosine = pick_threshold(known, unknown).threshold
    return pipe


def _top_score(pipe, sku, seed):
    frame = scene([sku], seed=seed)
    prop = max(pipe.proposer.propose(frame), key=lambda p: p.area_px)
    matches = pipe.gallery.match(pipe.embedder.embed([prop.crop(frame)])[0])
    return matches[0].score if matches else 0.0


def recognise(pipe, sku, seed, weight=None, frames=4):
    """Show the till one product for a few frames and take its verdict."""
    pipe.reset()
    items = []
    for i in range(frames):
        items = pipe.process(scene([sku], seed=seed + i), weight_delta_g=weight)
    return items


def test_enrolment_stores_one_vector_per_view(embedder):
    pipe = build(embedder, ["pepsi"], k=5)
    assert pipe.gallery.count("pepsi") == 5
    assert pipe.priors["pepsi"].weight_g == pytest.approx(340.0)


def test_enrolment_needs_something_on_the_mat(embedder):
    pipe = build(embedder, [], calibrate=False)
    with pytest.raises(ValueError, match="nothing found"):
        pipe.enrol("ghost", [empty_mat()])


def test_a_product_is_recognised_from_views_it_was_not_enrolled_on(embedder):
    """Held-out placements, not the enrolment frames."""
    pipe = build(embedder, EASY)
    for sku in EASY:
        items = recognise(pipe, sku, seed=900)
        assert len(items) == 1, f"{sku}: expected one item, got {len(items)}"
        assert items[0].sku_id == sku, f"{sku}: recognised as {items[0].sku_id}"
        assert items[0].status is Status.ACCEPTED


def test_a_product_nobody_enrolled_is_refused(embedder):
    """The behaviour a closed-set classifier structurally cannot have: it would
    have to name one of its trained classes."""
    pipe = build(embedder, EASY)
    items = recognise(pipe, "never-enrolled-snack", seed=910)
    assert items and items[0].status is Status.UNKNOWN
    assert items[0].sku_id is None


def test_a_removed_product_stops_being_recognised(embedder):
    pipe = build(embedder, EASY)
    assert recognise(pipe, "pepsi", seed=920)[0].sku_id == "pepsi"
    pipe.gallery.remove("pepsi")
    assert recognise(pipe, "pepsi", seed=920)[0].status is Status.UNKNOWN


def test_two_products_on_the_mat_become_two_items(embedder):
    pipe = build(embedder, EASY)
    pipe.reset()
    items = []
    for i in range(4):
        items = pipe.process(scene(["pepsi", "tasto-seaweed"], seed=930 + i))
    assert len(items) == 2
    assert {i.sku_id for i in items} == {"pepsi", "tasto-seaweed"}


def test_one_product_held_still_is_charged_for_once(embedder):
    """Twenty frames of the same packet is one cart line, not twenty."""
    pipe = build(embedder, EASY)
    pipe.reset()
    frame = scene(["pepsi"], seed=940)
    for _ in range(20):
        items = pipe.process(frame)
    assert len(items) == 1 and items[0].hits >= 20


def test_weight_separates_the_pair_that_appearance_cannot(embedder):
    """The multimodal claim, end to end: same art, different mass."""
    pipe = build(embedder, HARD_PAIR)
    for sku in HARD_PAIR:
        appearance_only = recognise(pipe, sku, seed=950)[0]
        with_scale = recognise(pipe, sku, seed=950, weight=true_mass(sku))[0]
        assert with_scale.sku_id == sku, (
            f"{sku}: scale said {with_scale.sku_id}")
        # the appearance-only verdict is allowed to be wrong or ambiguous here;
        # that it can be is the reason the scale exists
        assert appearance_only.status in (Status.ACCEPTED, Status.AMBIGUOUS, Status.UNKNOWN)


def test_settled_tracks_stop_being_re_embedded(embedder):
    """The Raspberry Pi cannot afford to embed every object in every frame."""
    pipe = build(embedder, EASY, cfg=FusionConfig())
    pipe.reset()
    calls = {"n": 0}
    real = pipe.embedder.embed

    def counting(crops):
        calls["n"] += len(crops)
        return real(crops)

    pipe.embedder = type("E", (), {"embed": staticmethod(counting), "dim": embedder.dim})()
    frame = scene(["pepsi"], seed=960)
    for _ in range(12):
        pipe.process(frame)
    assert calls["n"] <= 5, f"embedded {calls['n']} crops over 12 frames"
