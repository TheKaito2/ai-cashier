# Repo map — where everything lives

313 tracked files.  Roughly 6,900 lines of Python across the five source packages,
2,500 lines of Swift in the iPhone app, and 104 files of documentation.  The
counts matter less than the shape: **one algorithm, five surfaces, one research
harness.**

```
recognition/   the algorithm            no Qt, no database, no disk writes
scanner/       the till                 PySide6, the only thing a cashier touches
server/        records and the money     FastAPI + SQLite; the owner's dashboard
research/      the experiments          synthetic, captured, or public images
ios/           the same algorithm again  Swift port, kept honest by shared fixtures
site/          the landing page          a Cloudflare Worker that serves files
paper/         the write-up             LaTeX; every number comes from a table
docs/          everything known          the dossier, the design, this folder
tools/         operator scripts         export, calibrate, seed, set the threshold
build/         the Windows installer     PyInstaller spec + Inno Setup
```

## Root

| File | What it is |
|---|---|
| `app.py` | The only entry point.  Starts uvicorn on a daemon thread and the Qt till in the same process |
| `paths.py` | The single place that resolves filesystem locations — resource vs user data, checkout vs frozen build |
| `VERSION` | One line, read by the app, the dashboard, the tests and the Inno Setup script |
| `NOTICE` | Third-party licence audit, and the quarantine of the AGPL YOLO weights |
| `LICENSE` | Apache-2.0, unmodified |
| `CLAUDE.md` | The router: invariants, orientation, condensed runbooks |
| `.graphifyignore` | What the graph builder must not walk, with a reason per line |
| `requirements.txt` / `requirements-research.txt` | Runtime deps; research-only deps (torch, open_clip) kept separate so the till stays light |

## `recognition/` — the algorithm

Pure functions and small classes.  It never imports Qt, never touches the
database, and never writes a file — the last is enforced by `tests/test_privacy.py`.

| File | Owns |
|---|---|
| `recognition/proposer.py` | Where things are.  `BackgroundSubtractionProposer` is what ships; `WholeFrameProposer` serves pre-cropped benchmarks; `YoloProposer` is research-only; `mask_above_mat` blanks anything above the mat |
| `recognition/embedder.py` | Crop to vector.  `OnnxEmbedder` runs on the till, `TorchEmbedder` is for experiments and export |
| `recognition/gallery.py` | `SkuGallery` — k reference vectors per product, the frozen centre, and `project` (the F5 fix) |
| `recognition/fusion.py` | `fuse` combines appearance, grams and millimetres; `FusionConfig` holds τ; `verify_basket` is the whole-basket weight check |
| `recognition/tracker.py` | `CentroidTracker` — so one packet is charged once |
| `recognition/pipeline.py` | `RecognitionPipeline` orchestrates all of the above; `enrol` teaches a product |
| `recognition/scale.py` | `HX711Scale` (bit-banged over lgpio), `SimulatedScale`, and `ScaleStream` which polls in the background and tracks zero |
| `recognition/metrology.py` | ArUco markers to millimetres; also prints the marker sheets |
| `recognition/calibration.py` | `pick_threshold`, `auroc`, `fpr_at_tpr`, `energy_score`, `msp_score` — how τ is chosen from data |

## `scanner/` — the till

| File | Owns |
|---|---|
| `scanner/ui/main_window.py` | The window.  `MainWindow`, `ScanWorker` (the QThread), `ReceiptStrip`, `ReceiptDialog`, `PaymentDialog`, `TornEdge`.  The largest file in the tree |
| `scanner/ui/enrol_dialog.py` | Teach a product: capture k views, name it, price it, save it |
| `scanner/ui/theme.py` | `TOKENS` and the QSS built from them; `load_fonts` registers the bundled Plex faces with Qt |
| `scanner/detection/camera.py` | `VideoStream` — a background reader thread, DirectShow on Windows, exposure lock |
| `scanner/models/product.py` | The `Product` row as the UI sees it |
| `scanner/models/cart.py` | `ShoppingCart` and `CartItem` |

## `server/` — records, money, dashboard

| File | Owns |
|---|---|
| `server/main.py` | Fourteen FastAPI routes, the `/static` mount, and `require_pin` for LAN mode |
| `server/services/database.py` | The only SQLite gateway.  `SCHEMA`, six tables, `process_pending_payment` |
| `server/services/checkout.py` | `create_payment` and `confirm_payment` — the money path as plain functions |
| `server/services/promptpay.py` | Real EMVCo merchant-presented QR payloads, with CRC |
| `server/services/receipt.py` | `render` — 32 columns, abbreviated tax invoice or plain receipt |
| `server/services/restrictions.py` | `sale_gate` — alcohol hours and the tobacco rule |
| `server/services/slip_verify.py` | The payment-slip hook; `NullVerifier` when unconfigured |
| `server/static/` | Four HTML pages, six JS modules, one stylesheet, seven woff2 faces |

## `research/` — the harness

| File | Owns |
|---|---|
| `research/experiments.py` | E2–E9, one function each |
| `research/run.py` | The driver; stamps environment and split onto every result |
| `research/report.py` | Results JSON to `paper/tables/*.tex` and `paper/figures/*.pdf` |
| `research/dataset.py` | `SyntheticSource`, `CaptureSource`, `ImageFolderSource`, and `make_split` |
| `research/capture.py` | The rig camera CLI |
| `research/bench.py` | Per-stage latency; records the machine so a laptop run cannot be quoted as a Pi run |
| `research/prepare_grocerystore.py` | Lays the public Grocery Store dataset out for E9 as symlinks |
| `research/PROTOCOL.md` | What to buy, how to photograph it, and the two ways this goes wrong |

## `tools/` — operator scripts

`tools/set_threshold.py` (write the measured τ where the till reads it) ·
`tools/seed_demo.py` (a demo shop from synthetic products) ·
`tools/export_embedder.py` (ONNX) · `tools/export_coreml.py` (Core ML, needs `.venv-coreml`) ·
`tools/export_fixtures.py` (the JSON that keeps Swift honest) ·
`tools/calibrate_scale.py` and `tools/scale_drift.py` (the load cell) ·
`tools/make_marker.py` (printable ArUco sheets) ·
`tools/check_kb.py` (this folder's link checker).

## `ios/AICashier/` — the phone

Twenty Swift sources under `Sources/`, five test files under `Tests/`.
`ios/AICashier/Sources/Recognition/` is a line-by-line port of `recognition/`; `ios/AICashier/Sources/Data/`
mirrors `server/services/`; `ios/AICashier/Sources/UI/` is four SwiftUI screens; `ios/AICashier/Sources/Theme.swift`
is `docs/DESIGN.md` in Swift; `ios/AICashier/Sources/Store.swift` is the observable object every
screen shares.  `ios/AICashier/project.yml` is the xcodegen definition — there is no checked-in
Xcode project.

## `docs/`

| Path | What it is |
|---|---|
| `docs/kb/` | This knowledge base |
| `docs/research/` | The dossier: nine numbered documents plus `docs/research/claims.csv`, a 145-row evidence ledger |
| `docs/DESIGN.md` | The one token table, hand-copied into four files |
| `docs/HARDWARE.md` | Bill of materials, geometry, wiring, thermals, bring-up |
| `docs/PRIVACY.md` | What a frame becomes, and the one-page DPIA |
| `docs/DISTRIBUTION.md` | Release runbook and the landing page |
| `docs/notice-th.md` | The printable bilingual camera notice |
| `docs/tools/` | Eight scripts that generate the school deliverables and every screenshot |
| `docs/evidence/` | Eight captured terminal transcripts backing the progress reports |
| `docs/assets/` | The demo frame, the demo mat, and six real product photographs |
| `docs/shots/` | Thirteen dated screenshot sets, indexed by `docs/shots/README.md` — `aug10`…`aug28` back the eight submitted EDI reports; `v4`…`v4d` and `ios` are the current surfaces |

## Generated, never edited by hand

`paper/tables/` and `paper/figures/` (from `research/report.py`) ·
`research/results/` (from `research/run.py`) · `graphify-out/` (from `graphify`) ·
`data/checkout.sqlite3`, `data/gallery.npz`, `data/mat_background.png` ·
`dist/`, `build/pyinstaller/`, `ios/AICashier/build/`.
All of them are gitignored.
