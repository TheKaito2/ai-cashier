# Capture and experiment protocol

Everything the software needs is built and tested. Nothing in the paper is real
until this is done, because the version 1 training images were lost and the only
photographs that count are the ones taken on the rig that will be recognising.

---

## 0. Before you photograph anything

The rig must be finished and then **left alone**. Every measurement assumes the
camera, the mat and the light have not moved since the empty-mat photograph.
If any of them shifts, recalibrate and re-shoot — mixing before and after
silently poisons the whole dataset.

- [ ] Camera fixed, in focus, not on auto-exposure if that can be turned off
- [ ] Light ring on, room lights in whatever state they will be for the demo
- [ ] ArUco marker glued flat on the mat, fully in frame, not under products
- [ ] Load cell tared and calibrated (`python tools/calibrate_scale.py`)
- [ ] `python research/capture.py --mat` with the mat completely clear

## 0b. People and privacy

**No person may appear in any stored frame.** The capture session stores images;
the till never does (docs/PRIVACY.md). Before a capture session:

- clear the shop or the room of customers; only the team is present
- keep hands out of frame at the moment of capture, or delete the frame
- if a frame with a person, a reflection of a person, or a readable name or card
  in it is found at `--verify` time, delete it before building the dataset

Record with the session (in `research/data/manifest.json`, via `--rig-note`):
camera model, resolution, exposure/white-balance lock, light model and distance,
mat colour, marker size, date, and where the products were bought. Reviewers ask,
and the same fields make E3/E4 reproducible.

## 0c. Who rings up the baskets (E7)

Experiment E7 has real people put baskets through the till. Under ISEF rules
(docs/research/01, section 6) that is human-participants research as soon as anyone
outside the team does it, and needs ethics pre-approval and consent forms before
recruitment. Two options:

- **Team members only.** No approval needed. Say so in the paper: "baskets were
  assembled and scanned by the authors". This is the working assumption until the
  team decides otherwise.
- **Classmates or shoppers.** Obtain approval from a partner university's ethics
  committee first, use their consent form, and keep no identifying data.

Decide before the capture session, not after; the decision is recorded here.

## 1. What to buy

**At least 20 products, and ideally 30.** This is the single biggest thing that
decides whether the paper stands up. Below about ten products the open-set
experiment measures which handful landed on which side of the split, not the
method — the harness refuses to report it rather than print a number that reads
like a result.

Buy deliberately:

| How many | What | Why it is in the set |
|---|---|---|
| 12 | the products the version 1 detector knows | the only fair baseline for E1 |
| 8–15 | products it has never seen | the few-shot claim lives or dies here |
| ≥3 pairs | same brand, different flavour or size | the hard case — the honest limitation |
| ≥4 | similar mass, different appearance | where the scale is blind and the camera must carry |
| ≥4 | similar appearance, different mass | where the camera is blind and the scale must carry |

Those last two rows are what make the fusion table say something. Without them
every modality looks equally good and the paper has no argument.

## 2. Photographing

```bash
python research/capture.py --sku lays-nori-seaweed --name "Lay's Nori Seaweed" \
    --price 25 --weight 75 --category chips --views 14 --in-legacy-model
```

**14 views each.** Enrolment uses the first 5; the rest are the test set. A
product with no held-out views cannot be scored on at all.

Vary between shots, on purpose:
- rotate roughly 30–40° each time, and turn it over for at least two views
- move it around the mat, not just the middle
- for two or three views, put it where a real customer would drop it: at an
  angle, near the edge, slightly overlapping the marker

Do **not** vary the lighting. That is the one thing held constant.

`--weight` is what the scale reads with the product on the pan. Type the real
number, not the printed pack weight — a "75 g" packet is rarely 75 g, and the
gap between printed and actual is exactly what the weight check has to tolerate.

Then:

```bash
python research/capture.py --verify
```

It will say plainly what is missing. Do not move on until it says `ready`.

## 2b. Laptop rig (development captures)

The same tool runs on a laptop with its built-in camera, or with an iPhone as the
camera (macOS Continuity Camera: unlock the phone nearby and it appears as another
index in `capture.py --list`). Use it to photograph real products before the Pi rig
exists; label every product with `--rig-note macbook-facetime` or
`--rig-note iphone-continuity` so the manifest says which camera took it. There is no
load cell, so give `--weight` from a kitchen scale or leave it out, in which case E6
and E7 are skipped and `--verify` says so. The sequence is:

    python research/capture.py --list
    python research/capture.py --mat --camera 0
    python research/capture.py --sku lays-nori --name "Lay's Nori" --price 25 --weight 52 --rig-note macbook-facetime
    python research/capture.py --verify
    python research/run.py --source captures && python research/report.py
    python tools/set_threshold.py

The tables this produces are real photographs and can calibrate the threshold for a
laptop demo, but the paper's rig numbers still come from the Pi, its light and its mat.

## 3. The adversarial set

Separate from the product photographs, and quick — half an hour.

For each of ~20 attempts, record in `research/data/swaps.csv`:
`scanned_sku, actual_sku, measured_g`

Cover all three cases, because the interesting result is that they fail
differently:
1. cheap item swapped for an expensive one of clearly different mass
2. swapped for one of **almost the same mass** — the scale cannot see this
3. an extra item added to the bag after scanning

## 4. Running everything

```bash
python research/run.py --source captures --retrain-hours <your real figure>
python research/report.py
```

`--retrain-hours` is the number **you** must supply: the hours actually spent
photographing, labelling and training the version 1 model. Find it from your own
records. Do not estimate it — the whole enrolment-cost comparison rests on that
figure, and a made-up number is the fastest way to lose a judge.

## 5. What to check before writing any of it up

- [ ] `python research/run.py --source captures` ran without skipping an experiment
- [ ] E5 produced a number rather than `insufficient_data` (if not, buy more products)
- [ ] Every table in `paper/tables/` says `SOURCE = captures`, not `synthetic`
- [ ] `python research/bench.py` was run **on the Raspberry Pi**, not on a laptop
- [ ] The split in the results shows the products you meant to hold out
- [ ] Accuracy on the near-identical pairs is reported, not quietly averaged away

## 6. The two ways this goes wrong

**Evaluating on products the representation was trained on.** The claim is that
a *new* product can be enrolled from a handful of views. Measuring that on
products already in the training set measures nothing, and it is the first thing
a reviewer will look for. `make_split` in `research/dataset.py` enforces the
separation; do not work around it.

**Reporting synthetic numbers as results.** Every generated table carries a
warning header when it came from synthetic data. If you see that header in
something you are about to submit, the experiments have not been run yet.
