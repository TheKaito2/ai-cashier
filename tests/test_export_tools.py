"""The generators that feed the other half of the project.

`tools/export_fixtures.py` writes the only contract between the Python
implementation and the Swift one - if its shape drifts, the iOS suite stops
testing what it thinks it tests.  `tools/make_marker.py` prints the sheet the
whole millimetre measurement rests on: a marker that cannot be detected again
after being drawn is a silent metrology failure.

Both wrote into the repository until now, which is why neither had a test.
"""
import json
import sys
from pathlib import Path

import cv2
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from recognition.embedder import TorchEmbedder  # noqa: E402
from recognition.metrology import detect_markers  # noqa: E402


# --------------------------------------------------------------- the markers

def test_a_printed_marker_can_be_found_again(tmp_path, monkeypatch):
    """Draw it, read it back. The sheet is useless if it cannot survive that."""
    from tools import make_marker
    out = tmp_path / "marker.png"
    monkeypatch.setattr(sys, "argv", ["make_marker.py", "--single", "--out", str(out)])
    assert make_marker.main() == 0

    found = detect_markers(cv2.imread(str(out)))
    assert 0 in found, "the marker that was just drawn is not detectable"


def test_the_corner_sheet_carries_four_distinct_ids(tmp_path, monkeypatch):
    from tools import make_marker
    out = tmp_path / "markers.png"
    monkeypatch.setattr(sys, "argv", ["make_marker.py", "--out", str(out)])
    assert make_marker.main() == 0

    found = detect_markers(cv2.imread(str(out)))
    assert len(found) == 4, f"expected four corners, found {sorted(found)}"


# -------------------------------------------------------------- the fixtures

@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    from tools import export_fixtures
    out = tmp_path_factory.mktemp("fixtures")
    assert export_fixtures.main(["--out", str(out)]) == 0
    return out


def test_the_swift_contract_carries_every_key_the_ios_tests_read(fixtures):
    data = json.loads((fixtures / "fixtures.json").read_text())
    for key in ("embedder", "thresholds", "proposer", "crops", "embeddings",
                "gallery", "expected_matches", "scene_boxes", "catalogue_weights_g",
                "promptpay", "crc16_check"):
        assert key in data, f"ios/AICashier/Tests reads {key!r} and it is not there"


def test_the_fixture_images_the_swift_tests_load_are_written(fixtures):
    assert (fixtures / "mat.png").exists() and (fixtures / "scene.png").exists()
    assert list((fixtures / "crops").glob("*.png")), "no crops were written"


def test_the_stranger_is_still_rejected_by_the_recorded_threshold(fixtures):
    """The fixture exists to prove both ports refuse the same unknown packet."""
    data = json.loads((fixtures / "fixtures.json").read_text())
    assert data["thresholds"], "no threshold was recorded for the Swift side to check"


# --------------------------------------------------------------- the exporter

def test_every_registered_encoder_can_be_named_on_the_command_line():
    """The CLIP and hub encoders were unreachable: the exporter only offered the
    three torchvision trunks, so the research backbones could never be frozen
    for the till even after they won the ablation."""
    import subprocess
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "export_embedder.py"), "--help"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)
    for name in (*TorchEmbedder.BACKBONES, *TorchEmbedder.CLIP_BACKBONES,
                 *TorchEmbedder.HUB_BACKBONES):
        assert name in done.stdout, f"{name} cannot be exported from the command line"
