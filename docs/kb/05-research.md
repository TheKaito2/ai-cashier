# The research harness

Nine experiments, one driver, one report generator, and a rule: **no number in
the paper is typed by hand.**  `research/run.py` writes JSON, `research/report.py`
turns JSON into LaTeX, and `paper/main.tex` only ever `\input`s the result.  If a
figure in the paper cannot be traced to a file in `research/results/`, it is a bug.

## The experiments

All defined in `research/experiments.py`, one function each, each returning a plain
dict.

| | Question | Function |
|---|---|---|
| E1 | How does the version 1 closed-set detector compare? | `research/experiments.py:e1_closed_set_baseline` |
| E2 | How many reference views does a new product need? | `research/experiments.py:e2_fewshot_vs_k` |
| E3 | Which backbone, at what cost per crop? | `research/experiments.py:e3_backbones` |
| E4 | How many frames should vote on one decision? | `research/experiments.py:e4_temporal_voting` |
| E5 | Can it tell a product it has never seen from one it knows? | `research/experiments.py:e5_open_set` |
| E6 | What do mass and size add over appearance alone? | `research/experiments.py:e6_fusion` |
| E7 | What does a whole basket cost, in baht of error? | `research/experiments.py:e7_basket_error` |
| E8 | What does putting one new product on sale actually cost? | `research/experiments.py:e8_enrolment_cost` |
| E9 | Does any of this hold on somebody else's photographs? | `research/experiments.py:e9_public_benchmark` |

### E1, and why its numbers will not flatter us

E1 was a citation with no code behind it until 6 September 2026 — named in four
places, implemented in none, and used in `NOTICE` to justify keeping the AGPL
YOLO weights.  It now exists, and three of its choices are deliberate.

**It scores every legacy product, not only `split.unseen`.**  The version 1
detector was trained on all twelve classes; no half of them is held out from it,
and taking only the unseen half would halve the sample without buying any
honesty.  `n_legacy_in_unseen` in the result records the overlap so a reader can
see it.  It is the only experiment that scores on products from the seen half, and
`research/experiments.py:e1_closed_set_baseline` says why in its docstring.

**Both systems answer over the same labels, on the same probe views** — the ones
after the first `k`, held out from the proposed system's enrolment but not from
anything the detector ever saw.  That is the setting most favourable to the
baseline, on purpose.

**The closed-set row is expected to win on accuracy.**  That is the result the
paper wants: the detector is better on the twelve products it was trained on and
cannot name a thirteenth at all.  The argument is the `catalogue_coverage`
column, and `paper/tables/e8_enrolment.tex` is what changing that costs.

The twelve classes are `Lay's-Flat-Original-Flavor`, `Lay's-Nori-Seaweed-Flavor`,
`Lay's-Ridged-Original-Flavor`, `Snackjack-Original-Flavor`,
`Tasto-Japanese-Seaweed-Flavor`, `Tasto-Original-Flavor`, `CocaCola-Bottle`,
`CocaCola-Can`, `Crystal-Water`, `Fanta-FruitPunch-Flavor`, `Pepsi` and `Sprite`.
Six live in `models/chips_model.pt` and six in `models/drinks_model.pt`, each
numbered 0–5, so the union has to be taken **by name** — merging the index maps
silently drops one model's six.  The class-to-`sku_id` mapping is the legacy
`yolo_class` column in `data/products.json`, which is the only record of it.

**E1 does not run in a fresh checkout, and says so.**  The weights are AGPL and
gitignored, ultralytics is not in `requirements.txt`, and there are no captured
photographs of the twelve products, so E1 returns `insufficient_data` with the
reason and `research/report.py:table_e1` writes a "NOT RUN" stub instead of a
table.  On synthetic data it runs end to end — the four rendered packets whose
sku_ids the detector knows — but the detector was trained on photographs and is
being shown renders, so it recognises almost nothing.  That error flatters us,
which is why the generated caption says in bold that it measures the renderer.

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

Twelve files in `research/results/`.  **E1 through E8 are all synthetic.**  Only
the three E9 files contain numbers from photographs somebody else took.

### E9 — Grocery Store dataset (Klasson et al., WACV 2019, MIT)

Phone photographs of groceries on shelves, laid out by
`research/prepare_grocerystore.py` into three symlinked views.  No fine-tuning:
every encoder is frozen and the products are enrolled from k views like any
other.  Scored on the unseen half only.  Numbers below are read off
`paper/tables/e9_public.tex`; the table is the authority.

**Identification, top-1 %, nearest-view scoring:**

| View | SKUs | Encoder | k=1 | k=3 | k=5 |
|---|---|---|---|---|---|
| packages (cartons) | 16 | mobilenet_v3_small | 33.7 | 47.7 | 45.8 |
| packages | 16 | dinov2_vits14 | 43.3 | 53.4 | 45.8 |
| packages | 16 | **mobileclip_b** | **75.0** | 88.6 | **89.6** |
| all 81 classes | 40 | mobilenet_v3_small | 44.8 | 61.8 | 59.7 |
| all 81 | 40 | dinov2_vits14 | 62.7 | 75.0 | 73.3 |
| all 81 | 40 | **mobileclip_b** | **72.1** | 83.9 | 81.4 |
| iconic-first | 40 | mobilenet_v3_small | 29.8 | 59.8 | 62.8 |
| iconic-first | 40 | dinov2_vits14 | 54.0 | 72.5 | 74.2 |
| iconic-first | 40 | **mobileclip_b** | **82.9** | 83.2 | 81.7 |

**Abstention, max-cosine rule:**

| View | Encoder | AUROC | FPR at 95 % TPR |
|---|---|---|---|
| packages | mobilenet_v3_small | 0.668 | 0.795 |
| packages | dinov2_vits14 | 0.770 | 0.679 |
| packages | **mobileclip_b** | **0.985** | **0.080** |
| all 81 | mobilenet_v3_small | 0.365 | 0.986 |
| all 81 | dinov2_vits14 | 0.662 | 0.811 |
| all 81 | **mobileclip_b** | 0.837 | 0.621 |
| iconic-first | mobilenet_v3_small | 0.401 | 0.975 |
| iconic-first | dinov2_vits14 | 0.727 | 0.732 |
| iconic-first | **mobileclip_b** | 0.842 | 0.596 |

Five things this says, and they are why the experiment was worth running:

1. **The encoder is the lever, and now there is a number for it.**  Swapping the
   frozen ImageNet trunk for MobileCLIP-B roughly doubles top-1 on cartons —
   45.8 % to 89.6 % — without changing a line of the matching code.  Nothing
   about k, the tracker or the fusion moves accuracy anywhere near that far.
   This was open item 33 and it is now closed.
2. **The abstention rule is where the swap actually matters.**  On cartons the
   proportion of unknown products wrongly accepted at 95 % true-positive rate
   falls from 79 % to **8 %** — a tenfold reduction in the failure that takes the
   wrong money.  Identification accuracy is the headline; this is the number the
   till's safety claim rests on.
3. **Identifying well and knowing what you do not know are separable.**  DINOv2-S
   scores exactly the same top-1 as MobileNetV3 on cartons at k=5 (45.8 %) while
   being clearly better at abstention (AUROC 0.770 against 0.668).  A
   representation can be no better at naming things and still much better at
   admitting it has not seen one.  Worth a sentence in the paper: the
   retail-checkout literature tends to report only the first.
4. **More views is not monotonic.**  Nearest-view scoring peaks at k=3 and dips
   at k=5 on several rows, while prototype-mean scoring keeps climbing.  A fifth
   shelf photograph adds as much noise as signal to nearest-view scoring.
5. **Zero-capture enrolment works, given the right encoder — and this is the
   largest result here.**  Enrolling a product from the manufacturer's pack shot
   and nothing else gives **82.9 %** top-1 with MobileCLIP-B.  Three things about
   that number.  It beats the same encoder enrolled from *one real shelf
   photograph* (72.1 %), because a clean canonical product image is a better
   single reference than one arbitrary photograph of a shelf.  It essentially
   matches the same encoder given **five** real photographs (81.7 %), so four
   further captures buy nothing once the pack shot is there.  And on the old
   ImageNet trunk the same setup gives 29.8 %, which is useless — so this is not
   a property of the method, it is a property of the encoder.

   If it holds on the rig, a shop enrols a product from the manufacturer's web
   image with no photography at all.  That is Tier 2 question 3 in
   `docs/research/07-research-roadmap.md`, answered on a public benchmark, and it
   is a stronger claim than the encoder swap that produced it.

### E3 — what it costs to be that accurate

The E9 rows above say the encoder is the lever.  E3 puts a price on it: the same
matching code and the same split over five encoders, **every one under ONNX
Runtime**, so the milliseconds are comparable — `comparable_timings` is true in
`research/results/E3.json` and the harness refuses to claim it otherwise.
Measured on an M1 laptop, on the public cartons.

| Encoder | dim | top-1 % | whitened % | ms/crop |
|---|---|---|---|---|
| mobilenet_v3_small (ships today) | 576 | 45.8 | 41.7 | **7.9** |
| mobileclip2_s0 | 512 | 79.9 | 76.4 | 203 |
| mobileclip_s1 | 512 | **85.4** | 78.5 | 292 |
| mobileclip_s2 | 512 | 83.3 | 83.3 | 281 |
| mobileclip_b | 512 | **89.6** | 84.7 | 584 |

Three things follow.

**The accuracy is not free: it is 26 to 74 times the cost.**  The cheapest CLIP
encoder is 203 ms against 7.9 ms.  On an M1.  A Pi 5 is several times slower
again, so whether any of this is affordable at the till is a measurement nobody
has made — ledger item 40, and it needs the hardware rather than more thinking.

**S1 dominates S2.**  More accurate and slightly cheaper, so S2 is off the table
whatever the budget.  Worth stating because the naming implies otherwise.

**MobileCLIP2-S0 is the interesting row.**  It gives up four points to S1 for a
third off the cost, and it is the smallest thing here that beats the shipped
encoder by thirty-four points.  If the Pi can afford anything, it is this.

**DINOv2-S/14 cannot be exported at all.**  `torch.export` fails on it, so it has
no ONNX row above and could not ship even if it scored well — which it does not
(45.8 %, the same as the trunk it would replace).  That is a deployability fact
worth one line in the paper: a representation that cannot be frozen is not a
candidate, however it benchmarks.

**A trap this uncovered.**  Preprocessing happens outside the graph, and the
first CLIP export scored a cosine of **0.19** against the torch model it came
from — because `OnnxEmbedder` normalised everything with ImageNet statistics and
MobileCLIP uses mean 0, standard deviation 1.  It still returned 512 numbers,
just meaningless ones, and it reads as "this encoder is bad" rather than "we fed
it wrongly".  Exported graphs now carry their own statistics
(`recognition/embedder.py:export_onnx`), after which every MobileCLIP variant
agrees at cosine 1.00000.  See `docs/kb/07-gotchas.md`.

**What this does not say.**  These are shelf photographs under supermarket
lighting, not mat crops under a ring light.  And every millisecond above was
measured on an M1: the Pi 5 numbers, which are the ones that decide what ships,
still need the hardware.  `research/bench.py` answers that and needs no products.

**The synthetic threshold does not transfer.**  E5 on synthetic data sits in the
`insufficient_data` state — the split yields one enrolled product and two
strangers, below the minimum the experiment needs.  τ stays a placeholder until a
real capture session runs.

### The rest

`research/results/E1.json`, `research/results/E2.json`, `research/results/E3.json`, `research/results/E4.json`, `research/results/E6.json`, `research/results/E7.json`, `research/results/E8.json` — synthetic, and
every table they generate carries a machine-written warning saying so.
`research/results/E8.json` has `closed_set_retrain_hours: null`; the code refuses to invent it and
the team must supply it from its own record.  `research/results/bench-devlaptop.json` is per-stage
latency on an M1 and is explicitly **not** a Raspberry Pi number.

## Tables and figures

`research/report.py` writes eleven `.tex` files into `paper/tables/` and three PDFs
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
