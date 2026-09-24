"""Version 1's detector, as a mode the till can switch to.

It is here to be compared against, so what matters is that it behaves honestly:
it names the twelve things it knows, it says nothing useful about anything else,
and it never pretends a product could be enrolled into it.
"""
import numpy as np
import pytest

import recognition.proposer as proposer_module
from recognition.closed_set import ClosedSetRecogniser, class_to_sku
from recognition.fusion import Status
from recognition.proposer import Proposal

FRAME = np.zeros((480, 640, 3), np.uint8)


class StubDetector:
    """Stands in for ultralytics, which the till must not require to start."""

    def __init__(self, model_path, conf=0.25, imgsz=416):
        self.model_path = model_path
        self.found: list[Proposal] = []

    @property
    def class_names(self):
        return {0: "Lay's-Flat-Original-Flavor", 1: "Pepsi"}

    def propose(self, frame):
        return self.found


@pytest.fixture
def detector(monkeypatch, tmp_path):
    monkeypatch.setattr(proposer_module, "YoloProposer", StubDetector)
    weights = tmp_path / "chips_model.pt"
    weights.write_bytes(b"not really a model")

    def build(mapping=None):
        return ClosedSetRecogniser(
            [weights], mapping if mapping is not None
            else {"Lay's-Flat-Original-Flavor": "lays-flat-original"})
    return build


def test_a_trained_class_becomes_the_shop_s_product(detector):
    r = detector()
    r.detectors[0].found = [Proposal(box=(10, 10, 90, 120), area_px=9600,
                                     confidence=0.91,
                                     label="Lay's-Flat-Original-Flavor")]
    items = r.process(FRAME)
    assert len(items) == 1
    assert items[0].sku_id == "lays-flat-original"
    assert items[0].status is Status.ACCEPTED
    assert items[0].box == (10, 10, 90, 120)


def test_a_class_with_no_product_row_is_not_priced(detector):
    """A detector class the shop does not stock must not become a sale."""
    r = detector(mapping={})
    r.detectors[0].found = [Proposal(box=(0, 0, 50, 50), area_px=2500,
                                     confidence=0.8, label="Pepsi")]
    items = r.process(FRAME)
    assert items[0].status is Status.UNKNOWN
    assert items[0].sku_id is None


def test_it_finds_several_products_in_one_frame(detector):
    r = detector(mapping={"Lay's-Flat-Original-Flavor": "lays-flat-original",
                          "Pepsi": "pepsi"})
    r.detectors[0].found = [
        Proposal(box=(0, 0, 50, 50), area_px=2500, confidence=0.9,
                 label="Lay's-Flat-Original-Flavor"),
        Proposal(box=(60, 0, 110, 50), area_px=2500, confidence=0.8, label="Pepsi")]
    assert [i.sku_id for i in r.process(FRAME)] == ["lays-flat-original", "pepsi"]


def test_nothing_on_the_mat_is_nothing(detector):
    assert detector().process(FRAME) == []


def test_it_reports_the_only_twelve_things_it_can_ever_say(detector):
    """The ceiling, stated by the object itself, so the till can show it."""
    assert detector().classes == ["Lay's-Flat-Original-Flavor", "Pepsi"]


def test_missing_weights_say_what_is_missing_and_why(monkeypatch, tmp_path):
    monkeypatch.setattr(proposer_module, "YoloProposer", StubDetector)
    with pytest.raises(FileNotFoundError) as e:
        ClosedSetRecogniser([tmp_path / "absent.pt"], {})
    assert "gitignored" in str(e.value)


def test_it_offers_no_gallery_because_it_cannot_learn(detector):
    """The till reads these to decide whether enrolment is possible at all."""
    r = detector()
    assert r.gallery is None and r.metrology is None


def test_the_mat_calibration_is_accepted_and_ignored(detector):
    """A detector has no empty mat to photograph, but the till must not error."""
    r = detector()
    r.calibrate(FRAME, marker_mm=60.0)
    assert r.proposer.calibrated is True


def test_class_to_sku_reads_the_legacy_column():
    products = [{"id": "pepsi", "yolo_class": "Pepsi"},
                {"id": "kanom", "yolo_class": None},
                {"id": "lays", "yolo_class": "Lay's-Flat-Original-Flavor"}]
    assert class_to_sku(products) == {"Pepsi": "pepsi",
                                      "Lay's-Flat-Original-Flavor": "lays"}
