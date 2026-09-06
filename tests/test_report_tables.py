"""The paper's tables are generated, so the generator is what must be right.

Every number in `paper/` comes through `research/report.py`.  A silent mistake
here is a wrong figure in a submitted paper, which is the most expensive kind of
bug this project can ship - so the escaping, the synthetic warning and the
multi-dataset glob are pinned rather than trusted.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research import report  # noqa: E402


def test_latex_specials_in_a_cell_are_escaped():
    # a backbone called mobilenet_v3_small once broke the build: LaTeX read the
    # underscore as a subscript and tectonic stopped
    assert report._tex("mobilenet_v3_small") == "mobilenet\\_v3\\_small"
    assert report._tex("95% & rising") == "95\\% \\& rising"
    assert report._tex("a\\b").startswith("a\\textbackslash{}")


def test_a_synthetic_result_carries_the_warning_and_a_real_one_does_not():
    assert "NOT evidence about real products" in report.header({"source": "synthetic"})
    assert "NOT evidence" not in report.header({"source": "folder:grocerystore-packages"})
    assert "do not edit" in report.header({"source": "captures"})


def test_a_missing_value_is_a_dash_rather_than_a_guess():
    text = report.latex_table(
        {"source": "captures"},
        [("name", "Name", ""), ("value", "Value", ".1f")],
        [{"name": "with_underscore", "value": 12.345}, {"name": "absent", "value": None}],
        caption="c", label="l")
    assert "with\\_underscore & 12.3" in text
    assert "absent & --" in text
    assert "\\label{tab:l}" in text


def _e9(tag: str, accuracy: float, backbone: str = "mobilenet_v3_small") -> dict:
    return {"experiment": "E9", "source": f"folder:{tag}", "backbone": backbone, "k": 5,
            "n_skus": 3,
            "fewshot": [{"k": 1, "accuracy": accuracy, "accuracy_prototype": accuracy,
                         "n_probes": 10, "n_skus": 3}],
            "openset": {"scores": {"max_cosine": {"auroc": 0.7, "fpr_at_95_tpr": 0.4,
                                                  "threshold": 0.25, "tpr": 0.95, "fpr": 0.4}}}}


def test_every_public_run_becomes_a_row_whatever_its_tag(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E9-packages.json").write_text(json.dumps(_e9("packages", 0.5)))
    (report.RESULTS / "E9-all.json").write_text(json.dumps(_e9("all", 0.25)))

    report.table_e9()

    public = (report.TABLES / "e9_public.tex").read_text()
    assert "packages" in public and "all" in public
    assert "50.0" in public and "25.0" in public
    assert (report.TABLES / "e9_public_openset.tex").exists()


def test_the_same_dataset_under_two_encoders_stays_two_readable_rows(tmp_path, monkeypatch):
    """Without an encoder column the table shows one dataset with two different
    accuracies and explains neither."""
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E9-packages.json").write_text(
        json.dumps(_e9("grocerystore-packages", 0.458)))
    (report.RESULTS / "E9-packages-mobileclip_b.json").write_text(
        json.dumps(_e9("grocerystore-packages", 0.896, backbone="mobileclip_b")))

    report.table_e9()

    public = (report.TABLES / "e9_public.tex").read_text()
    assert "Encoder" in public
    assert "mobileclip\\_b" in public, "the encoder name must survive LaTeX escaping"
    assert "45.8" in public and "89.6" in public
    assert "Encoder" in (report.TABLES / "e9_public_openset.tex").read_text()


def test_no_results_writes_no_table(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "RESULTS", tmp_path / "empty")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    report.table_e9()
    assert not report.TABLES.exists(), "an absent experiment must not leave a stub behind"


@pytest.mark.parametrize("name", ["e2_fewshot", "e9_public"])
def test_generated_tables_say_they_are_generated(name, tmp_path, monkeypatch):
    monkeypatch.setattr(report, "TABLES", tmp_path)
    report.write(name, report.header({"source": "captures"}) + "body")
    assert (tmp_path / f"{name}.tex").read_text().startswith("% GENERATED")


# ------------------------------------------------------ the escalation table

def _e6_with_escalation() -> dict:
    return {"experiment": "E6", "source": "captures", "backbone": "b",
            "identification": [], "item_swap": [],
            "escalation": [
                {"supervise_above_baht": 0.0, "k_sigma": 3.0, "swaps_caught_pct": 82.0,
                 "swaps_escalated_pct": 82.0, "false_calls_per_1000": 41.0,
                 "n_swaps": 100, "n_honest": 50},
                {"supervise_above_baht": 250.0, "k_sigma": 3.0, "swaps_caught_pct": 82.0,
                 "swaps_escalated_pct": 12.0, "false_calls_per_1000": 4.0,
                 "n_swaps": 100, "n_honest": 50}]}


def test_the_escalation_table_shows_what_the_shop_pays_for_the_security(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E6.json").write_text(json.dumps(_e6_with_escalation()))

    report.table_e6_escalation()

    text = (report.TABLES / "e6_escalation.tex").read_text()
    assert "Honest baskets escalated" in text, "the nuisance column is the point of the table"
    assert "250" in text and "12.0" in text
    assert "\\label{tab:escalation}" in text


def test_an_e6_from_before_the_escalation_sweep_writes_no_table(tmp_path, monkeypatch):
    """Old result files have no escalation block; that is not an error."""
    monkeypatch.setattr(report, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(report, "TABLES", tmp_path / "tables")
    report.RESULTS.mkdir()
    (report.RESULTS / "E6.json").write_text(json.dumps(
        {"experiment": "E6", "source": "synthetic", "identification": [], "item_swap": []}))
    report.table_e6_escalation()
    assert not report.TABLES.exists()
