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
| Load cell | **single-point 5 kg**, aluminium bar | 150–300 | See below — not the 50 kg half-bridges |
| HX711 | 24-bit ADC breakout | 50–120 | Standard; `recognition/scale.py` bit-bangs it over `lgpio` (the Pi 5 GPIO library) |
| Ring light | 15–20 cm, diffused, ~5000 K, dimmable | 400–900 | The cheapest accuracy you can buy |
| Second webcam | 1080p, manual focus if possible | 500–1200 | Front view, for bottles and cans |
| Powered USB hub | 4-port, own supply | 300–600 | Two cameras exceed the Pi's per-port budget |
| Pi 5 active cooler | official or equivalent | 250–400 | **Required** — see thermals |
| PSU | 5 V / 5 A USB-C (official Pi 5 supply) | 500–800 | Under-powering a Pi 5 causes faults that look like software bugs |
| Mat | matte black or mid-grey, non-reflective, A3 | 100–250 | Gloss produces specular highlights that move with the product |
| Markers | four printed ArUco, laminated | ~20 | `python tools/make_marker.py` - one per mat corner |

**Why a 5 kg single-point cell, not 4 × 50 kg half-bridges.** The four-cell kit is
what most tutorials use because it comes from bathroom scales, but its full range
is 200 kg. Spread over a 24-bit ADC that is roughly 12 mg per count *in theory*
and far worse in practice once noise is included — and a 75 g crisp packet sits in
the bottom 0.04 % of the range, where the cell is least linear. A single 5 kg cell
puts the same packet at 1.5 % of range. Since the whole point of weighing is to
tell 75 g from 98 g, resolution at low mass is the only specification that matters.

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

The two views are combined by track id, not by hoping: an item gets one identity
and both cameras contribute votes to it, so one physical bottle produces one cart
line. That is why tracking had to exist before the second camera was worth adding.

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
