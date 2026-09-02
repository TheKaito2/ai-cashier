# 09 — Architecture review: every decision questioned, with the verdict

Written 2 Sep 2026, after phases 1–4. The brief was: question every architectural decision in v4, find out why it was made, research whether it is the best way, and change what is not. Every entry has the same shape — what v4 did, why, the alternatives with evidence rows from `claims.csv` (`[A..]`), a verdict, and what was done about it in this round. Verdicts are **KEEP**, **CHANGE** (done in this round) or **MEASURE** (a number the Pi has to produce first).

Four things were found broken on the target hardware or in production use before any design question was reached. They head the list because a review that argues about UI stacks while the scale is never read would be a review of the wrong thing.

## Summary

| # | Decision | Verdict | One line |
|---|---|---|---|
| D1 | A Qt till *and* a browser till + web dashboard | CHANGE | Browser till deleted; web = owner dashboard only |
| D2 | Till reaches its own server over HTTP; server keeps a second cart | CHANGE | One cart; a checkout service both doors call |
| D3 | uvicorn on a thread in the till process | KEEP | `--lan` + PIN for writes; CORS removed |
| D4 | The 5-frame scan on the UI thread | CHANGE | Measured 191 ms cold on M1 → QThread worker |
| D5 | Scale wiring | CHANGE | Never polled; wrong library for the Pi 5; both fixed |
| D6 | Per-item weight = whole pan | CHANGE | One-item rule: pan delta since the cart last changed |
| D7 | Centre = live gallery mean | CHANGE | Frozen centre; whitening as the research row |
| D8 | SKU score = nearest view | KEEP | Prototype row added to E2 |
| D9 | MobileNetV3-Small, ImageNet | MEASURE | E3 decides; exposure lock added now |
| D10 | Background-subtraction proposer | KEEP + | Shadow suppression added |
| D11 | Centroid tracker | KEEP | — |
| D12 | One 60 mm marker | CHANGE | Four corner markers |
| D13 | SQLite; config split file/DB | KEEP | Dead surface removed; the split written down |
| D14 | Events table | KEEP | — |
| D15 | Static PromptPay + slip hook | KEEP | — |
| D16 | No kiosk, no service, no Pi OS guidance | CHANGE | Fullscreen, systemd unit, Trixie guidance |
| D17 | Money path tested over HTTP | KEEP + | Service is the seam; tests hit both doors |
| D18 | Paper's "one process" | KEEP | Reworded to match |
| D19 | Research harness, ONNX, INT8 | KEEP | — |

161 tests passed after the changes (136 before); 167 after Phase 6 added the path and self-test checks.

## The four faults

### F1 — The scale was never read
`_FilteredScale.read_stable_grams()` returns a number only when its 8-sample window is full and still. Nothing in `app.py` or `scanner/` ever called `read_grams()`, so the window was always empty and every weight question — at scan, at enrolment, at PAY — was answered "unknown". The multimodal claim the paper makes existed only in the tests, which call `SimulatedScale.settle()` by hand. `docs/HARDWARE.md` also said the till tares between baskets; no `tare()` call existed.
**Fix (D5):** `ScaleStream` reads the cell on its own thread at the HX711's 10 Hz and re-zeroes the pan whenever it settles within 5 g of empty. The enrol dialog now shows the reading (`docs/shots/v4c/01-till-enrol.png`: "Scale reads 75 g").

### F2 — `HX711Scale` could not run on the Pi 5
`requirements.txt` pinned PyPI `hx711`, which requires `RPi.GPIO` [A01, A02]; `RPi.GPIO` does not work on the Pi 5's RP1 GPIO controller [A03]. Worse, the code called `get_raw_data_mean(readings=1)`, a method from a different library (gandalf15's); the pinned package only has `get_raw_data(times)` [A02]. It would have raised `AttributeError` on a Pi 4 too.
**Fix (D5):** the HX711 protocol [A20] is bit-banged in ~40 lines over `lgpio`, the library the Pi engineers put under gpiozero and the one that drives the Pi 5 [A04]. Tested against a fake GPIO chip that replays known 24-bit words and counts clock pulses (25 at gain 128, 27 at gain 64).

### F3 — Every item was weighed as the whole pan
`on_scan_clicked` passed the pan's total to `RecognitionPipeline.process(weight_delta_g=…)` for every item on the mat, although the argument is documented as the mass one item added. With two items every weight likelihood was wrong and pulled decisions toward the heaviest enrolled product.
**Fix (D6):** `item_weight_for_scan(pan, baseline, n_items)` returns the pan's change since the cart last changed, and only when exactly one item is on the mat; otherwise `None`, which the fusion treats as "no evidence". The basket check at PAY still verifies the total.

### F4 — Two carts drifted apart
The Qt `ShoppingCart` and the server's in-memory `CartManager` were both authoritative. The `+` stepper changed the Qt one only, so `POST /api/checkout-cart` priced the server's stale quantities. `get_product_flexible` also accepted any product whose id merely *contained* the request (`"coke"` → `"coke-zero"`).
**Fix (D2):** one cart, exact ids.

## The decisions

### D1 — Why a Qt window *and* a website?
**Current.** v2 was two processes: a PyQt scanner and a Flask/FastAPI web app with its own copy of the YOLO weights. v3 merged them into one process but kept both user interfaces: the Qt till, and a browser till (`checkout.html`) that pushed JPEG frames over a websocket to the server's own copy of the pipeline, plus inventory/analytics pages. v4 inherited all of it.
**Why.** History, not design. The web pages were the group's original dashboard; the browser till was a second way to demo without a Qt install.
**What was actually there.** The browser till was half dead: `checkout.js` called `/api/create-payment` (no such route), keyed products by the v3 `yolo_class`, and `DetectionService.reload_gallery` — the only way the server's pipeline would learn about a product enrolled on the till — was never called. Two pipelines, two galleries in memory, one of them stale.
**Alternatives.** (a) All-web: the industry precedent is Odoo POS, a browser UI with a LAN "IoT box" owning printers and scales [A10]; on a Pi the documented kiosk path is Chromium under labwc [A11]. Cost: the process that owns the camera must still be local, and the browser needs frames — JPEG over a websocket at 10 fps (what `checkout.js` did) or an MJPEG stream — a round trip the Qt till does not pay; plus a rewrite of a till that already renders and is screenshot-verified. (b) All-Qt: fold inventory/analytics into tabs, delete the server. Loses the one thing a web page does that Qt cannot: the shopkeeper checking takings on a phone. (c) Qt till, web dashboard only.
**Verdict: CHANGE → (c).** The user chose (c). Deleted: `checkout.html/js`, `cart.html/js`, `/ws/detection`, `DetectionService`, the session-cart endpoints. Kept: `/`, `/inventory`, `/admin`, `/monitor` — all REST-only. There is now exactly one process that ever holds a frame (`docs/PRIVACY.md`).

### D2 — The till talked to itself over HTTP
**Current.** `MainWindow` posted to `127.0.0.1:8000/api/add-batch-to-cart` and `/api/checkout-cart` with `requests`, while holding a direct `Database()` handle for products and events. The server kept a `CartManager` dict.
**Why.** Leftover from the two-process v2, where HTTP was the only bridge.
**Verdict: CHANGE.** `server/services/checkout.py`: `create_payment(db, items, staff_confirmed)` and `confirm_payment(db, payment_id, slip)` are pure functions over the database holding the stock check, the restricted-goods gate, the event log, the PromptPay QR, slip verification and the receipt. The till calls them; `POST /api/checkout` and `POST /api/confirm-payment/{id}` are one-line wrappers for the dashboard and the tests. `requests` is gone from the till; the "server online" pill became a signpost to the dashboard URL.

### D3 — A web server inside the till process
**Current.** `app.py` runs uvicorn on a daemon thread, bound to `127.0.0.1`, with `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` and no authentication on any write.
**Why.** One command, one database (v3's stated reason). Sound: SQLite in WAL mode lets the dashboard read while the till writes, and a second process would need its own supervision.
**What was wrong.** `*` with credentials is not a valid CORS combination [A21] and same-origin pages need no CORS at all. The moment `--server-only` is used on a "spare screen" the server must bind a LAN address, and then anyone on the shop wifi could restock, reclassify or confirm payments.
**Verdict: KEEP the process shape, CHANGE the exposure.** Default stays loopback. `--lan` binds every interface and makes every write route (`checkout`, `confirm-payment`, `restock`, `restriction`, `events` POST) require `X-Dashboard-Pin` equal to `settings.dashboard_pin`; with `--lan` and no PIN, writes are refused — the safe direction. CORS middleware removed. The inventory page asks for the PIN once.

### D4 — Recognition on the UI thread
**Current.** `on_scan_clicked` ran five frames of propose → embed → match synchronously.
**Measured.** `research/bench.py` gained `scan_5_frames`: **191 ms cold on the M1** (propose 14 ms, embed 7 ms/crop, three items). A Pi 5 is several times slower per core, so the plan's rule ("worker thread if the Pi exceeds 200 ms") is already decided by the laptop number.
**Verdict: CHANGE.** `ScanWorker(QObject)` on a `QThread`, results back by signal — the pattern Qt documents for long work [A19]. SCAN is disabled and the enrol dialog cannot open while a scan runs, so nothing else touches the pipeline. Still worth measuring on the Pi (`research/bench.py`) for the paper.

### D5 — Scale wiring
See F1 and F2. **CHANGE**, done: `ScaleStream`, `HX711Scale` on `lgpio`, `lgpio` replaces `hx711` in `requirements.txt`, zero tracking replaces the tare the till never did.

### D6 — Per-item weight
See F3. **CHANGE**, done: `item_weight_for_scan`; the till keeps `_pan_baseline_g` and updates it after each add-to-cart; the worker counts items on the mat before deciding whether the scale may speak. Documented limit: put items down one at a time to get the mass term; several at once get appearance and size only.

### D7 — Centring on a mean that moves
**Current.** `SkuGallery.match` centres queries and references on the *live* gallery mean. That is the right idea — an ImageNet trunk's features share a large common direction, and centring turned a 0.81 cosine between unrelated products into −0.18 [gallery docstring].
**What was wrong.** The rejection threshold τ (`FusionConfig.reject_below_cosine`, calibrated by `recognition.calibration.pick_threshold` / E5) is a cosine in the centred space. Every enrolment moved the mean, so every existing score, and τ was silently calibrated in a coordinate system that no longer existed after the next product.
**Alternatives.** Jégou & Chum showed that mean subtraction and PCA whitening are the two halves of the same correction for retrieval descriptors, and that both should be fitted on an independent set [A14]. NVIDIA's retail reference sidesteps the problem by training a metric-learned embedder [A18], which is Tier-2 work.
**Verdict: CHANGE.** The gallery gets a **frozen centre**: once four products are enrolled the till pins the mean; later enrolments add rows and nothing else (test: scores identical to 1e-6 after enrolling two more products; the floating version moves them). `save/load` carry it; `thaw_centre()` is the explicit act that goes with recalibrating τ. `PcaWhitening` (fit on `split.seen`, transform everything) is the E3 ablation row — the correct long-term answer, but it needs real captures to fit.

### D8 — Nearest view, not mean prototype
**Current.** A SKU is scored by its closest reference view.
**Alternative.** Prototypical Networks score by the mean of the support views [A16]. With five views a mean is easily pulled off by one bad angle; the NeurIPS 2022 analysis says exactly that about small-shot prototypes [A17].
**Verdict: KEEP.** E2 now reports both columns (`match_prototypes`) so the paper shows the comparison instead of asserting it.

### D9 — MobileNetV3-Small ImageNet trunk
**Current.** 576-d, ONNX FP32, 6–7 ms per crop on the M1.
**Alternatives.** Already wired for E3: MobileCLIP-S1/B, SigLIP-B/16, DINOv2-S. NVIDIA's shipped retail embedder is metric-learned [A18].
**Verdict: MEASURE.** E3 on real captures decides. One thing done now: HARDWARE.md prescribed locking exposure and white balance and the code never did it — `VideoStream` now sets `CAP_PROP_AUTO_EXPOSURE`/`AUTO_WB` (V4L2 values) when `camera.lock_exposure` is on, plus MJPG and the configured resolution, which were also read from config and then ignored.

### D10 — Finding objects by subtracting the empty mat
**Current.** Colour absdiff against a calibrated empty-mat photo, half resolution, morphology, contours.
**Why.** Class-agnostic by construction — the only proposer that can propose a product it has never seen — and about a millisecond.
**Alternatives.** A class-agnostic detector (YOLO-World, FastSAM/EdgeSAM) costs tens of ms on a Pi and buys robustness to a cluttered background the rig does not have. MOG2 adapts the background over time (useful) but also absorbs a product that sits still (fatal at a till).
**What was wrong.** A shadow is the mat, darker; the absdiff counts it as foreground, so a box grows to include the product's shadow or a hand's.
**Verdict: KEEP, plus shadow suppression.** A masked pixel whose chromaticity matches the background within ε and whose intensity ratio sits in (0.55, 0.95) is dropped — the standard chromaticity shadow model, as in MOG2's `detectShadows` [A15]. Computed only on masked pixels, so the cost is negligible. Known ceiling (ponytail comment in the code): an achromatic packet whose intensity ratio falls in that band is invisible to the test; HARDWARE.md now recommends a black mat, where shadows barely register anyway. Automatic background refresh stays a roadmap item.

### D11 — Centroid tracker
**KEEP.** Items on a mat do not occlude or move fast; a heavier tracker would add nothing.

### D12 — One ArUco marker for millimetres
**Current.** One 60 mm marker → homography from four corners 60 mm apart, extrapolated across an A3 mat.
**What was wrong.** OpenCV's own FAQ says single-marker corners are relatively inaccurate even with subpixel refinement and recommends ChArUco-style multi-corner targets for measurement [A13]; the error grows with distance from the marker.
**Verdict: CHANGE.** Four markers (ids 0–3) at the mat corners, positions in `rig.marker_positions_mm`; the homography is fitted to all sixteen corners. Synthetic test: a 600×400 mm mat photographed off-axis; a 100 mm span at the far corner measures within 1 mm with four markers and worse with one. A ChArUco board would be better still but products would cover it. `tools/make_marker.py` prints the four on one sheet; one marker still works.

### D13 — SQLite, and settings in two places
**Current.** SQLite with WAL, thread-local connections, one write lock, JSON payloads for pending payments. Settings split between `config/settings.json` and the `settings` table.
**Verdict: KEEP.** The storage choice was right in v4 and stays. The split is now a rule, written at the top of the file: hardware and rig settings in the file, shop settings in the database. Dead surface removed: the `ui`/`detection`/`payment`/`app`/`localization` sections nothing read; `Product.yolo_class_name/image/volume`; `get_product_by_yolo_class` and its tests. The `yolo_class` column stays for old databases and is marked legacy.

### D14 — Events table
**KEEP.** One table with a `kind` column; the log the later tiers need.

### D15 — Static PromptPay QR with an optional slip verifier
**KEEP.** Analysed in `04-how-it-works.md` §4; the confirmation gap is documented, the verifier hook exists.

### D16 — Deployment
**Current.** `python app.py`; no fullscreen, no service, no note on which Pi OS.
**Found.** PySide6 wheels for aarch64 from 6.8 onward are built against glibc 2.39 [A05]; Raspberry Pi OS Bookworm has 2.36, Trixie 2.41 [A07]; Trixie's apt package is 6.8.2 [A06]. onnxruntime and opencv-contrib ship aarch64 wheels usable on either [A08, A09]. USB webcams on the Pi 5 go through V4L2, not libcamera [A12].
**Verdict: CHANGE.** `--fullscreen` (and `display.fullscreen`), `deploy/ai-cashier.service` (systemd user unit, restart on failure), and a "Bringing it up on Raspberry Pi OS" section in HARDWARE.md with the Trixie requirement, the Bookworm fallbacks, the camera notes and the `--lan` PIN.

### D17 — Tests that drove the money path over HTTP
**KEEP, adjusted.** The checkout service is the seam: `tests/test_checkout.py` exercises `create_payment/confirm_payment` directly and the two REST wrappers, plus the PIN rule in both modes.

### D18 — The paper's "one process" claim
**KEEP, reworded.** System paragraph now says who owns what; Method gains the frozen-centre sentence and the one-item mass rule.

### D19 — Research harness, ONNX export, INT8 decision
**KEEP.** Unchanged, except that E2 and E3 gained the D7/D8 ablation columns.

### F5 — found by the Swift port (3 Sep 2026): the query was never centred
`SkuGallery.project` subtracted the unit-length centre from the **raw** query vector (norm in the tens) and normalised afterwards. The gallery rows were centred; the query effectively was not. On the synthetic set that left known products at ~0.39 and a stranger at ~0.27 against a threshold of 0.38 — a margin of 0.12 that every E5 number so far was calibrated on. Porting the gallery to Swift (which normalised the query first) made the two implementations disagree on every score and exposed it. **Fix:** normalise the query before subtracting the centre. Re-measured on the same set: same product 0.92, different products −0.13 on average (0.90 for the hardest pair), stranger 0.67. The placeholder `reject_below_cosine` moves from 0.38 to 0.75 in both implementations; E5 still calibrates the real value. The docstring and paper numbers (0.81 / −0.18 / 0.88) were replaced by the re-measured ones (0.80 / −0.13 / 0.92). A cross-language fixture test (`ios/AICashier/Tests/RecognitionTests.swift`) now pins every gallery score to Python's.

## What this round could not verify

- The `lgpio` HX711 reader on real Pi 5 hardware. The protocol is tested against a fake chip; timing on real GPIO is not.
- The scan latency on the Pi (D4): the worker thread is in, the number for the paper is not.
- The USB webcam on the Pi 5 (D16): V4L2 with MJPG is the documented path; one forum report of an OpenCV open failure with a specific camera exists [A12].
- Shadow suppression on real lighting: the chromaticity thresholds were set on synthetic mats and should be checked on the first captures.

## Sources

Rows A01–A21 in `claims.csv`. `fetched` rows were opened and read this session; `search-snippet` rows were seen through a search engine's summary; `recalled` rows (the HX711 datasheet, the Fetch standard) are from memory with the URL where the primary text lives.
