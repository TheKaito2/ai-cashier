"""The capture session happens once, with products on a table and people waiting.

`research/capture.py` is the script that runs it, and `--verify` is the thing
that says whether the session produced a dataset the experiments can use.  If it
lies, the session is discovered to be wrong long after the products are gone.
`research/bench.py` is pinned for the same reason: a benchmark that misreports is
worse than no benchmark.
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research import bench, capture  # noqa: E402


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """capture.py pointed at a throwaway dataset instead of the real one."""
    monkeypatch.setattr(capture, "CAPTURES", tmp_path / "captures")
    monkeypatch.setattr(capture, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(capture, "MAT", tmp_path / "mat_background.png")
    return tmp_path


def _photograph(path: Path, n: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        cv2.imwrite(str(path / f"{i:03d}.jpg"), np.full((16, 16, 3), 40 + i, np.uint8))


def _enrol(rig, sku: str, views: int, **over) -> dict:
    _photograph(capture.CAPTURES / sku, views)
    manifest = capture.load_manifest()
    manifest[sku] = {"name": sku, "price": 20.0, "weight_g": 48.0,
                     "category": "chips", "in_legacy_model": False, "views": views, **over}
    capture.save_manifest(manifest)
    return manifest


def test_an_empty_dataset_is_reported_as_not_ready(rig, capsys):
    assert capture.verify() == 1
    assert "nothing captured" in capsys.readouterr().out


def test_too_few_views_is_named_as_the_problem(rig, capsys):
    _enrol(rig, "pepsi", capture.MIN_VIEWS - 1)
    capture.MAT.write_bytes(b"")
    assert capture.verify() == 1
    assert f"need {capture.MIN_VIEWS}" in capsys.readouterr().out


def test_a_product_with_no_price_or_weight_is_refused(rig, capsys):
    _enrol(rig, "pepsi", capture.MIN_VIEWS, price=0.0, weight_g=None)
    assert capture.verify() == 1
    out = capsys.readouterr().out
    assert "no price" in out and "no weight" in out


def test_a_forgotten_mat_photograph_is_caught(rig, capsys):
    for i in range(10):
        _enrol(rig, f"sku-{i}", capture.MIN_VIEWS)
    assert capture.verify() == 1
    assert "empty mat" in capsys.readouterr().out


def test_too_few_products_reads_as_noise_and_is_said_so(rig, capsys):
    capture.MAT.write_bytes(b"")
    for i in range(3):
        _enrol(rig, f"sku-{i}", capture.MIN_VIEWS)
    assert capture.verify() == 1
    assert "open-set" in capsys.readouterr().out


def test_a_complete_dataset_is_ready_and_says_what_to_run_next(rig, capsys):
    capture.MAT.write_bytes(b"")
    for i in range(10):
        _enrol(rig, f"sku-{i}", capture.MIN_VIEWS)
    assert capture.verify() == 0
    out = capsys.readouterr().out
    assert "ready: 10 products" in out
    assert "run.py --source captures" in out


def test_photographs_taken_elsewhere_come_in_with_a_manifest_entry(rig, tmp_path, capsys):
    outside = tmp_path / "from_the_phone"
    _photograph(outside / "lays-nori", 9)
    _photograph(outside / "empty-folder", 0)

    assert capture.import_folder(outside) == 0

    assert len(list((capture.CAPTURES / "lays-nori").glob("*.jpg"))) == 9
    manifest = json.loads(capture.MANIFEST.read_text())
    assert manifest["lays-nori"]["views"] == 9
    assert "empty-folder" not in manifest, "a folder with no images is not a product"
    assert "price and weight" in capsys.readouterr().out


def test_importing_twice_does_not_double_count(rig, tmp_path):
    outside = tmp_path / "again"
    _photograph(outside / "pepsi", 4)
    capture.import_folder(outside)
    capture.import_folder(outside)
    assert len(list((capture.CAPTURES / "pepsi").glob("*.jpg"))) == 4


# --------------------------------------------------------------------- bench

def test_a_timing_record_reports_the_spread_not_just_the_mean():
    delays = iter([0.004, 0.001, 0.002, 0.003, 0.010])

    def fake():
        import time
        time.sleep(next(delays, 0.001))

    record = bench.timed(fake, n=4)          # the first call is the warm-up
    assert record["n"] == 4
    assert record["mean_ms"] > 0
    assert record["p95_ms"] >= record["median_ms"], "p95 cannot be under the median"


def test_a_machine_without_a_thermal_sensor_says_nothing_rather_than_zero():
    # a laptop has no /sys/class/thermal; reporting 0 degrees would look like a
    # cold Pi and flatter the benchmark
    assert bench.cpu_temperature_c() is None or bench.cpu_temperature_c() > 0


# ------------------------------------------------------------- operator CLIs

@pytest.mark.parametrize("script", ["tools/calibrate_scale.py", "tools/scale_drift.py"])
def test_the_scale_tools_run_without_a_load_cell_attached(script, tmp_path):
    args = [sys.executable, str(ROOT / script), "--dry-run"]
    if script.endswith("calibrate_scale.py"):
        args += ["--known-mass", "100"]
    else:
        # --out defaults into research/results/; a test must not write there
        args += ["--minutes", "0", "--out", str(tmp_path / "drift.csv")]
    # calibration is a two-point procedure: it asks the operator to clear the pan
    # and then to place the known mass, so it wants a person at a keyboard
    done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          input="\n\n\n\n", timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
