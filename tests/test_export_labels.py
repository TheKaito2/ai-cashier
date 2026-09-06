"""The labels for the closed-set baseline are computed, not drawn.

`capture.py` already records which product a photograph is of, and the empty mat
photograph makes the rectangle recoverable by subtraction. So a training set for
the detector costs one command instead of three hundred hand-dragged boxes - and
because the boxes come from the same proposer the till runs, experiment E1
compares the two systems on identical crops rather than on somebody's mouse.

These tests build a real capture tree from the synthetic renderer and export it,
so the geometry is checked rather than assumed.
"""
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.synthetic import empty_mat, views  # noqa: E402
from tools.export_labels import export, to_yolo  # noqa: E402

SKUS = ["lays-flat-original", "pepsi", "tasto-seaweed"]


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    """A capture session, the way research/capture.py would leave it."""
    root = tmp_path_factory.mktemp("session")
    mat = root / "mat_background.png"
    cv2.imwrite(str(mat), empty_mat())
    captures = root / "captures"
    for sku in SKUS:
        (captures / sku).mkdir(parents=True)
        for i, frame in enumerate(views(sku, 8, seed=100)):
            cv2.imwrite(str(captures / sku / f"{i:03d}.jpg"), frame)
    return captures, mat, root


@pytest.fixture(scope="module")
def exported(captured, tmp_path_factory):
    captures, mat, _ = captured
    out = tmp_path_factory.mktemp("yolo")
    return export(captures, mat, out, k=5), out


# ------------------------------------------------------------ the geometry

def test_pixel_corners_become_the_fractions_yolo_expects():
    # a 40x20 box in the middle of a 100x100 image
    cx, cy, w, h = to_yolo((30, 40, 70, 60), 100, 100)
    assert (cx, cy, w, h) == (0.5, 0.5, 0.4, 0.2)


def test_every_label_is_inside_the_image_and_not_empty(exported):
    _, out = exported
    labels = list((out / "labels").rglob("*.txt"))
    assert labels, "no labels were written at all"
    for path in labels:
        index, cx, cy, w, h = path.read_text().split()
        assert int(index) >= 0
        for value in (float(cx), float(cy), float(w), float(h)):
            assert 0.0 <= value <= 1.0, f"{path.name} has a box outside the image"
        assert float(w) > 0.01 and float(h) > 0.01, f"{path.name} has a degenerate box"


def test_the_box_actually_covers_the_product(exported, captured):
    """A label that is merely well-formed is not a label that is right."""
    _, out = exported
    label = sorted((out / "labels" / "train").glob("lays-flat-original-*.txt"))[0]
    image = out / "images" / "train" / (label.stem + ".jpg")
    frame = cv2.imread(str(image))
    h, w = frame.shape[:2]
    _, cx, cy, bw, bh = (float(v) for v in label.read_text().split())

    # the product is rendered somewhere on the mat, so its box must be a real
    # part of the frame rather than the whole thing or a speck
    assert 0.01 < bw * bh < 0.9, "the box is either the whole mat or nothing"
    inside = frame[int((cy - bh / 2) * h):int((cy + bh / 2) * h),
                   int((cx - bw / 2) * w):int((cx + bw / 2) * w)]
    assert inside.size, "the box does not intersect the image"
    assert inside.std() > 3, "the box covers flat mat, not a product"


# --------------------------------------------------------------- the split

def test_training_uses_the_views_enrolment_uses(exported):
    """Both systems must learn from the same examples, or E1 compares nothing."""
    report, out = exported
    assert report["train"] == len(SKUS) * 5
    assert report["val"] == len(SKUS) * 3
    for path in (out / "images" / "train").glob("*.jpg"):
        assert int(path.stem.split("-")[-1]) < 5
    for path in (out / "images" / "val").glob("*.jpg"):
        assert int(path.stem.split("-")[-1]) >= 5


def test_each_image_has_exactly_one_label_beside_it(exported):
    _, out = exported
    for split in ("train", "val"):
        images = {p.stem for p in (out / "images" / split).glob("*.jpg")}
        labels = {p.stem for p in (out / "labels" / split).glob("*.txt")}
        assert images == labels, f"{split} has an image without a label, or the reverse"


def test_class_numbers_are_stable_and_match_the_manifest_file(exported):
    report, out = exported
    yaml = (out / "data.yaml").read_text()
    assert report["classes"] == sorted(SKUS)
    for i, sku in enumerate(report["classes"]):
        assert f"  {i}: {sku}" in yaml
    assert "do not edit" in yaml and "never drawn by hand" in yaml


# ------------------------------------------------------------- refusals

def test_a_photograph_the_mat_subtraction_cannot_explain_is_left_out(tmp_path):
    """An empty label would say "there is nothing here", which is false and
    teaches the detector to miss the product. Dropping it and saying so is the
    only honest option."""
    mat_frame = empty_mat()
    mat = tmp_path / "mat.png"
    cv2.imwrite(str(mat), mat_frame)
    captures = tmp_path / "captures"
    (captures / "pepsi").mkdir(parents=True)
    cv2.imwrite(str(captures / "pepsi" / "000.jpg"), mat_frame)      # mat, no product
    for i, frame in enumerate(views("pepsi", 2, seed=100), start=1):
        cv2.imwrite(str(captures / "pepsi" / f"{i:03d}.jpg"), frame)

    report = export(captures, mat, tmp_path / "out", k=5)

    assert report["train"] == 2, "the empty frame was labelled anyway"
    assert "pepsi" in report["skipped"]
    assert not (tmp_path / "out" / "labels" / "train" / "pepsi-000.txt").exists()


def test_a_missing_mat_photograph_stops_the_export(tmp_path):
    with pytest.raises(SystemExit, match="photograph the empty mat"):
        export(tmp_path / "captures", tmp_path / "absent.png", tmp_path / "out")


def test_an_empty_capture_folder_says_so(tmp_path):
    mat = tmp_path / "mat.png"
    cv2.imwrite(str(mat), empty_mat())
    (tmp_path / "captures").mkdir()
    with pytest.raises(SystemExit, match="no captures"):
        export(tmp_path / "captures", mat, tmp_path / "out")
