"""Development keeps everything in the checkout; an installed build keeps its
data in the user's folder and never writes next to the program (Phase 6, B1)."""
import importlib
import json
import sys

import paths


def test_development_layout_is_the_checkout(monkeypatch):
    monkeypatch.delenv("AI_CASHIER_DATA", raising=False)
    monkeypatch.setattr(paths, "FROZEN", False)
    assert paths.data_dir() == paths.RESOURCES / "data"
    assert paths.settings_path() == paths.RESOURCES / "config" / "settings.json"
    assert paths.first_run_seed() == []                    # nothing to seed
    assert paths.EMBEDDER.name == "mobilenet_v3_small.onnx"


def test_an_override_moves_the_data_and_seeds_it(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_CASHIER_DATA", str(tmp_path / "shop"))
    assert paths.data_dir() == tmp_path / "shop"
    assert paths.database_path() == tmp_path / "shop" / "checkout.sqlite3"
    assert paths.gallery_path().parent == tmp_path / "shop"
    copied = paths.first_run_seed()
    assert {p.name for p in copied} == {"settings.json", "products.json"}
    assert json.loads(paths.settings_path().read_text())["camera"]["default_source"] == 0
    assert paths.first_run_seed() == []                    # second run copies nothing


def test_a_frozen_build_uses_the_user_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("AI_CASHIER_DATA", raising=False)
    monkeypatch.setattr(paths, "FROZEN", True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(sys, "platform", "win32")
    assert paths.data_dir() == tmp_path / "AI Cashier"
    assert paths.settings_path() == tmp_path / "AI Cashier" / "settings.json"


def test_the_database_module_follows_the_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_CASHIER_DATA", str(tmp_path / "shop"))
    paths.first_run_seed()
    import server.services.database as database
    importlib.reload(database)
    try:
        assert database.DEFAULT_DB == tmp_path / "shop" / "checkout.sqlite3"
        db = database.Database()                           # default path, seeded products
        assert db.get_products() and (tmp_path / "shop" / "checkout.sqlite3").exists()
    finally:
        monkeypatch.delenv("AI_CASHIER_DATA")
        importlib.reload(database)


def test_version_is_a_dotted_number():
    major, minor, patch = paths.version().split(".")
    assert all(part.isdigit() for part in (major, minor, patch))
