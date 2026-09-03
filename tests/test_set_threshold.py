"""The measured E5 threshold lands in the setting the till reads."""
import pytest

from tools.set_threshold import apply, report_from


def _e5(**over):
    base = {"experiment": "E5", "source": "captures", "threshold": 0.8123456,
            "tpr": 0.95, "fpr": 0.10, "auroc": 0.97, "fpr_at_95_tpr": 0.10}
    return {**base, **over}


def test_the_threshold_is_written_where_the_till_reads_it(db):
    r = apply(_e5(), db)
    assert db.get_settings()["reject_below_cosine"] == pytest.approx(0.8123)
    assert "tau=0.812" in str(r)


def test_an_unrun_e5_is_refused(db):
    before = db.get_settings().get("reject_below_cosine")
    with pytest.raises(ValueError, match="Photograph more"):
        apply(_e5(insufficient_data=True, error="need 4 and 3. Photograph more products."), db)
    with pytest.raises(ValueError, match="not an E5"):
        report_from({"experiment": "E2"})
    assert db.get_settings().get("reject_below_cosine") == before
