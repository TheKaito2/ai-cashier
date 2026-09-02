"""Freezing the centre: enrolling a product must not move anyone else's score
(docs/research/09, D7)."""
import numpy as np
import pytest

from recognition.gallery import SkuGallery

DIM = 16


def _cluster(rng, n=5):
    centre = rng.normal(size=DIM)
    return centre + 0.15 * rng.normal(size=(n, DIM))


def _gallery(rng, skus):
    g = SkuGallery(DIM)
    clusters = {}
    for sku in skus:
        clusters[sku] = _cluster(rng)
        g.enrol(sku, clusters[sku])
    return g, clusters


def _scores(g, queries):
    return {sku: g.match(q, top_k=1)[0].score for sku, q in queries.items()}


def test_a_floating_centre_moves_every_score_when_a_product_is_enrolled():
    rng = np.random.default_rng(0)
    g, clusters = _gallery(rng, ["a", "b", "c", "d"])
    queries = {s: c[0] + 0.1 * rng.normal(size=DIM) for s, c in clusters.items()}
    before = _scores(g, queries)
    g.enrol("e", _cluster(rng))
    after = _scores(g, queries)
    assert any(abs(before[s] - after[s]) > 1e-3 for s in before)


def test_a_frozen_centre_keeps_existing_scores_exactly():
    rng = np.random.default_rng(0)
    g, clusters = _gallery(rng, ["a", "b", "c", "d"])
    queries = {s: c[0] + 0.1 * rng.normal(size=DIM) for s, c in clusters.items()}
    g.freeze_centre()
    before = _scores(g, queries)
    g.enrol("e", _cluster(rng))
    g.enrol("f", _cluster(rng))
    after = _scores(g, queries)
    for sku in before:
        assert after[sku] == pytest.approx(before[sku], abs=1e-6)
    assert g.match(queries["a"])[0].sku_id == "a"


def test_the_frozen_centre_survives_save_and_load(tmp_path):
    rng = np.random.default_rng(1)
    g, clusters = _gallery(rng, ["a", "b", "c", "d"])
    g.freeze_centre()
    g.save(tmp_path / "g.npz")
    back = SkuGallery.load(tmp_path / "g.npz")
    assert back.frozen and np.allclose(back.centre, g.centre)
    q = clusters["b"][1]
    assert back.match(q)[0].score == pytest.approx(g.match(q)[0].score, abs=1e-6)


def test_thawing_lets_the_centre_float_again():
    rng = np.random.default_rng(2)
    g, _ = _gallery(rng, ["a", "b", "c", "d"])
    g.freeze_centre()
    g.enrol("e", _cluster(rng))
    assert not np.allclose(g.centre, g.mean)
    g.thaw_centre()
    assert not g.frozen and np.allclose(g.reference(), g.mean)


def test_prototype_scoring_is_available_for_the_ablation():
    rng = np.random.default_rng(3)
    g, clusters = _gallery(rng, ["a", "b", "c", "d"])
    q = clusters["c"][0]
    assert g.match_prototypes(q)[0].sku_id == "c"
