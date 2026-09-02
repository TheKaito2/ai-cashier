"""A stand-in for real product photographs.

The rig and the capture session do not exist yet, so these tests cannot measure
recognition *accuracy* - that is what research/exp2 is for, once the products
have been photographed.  What they can and do verify is that the system logic is
correct end to end: that enrolling works, that a matching item is found, that an
item nobody enrolled is refused rather than guessed at, and that weight breaks a
tie the camera cannot.

Each SKU is rendered with its own colour, banding and logo so an ImageNet trunk
has something real to separate.  The "hard pair" deliberately differs by almost
nothing, standing in for Lay's Flat Original versus Lay's Ridged Original.
"""

from __future__ import annotations

import zlib

import cv2
import numpy as np


def _stable_seed(text: str) -> int:
    """A seed that is the same in every process.

    Python's built-in hash() is salted per interpreter, so seeding a product's
    artwork with it renders a *different* packet in every run - enrolment and
    recognition then look at two different products and every experiment built
    on them is quietly meaningless.
    """
    return zlib.crc32(text.encode()) % 100_000

MAT = (720, 1280)


def empty_mat(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mat = np.full((*MAT, 3), 44, np.uint8)
    noise = rng.integers(0, 9, mat.shape, dtype=np.int64).astype(np.uint8)
    return cv2.add(mat, noise)


def packet(seed: int, base: tuple[int, int, int], stripe: tuple[int, int, int],
           size: tuple[int, int] = (300, 380), logo: str = "circle") -> np.ndarray:
    """One product's packaging."""
    rng = np.random.default_rng(seed)
    w, h = size
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = base

    for y in range(0, h, 26):                                  # printed banding
        cv2.line(img, (0, y), (w, y), stripe, 7)

    cx, cy = w // 2, h // 3
    if logo == "circle":
        cv2.circle(img, (cx, cy), w // 5, (250, 250, 250), -1)
        cv2.circle(img, (cx, cy), w // 8, base, -1)
    elif logo == "diamond":
        pts = np.array([[cx, cy - w // 4], [cx + w // 4, cy],
                        [cx, cy + w // 4], [cx - w // 4, cy]])
        cv2.fillPoly(img, [pts], (250, 250, 250))
    else:
        cv2.rectangle(img, (cx - w // 4, cy - w // 5), (cx + w // 4, cy + w // 5),
                      (250, 250, 250), -1)

    for i in range(4):                                          # text-like bars
        y = int(h * 0.68) + i * 18
        cv2.rectangle(img, (24, y), (24 + rng.integers(w // 3, w - 60), y + 9),
                      (240, 240, 240), -1)
    return img


#: id -> (base BGR, stripe BGR, size px, logo, true mass g)
CATALOGUE = {
    "lays-flat-original":   ((30, 130, 220), (12, 90, 170),  (300, 380), "circle",  75.0),
    # the hard pair: same brand, near-identical art, different mass
    "lays-ridged-original": ((34, 138, 226), (16, 96, 176),  (310, 392), "circle",  98.0),
    "tasto-seaweed":        ((40, 150, 70),  (20, 110, 45),  (290, 370), "diamond", 68.0),
    "pepsi":                ((190, 60, 40),  (140, 30, 20),  (150, 320), "square", 340.0),
    "crystal-water":        ((210, 200, 190), (170, 165, 160), (140, 340), "square", 622.0),
    "never-enrolled-snack": ((60, 60, 190),  (30, 30, 140),  (280, 360), "diamond", 55.0),
}


def scene(sku_ids: list[str], seed: int = 0, jitter: bool = True) -> np.ndarray:
    """Lay products on the mat, with the variation a real capture would have."""
    rng = np.random.default_rng(seed)
    frame = empty_mat()
    x = 120
    for sku in sku_ids:
        base, stripe, size, logo, _ = CATALOGUE[sku]
        img = packet(_stable_seed(sku), base, stripe, size, logo)

        if jitter:
            angle = rng.uniform(-7, 7)                          # never placed square
            m = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), angle, 1.0)
            img = cv2.warpAffine(img, m, (img.shape[1], img.shape[0]),
                                 borderValue=(44, 44, 44))
            img = cv2.convertScaleAbs(img, alpha=rng.uniform(0.88, 1.12),  # lighting
                                      beta=rng.uniform(-10, 10))

        y = 170 + (rng.integers(-18, 18) if jitter else 0)
        h, w = img.shape[:2]
        frame[y:y + h, x:x + w] = img
        x += w + 60
    return frame


def views(sku_id: str, n: int, seed: int = 0) -> list[np.ndarray]:
    """n separate placements of one product, as an enrolment or test set."""
    return [scene([sku_id], seed=seed + i) for i in range(n)]


def true_mass(sku_id: str) -> float:
    return CATALOGUE[sku_id][4]
