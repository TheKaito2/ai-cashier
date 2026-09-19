# The rig

Everything in software is finished and tested against a simulated scale. This is
what has to exist physically before the paper has numbers.

Prices are indicative Thai retail and should be checked before ordering.

---

## Bill of materials

### Already have
| Part | Note |
|---|---|
| Raspberry Pi 5, 8 GB | plenty; the pipeline is CPU-bound, not memory-bound |
| 14″ touchscreen | the till UI is laid out for this |
| USB webcam | the overhead camera |

### To buy

| Part | Spec | ~THB | Why this one |
|---|---|---|---|
| Load cell | **Zemic L6D-C3-5kg** (single-point, rated platform 250 × 350 mm); listed equivalents Tedea 1022, Keli AMI, Mavin NA1 | quote on request | See below — a cell with a published platform rating and accuracy class, not the unspecified hobby bar |
| HX711 | 24-bit ADC breakout, header pins already soldered unless you solder | 50–120 | Standard; `recognition/scale.py` bit-bangs it over `lgpio` (the Pi 5 GPIO library) |
| Weighing plate | flat and rigid, **no larger than 250 × 350 mm** (A4 fits inside); 5 mm acrylic or 3 mm aluminium | 150–400 *(rough)* | Its own mass is dead load on the cell; larger than the rated platform and off-centre items read wrong |
| Base plate | stiffer and heavier than the top; 10–12 mm plywood or MDF | 100–250 *(rough)* | A base that flexes under load reads as drift |
| Spacers and bolts | **four M6 bolts, class 8.8**, two per end, torqued to 6 N·m, plus spacers | 50–120 *(rough)* | The L6D's holes are M6 through; the gap the spacers make is what stops the plate resting on anything but the cell |
| Jumper wires | female-to-female Dupont, at least four | 30–60 | HX711 to the Pi's GPIO header |
| Kitchen scale | digital, 1 g resolution or better, 3–5 kg | 200–500 *(rough)* | Calibration needs a known mass and verification a *different* one; the capture session needs every product's `--weight` before the rig exists |
| Ring light | 15–20 cm, diffused, ~5000 K, dimmable, **on its own wall adapter** | 400–900 | The cheapest accuracy you can buy; do not power it from the Pi |
| Overhead stand | arm or frame holding the webcam and the ring light above the mat | 300–800 *(rough)* | The mat must fill the frame with ~10 % margin, and neither may move once set |
| Pi 5 active cooler | official or equivalent | 250–400 | **Required** — see thermals |
| PSU | 5 V / 5 A USB-C (official Pi 5 supply) | 500–800 | Under-powering a Pi 5 causes faults that look like software bugs |
| Mat | matte, plain black or mid-grey, **no grid lines**, cut to the plate — **not A3** | 100–250 | Gloss produces specular highlights that move with the product; a cutting-mat grid is texture the proposer has to ignore |
| Markers | four printed ArUco, laminated | ~20 | `python tools/make_marker.py` - one per mat corner |

**Not yet — the software cannot use them.**

| Part | Spec | ~THB | Why it waits |
|---|---|---|---|
| Second webcam | 1080p, manual focus if possible | 500–1200 | Planned for bottle and can labels, but nothing in the till reads a second camera yet: `config/settings.json` has one source and no code path combines two views |
| Powered USB hub | 4-port, own supply | 300–600 | Only needed once there are two cameras |

**Why a 5 kg single-point cell, not 4 × 50 kg half-bridges.** The four-cell kit is
what most tutorials use because it comes from bathroom scales, but its full range
is 200 kg. Spread over a 24-bit ADC that is roughly 12 mg per count *in theory*
and far worse in practice once noise is included — and a 75 g crisp packet sits in
the bottom 0.04 % of the range, where the cell is least linear. A single 5 kg cell
puts the same packet at 1.5 % of range. Since the whole point of weighing is to
tell 75 g from 98 g, resolution at low mass is what rules the bathroom kit out.

**Why 5 kg rather than 10 kg.**  Bigger is not free.  Creep and temperature drift
are quoted as a fraction of *full scale* (see *Measuring drift* below), so doubling
the capacity doubles them: roughly 1 g and 1.5 g on a 5 kg cell become 2 g and 3 g
on a 10 kg one — level with `CELL_SIGMA_G` (2 g) in `recognition/fusion.py`, and
closing on the 4 g the basket check allows per item.  At that point the till
starts accusing honest customers.  The capacity has to cover the plate plus the
whole basket, because the goods stay on the pan until PAY; for snacks and
shop-size drinks (55–622 g each here) that is well under 5 kg.  Go to 10 kg only
if baskets routinely carry 1.5 L bottles or multi-packs.

**Platform size is the specification people miss.**  A single-point cell
compensates for where on the plate an item sits, but only across the platform it
is rated for.  Put a larger plate on it and the same packet reads differently at
the centre and at a corner.  Whatever you buy, test it: weigh one mass at the
centre and at each corner — the readings should agree within 2 g.

**What was found when this was checked (19 September 2026).**  The 5 kg cells the
Thai hobby shops sell — the 80 × 12.7 mm aluminium bar and the YZC-133, around
100 THB — publish **no platform rating and no accuracy figures at all**.  The
nearest thing to a datasheet for that class of cell (Phidgets 3133, 5 kg) gives
±2.5 g repeatability, 2.5 g non-linearity, 2.5 g hysteresis and a temperature
effect on zero of 500 mg per °C — each of the first three already past the 2 g
the till budgets for the cell, and the last three times worse than the figure
this document used to assume.

The **Zemic L6D** is the specified alternative, and Thai scale distributors stock
it in 5 kg (ScalesThai, Mainscale, GPM Scales; prices are quote-on-request).  Its
datasheet gives a maximum platform of **250 × 350 mm**, combined error within
±0.023 % of full scale — about ±1.2 g on the 5 kg model — 150 % safe overload,
and the same red/black/white/green wiring as the diagram below.  Mainscale lists
the Tedea 1022, Keli AMI and Mavin NA1 as equivalents.

**So the plate cannot be A3.**  A3 is 297 × 420 mm; the L6D is rated to
250 × 350.  A4 (210 × 297) fits inside it with room to spare.  The obvious larger
cell, the Zemic L6E, is rated for 400 × 400 mm but its smallest model is 50 kg,
where drift quoted as a fraction of full scale becomes ten times worse.  No
affordable single cell covers A3 — which is the one situation where four corner
cells, each read by its own HX711, earns its extra complexity.

A smaller plate leaves less room for 60 mm corner markers.  Print them smaller
(`python tools/make_marker.py --mm 40`) or mount them on a fixed frame around
the plate, flush with its surface, so they stay on the measuring plane without
being weighed.

**Excitation.**  The L6D datasheet recommends 5–12 V.  Keep the HX711 on the
Pi's 3.3 V as wired below anyway: powering it from 5 V puts a 5 V logic level on
a 3.3 V GPIO pin.  At 3.3 V the bridge gives about 6.6 mV at full scale, which is
well inside the HX711's range — less signal, not a problem.

---

## Geometry

### Overhead camera
Mounted so the mat fills most of the frame with ~10 % margin. Fix the focus if the
camera allows it; autofocus hunting between frames changes the crop and therefore
the embedding.

### Second camera — at product height, not above
From overhead, a bottle is a cap. The label — the only part carrying identity — is
on the side and invisible. Mount the second camera at the front of the stand,
roughly at mid-product height, tilted slightly down, with its field of view
overlapping the mat.

**Not built yet.**  The design is to combine the two views by track id, so that an
item gets one identity and both cameras vote on it and one physical bottle
produces one cart line — which is why tracking had to exist first.  But no code
path reads a second camera today; `recognition/proposer.py:mask_above_mat`, the
privacy mask a side camera would need, is the only part that exists.

### Light ring
Above and slightly forward of the mat, diffused, angled to avoid throwing the
camera's own shadow. Set it once and never move it. All recognition assumes the
lighting at enrolment and the lighting at checkout are the same, and the software
cannot tell you when that stops being true — you have to not break it.

### Mat and markers
Matte, and black for preference: a shadow on a black mat barely registers, and
the proposer's shadow rule (`recognition/proposer.py`) has less to do. Glue the
four printed markers flat, one in each corner, in frame, where products will
not cover them. Measure a printed black square with a ruler and put the real
number in `config/settings.json` → `rig.marker_mm`; printers rescale, and "fit
to page" will silently make every size measurement wrong by a constant factor.
Then measure each marker's top-left black corner from the mat's top-left corner
and write the four positions into `rig.marker_positions_mm`
(`{"0": [20, 20], "1": [340, 20], ...}`). One 60 mm marker fits the pixel→mm
homography to four corners and extrapolates it across the mat; four corner
markers fit it to sixteen corners spanning the mat, which is what makes the
far corner measure true (docs/research/09, D12). With no positions set, the
till uses whichever single marker it sees.

---

## Wiring the load cell

```
load cell            HX711            Raspberry Pi 5 (BCM)
  red   (E+)  ──────  E+
  black (E-)  ──────  E-
  white (A-)  ──────  A-
  green (A+)  ──────  A+
                      VCC   ────────  3.3 V   (pin 1)
                      GND   ────────  GND     (pin 6)
                      DT    ────────  GPIO 5  (pin 29)
                      SCK   ────────  GPIO 6  (pin 31)
```

Pins are set in `config/settings.json` → `scale.dout_pin` / `scale.sck_pin`.
The reader is `HX711Scale` in `recognition/scale.py`: it clocks the 24-bit word
out over `lgpio`, which is the library that drives the Pi 5's RP1 GPIO
controller. (The PyPI `hx711` package needs `RPi.GPIO`, which does not work on
a Pi 5; that dependency is gone.) `pip install lgpio` on the Pi.

Mechanically: the cell bolts to the base at one end and to the weighing plate at
the other, with a gap so the plate rests **only** on the cell. If the plate touches
the frame anywhere else, part of the load bypasses the cell and readings become
nonsense that looks like drift.

### Calibrating

```bash
python tools/calibrate_scale.py --known-mass 500
```

Rehearse it first with `--dry-run`, which uses a simulated cell.

Use a mass you have checked on a shop scale — not what the packet claims. Redo the
calibration if the cell is remounted, the plate is changed, or readings drift.

Then verify with a *different* known mass. If it reads more than 2 g out,
calibrate again before trusting anything the weight check says.

### A verification scale, not a trade scale

The cell never sets a price. It answers one question — does the basket weigh what the
camera says it should? — and raises a flag when it does not. That is what keeps it
outside the Weights and Measures Act B.E. 2542, which requires verification of
non-automatic weighing instruments *used in trade* (docs/research/01, section 3). A
THB-300 bar cell with an HX711 would never pass class III verification, and does not
need to. The moment the till sells anything **by weight** — loose produce, bulk goods —
that changes: the scale becomes a trade instrument and must be a verified, class III
unit. Do not add sale-by-weight to this rig.

### Measuring drift

Cheap cells creep (about 0.02 % of full scale in ten minutes) and drift with
temperature (about 0.03 % of full scale per 10 °C) — on a 5 kg cell that is grams,
the same order as the tolerance the basket check works to. Measure it rather than
assume it, and put the number in the paper:

```bash
python tools/scale_drift.py --minutes 30 --known-mass 500      # after warm-up
python tools/scale_drift.py --minutes 240 --known-mass 500     # across a shift
```

Rehearse with `--dry-run`. Report the spread. If it exceeds `ITEM_SIGMA_G` in
`recognition/fusion.py`, say so. Between baskets the till re-zeroes the pan on
its own: `ScaleStream` reads the cell continuously, and whenever the pan is
settled within 5 g of empty it tares, so slow drift never carries into the next
basket (zero tracking).

### Filtering and settling
Handled in `recognition/scale.py`: an 8-sample moving average, and
`read_stable_grams()` which returns nothing at all unless the window has stopped
moving and there is something on the pan. The cell is read on its own thread
(`ScaleStream`, 10 Hz, the HX711's own rate), so the window is always full.

### One item at a time
The fusion wants the mass of *one* item; the pan reports everything on it. The
till only passes a mass to the fusion when exactly one item was placed since the
cart last changed - the difference between the pan now and the pan then. Put two
items down at once and the camera and the ruler decide alone; the basket check
at PAY still verifies the total. Keep the goods on the pan until PAY.

That last part is not a nicety. During development, feeding fusion a reading of
"about zero" from an empty pan made every product look far too heavy and dragged
the decision towards whichever enrolled product was lightest — a confidently wrong
answer. A reading that cannot be trusted is now reported as absent, never as zero.

---

## Thermals

The Pi 5 throttles under sustained load, and a benchmark taken cold reports a
speed the till will not hold through a lunchtime queue. Fit the active cooler.
`research/bench.py` records CPU temperature before and after; if they differ by
much, run it for longer and quote the sustained figure.

---

## Bringing it up on Raspberry Pi OS

Use **Raspberry Pi OS Trixie (64-bit)** or later. The PySide6 wheels for
aarch64 from 6.8 onwards are built against glibc 2.39; Bookworm ships 2.36 and
`pip install PySide6` fails there (`PySide6==6.7.3` or the apt package
`python3-pyside6.qtwidgets` are the Bookworm fallbacks). `onnxruntime` and
`opencv-contrib-python` ship aarch64 wheels that work on either.

```bash
sudo apt install python3-venv libxcb-cursor0     # xcb-cursor only matters under X11
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt                   # pulls lgpio on aarch64
python tools/export_embedder.py                   # or copy models/ from the laptop
python tools/make_marker.py                       # print at 100%, glue four down
python tools/calibrate_scale.py --known-mass 500  # after wiring
python app.py --scale hx711 --fullscreen          # the real till
```

Camera: a USB webcam is read through V4L2 (`/dev/video0`; set
`camera.default_source` to 0). `camera.fourcc: "MJPG"` is what lets a USB2 webcam
deliver 720p at full rate, and `camera.lock_exposure: true` pins exposure and
white balance once the ring light is on - a retrieval system must see the same
packet the same way at enrolment and at checkout. A CSI camera module is not
supported: it goes through libcamera, not V4L2.

To start at boot, install `deploy/ai-cashier.service` (instructions in the
file). To let the shopkeeper's phone open the dashboard, run with `--lan` and
set `dashboard_pin` in the shop settings first; every write from the network
needs it.

In the till: **Calibrate mat** with the mat empty, then **Add product** for each
line you stock.

## Checks before the demonstration

- [ ] Markers' printed squares measured with a ruler, `rig.marker_mm` set to it
- [ ] Four marker positions measured and written to `rig.marker_positions_mm`; status bar says *4 size marker(s) found*
- [ ] Scale reading visible in the enrol dialog with a product on the pan (proves the stream is running)
- [ ] Scale reads a second known mass within 2 g
- [ ] Weighing plate touches nothing but the load cell
- [ ] `python app.py --scale hx711` starts and the status bar says *mat calibrated*
- [ ] Every stocked product enrolled; status bar shows the count you expect
- [ ] An unenrolled product produces an amber **Unknown item**, not a wrong price
- [ ] `promptpay_id` set, and one real phone has scanned a real code
- [ ] `python research/bench.py` run on the Pi, warm, not on a laptop
