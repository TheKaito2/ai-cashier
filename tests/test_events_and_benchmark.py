"""The deployment log, and the public-benchmark experiment on a folder of crops."""
import json

import cv2
import numpy as np
import pytest


def test_events_are_kept_by_kind_and_newest_first(db):
    db.log_event("enrolment", {"sku_id": "a", "views": 5})
    db.log_event("abstention", {"top_sku": None, "score": 0.1})
    db.log_event("enrolment", {"sku_id": "b", "views": 3})
    got = db.get_events("enrolment")
    assert [e["sku_id"] for e in got] == ["b", "a"]
    assert len(db.get_events()) == 3


def test_an_unknown_event_kind_is_refused(db):
    with pytest.raises(ValueError):
        db.log_event("gossip", {})


def test_a_pre_gate_database_gains_the_restricted_column(tmp_path):
    import sqlite3
    from server.services.database import Database
    path = tmp_path / "old.sqlite3"
    c = sqlite3.connect(path)
    c.executescript("""CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT NOT NULL,
        price REAL NOT NULL, category TEXT NOT NULL, stock INTEGER NOT NULL,
        min_stock INTEGER NOT NULL DEFAULT 0, yolo_class TEXT, barcode TEXT, size TEXT,
        description TEXT, weight_g REAL, weight_is_estimated INTEGER NOT NULL DEFAULT 1,
        size_mm_long REAL, size_mm_short REAL);
        INSERT INTO products(id,name,price,category,stock) VALUES ('x','X',1,'other',1);""")
    c.commit(); c.close()
    db = Database(path, migrate_from=None)
    assert db.get_product("x")["restricted"] == "none"


def test_e9_runs_on_a_folder_of_crops(tmp_path):
    """Lay out synthetic packets as a public benchmark would be, then run E9."""
    from tests.synthetic import CATALOGUE, empty_mat, scene
    from recognition.proposer import BackgroundSubtractionProposer
    from research.dataset import ImageFolderSource, make_split
    from research import experiments as X

    prop = BackgroundSubtractionProposer()
    prop.calibrate(empty_mat())
    for sku in CATALOGUE:
        d = tmp_path / sku
        d.mkdir()
        for i in range(8):
            f = scene([sku], seed=500 + i)
            crop = max(prop.propose(f), key=lambda p: p.area_px).crop(f)
            cv2.imwrite(str(d / f"{i:02d}.jpg"), crop)
    (tmp_path / "meta.json").write_text(json.dumps({"pepsi": {"name": "Pepsi", "price": 14}}))

    class ToyEmbedder:                      # colour histogram: enough to run the harness
        dim, name = 48, "toy"
        def embed(self, crops):
            out = []
            for c in crops:
                h = [np.histogram(c[..., ch], bins=16, range=(0, 255))[0] for ch in range(3)]
                out.append(np.concatenate(h).astype(np.float32))
            return np.array(out)

    src = ImageFolderSource(tmp_path)
    assert [s.name for s in src.skus() if s.sku_id == "pepsi"] == ["Pepsi"]
    r = X.e9_public_benchmark(src, ToyEmbedder(), make_split(src.skus(), unseen_fraction=1.0), k=3)
    assert r["n_skus"] == len(CATALOGUE)
    assert [row["k"] for row in r["fewshot"]] == [1, 3, 3]
    assert r["openset"].get("insufficient_data") or set(r["openset"]["scores"]) == {"max_cosine", "energy", "msp"}


def test_energy_and_msp_rank_a_confident_vector_above_a_flat_one():
    from recognition.calibration import energy_score, msp_score
    sharp, flat = np.array([0.9, 0.1, 0.1]), np.array([0.4, 0.4, 0.4])
    assert energy_score(sharp) > energy_score(flat)
    assert msp_score(sharp) > msp_score(flat)
