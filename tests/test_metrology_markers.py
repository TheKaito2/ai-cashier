"""Four corner markers measure the far side of the mat better than one marker
extrapolated across it (docs/research/09, D12)."""
import cv2
import numpy as np
import pytest

from recognition.metrology import MatMetrology, detect_markers, marker_image, write_corner_markers_sheet

PX_PER_MM = 2.0
MARKER_MM = 60.0
LAYOUT = {0: (20.0, 20.0), 1: (520.0, 20.0), 2: (520.0, 320.0), 3: (20.0, 320.0)}
MAT_MM = (600, 400)


def _mat_canvas():
    """A 600 x 400 mm grey mat at 2 px/mm with four markers glued at the corners."""
    h, w = int(MAT_MM[1] * PX_PER_MM), int(MAT_MM[0] * PX_PER_MM)
    canvas = np.full((h, w), 128, np.uint8)
    for i, (x, y) in LAYOUT.items():
        tile = marker_image(MARKER_MM, dpi=25.4 * PX_PER_MM, marker_id=i)
        quiet = (tile.shape[0] - int(MARKER_MM * PX_PER_MM)) // 2
        y0, x0 = int(y * PX_PER_MM) - quiet, int(x * PX_PER_MM) - quiet
        canvas[y0:y0 + tile.shape[0], x0:x0 + tile.shape[1]] = tile
    return canvas


def _camera_view(canvas):
    """Photograph the mat from a slightly off-axis camera."""
    h, w = canvas.shape
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[90, 70], [1150, 40], [1230, 790], [40, 810]])
    H = cv2.getPerspectiveTransform(src, dst)
    image = cv2.warpPerspective(canvas, H, (1280, 840), borderValue=200)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), H


def _image_point(H, x_mm, y_mm):
    p = np.float32([[[x_mm * PX_PER_MM, y_mm * PX_PER_MM]]])
    return cv2.perspectiveTransform(p, H)[0, 0]


@pytest.fixture(scope="module")
def photo():
    return _camera_view(_mat_canvas())


def test_all_four_markers_are_seen(photo):
    image, _ = photo
    assert set(detect_markers(image)) == {0, 1, 2, 3}


def _span_error(m, H, a, b):
    pa, pb = _image_point(H, *a), _image_point(H, *b)
    measured = float(np.linalg.norm(np.diff(m.to_mm([pa, pb]), axis=0)))
    true = float(np.hypot(a[0] - b[0], a[1] - b[1]))
    return abs(measured - true)


def test_four_markers_measure_the_far_corner_within_a_millimetre(photo):
    image, H = photo
    four = MatMetrology.from_frame(image, MARKER_MM, layout_mm=LAYOUT)
    assert four is not None and four.n_markers == 4
    # a 100 mm span down at the far side of the mat from marker 0
    assert _span_error(four, H, (400, 350), (500, 350)) < 1.0
    assert _span_error(four, H, (300, 100), (300, 350)) < 1.0


def test_one_marker_is_worse_far_from_itself(photo):
    image, H = photo
    one = MatMetrology.from_frame(image, MARKER_MM)
    four = MatMetrology.from_frame(image, MARKER_MM, layout_mm=LAYOUT)
    assert one is not None and one.n_markers == 1
    e_one = _span_error(one, H, (400, 350), (500, 350))
    e_four = _span_error(four, H, (400, 350), (500, 350))
    assert e_four <= e_one


def test_string_keys_from_json_are_accepted(photo):
    image, _ = photo
    layout = {str(k): list(v) for k, v in LAYOUT.items()}
    assert MatMetrology.from_frame(image, MARKER_MM, layout_mm=layout).n_markers == 4


def test_the_printed_sheet_carries_four_distinct_ids(tmp_path):
    path = write_corner_markers_sheet(str(tmp_path / "markers.png"), dpi=150)
    sheet = cv2.imread(path)
    assert set(detect_markers(sheet)) == {0, 1, 2, 3}
