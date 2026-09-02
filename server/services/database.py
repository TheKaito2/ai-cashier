"""The shop's records, in SQLite.

Version 3 kept products, sales, pending payments and settings in one JSON file
that was rewritten in full on every change.  Two faults came with that:

  * `update_stock` read the file, changed it and wrote it back with the lock
    released in between, so two sales rung up at once lost one of the updates;
  * `json.dump` truncates before it writes, so a power cut mid-sale destroyed
    the products, the sales and the stock together.

SQLite fixes both properly.  A sale is one transaction - the stock comes down,
the sale is written and the payment is closed, or none of it happens.  WAL mode
lets the dashboard read while the till writes.

The method names are unchanged from `JsonDatabase`, so nothing that calls this
had to be rewritten.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import paths

DEFAULT_DB = paths.database_path()
LEGACY_JSON = paths.legacy_products_json()

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    price         REAL NOT NULL CHECK (price >= 0),
    category      TEXT NOT NULL,
    stock         INTEGER NOT NULL CHECK (stock >= 0),
    min_stock     INTEGER NOT NULL DEFAULT 0,
    yolo_class    TEXT,             -- v3 legacy column; nothing reads it
    barcode       TEXT,
    size          TEXT,
    description   TEXT,
    -- filled in when the product is enrolled on the rig
    weight_g            REAL,
    weight_is_estimated INTEGER NOT NULL DEFAULT 1,
    size_mm_long        REAL,
    size_mm_short       REAL,
    -- 'none' | 'alcohol' | 'tobacco'.  Thai law gates these at the till
    -- (docs/research/01-legal-thailand.md, section 2)
    restricted          TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE IF NOT EXISTS sales (
    id         TEXT PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    subtotal   REAL NOT NULL,
    tax        REAL NOT NULL,
    total      REAL NOT NULL,
    payment_id TEXT
);
CREATE TABLE IF NOT EXISTS sale_items (
    sale_id      TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id   TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    price        REAL NOT NULL,
    total        REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_payments (
    payment_id TEXT PRIMARY KEY,
    timestamp  TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    payload    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- deployment log: what the till learnt, refused, was overridden on, and how
-- each basket check went.  ponytail: one table with a kind column rather than
-- four tables; split it if any kind needs its own indexes.
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    kind      TEXT NOT NULL,     -- enrolment | abstention | override | basket_check
    payload   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind, timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_time ON sales(timestamp);
CREATE INDEX IF NOT EXISTS idx_items_sale ON sale_items(sale_id);
"""

DEFAULT_SETTINGS = {
    "store_name": "Smart Checkout Store",
    "tax_rate": 0.07,
    "currency": "฿",
    "detection_confidence": 0.6,
    "theme": "dark",
    # receipts (docs/research/01 section 4): a VAT-registered shop prints an
    # abbreviated tax invoice; everyone else prints a plain receipt
    "vat_registered": False,
    "tin": "",
    "store_address": "",
    # slip verification (docs/research/04 section 4); empty = not verified
    "slip_verifier_url": "",
    "slip_verifier_token": "",
}

RESTRICTIONS = ("none", "alcohol", "tobacco")


class Database:
    def __init__(self, db_path: str | Path | None = None,
                 migrate_from: str | Path | None = LEGACY_JSON):
        self.db_path = str(db_path or DEFAULT_DB)
        self._local = threading.local()
        self._write_lock = threading.Lock()
        fresh = not Path(self.db_path).exists() or Path(self.db_path).stat().st_size == 0
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
            cols = {r["name"] for r in c.execute("PRAGMA table_info(products)")}
            if "restricted" not in cols:      # a database from before the gate existed
                c.execute("ALTER TABLE products ADD COLUMN restricted TEXT NOT NULL DEFAULT 'none'")
        self._seed_settings()
        if fresh and migrate_from and Path(migrate_from).exists():
            self.migrate_from_json(migrate_from)

    # ------------------------------------------------------------ connections

    def _conn(self) -> sqlite3.Connection:
        """One connection per thread - the server answers on several."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=10.0,
                                   detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")     # readers never block the till
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _seed_settings(self) -> None:
        with self._conn() as c:
            for k, v in DEFAULT_SETTINGS.items():
                c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                          (k, json.dumps(v)))

    # -------------------------------------------------------------- migration

    def migrate_from_json(self, path: str | Path) -> dict[str, int]:
        """Bring version 3's single JSON file across, without losing anything."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        counts = {"products": 0, "sales": 0, "settings": 0}
        with self._write_lock, self._conn() as c:
            for p in data.get("products", []):
                c.execute("""INSERT OR REPLACE INTO products
                    (id, name, price, category, stock, min_stock, yolo_class,
                     barcode, size, description, weight_g, weight_is_estimated,
                     size_mm_long, size_mm_short)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (p["id"], p["name"], p["price"], p["category"], p["stock"],
                     p.get("min_stock", 0), p.get("yolo_class"), p.get("barcode"),
                     p.get("size"), p.get("description"), p.get("weight_g"),
                     0 if p.get("weight_g") else 1,
                     (p.get("size_mm") or [None, None])[0],
                     (p.get("size_mm") or [None, None])[1]))
                counts["products"] += 1

            for s in data.get("sales", []):
                c.execute("""INSERT OR REPLACE INTO sales
                    (id, timestamp, subtotal, tax, total, payment_id) VALUES (?,?,?,?,?,?)""",
                    (s["id"], s["timestamp"], s.get("subtotal", 0.0),
                     s.get("tax", 0.0), s["total"], s.get("payment_id")))
                c.execute("DELETE FROM sale_items WHERE sale_id = ?", (s["id"],))
                for it in s.get("items", []):
                    c.execute("""INSERT INTO sale_items
                        (sale_id, product_id, product_name, quantity, price, total)
                        VALUES (?,?,?,?,?,?)""",
                        (s["id"], it["product_id"], it.get("product_name", ""),
                         it["quantity"], it["price"], it.get("total", 0.0)))
                counts["sales"] += 1

            for k, v in (data.get("settings") or {}).items():
                c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)",
                          (k, json.dumps(v)))
                counts["settings"] += 1
        return counts

    # --------------------------------------------------------------- products

    @staticmethod
    def _product(row: sqlite3.Row) -> dict[str, Any]:
        p = dict(row)
        long_mm, short_mm = p.pop("size_mm_long"), p.pop("size_mm_short")
        p["size_mm"] = [long_mm, short_mm] if long_mm and short_mm else None
        p["weight_is_estimated"] = bool(p["weight_is_estimated"])
        p["restricted"] = p.get("restricted") or "none"
        return p

    def get_products(self) -> list[dict]:
        return [self._product(r) for r in
                self._conn().execute("SELECT * FROM products ORDER BY rowid")]

    def get_product(self, product_id: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM products WHERE id = ?",
                                   (product_id,)).fetchone()
        return self._product(row) if row else None

    def upsert_product(self, product: dict) -> dict:
        """Add or update a product. Used by enrolment."""
        size_mm = product.get("size_mm") or [None, None]
        with self._write_lock, self._conn() as c:
            c.execute("""INSERT INTO products
                (id, name, price, category, stock, min_stock, yolo_class, barcode,
                 size, description, weight_g, weight_is_estimated, size_mm_long, size_mm_short,
                 restricted)
                VALUES (:id,:name,:price,:category,:stock,:min_stock,:yolo_class,:barcode,
                        :size,:description,:weight_g,:weight_is_estimated,:long,:short,
                        :restricted)
                ON CONFLICT(id) DO UPDATE SET
                    restricted=excluded.restricted,
                    name=excluded.name, price=excluded.price, category=excluded.category,
                    stock=excluded.stock, min_stock=excluded.min_stock,
                    size=excluded.size, description=excluded.description,
                    weight_g=excluded.weight_g,
                    weight_is_estimated=excluded.weight_is_estimated,
                    size_mm_long=excluded.size_mm_long, size_mm_short=excluded.size_mm_short
            """, {"id": product["id"], "name": product["name"],
                  "price": float(product["price"]), "category": product.get("category", "other"),
                  "stock": int(product.get("stock", 0)),
                  "min_stock": int(product.get("min_stock", 0)),
                  "yolo_class": product.get("yolo_class"), "barcode": product.get("barcode"),
                  "size": product.get("size"), "description": product.get("description"),
                  "weight_g": product.get("weight_g"),
                  "weight_is_estimated": 0 if product.get("weight_g") else 1,
                  "long": size_mm[0], "short": size_mm[1],
                  "restricted": self._restriction(product.get("restricted"))})
        return self.get_product(product["id"])

    @staticmethod
    def _restriction(value) -> str:
        value = (value or "none").lower()
        if value not in RESTRICTIONS:
            raise ValueError(f"restricted must be one of {RESTRICTIONS}, not {value!r}")
        return value

    def set_restriction(self, product_id: str, restricted: str) -> bool:
        with self._write_lock, self._conn() as c:
            cur = c.execute("UPDATE products SET restricted = ? WHERE id = ?",
                            (self._restriction(restricted), product_id))
            return cur.rowcount > 0

    def update_stock(self, product_id: str, quantity: int, operation: str = "add") -> bool:
        """Change stock in a single statement, so two tills cannot lose an update."""
        delta = quantity if operation == "add" else -quantity
        with self._write_lock, self._conn() as c:
            cur = c.execute(
                "UPDATE products SET stock = stock + ? WHERE id = ? AND stock + ? >= 0",
                (delta, product_id, delta))
            return cur.rowcount > 0

    # --------------------------------------------------------------- payments

    def add_pending_payment(self, payment_id: str, payment_data: dict) -> None:
        with self._write_lock, self._conn() as c:
            c.execute("""INSERT OR REPLACE INTO pending_payments
                (payment_id, timestamp, status, payload) VALUES (?,?,?,?)""",
                (payment_id, payment_data["timestamp"], payment_data.get("status", "pending"),
                 json.dumps(payment_data)))

    def get_pending_payment(self, payment_id: str) -> dict | None:
        row = self._conn().execute(
            "SELECT payload, status FROM pending_payments WHERE payment_id = ?",
            (payment_id,)).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["status"] = row["status"]
        return payload

    def process_pending_payment(self, payment_id: str) -> dict | None:
        """Turn a pending payment into a sale.

        Stock down, sale written, payment closed - one transaction.  Either the
        whole sale happened or none of it did; version 3 could leave stock
        decremented with no sale recorded if it died in the middle.
        """
        with self._write_lock:
            c = self._conn()
            try:
                c.execute("BEGIN IMMEDIATE")
                row = c.execute("""SELECT payload FROM pending_payments
                                   WHERE payment_id = ? AND status = 'pending'""",
                                (payment_id,)).fetchone()
                if not row:
                    c.execute("ROLLBACK")
                    return None
                payment = json.loads(row["payload"])

                for item in payment["items"]:
                    cur = c.execute("""UPDATE products SET stock = stock - ?
                                       WHERE id = ? AND stock >= ?""",
                                    (item["quantity"], item["product_id"], item["quantity"]))
                    if cur.rowcount == 0:
                        # someone else sold the last one between checkout and payment
                        c.execute("ROLLBACK")
                        return None

                sale_id = (f"SALE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                           f"-{payment_id[:8]}")
                c.execute("""INSERT INTO sales
                    (id, timestamp, subtotal, tax, total, payment_id) VALUES (?,?,?,?,?,?)""",
                    (sale_id, datetime.now().isoformat(), payment["subtotal"],
                     payment["tax"], payment["total"], payment_id))
                for item in payment["items"]:
                    c.execute("""INSERT INTO sale_items
                        (sale_id, product_id, product_name, quantity, price, total)
                        VALUES (?,?,?,?,?,?)""",
                        (sale_id, item["product_id"], item["product_name"],
                         item["quantity"], item["price"], item["total"]))
                c.execute("UPDATE pending_payments SET status='completed' WHERE payment_id=?",
                          (payment_id,))
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise

        return self.get_sale(sale_id)

    # ------------------------------------------------------------------ sales

    def _sale(self, row: sqlite3.Row) -> dict:
        items = self._conn().execute(
            "SELECT product_id, product_name, quantity, price, total "
            "FROM sale_items WHERE sale_id = ?", (row["id"],)).fetchall()
        sale = dict(row)
        sale["items"] = [dict(i) for i in items]
        return sale

    def get_sale(self, sale_id: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        return self._sale(row) if row else None

    def get_sales(self, limit: int = 50) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM sales ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [self._sale(r) for r in rows]

    # --------------------------------------------------------------- settings

    def get_settings(self) -> dict:
        return {r["key"]: json.loads(r["value"])
                for r in self._conn().execute("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value) -> None:
        with self._write_lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)",
                      (key, json.dumps(value)))

    def get_theme(self) -> str:
        return self.get_settings().get("theme", "light")

    def set_theme(self, theme: str) -> None:
        self.set_setting("theme", theme)

    # ----------------------------------------------------------- deployment log

    EVENT_KINDS = ("enrolment", "abstention", "override", "basket_check")

    def log_event(self, kind: str, payload: dict) -> int:
        """Record something the paper's later tiers will want to count.

        Enrolments, abstentions, staff overrides and basket checks are the
        dataset for lifelong-enrolment and self-calibrating-fusion work
        (docs/research/07).  They cost nothing to keep now.
        """
        if kind not in self.EVENT_KINDS:
            raise ValueError(f"unknown event kind {kind!r}")
        with self._write_lock, self._conn() as c:
            cur = c.execute("INSERT INTO events(timestamp, kind, payload) VALUES (?,?,?)",
                            (datetime.now().isoformat(), kind, json.dumps(payload)))
            return int(cur.lastrowid)

    def get_events(self, kind: str | None = None, limit: int = 200) -> list[dict]:
        q = "SELECT id, timestamp, kind, payload FROM events"
        args: tuple = ()
        if kind:
            q += " WHERE kind = ?"
            args = (kind,)
        q += " ORDER BY id DESC LIMIT ?"
        rows = self._conn().execute(q, args + (limit,)).fetchall()
        # payload keys never shadow the row's own id/timestamp/kind
        return [{**json.loads(r["payload"]), "id": r["id"], "timestamp": r["timestamp"],
                 "kind": r["kind"]} for r in rows]

    # -------------------------------------------------------------- analytics

    def get_analytics(self) -> dict:
        c = self._conn()
        today = datetime.now().date().isoformat()
        totals = c.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) rev FROM sales").fetchone()
        todays = c.execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) rev FROM sales "
                           "WHERE date(timestamp) = ?", (today,)).fetchone()
        top = c.execute("""SELECT i.product_id,
                                  COALESCE(p.name, i.product_name) product_name,
                                  SUM(i.quantity) quantity_sold,
                                  SUM(i.total) revenue
                           FROM sale_items i LEFT JOIN products p ON p.id = i.product_id
                           GROUP BY i.product_id ORDER BY revenue DESC LIMIT 10""").fetchall()
        low = c.execute("SELECT COUNT(*) n FROM products WHERE stock <= min_stock").fetchone()
        return {
            "total_sales": totals["n"],
            "today_sales": todays["n"],
            "today_revenue": todays["rev"],
            "total_revenue": totals["rev"],
            "top_products": [dict(r) for r in top],
            "low_stock_count": low["n"],
        }
