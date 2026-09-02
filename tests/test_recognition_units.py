"""Unit tests for the recognition building blocks."""

import numpy as np
import pytest

from recognition.fusion import (FusionConfig, SkuPrior, Status, basket_tolerance_g,
                                estimate_weight_g, fuse, verify_basket)
from recognition.gallery import Match, SkuGallery, l2_normalise
from recognition.scale import SimulatedScale, calibrate
from recognition.tracker import CentroidTracker


# ------------------------------------------------------------------- gallery

def test_a_vector_matches_itself_exactly():
    g = SkuGallery(16)
    rng = np.random.default_rng(0)
    g.enrol("pepsi", rng.normal(size=(4, 16)))
    assert g.match(g.vectors[1])[0] == Match("pepsi", pytest.approx(1.0, abs=1e-5), 4)


def test_a_sku_is_scored_by_its_closest_view_not_its_average():
    """One good angle should be enough; a bad angle should not drag it down."""
    g = SkuGallery(3)
    g.enrol("target", np.array([[1, 0, 0], [0, 0, 1]], dtype=np.float32))
    g.enrol("other", np.array([[0.7, 0.7, 0]], dtype=np.float32))
    assert g.match(np.array([1, 0, 0]))[0].sku_id == "target"


def test_enrolling_twice_accumulates_views():
    g = SkuGallery(4)
    g.enrol("x", np.ones((2, 4)))
    assert g.enrol("x", np.ones((3, 4))) == 5


def test_removing_a_sku_leaves_the_others_intact():
    g = SkuGallery(4)
    g.enrol("a", np.eye(4)[:2])
    g.enrol("b", np.eye(4)[2:])
    assert g.remove("a") == 2
    assert g.skus == ["b"] and len(g) == 2


def test_an_empty_gallery_matches_nothing_rather_than_crashing():
    assert SkuGallery(8).match(np.ones(8)) == []


def test_a_zero_vector_does_not_divide_by_zero():
    assert np.all(np.isfinite(l2_normalise(np.zeros((1, 4)))))


def test_gallery_survives_a_round_trip_to_disk(tmp_path):
    g = SkuGallery(8)
    g.enrol("sprite", np.random.default_rng(1).normal(size=(3, 8)))
    g.save(tmp_path / "gallery.npz")
    back = SkuGallery.load(tmp_path / "gallery.npz")
    assert back.skus == g.skus and np.allclose(back.vectors, g.vectors)


def test_wrong_dimension_is_refused_rather_than_silently_reshaped():
    with pytest.raises(ValueError):
        SkuGallery(8).enrol("x", np.ones((1, 4)))


# -------------------------------------------------------------------- fusion

HARD_PAIR = [Match("flat", 0.880, 5), Match("ridged", 0.872, 5)]
PRIORS = {
    "flat": SkuPrior("flat", weight_g=75.0, size_mm=(190.0, 130.0)),
    "ridged": SkuPrior("ridged", weight_g=98.0, size_mm=(205.0, 140.0)),
}


def test_near_identical_packets_are_ambiguous_on_appearance_alone():
    d = fuse(HARD_PAIR, PRIORS)
    assert d.status is Status.AMBIGUOUS


def test_weight_resolves_what_appearance_cannot():
    """The whole point of the scale: 98 g is not 75 g, however alike they look."""
    d = fuse(HARD_PAIR, PRIORS, measured_weight_g=97.4)
    assert d.status is Status.ACCEPTED and d.sku_id == "ridged"


def test_size_alone_also_resolves_the_pair():
    d = fuse(HARD_PAIR, PRIORS, measured_size_mm=(205.0, 140.0))
    assert d.sku_id == "ridged"


#: threshold stated here rather than inherited from the default, so these test
#: the rejection *logic* and not whatever constant happens to ship
STRICT = FusionConfig(reject_below_cosine=0.50)


def test_a_product_nobody_enrolled_is_refused_not_guessed():
    """A closed-set classifier structurally cannot do this."""
    d = fuse([Match("flat", 0.41, 5)], PRIORS, cfg=STRICT)
    assert d.status is Status.UNKNOWN and d.sku_id is None


def test_a_product_above_the_threshold_is_accepted():
    d = fuse([Match("flat", 0.83, 5)], PRIORS, cfg=STRICT)
    assert d.status is Status.ACCEPTED and d.sku_id == "flat"


def test_weight_agreement_cannot_rescue_something_that_looks_wrong():
    """Abstention is an appearance decision; mass must not override it."""
    d = fuse([Match("flat", 0.30, 5)], PRIORS, measured_weight_g=75.0, cfg=STRICT)
    assert d.status is Status.UNKNOWN


def test_a_missing_prior_does_not_penalise_that_sku():
    """Otherwise adding weight data to some products would hurt the others."""
    priors = {"flat": PRIORS["flat"]}                    # ridged has no prior at all
    ranked = fuse(HARD_PAIR, priors).candidates
    assert next(c for c in ranked if c.sku_id == "ridged").weight == 0.0


def test_no_matches_means_unknown():
    assert fuse([], PRIORS).status is Status.UNKNOWN


# --------------------------------------------------------------- basket check

def test_tolerance_grows_with_the_square_root_of_basket_size():
    """Independent errors add in quadrature; adding them linearly gives a band
    so wide it swallows the swaps this check exists to catch."""
    assert basket_tolerance_g(10) < 4 * basket_tolerance_g(1)


def test_an_honest_basket_passes():
    assert verify_basket(PRIORS, {"flat": 1, "ridged": 1}, 173.0).ok


def test_swapping_a_light_item_for_a_heavy_one_is_caught():
    check = verify_basket(PRIORS, {"flat": 2}, 173.0)
    assert not check.ok and "heavier" in check.reason


def test_an_unscanned_item_in_the_bag_is_caught():
    assert not verify_basket(PRIORS, {"flat": 1}, 697.0).ok


def test_a_check_that_cannot_be_performed_reports_none_not_success():
    """Returning True here would mean the till claims to have verified a basket
    it had no reference weights for."""
    assert verify_basket({}, {"unknown-sku": 1}, 100.0) is None


def test_equal_mass_swap_is_a_known_blind_spot():
    """Documented, not hidden: this case is the camera's job, not the scale's."""
    priors = {**PRIORS, "decoy": SkuPrior("decoy", weight_g=76.0)}
    assert verify_basket(priors, {"flat": 1}, 76.0).ok


# ---------------------------------------------------------------- pack labels

@pytest.mark.parametrize("label, name, expected", [
    ("75g", "Lay's", 75.0),
    ("1.5kg", "Rice", 1500.0),
    ("325ml", "Coca-Cola Can", 340.0),          # 325 g of liquid + a 15 g can
    ("600ml", "Crystal Water Bottle", 622.0),
    (None, "", None),
    ("family size", "Chips", None),
])
def test_pack_labels_become_provisional_masses(label, name, expected):
    assert estimate_weight_g(label, name) == expected


# --------------------------------------------------------------------- scale

def test_the_scale_reports_what_is_on_it():
    s = SimulatedScale(seed=1)
    s.settle()
    s.place(75.0)
    assert s.settle() == pytest.approx(75.0, abs=3.0)


def test_taring_zeroes_the_current_load():
    s = SimulatedScale(seed=2)
    s.place(400.0)
    s.settle()
    s.tare()
    assert s.settle() == pytest.approx(0.0, abs=3.0)


def test_a_scale_that_has_not_settled_says_so():
    """The till must not price an item while the pan is still bouncing."""
    assert not SimulatedScale(seed=3).is_settled()


def test_two_point_calibration_recovers_the_cell_constants(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a: None)
    state = {"mass": 0.0}

    def read_raw():
        return 120000 + 412 * state["mass"]

    monkeypatch.setattr("builtins.input", lambda *a: state.__setitem__("mass", 500.0))
    counts_per_gram, offset = calibrate(read_raw, 500.0)
    assert counts_per_gram == pytest.approx(412.0) and offset == pytest.approx(120000.0)


def test_calibration_with_a_dead_cell_fails_loudly(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *a: None)
    with pytest.raises(RuntimeError, match="wiring"):
        calibrate(lambda: 120000.0, 500.0)


# ------------------------------------------------------------------- tracking

def test_an_object_that_stays_put_keeps_one_identity():
    """This is what stops one packet becoming two cart lines."""
    t = CentroidTracker()
    for _ in range(5):
        t.update([(10, 10, 90, 90)])
    assert len(t.tracks) == 1 and next(iter(t.tracks.values())).hits == 5


def test_two_objects_get_two_identities():
    t = CentroidTracker()
    for _ in range(3):
        t.update([(10, 10, 90, 90), (400, 400, 480, 480)])
    assert len(t.confirmed) == 2


def test_a_track_survives_a_dropped_frame():
    t = CentroidTracker(max_misses=3)
    t.update([(10, 10, 90, 90)])
    t.update([])
    t.update([(14, 12, 94, 92)])
    assert len(t.tracks) == 1


def test_a_track_that_leaves_is_forgotten():
    t = CentroidTracker(max_misses=2)
    t.update([(10, 10, 90, 90)])
    for _ in range(4):
        t.update([])
    assert not t.tracks


def test_voting_over_frames_outvotes_a_single_bad_frame():
    t = CentroidTracker()
    for _ in range(2):
        t.update([(10, 10, 90, 90)])
    track = next(iter(t.tracks.values()))
    for sku in ("pepsi", "pepsi", "sprite", "pepsi"):
        track.observe(sku, 0.9)
    sku, _, agreement = track.decision
    assert sku == "pepsi" and agreement == pytest.approx(0.75)


# ------------------------------------- a reading fusion is allowed to believe

def test_an_empty_pan_reports_no_reading_rather_than_zero():
    """The bug this guards: an empty pan reads about zero, and zero fed into
    fusion makes every product look far too heavy, dragging the decision to
    whichever enrolled product is lightest.  A confident wrong answer."""
    s = SimulatedScale(seed=4)
    s.settle()
    assert s.read_stable_grams() is None


def test_an_unsettled_pan_reports_no_reading():
    s = SimulatedScale(seed=5)
    s.place(200.0)
    assert s.read_stable_grams() is None          # window not full yet


def test_a_settled_loaded_pan_reports_its_reading():
    s = SimulatedScale(seed=6)
    s.place(200.0)
    s.settle()
    assert s.read_stable_grams() == pytest.approx(200.0, abs=3.0)


def test_no_weight_leaves_the_appearance_ranking_untouched():
    """Passing None must be neutral, not a vote for the lightest product."""
    with_none = fuse(HARD_PAIR, PRIORS, measured_weight_g=None).candidates
    assert [c.sku_id for c in with_none] == ["flat", "ridged"]
    assert all(c.weight == 0.0 for c in with_none)


def test_a_bogus_zero_weight_would_have_flipped_the_answer():
    """Documents why read_stable_grams exists: this is what used to happen."""
    flipped = fuse(HARD_PAIR, PRIORS, measured_weight_g=0.0)
    assert flipped.sku_id == "flat"               # the lighter of the two
    honest = fuse(HARD_PAIR, PRIORS, measured_weight_g=97.4)
    assert honest.sku_id == "ridged"
