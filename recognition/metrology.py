"""Real-world size from printed markers on the mat.

ArUco markers of known side length, printed once and glued to the scan mat,
turn pixels into millimetres.  That gives a third way to tell products apart:
two crisp packets can look almost identical and weigh almost the same, but a
75 g packet and an 80 g packet are rarely the same size.

Cost: one sheet of paper.

One marker or four.  A single 60 mm marker fits a homography to four corners
60 mm apart and then extrapolates it across an A3 mat, where lens distortion and
the marker's own corner error grow with distance (docs/research/09, D12).  Four
markers at the mat corners fit the same homography to sixteen corners spanning
the whole mat.  `rig.marker_positions_mm` in config/settings.json says where
each marker's top-left corner sits; with no layout the first marker found is the
origin, exactly as before.

Note on accuracy: the homography is fitted to the mat plane, so a tall object's
top face projects larger than its true footprint and is over-measured.  That
does not matter here, because the gallery stores the *measured* size recorded at
enrolment on this same rig - the projection bias is identical at enrolment and
at checkout and cancels out.  These numbers are repeatable, not absolute.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

DEFAULT_DICT = cv2.aruco.DICT_4X4_50
Layout = dict[int, tuple[float, float]]


def _detector(dict_id: int):
    """cv2 moved the ArUco API in 4.7; support both."""
    dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
    if hasattr(cv2.aruco, "ArucoDetector"):
        return cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    return None, dictionary


def detect_markers(frame: np.ndarray, dict_id: int = DEFAULT_DICT) -> dict[int, np.ndarray]:
    """marker id -> its 4 image-space corners, clockwise from top-left."""
    det = _detector(dict_id)
    if det is not None and hasattr(det, "detectMarkers"):
        corners, ids, _ = det.detectMarkers(frame)
    else:                                                   # pragma: no cover - old cv2
        _, dictionary = det
        corners, ids, _ = cv2.aruco.detectMarkers(frame, dictionary)
    if ids is None or not len(corners):
        return {}
    return {int(i): np.asarray(c, dtype=np.float32).reshape(4, 2)
            for i, c in zip(ids.flatten(), corners)}


def detect_marker(frame: np.ndarray, dict_id: int = DEFAULT_DICT) -> np.ndarray | None:
    """The first marker's corners, or None."""
    found = detect_markers(frame, dict_id)
    return next(iter(found.values())) if found else None


def _square(x: float, y: float, side: float) -> np.ndarray:
    return np.array([[x, y], [x + side, y], [x + side, y + side], [x, y + side]], np.float32)


@dataclass
class MatMetrology:
    """Maps image pixels to millimetres on the mat plane."""

    homography: np.ndarray      # 3x3, image px -> mat mm
    marker_mm: float
    n_markers: int = 1

    @classmethod
    def from_frame(cls, frame: np.ndarray, marker_mm: float,
                   dict_id: int = DEFAULT_DICT,
                   layout_mm: Layout | dict | None = None) -> "MatMetrology | None":
        found = detect_markers(frame, dict_id)
        if not found:
            return None

        if layout_mm:
            # JSON gives string keys; accept either
            layout = {int(k): (float(v[0]), float(v[1])) for k, v in layout_mm.items()}
            used = [i for i in found if i in layout]
            if not used:
                return None
            src = np.vstack([found[i] for i in used])
            dst = np.vstack([_square(*layout[i], marker_mm) for i in used])
        else:
            first = next(iter(found))
            used = [first]
            src, dst = found[first], _square(0.0, 0.0, marker_mm)

        H, _ = cv2.findHomography(src, dst, 0)
        if H is None:
            return None
        return cls(homography=H, marker_mm=marker_mm, n_markers=len(used))

    def to_mm(self, points: np.ndarray) -> np.ndarray:
        """Project image points onto the mat plane, in millimetres."""
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
        return cv2.perspectiveTransform(pts, self.homography).reshape(-1, 2)

    def box_mm(self, box: tuple[int, int, int, int]) -> tuple[float, float]:
        """Footprint of a bounding box, as (longer_mm, shorter_mm).

        Sorted so an object rotated on the mat gives the same pair of numbers.
        """
        x1, y1, x2, y2 = box
        quad = self.to_mm([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
        (_, _), (w, h), _ = cv2.minAreaRect(quad.astype(np.float32))
        return (max(w, h), min(w, h))

    @property
    def px_per_mm(self) -> float:
        """Rough scale at the mat centre, for sanity checks and overlays."""
        probe = self.to_mm([(0, 0), (100, 0)])
        mm = float(np.linalg.norm(probe[1] - probe[0]))
        return 100.0 / mm if mm > 1e-9 else 0.0


def marker_image(marker_mm: float = 60.0, dpi: int = 300, marker_id: int = 0,
                 dict_id: int = DEFAULT_DICT) -> np.ndarray:
    """One marker with its white quiet zone, at print resolution."""
    px = int(round(marker_mm / 25.4 * dpi))
    dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
    img = cv2.aruco.generateImageMarker(dictionary, marker_id, px)
    quiet = px // 5                                  # ArUco needs a white margin
    sheet = np.full((px + 2 * quiet, px + 2 * quiet), 255, np.uint8)
    sheet[quiet:quiet + px, quiet:quiet + px] = img
    return sheet


def write_marker_sheet(path: str, marker_mm: float = 60.0, dpi: int = 300,
                       marker_id: int = 0, dict_id: int = DEFAULT_DICT) -> str:
    """Render one marker to print and glue on the mat."""
    cv2.imwrite(path, marker_image(marker_mm, dpi, marker_id, dict_id))
    return path


def write_corner_markers_sheet(path: str, marker_mm: float = 60.0, dpi: int = 300,
                               ids: tuple[int, ...] = (0, 1, 2, 3),
                               dict_id: int = DEFAULT_DICT) -> str:
    """Four markers on one sheet, labelled, to cut out and glue at the mat corners."""
    tiles = [marker_image(marker_mm, dpi, i, dict_id) for i in ids]
    side = tiles[0].shape[0]
    gap = side // 6
    label_h = side // 4
    sheet = np.full((side + label_h + 2 * gap, len(tiles) * (side + gap) + gap), 255, np.uint8)
    for n, (i, tile) in enumerate(zip(ids, tiles)):
        x = gap + n * (side + gap)
        sheet[gap:gap + side, x:x + side] = tile
        cv2.putText(sheet, f"id {i}", (x, gap + side + label_h - gap // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, side / 400.0, 0, max(1, side // 150), cv2.LINE_AA)
    cv2.imwrite(path, sheet)
    return path
