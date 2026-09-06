# Runbooks

Exact commands, and what success looks like.  All paths are relative to the
repository root, and every command assumes the virtual environment is active:

```bash
source .venv/bin/activate
```

## Tests

```bash
python -m pytest tests/ -q
```

CI runs the same thing on Ubuntu with Python 3.12 and `QT_QPA_PLATFORM=offscreen`,
after installing the Qt offscreen system libraries.  If a Qt test fails locally on
a headless machine, set that variable.

The iPhone suite needs Xcode and a booted simulator:

```bash
cd ios/AICashier && xcodegen generate && xcodebuild test -scheme AICashier -destination 'platform=iOS Simulator,name=iPhone 17 Pro'
```

## Run the till

```bash
python app.py                      # camera, simulated scale, windowed
python app.py --demo               # replay docs/assets/demo_frame.jpg, no camera needed
python app.py --fullscreen --scale hx711   # the Pi rig
python app.py --server-only        # dashboard only, no Qt
python app.py --lan                # bind to the network; writes need the PIN
python app.py --self-test          # headless; exits 0 if it finds the two demo products
```

The dashboard is on `http://localhost:8000`.

## Seed a demo shop

```bash
python tools/seed_demo.py
```

Creates a mat, a synthetic gallery and one deliberately un-enrolled product so the
Unknown path is demonstrable.  It also writes a `reject_below_cosine` — a demo
value, not a measured one.

## The capture session

Blocked on nothing but products and a granted camera.  Full protocol in
`research/PROTOCOL.md`; section 2b covers the laptop and iPhone-Continuity rig.

```bash
python research/capture.py --list                    # which cameras open, at what size
python research/capture.py --mat                     # photograph the empty mat first
python research/capture.py --sku lays-nori --name "Lay's Nori" --price 20 --weight 48 \
    --views 14 --rig-note "macbook-facetime, ring light, 2026-09-06"
python research/capture.py --import photos/          # pictures taken elsewhere
python research/capture.py --verify                  # is the dataset good enough yet?
```

`--verify` prints a per-product table and says plainly what is missing.  It wants
at least eight views each and at least ten products before the open-set experiment
reads as anything but noise.

**On macOS the camera permission belongs to the terminal, not to the script.**  Run
this from a terminal a human has granted camera access; an agent's process is
refused with "not authorized to capture video".

## Run the experiments

```bash
python research/run.py --source synthetic            # everything except E9
python research/run.py --source captures             # what the paper reports
python research/run.py --source folder --root research/data/public/grocerystore-packages --tag packages
python research/report.py                            # tables and figures
```

`--only E2 E5` restricts the run.  `--tag` names the output file so several folder
runs coexist.  Results land in `research/results/`, which is gitignored.

Rebuild the public benchmark from scratch:

```bash
git clone --depth 1 https://github.com/marcusklasson/GroceryStoreDataset research/data/public/GroceryStoreDataset
python research/prepare_grocerystore.py --dataset research/data/public/GroceryStoreDataset --out research/data/public
```

## Set the threshold

After a real E5 run, and only then:

```bash
python tools/set_threshold.py --dry-run     # print the report, change nothing
python tools/set_threshold.py               # write it where the till reads it
```

It refuses a result marked `insufficient_data`, and prints the matching Swift line
for `ios/AICashier/Sources/Recognition/Fusion.swift`.

## Build the paper

```bash
cd paper && make        # tectonic; runs BibTeX itself
```

`make tables` regenerates from the results first.  `\todo{}` holes render in red in
the PDF on purpose.

## Screenshots

```bash
python docs/tools/shoot_qt.py                        # the till, offscreen
SHOT_W=390 SHOT_H=844 python docs/tools/shoot_web.py  # the dashboard at a phone width
python docs/tools/make_demo_frame.py                 # regenerate the demo images
```

For the phone, boot a simulator and use `xcrun simctl io booted screenshot`, with
`--demo-seed`, `--demo-scan` and `--tab` as launch arguments.

## Cut a release

```bash
# bump VERSION first, then:
python -m pytest tests/ -q
git tag v4.2.1 && git push origin v4.2.1
gh run watch
curl -sIL https://github.com/TheKaito2/ai-cashier/releases/latest/download/AI-Cashier-Setup-Windows.exe | head -3
```

The tag triggers `.github/workflows/release.yml`, which builds on `windows-latest`,
runs `build/windows/smoke.ps1` against the frozen executable, and attaches the
installer plus a `.sha256`.  Longer version in `docs/DISTRIBUTION.md`.

## Deploy the landing page

```bash
cd site && npx wrangler deploy
```

Assets only.  The download button already points at `releases/latest/download/`, so
a release needs no page edit.

## Refresh the knowledge graph

```bash
graphify update .          # after code changes; local AST, no API key
graphify query "where is the rejection threshold read" --budget 2000
graphify affected "SkuGallery"
graphify god-nodes --top 20
```

`graphify-out/GRAPH_REPORT.md` records the commit the graph was built from; compare
it with `git rev-parse HEAD` to know whether it is stale.

## Check this knowledge base

```bash
python tools/check_kb.py
```

Asserts every path referenced in `docs/kb/` and `CLAUDE.md` exists, and that every
named symbol still appears in its file.  `tests/test_kb_links.py` runs it in CI.
