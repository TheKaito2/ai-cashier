"""A region that differs from the mat is not yet a product.

Written after the first real rig: on a white table the proposer offered the
table's own edges, a cable, the floor and a moving shadow as products, because
"differs from the empty mat, and is bigger than 4000 px" was the entire test.
Each case here is one of the shapes that actually appeared.
"""
import numpy as np

from recognition.proposer import BackgroundSubtractionProposer

MAT = (100, 110, 120)          # the same warm mid-grey test_proposer_shadows uses
H, W = 480, 640


def _mat():
    return np.full((H, W, 3), MAT, np.uint8)


def _calibrated(**kw):
    p = BackgroundSubtractionProposer(**kw)
    p.calibrate(_mat())
    return p


PACKET = (40, 190, 210)        # a warm packet, clearly not the mat


def test_an_unchanged_mat_proposes_nothing():
    assert _calibrated().propose(_mat()) == []


def test_the_whole_frame_going_dark_is_not_a_product():
    """Auto-exposure drift, or a mat photograph that no longer matches the mat.
    Half brightness is below the shadow rule's 0.55 floor, so the shadow rule
    deliberately keeps it and the objectness rules have to refuse it.  This is
    the failure that was seen on the rig: one proposal covering 99.3 % of the
    frame, which then reads as a single unrecognisable product."""
    frame = (_mat().astype(np.float32) * 0.5).astype(np.uint8)
    assert _calibrated().propose(frame) == []


def test_a_region_too_large_to_be_a_packet_is_refused_on_size_alone():
    """Half the mat, inset from every border, solid, unremarkable aspect - so
    only the upper area bound can refuse it.  Without one, a lighting change
    over part of the mat becomes the biggest 'product' on the table and sorts
    to the top."""
    frame = _mat()
    frame[60:420, 100:540] = PACKET            # 51.6 % of the frame
    assert _calibrated().propose(frame) == []


def test_a_long_thin_strip_is_not_a_product():
    """The table edge and the cable. Well clear of the border, so only the
    aspect rule can reject it."""
    frame = _mat()
    frame[200:230, 20:620] = PACKET            # 600 x 30, aspect 20
    assert _calibrated().propose(frame) == []


def test_a_region_that_does_not_fill_its_own_box_is_not_a_product():
    """An L of shadow round two sides of something. Its contour area passes the
    floor, but the box it would hand the embedder is mostly mat."""
    frame = _mat()
    frame[120:360, 200:248] = PACKET           # the upright of the L
    frame[312:360, 200:440] = PACKET           # the foot
    assert _calibrated().propose(frame) == []


def test_something_touching_the_frame_edge_is_not_a_product():
    frame = _mat()
    frame[150:330, 0:240] = PACKET             # flush against the left edge
    assert _calibrated().propose(frame) == []


def test_a_packet_well_inside_the_mat_is_still_found():
    """The rules above must not eat the thing the till exists to see."""
    frame = _mat()
    frame[150:330, 200:440] = PACKET
    boxes = _calibrated().propose(frame)
    assert len(boxes) == 1
    x1, y1, x2, y2 = boxes[0].box
    assert abs(x1 - 200) < 12 and abs(y1 - 150) < 12
    assert abs(x2 - 440) < 12 and abs(y2 - 330) < 12


def test_a_region_outside_the_mat_is_ignored_and_one_inside_is_not():
    """rig.mat_roi. Both patches are identical; only their position differs."""
    roi = (150, 100, 500, 400)

    outside = _mat()
    outside[20:120, 20:160] = PACKET           # beyond the mat: the floor
    assert _calibrated(roi=roi).propose(outside) == []

    inside = _mat()
    inside[180:300, 200:380] = PACKET
    assert len(_calibrated(roi=roi).propose(inside)) == 1


def test_boxes_stay_in_full_frame_coordinates_when_a_roi_is_set():
    """The mask is masked, not the frame. If this ever returns roi-relative
    coordinates the tracker, the crops and the overlay all silently misalign."""
    roi = (150, 100, 500, 400)
    frame = _mat()
    frame[180:300, 200:380] = PACKET
    x1, y1, x2, y2 = _calibrated(roi=roi).propose(frame)[0].box
    assert abs(x1 - 200) < 12 and abs(y1 - 180) < 12
    assert abs(x2 - 380) < 12 and abs(y2 - 300) < 12
