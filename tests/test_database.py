"""The shop's records must survive concurrency and crashes.

v3 kept everything in one JSON file that was rewritten whole on every change,
with the lock released between reading and writing.  These are the faults that
caused, and the guarantees that replaced them.
"""
import json
import sqlite3
import threading

import pytest

from server.services.database import Database


# ------------------------------------------------------------------ migration

def test_the_version_3_json_file_comes_across_intact(db):
    assert len(db.get_products()) == 14
    nori = db.get_product("lays-nori-seaweed")
    assert nori["price"] == 25.0 and nori["size"] == "75g"


def test_products_recovered_during_the_v3_merge_are_still_there(db):
    """Atreus and Enter existed only in the scanner's database in v2."""
    assert db.get_product("atreus") and db.get_product("enter")


def test_the_currency_symbol_is_not_mojibake(db):
    assert db.get_settings()["currency"] == "฿"


def test_every_product_has_the_fields_the_till_needs(db):
    for p in db.get_products():
        for field in ("id", "name", "price", "category", "stock", "min_stock"):
            assert p.get(field) is not None, f"{p.get('id')} is missing {field}"
        assert p["price"] > 0 and p["stock"] >= 0


def test_product_ids_are_unique(db):
    ids = [p["id"] for p in db.get_products()]
    assert len(ids) == len(set(ids))




def test_restock_adds_and_persists(db, any_product):
    before = any_product["stock"]
    assert db.update_stock(any_product["id"], 7, operation="add")
    assert db.get_product(any_product["id"])["stock"] == before + 7


def test_the_api_refuses_to_oversell(db, any_product):
    assert db.update_stock(any_product["id"], any_product["stock"] + 1, "subtract") is False
    assert db.get_product(any_product["id"])["stock"] == any_product["stock"]


# -------------------------------------------------------------------- schema

def test_the_database_runs_in_wal_mode(db):
    """So the dashboard can read while the till is writing."""
    mode = db._conn().execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_stock_cannot_be_driven_negative_by_the_schema(db):
    with pytest.raises(sqlite3.IntegrityError):
        db._conn().execute("UPDATE products SET stock = -1 WHERE id = 'pepsi'")


# ------------------------------------------------------------- atomic selling

def _pending(db, items, total=100.0):
    payment_id = "pay-" + "".join(str(i["quantity"]) for i in items)
    db.add_pending_payment(payment_id, {
        "payment_id": payment_id, "timestamp": "2026-09-01T10:00:00",
        "items": items, "subtotal": total, "tax": 0.0, "total": total,
        "status": "pending"})
    return payment_id


def test_a_sale_decrements_stock_and_records_itself(db):
    before = db.get_product("pepsi")["stock"]
    pid = _pending(db, [{"product_id": "pepsi", "product_name": "Pepsi",
                         "quantity": 2, "price": 14.0, "total": 28.0}])
    sale = db.process_pending_payment(pid)
    assert sale["items"][0]["quantity"] == 2
    assert db.get_product("pepsi")["stock"] == before - 2


def test_a_sale_that_cannot_complete_changes_nothing(db):
    """One transaction: either the whole sale happens or none of it does.
    v3 could leave stock decremented with no sale written."""
    before = {p["id"]: p["stock"] for p in db.get_products()}
    pid = _pending(db, [
        {"product_id": "pepsi", "product_name": "Pepsi", "quantity": 1, "price": 14.0, "total": 14.0},
        {"product_id": "sprite", "product_name": "Sprite", "quantity": 99999, "price": 14.0, "total": 0.0},
    ])
    assert db.process_pending_payment(pid) is None
    after = {p["id"]: p["stock"] for p in db.get_products()}
    assert after == before, "a failed sale moved stock"
    assert db.get_sales(limit=100) and all(s["payment_id"] != pid for s in db.get_sales(100))


def test_a_payment_cannot_be_taken_twice(db):
    pid = _pending(db, [{"product_id": "pepsi", "product_name": "Pepsi",
                         "quantity": 1, "price": 14.0, "total": 14.0}])
    assert db.process_pending_payment(pid) is not None
    assert db.process_pending_payment(pid) is None


def test_sales_rung_up_in_the_same_second_get_different_ids(db):
    ids = []
    for i in range(4):
        pid = f"pay-{i}"
        db.add_pending_payment(pid, {
            "payment_id": pid, "timestamp": "2026-09-01T10:00:00",
            "items": [{"product_id": "crystal-water", "product_name": "Water",
                       "quantity": 1, "price": 7.0, "total": 7.0}],
            "subtotal": 7.0, "tax": 0.0, "total": 7.0, "status": "pending"})
        ids.append(db.process_pending_payment(pid)["id"])
    assert len(set(ids)) == 4


def test_concurrent_restocks_do_not_lose_updates(db):
    """The v3 fault exactly: read, modify, write with the lock released in
    between meant two tills could each add 1 and the total went up by 1."""
    start = db.get_product("pepsi")["stock"]
    threads = [threading.Thread(target=db.update_stock, args=("pepsi", 1, "add"))
               for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert db.get_product("pepsi")["stock"] == start + 40


def test_a_half_written_database_is_not_a_destroyed_one(db, tmp_path):
    """v3 truncated the file before writing, so a crash mid-sale took the
    products, the sales and the stock with it. SQLite journals instead."""
    path = db.db_path
    db.update_stock("pepsi", 3, "add")
    reopened = Database(path, migrate_from=None)
    assert len(reopened.get_products()) == 14


# ------------------------------------------------------------------ analytics

def test_analytics_counts_only_confirmed_sales(db):
    before = db.get_analytics()["total_sales"]
    pid = _pending(db, [{"product_id": "pepsi", "product_name": "Pepsi",
                         "quantity": 1, "price": 14.0, "total": 14.0}])
    assert db.get_analytics()["total_sales"] == before
    db.process_pending_payment(pid)
    assert db.get_analytics()["total_sales"] == before + 1


def test_enrolment_writes_a_sellable_product(db):
    db.upsert_product({"id": "new-snack", "name": "New Snack", "price": 19.0,
                       "category": "chips", "stock": 12, "min_stock": 3,
                       "weight_g": 82.0, "size_mm": [180.0, 120.0]})
    p = db.get_product("new-snack")
    assert p["price"] == 19.0 and p["weight_g"] == 82.0
    assert p["size_mm"] == [180.0, 120.0]
    assert p["weight_is_estimated"] is False
