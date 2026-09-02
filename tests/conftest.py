"""Every test runs against a throwaway copy of the shop's database.

The till stores products, stock and sales in one SQLite file, so a test that
wrote to the real one would change the shop's stock.  Each test gets its own.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def db(tmp_path):
    from server.services.database import Database
    return Database(tmp_path / "checkout.sqlite3", migrate_from=ROOT / "data" / "products.json")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient whose server writes to a throwaway database."""
    from fastapi.testclient import TestClient
    from server.services.database import Database
    import server.main as main

    fresh = Database(tmp_path / "checkout.sqlite3",
                     migrate_from=ROOT / "data" / "products.json")
    monkeypatch.setattr(main, "db", fresh)

    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def any_product(db):
    return db.get_products()[0]
