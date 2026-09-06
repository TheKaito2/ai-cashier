# The research harness

Eight experiments, one driver, one report generator, and a rule: **no number in
the paper is typed by hand.**  `research/run.py` writes JSON, `research/report.py`
turns JSON into LaTeX, and `paper/main.tex` only ever `\input`s the result.  If a
figure in the paper cannot be traced to a file in `research/results/`, it is a bug.

## The experiments

All defined in `research/experiments.py`, one function each, each returning a plain
dict.

| | Question | Function |
|---|---|---|
| E1 | How does a retrained closed-set detector compare? | **Does not exist.**  See below |
| E2 | How many reference views does a new product need? | `research/experiments.py:e2_fewshot_vs_k` |
| E3 | Which backbone, at what cost per crop? | `research/experiments.py:e3_backbones` |
| E4 | How many frames should vote on one decision? | `research/experiments.py:e4_temporal_voting` |
| E5 | Can it tell a product it has never seen from one it knows? | `research/experiments.py:e5_open_set` |
| E6 | What do mass and size add over appearance alone? | `research/experiments.py:e6_fusion` |
| E7 | What does a whole basket cost, in baht of error? | `research/experiments.py:e7_basket_error` |
| E8 | What does putting one new product on sale actually cost? | `research/experiments.py:e8_enrolment_cost` |
| E9 | Does any of this hold on somebody else's photographs? | `research/experiments.py:e9_public_benchmark` |

**E1 is a citation with no code behind it.**  It is named in the module docstring
of `research/experiments.py`, cited in `paper/main.tex`, referenced by
`research/PROTOCOL.md`, and used in `NOTICE` to justify keeping the AGPL YOLO
weights.  There is no `e1_*` function and no E1 result file.  Anyone writing the
closed-set comparison starts from zero.

## Where images come from

Three sources behind one interface, in `research/dataset.py`:

- `research/dataset.py:SyntheticSource` — rendered packets from `tests/synthetic.py`.
  Runs anywhere, proves the harness works, **is not evidence about real crisps**.
- `research/dataset.py:CaptureSource` — photographs taken on the rig by
  `research/capture.py`.  This is what the paper is meant to report.  **None exist yet.**
- `research/dataset.py:ImageFolderSource` — one folder per SKU of pre-cropped
  images; paired with `recognition/proposer.py:WholeFrameProposer` because there is
  no mat to subtract.

`research/dataset.py:make_split` divides products into seen and unseen and every
experiment scores only on the unseen half.  Evaluating few-shot enrolment on
products the representation was trained on would measure nothing, and
`research/PROTOCOL.md` names it as one of the two ways this work goes wrong.

## What has actually been measured

Eleven files in `research/results/`.  **E2 through E8 are all synthetic.**  Only
the three E9 files contain numbers from photographs somebody else took.

### E9 — Grocery Store dataset (Klasson et al., WACV 2019, MIT)

Phone photographs of groceries on shelves, laid out by
`research/prepare_grocerystore.py` into three symlinked views.  Frozen ImageNet
MobileNetV3-Small trunk, no fine-tuning.  Scored on the unseen half only.

| View | SKUs | k=1 | k=3 | k=5 | probes at k=5 |
|---|---|---|---|---|---|
| `grocerystore-packages` (cartons — closest to a till item) | 31 | 33.7 % | 47.7 % | **45.8 %** | 144 |
| `grocerystore-all` (all 81 fine classes) | 81 | 44.8 % | 61.8 % | **59.7 %** | 360 |
| `grocerystore-iconic` (the manufacturer's pack shot enrolled first) | 81 | **29.8 %** | 59.8 % | 62.8 % | 360 |

Open-set, max-cosine rule: AUROC **0.668** on packages, **0.365** on all 81,
**0.401** on iconic-first.  Energy scoring gives 0.688 on packages.  FPR at 95 %
TPR is 79 % on packages and 99 % on all — at that operating point the abstention
rule is barely better than a coin.

Three things this says, and they are the point of having run it:

1. **The encoder is the lever, not the number of views.**  Going from one view to
   five buys about twelve points; the ceiling is set by a trunk that was never
   shown a grocery shelf.  This is open item 33 in `docs/research/08-action-items.md`
   — rerun E9 with MobileCLIP-B or DINOv2.
2. **More views is not monotonic.**  On all 81 classes, nearest-view scoring peaks
   at k=3 (61.8 %) and dips at k=5 (59.7 %), while prototype-mean scoring keeps
   climbing to 65.0 %.  A fifth view of a shelf photograph adds as much noise as
   signal to nearest-view scoring.  Worth a sentence in the paper rather than a
   quiet omission.
3. **Zero-capture enrolment is not free but is not hopeless.**  Enrolling from the
   manufacturer's pack shot alone gives 29.8 %; adding four real photographs takes
   it to 62.8 %, past the all-real number.  That is the seed of Tier 2 question 3
   in `docs/research/07-research-roadmap.md`.

**The synthetic threshold does not transfer.**  E5 on synthetic data sits in the
`insufficient_data` state — the split yields one enrolled product and two
strangers, below the minimum the experiment needs.  τ stays a placeholder until a
real capture session runs.

### The rest

`research/results/E2.json`, `research/results/E3.json`, `research/results/E4.json`, `research/results/E6.json`, `research/results/E7.json`, `research/results/E8.json` — synthetic, and
every table they generate carries a machine-written warning saying so.
`research/results/E8.json` has `closed_set_retrain_hours: null`; the code refuses to invent it and
the team must supply it from its own record.  `research/results/bench-devlaptop.json` is per-stage
latency on an M1 and is explicitly **not** a Raspberry Pi number.

## Tables and figures

`research/report.py` writes ten `.tex` files into `paper/tables/` and three PDFs
into `paper/figures/`, each prefixed with a "generated, do not edit" banner and,
when the source is synthetic, a three-line warning block.
`paper/tables/e5_openset.tex` is currently a "NOT RUN" stub rather than a table.

`paper/main.tex` has **eleven `\todo{}` holes** left.  Five of the six numbers in
the abstract are among them, and one covers the entire prose of the Results
section — which is currently tables with no argument around them.  Every one of
those holes waits on the same thing: photographs of real products.

## The one thing blocking all of it

There are no captured images.  `research/capture.py` is written and tested,
`research/PROTOCOL.md` says exactly what to buy and how to photograph it, the
laptop and iPhone-Continuity path is documented in its section 2b, and
`research/capture.py:list_cameras` will show which cameras open.  On macOS the
camera grant is per-terminal, so the session has to be started from a terminal a
human has granted access — an agent's process is refused.

Once photographs exist the chain is:
`research/capture.py --verify` → `research/run.py --source captures` →
`research/report.py` → `tools/set_threshold.py`.
