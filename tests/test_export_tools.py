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


# ------------------------------------------------- the preprocessing contract

def test_an_exported_graph_carries_the_statistics_it_was_trained_with(tmp_path):
    onnx = pytest.importorskip("onnx", reason="requirements-research.txt")
    pytest.importorskip("onnxscript", reason="torch.onnx.export needs it")
    """Normalisation happens outside the network, so the graph has to say which
    it wants.

    This was found the hard way: MobileCLIP normalises with mean 0 and standard
    deviation 1, the ONNX runner assumed ImageNet, and the exported encoder
    scored a cosine of 0.19 against the torch model it came from. It still
    returned 512 numbers - just meaningless ones - and the failure reads as
    "that encoder is bad" rather than "we normalised it wrongly". The only
    reason it never bit before is that every previously exported backbone
    happened to be ImageNet-normalised.
    """
    from recognition.embedder import MEAN, STD, OnnxEmbedder

    out = tmp_path / "mobilenet_v3_small.onnx"
    TorchEmbedder("mobilenet_v3_small").export_onnx(out)

    stamped = {p.key: p.value for p in onnx.load(str(out), load_external_data=False).metadata_props}
    assert "mean" in stamped and "std" in stamped, "the graph does not say how to feed it"

    loaded = OnnxEmbedder(out)
    assert loaded.mean == pytest.approx(MEAN, abs=1e-5)
    assert loaded.std == pytest.approx(STD, abs=1e-5)
    assert loaded.input == 224


def test_a_graph_exported_before_the_stamp_still_loads_as_imagenet(tmp_path):
    """Older exports carry no statistics; assuming ImageNet is what they were."""
    onnx = pytest.importorskip("onnx", reason="requirements-research.txt")
    pytest.importorskip("onnxscript", reason="torch.onnx.export needs it")
    from recognition.embedder import MEAN, OnnxEmbedder

    out = tmp_path / "legacy.onnx"
    TorchEmbedder("mobilenet_v3_small").export_onnx(out)
    model = onnx.load(str(out), load_external_data=False)
    del model.metadata_props[:]
    onnx.save(model, str(out))

    assert OnnxEmbedder(out).mean == pytest.approx(MEAN, abs=1e-5)


def test_the_exported_encoder_agrees_with_the_model_it_came_from(tmp_path):
    """The check that caught the bug above, kept as a test."""
    pytest.importorskip("onnxscript", reason="torch.onnx.export needs it")
    import numpy as np
    from recognition.embedder import OnnxEmbedder
    from recognition.proposer import BackgroundSubtractionProposer
    from tests.synthetic import CATALOGUE, empty_mat, scene

    torch_model = TorchEmbedder("mobilenet_v3_small")
    out = tmp_path / "agree.onnx"
    torch_model.export_onnx(out)

    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(empty_mat())
    crops = []
    for i, sku in enumerate(list(CATALOGUE)[:3]):
        frame = scene([sku], seed=900 + i)
        crops.append(max(proposer.propose(frame), key=lambda p: p.area_px).crop(frame))

    a, b = torch_model.embed(crops), OnnxEmbedder(out).embed(crops)
    cos = (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
    assert cos.min() > 0.999, f"the export disagrees with torch (worst cosine {cos.min():.4f})"
