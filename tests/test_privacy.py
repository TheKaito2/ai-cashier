"""The recognition path never writes a frame to disk (docs/PRIVACY.md)."""
import builtins
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from recognition.proposer import mask_above_mat

ROOT = Path(__file__).resolve().parents[1]


def test_no_file_write_exists_in_the_recognition_package():
    banned = re.compile(r"imwrite|np\.save|\.save\(|open\([^)]*['\"]w")
    offenders = []
    for path in (ROOT / "recognition").glob("*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if banned.search(line) and path.name not in ("gallery.py", "metrology.py"):
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    # gallery.py saves vectors, never pixels; metrology.py writes the printable
    # ArUco marker sheet, which is generated, not photographed.  Nothing else may.
    assert not offenders, offenders


def test_processing_a_frame_writes_nothing(monkeypatch, tmp_path):
    from recognition.gallery import SkuGallery
    from recognition.pipeline import RecognitionPipeline
    from recognition.proposer import BackgroundSubtractionProposer
    from tests.synthetic import empty_mat, scene

    class NoEmbedder:
        dim = 8
        def embed(self, crops):
            return np.random.default_rng(0).normal(size=(len(crops), 8)).astype(np.float32)

    def boom(*a, **k):
        raise AssertionError("the recognition path tried to write a file")
    monkeypatch.setattr(cv2, "imwrite", boom)
    monkeypatch.setattr(np, "save", boom)
    real_open = builtins.open
    def guarded_open(file, mode="r", *a, **k):
        if any(ch in mode for ch in "wa+"):
            boom()
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", guarded_open)

    prop = BackgroundSubtractionProposer()
    prop.calibrate(empty_mat())
    pipe = RecognitionPipeline(prop, NoEmbedder(), SkuGallery(8))
    pipe.enrol("pepsi", [scene(["pepsi"], seed=1)])
    for i in range(4):
        pipe.process(scene(["pepsi"], seed=10 + i))


def test_front_camera_is_blind_above_the_mat_plane():
    frame = np.full((100, 50, 3), 200, np.uint8)
    masked = mask_above_mat(frame, 40)
    assert masked[:40].max() == 0 and masked[40:].min() == 200
    assert frame.max() == 200                      # original untouched
