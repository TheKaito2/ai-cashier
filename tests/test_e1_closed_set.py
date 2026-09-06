"""E1: the closed-set baseline the rest of the paper is argued against.

The version 1 detectors are AGPL weights that are never committed (NOTICE, and
`.gitignore`), and ultralytics is not in `requirements.txt`, so the one test that
loads them for real is skipped wherever they are absent.  Everything E1 itself
decides - which products it will score, over which labels, on which views, and
when it refuses - is tested here with a stand-in detector, so a fresh checkout
still covers the logic.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from recognition.proposer import Proposal, WholeFrameProposer
from research import experiments as X
from research.dataset import SyntheticSource, make_split

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = X.LEGACY_WEIGHTS


class Silent:
    """A detector that finds nothing, ever.

    Standing in for the real one lets the arithmetic be asserted exactly, which
    is the part that belongs to this repository rather than to ultralytics.
    """

    def propose(self, frame):
        return []


class Oracle:
    """A detector that names whichever product E1 last asked for frames of."""

    current: str = ""

    def __init__(self, by_sku: dict[str, str]):
        self.by_sku = by_sku

    def propose(self, frame):
        return [Proposal(box=(0, 0, 1, 1), area_px=1, confidence=0.5,
                         label=self.by_sku[Oracle.current])]


@pytest.fixture
def source():
    return SyntheticSource(views_per_sku=7)


@pytest.fixture(scope="module")
def embedder():
    """One inference session for the whole file - they are not free to build."""
    return X.make_embedder("mobilenet_v3_small")


def _run(source, embedder, monkeypatch, detectors, classes, **kw):
    monkeypatch.setattr(X, "load_legacy_detectors", lambda weights=WEIGHTS: (detectors, classes))
    proposer = X.BackgroundSubtractionProposer()
    proposer.calibrate(source.background())
    split = make_split(source.skus(), seed=0)
    return X.e1_closed_set_baseline(source, embedder, proposer, split, **kw)


# ------------------------------------------------------------------ refusals

def test_e1_refuses_a_source_with_no_legacy_products(source, embedder, monkeypatch):
    """A public benchmark has no version 1 classes; say so instead of scoring 0."""
    monkeypatch.setattr(SyntheticSource, "LEGACY", frozenset())
    r = _run(source, embedder, monkeypatch, [], set())
    assert r["insufficient_data"] and r["legacy_skus"] == []
    assert "research/PROTOCOL.md" in r["error"]


def test_e1_refuses_when_the_version_1_weights_are_absent(source, embedder, tmp_path):
    """The weights are gitignored, so a fresh checkout must get an explanation."""
    proposer = X.BackgroundSubtractionProposer()
    proposer.calibrate(source.background())
    split = make_split(source.skus(), seed=0)
    r = X.e1_closed_set_baseline(source, embedder, proposer, split,
                                 weights=(tmp_path / "chips_model.pt",))
    assert r["insufficient_data"] and "NOTICE" in r["error"]


def test_e1_refuses_when_the_legacy_products_have_no_class(source, embedder, monkeypatch):
    """Marked in_legacy_model but absent from both models: unscorable, not wrong."""
    r = _run(source, embedder, monkeypatch, [], {"Sprite"})
    assert r["insufficient_data"]
    assert set(r["unmapped_skus"]) == set(r["legacy_skus"])


# -------------------------------------------------------------------- scoring

def test_e1_scores_both_systems_on_the_same_probes(source, embedder, monkeypatch):
    """A detector that never answers still shares the probe set with the gallery."""
    r = _run(source, embedder, monkeypatch, [Silent()], set(X.legacy_class_to_sku()))

    closed, proposed = r["rows"]
    assert r["n_probes"] > 0
    assert closed["no_answer"] == 1.0 and closed["accuracy"] == 0.0
    # both rows come from the same loop, so the sample is shared by construction
    assert proposed["accuracy"] > 0.5
    assert set(r["scored_skus"]) == set(SyntheticSource.LEGACY)
    # the coverage column is the argument: 4 of 6 products against all 6
    assert closed["recognisable_skus"] == 4 and proposed["recognisable_skus"] == 6
    assert closed["catalogue_coverage"] == pytest.approx(4 / 6)
    assert proposed["catalogue_coverage"] == 1.0


def test_e1_credits_the_detector_when_it_names_the_right_product(source, embedder, monkeypatch):
    """A detector that gets every frame right scores 1.0 - the arithmetic holds."""
    to_sku = X.legacy_class_to_sku()

    # E1 asks for one product's frames at a time, so the oracle can watch for which
    original = source.frames

    def frames(sku_id):
        Oracle.current = sku_id
        return original(sku_id)

    monkeypatch.setattr(source, "frames", frames)
    oracle = Oracle({v: k for k, v in to_sku.items()})
    r = _run(source, embedder, monkeypatch, [oracle], set(to_sku))
    assert r["rows"][0]["accuracy"] == 1.0
    assert r["rows"][0]["no_answer"] == 0.0


def test_e1_scores_every_legacy_product_not_only_the_unseen_half(source, embedder, monkeypatch):
    """The detector trained on all twelve, so no half of them is held out from it."""
    r = _run(source, embedder, monkeypatch, [Silent()], set(X.legacy_class_to_sku()))
    split = make_split(source.skus(), seed=0)
    assert len(r["scored_skus"]) > r["n_legacy_in_unseen"]
    assert set(r["scored_skus"]) - set(split.unseen)          # some are in the seen half
    assert "split.unseen" in r["note"]


def test_the_detector_and_the_embedder_see_the_same_view(source, embedder):
    """`embed_all` drops frames the proposer found nothing in; E1 must drop them too.

    Otherwise the i-th embedding and the i-th photograph are different views and
    the two systems are quietly scored on different data.
    """
    class Blind:
        """Finds nothing in every third frame."""
        calibrated = True

        def __init__(self):
            self.n = 0

        def calibrate(self, frame):
            pass

        def propose(self, frame):
            self.n += 1
            return [] if self.n % 3 == 0 else WholeFrameProposer().propose(frame)

    sku = next(iter(SyntheticSource.LEGACY))
    kept = X.proposed_frames(source, sku, Blind())
    vectors = X.embed_all(source, embedder, Blind())
    assert len(kept) == len(vectors[sku]) < len(source.frames(sku))


# -------------------------------------------------------------- the mapping

def test_the_seed_catalogue_names_every_class_the_v1_detectors_know():
    """`yolo_class` in data/products.json is the only record of that mapping."""
    to_sku = X.legacy_class_to_sku()
    ids = {p["id"] for p in json.loads(X.LEGACY_CATALOGUE.read_text())["products"]}
    assert "Lay's-Flat-Original-Flavor" in to_sku
    assert to_sku["Lay's-Flat-Original-Flavor"] == "lays-flat-original"
    assert set(to_sku.values()) <= ids


def test_the_synthetic_catalogue_marks_the_products_the_v1_detector_knows(source):
    legacy = {s.sku_id for s in source.skus() if s.in_legacy_model}
    assert legacy == set(SyntheticSource.LEGACY)
    assert legacy <= set(X.legacy_class_to_sku().values())
    assert "never-enrolled-snack" not in legacy


def test_a_class_agnostic_proposal_carries_no_label():
    """Only a classifying proposer has an opinion about what it found."""
    frame = np.zeros((16, 16, 3), np.uint8)
    assert WholeFrameProposer().propose(frame)[0].label is None


# --------------------------------------------------------------- the table


def test_the_table_says_not_run_rather_than_printing_an_empty_one(tmp_path, monkeypatch):
    """A fresh checkout has no weights; the paper must show that, not blanks."""
    from research import report
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E1.json").write_text(json.dumps(
        {"experiment": "E1", "source": "captures", "insufficient_data": True,
         "error": "the version 1 detectors could not be loaded"}))
    report.table_e1()
    tex = (report.TABLES / "e1_closed_set.tex").read_text()
    assert "NOT RUN" in tex and "\\begin{tabular}" not in tex


def test_the_table_says_a_synthetic_row_is_not_a_result(tmp_path, monkeypatch):
    """The synthetic error flatters us - the detector has never seen a render."""
    from research import report
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E1.json").write_text(json.dumps(
        {"experiment": "E1", "source": "synthetic", "n_probes": 8,
         "scored_skus": ["a", "b", "c", "d"],
         "rows": [{"system": "Closed set", "accuracy": 0.05, "no_answer": 0.9,
                   "recognisable_skus": 4, "catalogue_coverage": 0.67},
                  {"system": "Proposed", "accuracy": 1.0, "no_answer": 0.0,
                   "recognisable_skus": 6, "catalogue_coverage": 1.0}]}))
    report.table_e1()
    tex = (report.TABLES / "e1_closed_set.tex").read_text()
    assert "Not a result" in tex and "measures the renderer" in tex


# --------------------------------------------------------- the real detectors

#: Loading the detectors pulls torch into the process, and torch and onnxruntime
#: abort each other at interpreter shutdown on macOS - all tests pass and the
#: process still dies with SIGABRT. `tests/test_no_ultralytics.py` already keeps
#: ultralytics behind a subprocess for its own reasons; this does the same for
#: this one, so the suite never has both runtimes loaded at once.
LEGACY_CLASSES_CHECK = r"""
import sys
sys.path.insert(0, %r)
from research import experiments as X
_, classes = X.load_legacy_detectors()
assert len(classes) == 12, sorted(classes)
assert {"Lay's-Flat-Original-Flavor", "Pepsi"} <= classes, sorted(classes)
assert set(X.legacy_class_to_sku()) >= classes, sorted(classes - set(X.legacy_class_to_sku()))
print("ok")
""" % str(ROOT)


@pytest.mark.skipif(not all(w.exists() for w in WEIGHTS),
                    reason="the version 1 weights are AGPL and never committed")
@pytest.mark.skipif(importlib.util.find_spec("ultralytics") is None,
                    reason="research-only, see requirements-research.txt")
def test_both_version_1_detectors_contribute_their_classes():
    """Each model numbers its own six classes 0..5, so the union must be by name."""
    r = subprocess.run([sys.executable, "-c", LEGACY_CLASSES_CHECK],
                       capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]
