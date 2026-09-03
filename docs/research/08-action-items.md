# 08 — Action items derived from the research, ranked

Each item names the file, the change, the effort, and the dossier section it comes from. **Status as of 2 Sep 2026: all 16 built** (see the Status column). "Effort" is a rough size, not a schedule.

| # | Change | Files | Effort | From | Status |
|---|---|---|---|---|---|
| 1 | **Swap PyQt5 → PySide6** so the till can be released under Apache-2.0 instead of GPL | `requirements.txt`; `scanner/ui/*.py`; `app.py`; `docs/tools/` shot harness | S (mechanical: imports, `exec_`→`exec`, enum scoping) | 02 §1 | done: PySide6 6.11, `exec()`; rendered offscreen, `docs/shots/v4b/` |
| 2 | **Add `LICENSE` (Apache-2.0) and a `NOTICE` listing third-party licences**, incl. the AGPL status of the legacy `.pt` models | repo root; `models/README` | XS | 02 §1 | done: `LICENSE`, `NOTICE`, `models/README.md` |
| 3 | **Keep ultralytics out of the till**: a test that fails if `scanner/` or `server/` can import `ultralytics` | `tests/test_no_ultralytics.py` | XS | 02 §1 | done: `tests/test_no_ultralytics.py` blocks torch too |
| 4 | **Restricted-goods gate**: `products.restricted` ∈ {none, alcohol, tobacco}; alcohol refused outside 11:00–24:00 and requires staff ID confirmation; tobacco staff-only and hidden from the browser | `server/services/database.py` (schema + migration), `scanner/ui/main_window.py` `_sellable()`, `server/main.py`, dashboard product form | S–M | 01 §2 | done: `products.restricted`, `server/services/restrictions.py`, 403 + `staff_confirmed`, till dialog, enrol picker, inventory badge; tobacco hidden from `?staff=false` list and browser detections |
| 5 | **Privacy-by-design statement in code and docs**: assert no frame is written in the recognition path; front-camera mask above the mat plane; CCTV notice text + one-page DPIA | `recognition/pipeline.py` (docstring + test), `docs/PRIVACY.md`, `docs/notice-th.md` | S | 01 §1 | done: `docs/PRIVACY.md` (with DPIA), `docs/notice-th.md`, `mask_above_mat`, `tests/test_privacy.py` |
| 6 | **Receipt module with VAT / non-VAT modes** (abbreviated tax invoice fields) | `server/services/receipt.py`; `settings.vat_registered`, `settings.tin`; dashboard | S | 01 §4, 04 §5 | done: `server/services/receipt.py`, `/api/receipt/{id}`, settings `vat_registered`/`tin`/`store_address` |
| 7 | **Slip-verification hook** behind payment confirmation, with `NullVerifier` default and an `EasySlip`-style HTTP verifier | `server/services/slip_verify.py`; `server/main.py` confirm endpoint; `database.process_pending_payment` | S | 04 §4 | done: `server/services/slip_verify.py` (Null + HTTP), `POST /api/confirm-payment {slip}` → 402 on mismatch |
| 8 | **Public benchmark adapter**: `CaptureSource`-compatible loader for GroceryVision MPR and RPC held-out splits; E9 in the harness and report | `research/dataset.py`, `research/experiments.py`, `research/report.py` | M | 05 A, 07 T1 | done: `ImageFolderSource`, `WholeFrameProposer`, E9, `run.py --source folder --root`, `report.py` tables |
| 9 | **E5b energy-score baseline** next to MSP | `recognition/calibration.py`, `research/experiments.py` | XS | 05 E | done: `energy_score`, `msp_score`; E5 reports all three rules |
| 10 | **Static INT8 with calibration data** on the Pi, replacing the dynamic-quant result | `tools/export_embedder.py`, `research/bench.py` | S | 04 §8 | done: `--int8-static` (QDQ, per-channel, 24 calibration crops); `models/mobilenet_v3_small-int8s.onnx`. Measured on M1 with product-like crops: static INT8 cos 0.82 vs torch at ~2x FP32 speed; dynamic INT8 cos 0.61 and slower. Accuracy effect goes through E3 before it ships |
| 11 | **Small-VLM encoder ablation** (MobileCLIP-B, SigLIP-small, DINOv3-distilled) as E3 rows | `recognition/embedder.py` BACKBONES, `research/experiments.py` | M | 05 D | done: `mobileclip_b`, `mobileclip_s1`, `siglip_b16`, `dinov2_vits14` in `TorchEmbedder`; `run.py --backbones` |
| 12 | **"Verification scale, not trade scale"** paragraph + drift measurement procedure | `docs/HARDWARE.md`, paper System section | XS | 01 §3, 04 §6 | done: HARDWARE.md sections + `tools/scale_drift.py` |
| 13 | **Deployment logs** for future tiers: enrolments, abstentions, overrides, predicted-vs-scanned baskets | `server/services/database.py` (4 tables), till hooks | S | 07 | done: `events` table (one table, `kind` column), `log_event`/`get_events`, `/api/events`, till hooks |
| 14 | **Paper**: rewrite Related Work from 05; add "Deployment and compliance" subsection; extend Limitations; bib to ~40 verified entries | `paper/main.tex`, `paper/refs.bib` | done in this phase | 05, 01, 02 | done (phase 3) |
| 15 | **Capture protocol**: add "no people in frame / delete if present" and metadata fields | `research/PROTOCOL.md` | XS | 01 §1, 02 §2 | done: PROTOCOL.md 0b + `capture.py --rig-note` |
| 16 | **Ethics**: decide whether E7 uses team members only or gets a university ethics review before recruiting classmates | `research/PROTOCOL.md` | decision | 01 §6 | recorded in PROTOCOL.md 0c: default = authors only; classmates need ethics approval |

### From the architecture review (09), 2 Sep 2026

| # | Change | Files | From | Status |
|---|---|---|---|---|
| 17 | Browser till and websocket frame path removed; web = owner dashboard only | `server/main.py`, `server/static/` | 09 D1 | done |
| 18 | One cart: checkout service called by the till and by REST | `server/services/checkout.py`, `scanner/ui/main_window.py` | 09 D2 | done |
| 19 | `--lan` with PIN-protected writes; CORS removed | `app.py`, `server/main.py`, `inventory.js` | 09 D3 | done |
| 20 | Scale read on its own thread with zero tracking; HX711 on lgpio; one-item weight rule | `recognition/scale.py`, `recognition/fusion.py`, `scanner/ui/main_window.py` | 09 D5, D6 | done |
| 21 | Frozen gallery centre; prototype and whitening ablation rows | `recognition/gallery.py`, `research/experiments.py` | 09 D7, D8 | done |
| 22 | Shadow suppression in the proposer | `recognition/proposer.py` | 09 D10 | done |
| 23 | Four corner markers for metrology | `recognition/metrology.py`, `tools/make_marker.py` | 09 D12 | done |
| 24 | Camera exposure lock, MJPG, resolution honoured | `scanner/detection/camera.py`, `config/settings.json` | 09 D9 | done |
| 25 | Dead surface removed; hardware config in the file, shop settings in the DB | `config/settings.json`, `scanner/models/product.py`, `database.py` | 09 D13 | done |
| 26 | Fullscreen, systemd unit, Pi OS Trixie guidance | `app.py`, `deploy/ai-cashier.service`, `docs/HARDWARE.md` | 09 D16 | done |
| 27 | Scan latency on the Pi decides whether the scan moves to a worker thread | `research/bench.py` (`scan_5_frames`) | 09 D4 | done: moved to a QThread worker after measuring 191 ms cold on the M1 |
| 28 | Query centring fix (query normalised before the centre is subtracted); τ placeholder 0.38 → 0.75 | `recognition/gallery.py`, `recognition/fusion.py`, iOS `Gallery.swift`/`Fusion.swift` | 09 F5 | done (found by the Swift port, 3 Sep 2026) |

### Real-data readiness, 3 Sep 2026

| # | Change | Files | From | Status |
|---|---|---|---|---|
| 29 | First non-synthetic rows: E9 on the Grocery Store dataset (packages / all / iconic-first) | `research/prepare_grocerystore.py`, `run.py --tag`, `report.py`, `paper/main.tex` | 07 T1, 05 #4 | done: 45.8 % / 59.7 % top-1 at k=5, open-set AUROC 0.67 / 0.37 (claims X15) |
| 30 | Measured threshold written where the till reads it, with the iPhone line printed | `tools/set_threshold.py` | 09 F5, fusion.py | done |
| 31 | Capture session on a laptop or iPhone camera: `capture.py --list`, PROTOCOL 2b | `research/capture.py`, `research/PROTOCOL.md` | 07 T1 | done; camera permission is a per-terminal macOS grant |
| 32 | The paper compiles (tectonic) | `paper/Makefile` | — | done |
| 33 | E9 with the other encoders (MobileCLIP-B, DINOv2) — the public rows say the ImageNet trunk is the lever, not more views | `run.py --source folder --backbone …` | 05 P27, X15 | open: needs the weights downloaded |

Items 1–3 change what the project may legally claim. Items 4–7 turn a demo till into something a Thai shop could switch on. Items 8–11 are what a reviewer will ask for. Items 13–16 protect the master's/PhD path.
