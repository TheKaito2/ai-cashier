# AI Cashier — version 4

A self-checkout till that recognises products with a camera, **and can be taught a
new product in about thirty seconds without retraining anything.**

Built by **Group 3**, Engineering Design and Innovation, Assumption College Sriracha.
Punn · Pleum · Athens · Kit · Bible · Pokpong — instructor Mr. John Victor S. Opiña.

---

## What changed, and why it matters

Version 3 was a working closed-set system: two YOLOv8n models, twelve products,
one process, tested. Its limit was structural rather than cosmetic.

**It could only ever know twelve products.** A thirteenth meant photographing it
hundreds of times, labelling every image and retraining — days of work, in a shop
whose range changes weekly.

**It could not say "I don't know."** A softmax always names something. An unseen
packet was charged as whatever it resembled.

Version 4 replaces the classifier with retrieval:

```
frame ──► propose ──► embed ──► match against a gallery ──► fuse ──► price
          (what is    (what     (which product is it,      (mass and
           on the      does it   or none of them)           size settle
           mat)        look                                 what the
                       like)                                camera cannot)
```

Enrolling a product is appending rows to that gallery. There is no gradient step
anywhere in the loop, and the till can sell the new line on the very next frame.

## Run it

```bash
pip install -r requirements.txt
python tools/export_embedder.py        # one-off: freeze the backbone to ONNX
python app.py
```

One command, one process. The window is the till; the shopkeeper's dashboard
(inventory, takings, the deployment log) is on `http://127.0.0.1:8000`. The till
owns the camera, the scale and the cart and writes the database directly; the
dashboard is a read-mostly view on the same file.

| Flag | What it does |
|---|---|
| *(none)* | Till plus dashboard, simulated scale |
| `--scale hx711` | Use the real load cell |
| `--scale none` | No weighing; the basket check reports that it could not run |
| `--lan` | Dashboard reachable from the shop wifi; writes need `dashboard_pin` |
| `--fullscreen` | Kiosk: the till fills the screen |
| `--server-only` | Dashboard only — spare screen, or a headless Pi |
| `--demo` | Replay a still image instead of a camera |

To try it with no camera and no shelf of crisps:

```bash
python tools/seed_demo.py     # enrols synthetic products, holds one back
python app.py --demo
```

## Using the till

1. **Calibrate mat** — once per setup, with the mat empty. Everything builds on it.
2. **Add product** — put it on the mat, turn it between five captures, set a price.
3. **SCAN PRODUCTS** — items appear with their price and how many frames agreed.
   - amber *Unknown item* → not in the gallery; enrol it or call staff
   - blue *not sure* → two candidates too close to call; the operator chooses
4. **PAY** — the basket's mass is checked against what the till is charging for,
   then a PromptPay QR is shown that a banking app will actually open.

## Layout

```
app.py               the only entry point
recognition/         propose → embed → match → fuse, plus the scale and metrology
scanner/             the PySide6 till
server/              the dashboard: FastAPI, static pages, SQLite, the checkout service
research/            experiments, capture protocol, benchmark
paper/               LaTeX draft; tables and figures are generated, never typed
tools/               export the backbone, calibrate the scale, print the markers
deploy/              systemd unit for the Pi
tests/               161 tests
docs/HARDWARE.md     what to buy, how to wire it, how to calibrate it, Pi OS setup
docs/research/       the dossier: law, market, literature, venues, architecture review
```

## Notable fixes carried in from version 3

- **SQLite with real transactions.** A sale is one transaction — stock down, sale
  written, payment closed, or none of it. v3 read-modified-wrote a JSON file with
  the lock released in between, so concurrent sales lost updates, and `json.dump`
  truncated first, so a crash mid-sale destroyed products, sales and stock together.
- **A payment QR that is a payment.** v3 encoded `PAYMENT|68.48|<uuid>`, which no
  bank can read. Now a real EMVCo PromptPay payload with a CRC-16 checksum.
- **The proposer differences in colour.** A greyscale difference is blind to any
  product whose brightness matches the mat; a red-and-blue can simply vanished.
- **The mask is computed at half resolution.** Benchmarking showed this stage —
  not the neural network — dominated the frame budget. 3.9× faster, same boxes.

## Measured, on this machine

Numbers from an Apple M1. **The paper's figures must come from
`research/bench.py` run on the Raspberry Pi**; the script refuses to let a laptop
run be mistaken for a Pi run.

| | |
|---|---|
| Embedding, ONNX FP32 | 0.3 MB, ~6 ms per crop, cosine 1.00000 against torch |
| Dynamic INT8 | **2.2× slower and cosine 0.71** — measured, so we ship FP32 |
| Propose (720p, half-res mask) | ~5 ms |
| Gallery match | under 0.1 ms |
| Steady state, 3 items on the mat | ~6 ms per frame |

## Tests

```bash
pytest tests/ -v
```

161 checks over the money and the recognition: cart arithmetic, VAT, stock
decrement, transaction rollback, concurrent restocks, unique sale ids, PromptPay
checksums, gallery matching and the frozen centre, open-set rejection, fusion
and the one-item weight rule, the HX711 bit protocol against a fake GPIO chip,
the scale stream and zero tracking, shadow suppression, four-marker metrology,
camera settings, restricted goods, receipts, slip verification, the dashboard
PIN, and the full enrol-then-recognise path.

## Research

`research/PROTOCOL.md` is the capture and experiment protocol — read it before
photographing anything. The harness runs today on synthetic data so every table
regenerates and the code is debugged before the capture session:

```bash
python research/run.py --source synthetic    # verifies the harness
python research/report.py                    # regenerates paper/tables and figures
```

Every generated table says at the top which source it came from. If a table you
are about to submit says `SOURCE = synthetic`, the experiments have not been run.
