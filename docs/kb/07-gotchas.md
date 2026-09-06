# Gotchas

Every one of these cost real time at least once.  Symptom first, because that is
what you will have when you arrive here.

## Recognition

**Everything comes back Unknown and the box is the size of the frame.**
The proposer was calibrated against the wrong background.  `BackgroundSubtractionProposer`
subtracts the mat it was shown; give it a different scene and the whole frame is
foreground.  Calibrate on the mat you are actually going to use — the screenshot
harness calibrates on `docs/assets/demo_mat.png` for exactly this reason.

**Scores collapse after a change to the gallery.**
Check that `recognition/gallery.py:project` still normalises the query *before*
subtracting the centre.  See fault F5 in `docs/research/09-architecture-review.md`.
Any change here invalidates τ and needs the Swift fixtures regenerated.

**The till refuses things it clearly knows, or accepts things it has never seen.**
τ is wrong for this rig.  It is not a constant to tune by feel — run E5 and
`tools/set_threshold.py`.  The shipped `0.75` is a placeholder.

**A proposal silently vanishes between frames.**
`recognition/pipeline.py` matches proposals to tracks by exact equality on the box
tuple.  Nothing pins this behaviour in a test, so a change to how the tracker
stores boxes can drop proposals without any error.

## The Qt till

**The readout rail overlaps the camera view.**
A `QLabel` holding a pixmap refuses to shrink below the pixmap's size, so it pushes
its neighbours off-screen.  The viewfinder needs `QSizePolicy.Ignored`.

**Fonts look wrong and no error appears.**
`QFontDatabase.addApplicationFont` returns `-1` and Qt silently falls back.
`scanner/ui/theme.py:load_fonts` warns, and `docs/tools/shoot_qt.py` asserts the
family is present so a fallback render fails loudly instead of shipping a
screenshot in the wrong typeface.

**The screenshot harness produces an empty cart or an all-Unknown till.**
It needs its own throwaway `AI_CASHIER_DATA`, a seeded first run, a mat calibrated
on the demo image, and demo products actually enrolled.  Pointing it at the real
database is both wrong and destructive.

**A Thai product name breaks the receipt's column alignment.**
Plex Mono has no Thai glyphs, so Thai text in a monospace block falls back to Plex
Sans Thai, which is proportional.  `server/services/receipt.py` truncates by
character count, not by rendered width.  Known, unfixed.

## The dashboard

**A chart renders as nothing and no console error appears.**
Do not build SVG with `createElementNS('http://www.w3.org/2000/svg', …)`.
`tests/test_pages.py` refuses any `http(s)://` string in `server/static/`, because
the shop counter may have no internet.  `server/static/js/charts.js` assembles SVG
as an HTML string on purpose.

**A page 404s a stylesheet or a font after a rename.**
`tests/test_pages.py` walks every `href`/`src` on every page and every `url()` in
the stylesheet.  Run the suite before assuming the browser is at fault.

## iOS

**A font fails to register even though the file is in the bundle.**
IBM abbreviates PostScript names: `IBMPlexSansThai`, `-Medm`, `-SmBld`, `-Bold`,
`IBMPlexMono`, `-Medm`, `-SmBld` — not the full words.  Read the `name` table
rather than guessing.  `ios/AICashier/Tests/FontsTests.swift` fails if any of the
seven stops resolving.

**A launch flag does nothing, or a resource is missing at runtime.**
There is no checked-in Xcode project; `xcodegen generate` builds it from
`ios/AICashier/project.yml`.  Resources copied in after generation are not in the
bundle.  Regenerate, then build.

**The app sticks on the launch screen, or a scan never finishes.**
Something is starving the main thread with SwiftUI layout.  The demo camera
publishing a fresh `CGImage` ten times a second did exactly this; so did putting
`Date.now` in a receipt header, and a shadow applied without `.compositingGroup()`.
Sample the process and look at the main thread before assuming the recognition
code is slow.

**Debug builds are unusable.**
The pure-Swift proposer takes roughly eighteen seconds per frame without
optimisation.  `ios/AICashier/project.yml` sets `-O` and whole-module compilation
for this reason; do not "simplify" it away.

## Exporting an encoder

**An exported model returns plausible-looking vectors that match nothing.**
Check the normalisation.  Preprocessing happens outside the graph, so a frozen
encoder has to carry the mean and standard deviation it was trained with, and
until September 2026 `OnnxEmbedder` assumed ImageNet for everything.  MobileCLIP
uses mean 0 and standard deviation 1, so its first export scored a cosine of
0.19 against the torch model it came from.  Nothing errored.  Graphs now stamp
their own statistics, and `tools/export_embedder.py` prints the agreement
cosine — if that number is not ~1.0, stop and read it rather than concluding the
encoder is weak.

**A CLIP variant scores worse than it should.**  Check the input resolution.
MobileCLIP-S1/S2 and the MobileCLIP2 family are trained at 256 px, not 224.
Both the width and the resolution are now read from open_clip's own model config
rather than a hand-written table, because those are two more numbers that drift.

**`torch.export` fails on an encoder.**  Some models simply do not freeze —
DINOv2-S/14 is one.  `tools/export_embedder.py` reports it and exits non-zero
instead of writing a broken graph, and `research/bench.py` falls back to torch
while recording which runtime it timed.  A model that cannot be exported cannot
ship, whatever it scores.

## Research and the paper

**`make` in `paper/` fails on a generated table.**
LaTeX specials in the data — an underscore in `mobilenet_v3_small`, a percent
sign, an ampersand.  `research/report.py` escapes them; if you add a new table
writer, escape there rather than in the `.tex`.

**`make` reports success but the PDF is unchanged.**
The `paper/Makefile` target depends on `paper/main.tex`, `paper/refs.bib`, the tables and the
figures.  Touch a dependency or clean.

**A result file appears with the wrong numbers in it.**
Every result carries `environment` and `split`.  Check the `source` field before
believing anything: `synthetic` is not evidence about real products, and
`research/results/bench-devlaptop.json` is not a Raspberry Pi measurement.

## The machine

**`capture.py --list` reports no camera.**
On macOS the camera grant is per-terminal, and an agent's process does not have
it.  Run it from a terminal the user has granted access to; the operating system
asks once.

**`timeout` is not found.**
macOS ships no GNU `timeout`.  Use the tool's own timeout, or `gtimeout` from
coreutils.

**A shell command runs in the wrong directory.**
The working directory resets between calls in this harness.  Put the `cd` in every
command.

**`git status` is dirty on a clean checkout.**
`ios/AICashier/build/` is Xcode's SwiftPM checkout directory.  It is gitignored now;
if it reappears, that is why.

## The repository

**A screenshot in `docs/shots/aug10`…`aug28` looks out of date.**
It is.  Those are the figures in eight submitted school reports and are a record,
not a current artefact.  Regenerate `docs/shots/v4*` and `docs/shots/ios` instead.

**Something references `models/*.pt`.**
Those are AGPL YOLOv8 weights, quarantined in `NOTICE`, gitignored, and used only
as a research baseline.  `tests/test_no_ultralytics.py` blocks the import at test
time so they can never reach the till.
