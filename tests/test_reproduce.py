"""A reviewer must be able to regenerate the paper, and must never be able to
destroy a measurement by doing so.

`tools/reproduce.py` runs the synthetic experiments and rebuilds every table.
The one thing it must refuse is overwriting a result that came from
photographs - a synthetic number quietly replacing a measured one is the most
damaging thing this repository could do to itself.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import reproduce  # noqa: E402


def _write(dirpath, name, source):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / name).write_text(json.dumps({"experiment": name[:2], "source": source}))


def test_a_capture_run_stops_the_script_and_is_named(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(reproduce, "RESULTS", tmp_path)
    _write(tmp_path, "E2.json", "captures")
    _write(tmp_path, "E4.json", "synthetic")
    monkeypatch.setattr(sys, "argv", ["reproduce.py"])

    assert reproduce.main() == 1
    out = capsys.readouterr().out
    assert "refusing to run" in out
    assert "E2.json" in out


def test_public_benchmark_results_are_left_alone_but_do_not_block(tmp_path, monkeypatch):
    """E9 comes from a dataset a fresh checkout does not have. It is measured, so
    it is never regenerated - but it is not a reason to refuse to run."""
    monkeypatch.setattr(reproduce, "RESULTS", tmp_path)
    _write(tmp_path, "E9-packages.json", "folder:grocerystore-packages")
    rows = reproduce.existing()
    assert reproduce.measured("folder:grocerystore-packages")
    assert [p.name for p, s in rows] == ["E9-packages.json"]


def test_synthetic_results_are_not_treated_as_measured():
    assert not reproduce.measured("synthetic")
    assert reproduce.measured("captures")


def test_listing_changes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(reproduce, "RESULTS", tmp_path)
    _write(tmp_path, "E2.json", "captures")
    monkeypatch.setattr(sys, "argv", ["reproduce.py", "--list"])
    before = sorted(p.read_text() for p in tmp_path.iterdir())

    assert reproduce.main() == 0
    assert "captures" in capsys.readouterr().out
    assert sorted(p.read_text() for p in tmp_path.iterdir()) == before


def test_an_unreadable_result_is_reported_rather_than_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(reproduce, "RESULTS", tmp_path)
    (tmp_path / "E2.json").write_text("{ this is not json")
    assert reproduce.existing() == [(tmp_path / "E2.json", "unreadable")]
