"""A shadow is the mat, darker.  It must not become a product (docs/research/09, D10)."""
import numpy as np

from recognition.proposer import BackgroundSubtractionProposer

MAT = (100, 110, 120)          # a slightly warm mid-grey, BGR


def _mat(h=480, w=640):
    return np.full((h, w, 3), MAT, np.uint8)


def _with_patch(colour):
    frame = _mat()
    frame[150:330, 200:440] = colour
    return frame


def _shadowed(ratio):
    return _with_patch(tuple(int(round(c * ratio)) for c in MAT))


def test_a_soft_shadow_on_the_mat_proposes_nothing():
    p = BackgroundSubtractionProposer()
    p.calibrate(_mat())
    assert p.propose(_shadowed(0.6)) == []


def test_the_same_shadow_would_have_been_a_product_without_the_rule():
    p = BackgroundSubtractionProposer(shadow_chroma_eps=0.0)
    p.calibrate(_mat())
    assert len(p.propose(_shadowed(0.6))) == 1


def test_a_dark_packet_of_another_colour_is_still_found():
    p = BackgroundSubtractionProposer()
    p.calibrate(_mat())
    boxes = p.propose(_with_patch((140, 40, 40)))          # dark blue, similar intensity
    assert len(boxes) == 1
    x1, y1, x2, y2 = boxes[0].box
    assert abs(x1 - 200) < 12 and abs(y1 - 150) < 12 and abs(x2 - 440) < 12 and abs(y2 - 330) < 12


def test_a_black_packet_is_darker_than_any_shadow_and_is_found():
    p = BackgroundSubtractionProposer()
    p.calibrate(_mat())
    assert len(p.propose(_shadowed(0.25))) == 1
