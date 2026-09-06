# Data and contracts

Everything the till persists, everything it serves, and every JSON shape the
research harness writes.

## The database

One SQLite file.  The schema is a single string, `server/services/database.py:SCHEMA`,
executed once at open; WAL is on and `PRAGMA foreign_keys` is enforced.  There is
one runtime migration in the constructor — an `ALTER TABLE products ADD COLUMN
restricted` for databases created before the legal gate existed.

Where the file lives is decided by `paths.py:database_path`: `data/checkout.sqlite3`
in a checkout, `%LOCALAPPDATA%\AI Cashier` in a frozen Windows build, or wherever
`AI_CASHIER_DATA` points.  **`server/services/database.py:Database` is the only
gateway** — no other module opens a connection.

| Table | Holds | Written by | Read by |
|---|---|---|---|
| `products` | The catalogue: price, stock, category, weight, size in millimetres, barcode, restriction | `upsert_product` on enrolment, `update_stock` on restock, `process_pending_payment` on sale | `get_products`, `get_product`, `get_analytics` |
| `sales` | One row per completed sale | `process_pending_payment` | `get_sale`, `get_sales`, `get_analytics` |
| `sale_items` | The lines of each sale, cascading on delete | `process_pending_payment` | `get_sale`, `get_analytics` |
| `pending_payments` | A payment that has been quoted but not confirmed; the whole payload as JSON | `add_pending_payment` | `get_pending_payment`, `process_pending_payment` |
| `settings` | Key/value, JSON-encoded values | `set_setting`, `set_theme` | `get_settings` |
| `events` | The research log: what the till refused, what a human overrode | `log_event` | `get_events`, the monitor page |

**Stock only ever moves inside `server/services/database.py:process_pending_payment`.**
That function decrements stock, writes the sale, writes its lines and closes the
payment in one `BEGIN IMMEDIATE` transaction.  A failed sale leaves nothing behind.
`tests/test_database.py` pins this.

`events` is not incidental.  `docs/research/07-research-roadmap.md` asks for four
logs so the master's- and PhD-scale questions have data years from now; this table
is them.  The kinds are fixed in `server/services/database.py:EVENT_KINDS` —
`enrolment`, `abstention`, `override`, `basket_check` — and an unknown kind is
refused rather than stored.

## Settings

Two different things are called settings and they live in different places.

**Shop settings** live in the `settings` table, seeded from
`server/services/database.py:DEFAULT_SETTINGS`: `store_name`, `tax_rate` (0.07),
`currency`, `detection_confidence`, `theme`, `vat_registered`, `tin`,
`store_address`, `slip_verifier_url`, `slip_verifier_token`.

Three keys are read but **not** in that dict — they exist only once something
writes them, and the code must tolerate their absence:

| Key | Read at | Absent means |
|---|---|---|
| `reject_below_cosine` | `scanner/ui/main_window.py` | Falls back to the placeholder in `recognition/fusion.py:FusionConfig`.  Written by `tools/set_threshold.py` |
| `promptpay_id` | `server/services/checkout.py` | The QR is a `NOT-CONFIGURED` string and the payment is not payable.  **Never seed a real one into the repository** |
| `dashboard_pin` | `server/main.py:require_pin` | LAN mode has no PIN to check |

`detection_confidence` is seeded and read by nothing.  It is a leftover from the
v3 detector; see `docs/kb/09-state.md`.

**Hardware settings** live in `config/settings.json`, resolved by
`paths.py:settings_path`: display, camera, `rig.marker_mm` and the marker layout,
and the scale's `dout_pin`, `sck_pin`, `counts_per_gram`, `offset_counts`.  These
belong to a rig, not to a shop, which is why they are a file and not a table.

## The REST surface

Thirteen routes in `server/main.py`.  Writes are PIN-protected when the server is
started with `--lan`; on loopback there is no PIN.

| Route | Purpose |
|---|---|
| `POST /api/checkout` | Quote a basket, get a PromptPay payload |
| `POST /api/confirm-payment/{payment_id}` | Verify the slip and commit the sale |
| `GET /api/receipt/{sale_id}` | The rendered receipt text |
| `GET /api/products` | The catalogue |
| `PATCH /api/products/{product_id}/restriction` | Mark a product alcohol/tobacco/none |
| `POST /api/restock/{product_id}` | Add stock |
| `GET` / `POST /api/events` | The research log |
| `GET /api/sales` | Recent sales, `limit` capped |
| `GET /api/analytics` | Totals, today, top products |
| `GET` / `POST /api/theme` | Light or dark, shared across tabs |
| `GET /api/system-status` | Liveness; also what the smoke test polls |

**The dashboard never rings up a sale.**  Its JavaScript touches only
`/api/analytics`, `/api/sales`, `/api/products`, `/api/theme`, `/api/system-status`,
`/api/restock` and `/api/events`.  The checkout routes exist for the tests and for
a third party; the till itself calls `server/services/checkout.py` directly, in
process, without HTTP.

## The research JSON shapes

**`research/results/E*.json`** — one file per experiment, written by
`research/run.py`.  Every file carries `experiment`, `source` (`synthetic`,
`captures`, or `folder:<name>`), the experiment's own rows, plus two stamped
blocks: `environment` (python version, machine, platform, git short commit) and
`split` (which products were seen and which unseen).  The stamp is what stops a
laptop number being quoted as a Pi number, or a synthetic number as a real one.

Two states worth recognising: `research/results/E5.json` currently carries `insufficient_data: true`
because the synthetic split yields only one enrolled and two unenrolled products,
and `research/results/E8.json` carries `closed_set_retrain_hours: null` because the code refuses to
estimate a figure the team has to supply from its own record.

**`research/data/manifest.json`** — written by `research/capture.py`.  One entry
per product: `name`, `price`, `weight_g`, `category`, `in_legacy_model`, `views`,
and `rig_note` (camera, light, mat, marker size, date — `research/PROTOCOL.md`
section 0b).

**A folder source’s meta.json** — optional, one entry per SKU directory with
`name`, `price`, `weight_g`, `category`.  Read by
`research/dataset.py:ImageFolderSource`.

**The sale dict** returned by `server/services/checkout.py:confirm_payment` — the
sale row, its items, and a `receipt` string.  Both the Qt `ReceiptDialog` and
`GET /api/receipt/{sale_id}` render that string; nothing re-derives it.

## The Swift fixture contract

`ios/AICashier/Tests/Fixtures/fixtures.json` is generated by
`tools/export_fixtures.py` and holds `embedder`, `thresholds`, `proposer`, `crops`,
`embeddings`, `gallery`, `expected_matches`, `scene_boxes`, `catalogue_weights_g`,
`promptpay` and `crc16_check`.  It is the only contract between the two
implementations of the algorithm.  Regenerate it whenever the Python side of
`docs/kb/02-pipeline.md`'s port table changes.
