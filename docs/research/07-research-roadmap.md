# 07 — Research roadmap: from competition entry to master's to PhD

The same rig, the same codebase, three tiers of question. Each tier names the sub-field, the papers that define it (05), the data to start accumulating now, and the paper it could become.

## Tier 1 — the competition paper (what v4 already claims)

**Question.** On sub-USD-300 hardware, how much accuracy does a retrieval-based checkout give up against a retrained closed-set detector, and what does it gain in enrolment cost and unknown-item safety?

**Experiments.** E1–E8 in `research/experiments.py`, plus two additions from this dossier:
- E5b: energy score [P33] as a second open-set baseline next to MSP.
- E9: **public benchmark** — GroceryVision MPR [V11, P27] and/or RPC with held-out SKUs [P01]. One table row that is not from our own mat.

**Data to collect now.** 20+ products, 5 views each, under the ring light, with barcode ground truth; every basket photographed with its scale reading. Keep raw frames (no people) with capture metadata. This is the seed of every later tier.

**Output.** ECTI-CON/JCSSE paper + arXiv; YSC/TICTA entry.

## Tier 2 — master's-scale questions (one to two years, one lab)

1. **Continual enrolment without forgetting.** Today enrolment appends gallery rows to a frozen embedder. What happens after 500 SKUs, seasonal packaging changes, and re-enrolments? Sub-field: continual learning [P40 Wang 2024], open-world detection [P35]. Experiment: replay the capture log over simulated months; measure accuracy drift and gallery growth; compare frozen gallery vs periodic embedder fine-tuning with SupCon [P18] vs prototype refresh. *Paper:* "Lifelong SKU enrolment at the edge".
2. **Fusion calibration per store.** The weight and size Gaussians in `fusion.py` have fixed sigmas. Real cells drift [H06] and real stores have different product mixes. Learn the fusion weights and sigmas from the store's own barcode-verified transactions (the NVIDIA active-learning loop [H09], but for the fusion, not the embedding). *Paper:* "Self-calibrating multimodal verification for self-checkout".
3. **Synthetic-to-real enrolment.** AI City Track 4 trained on rendered products [P09]. Can a SKU be enrolled from a *rendered* pack shot (or the manufacturer's e-commerce photo, as in the Grocery Store dataset [P04]) instead of five live captures? Domain randomisation [P40 Tobin]. *Paper:* "Zero-capture enrolment".
4. **Small VLM encoders on ARM.** The May 2026 result [P27] says data quality beats scale and MobileCLIP-B is strong. Benchmark MobileCLIP / SigLIP-small / DINOv3-distilled on the Pi with static INT8 [P40 Gholami]; report accuracy-per-millisecond. Cheap, publishable, and directly improves the product.
5. **Loss-prevention HCI.** ECR says half of loss is accidental [M20]; Everseen says a 300 ms nudge fixes it [H04]. Run a user study (with ethics approval, 01 §6) on nudge wording and timing at the till. Sub-field: HCI/criminology of self-checkout [P37].

## Tier 3 — PhD-scale questions (three to five years)

1. **Open-world recognition under distribution shift in the wild.** Open-set recognition [P29, P34] assumes a fixed test distribution; a shop's is not. Formalise "enrol, drift, re-enrol" as an online open-world problem with a cost for each abstention, each wrong charge, and each enrolment. Theory + a multi-store dataset collected from Tier 1–2 deployments.
2. **Privacy-preserving edge vision.** The retrieval design never stores a frame. Push that to a formal guarantee: embeddings that are provably non-invertible to identity, on-device only, with a PDPA-shaped threat model. Sub-field: privacy in CV; relevant as PDPC guidance tightens [L02].
3. **The economics of human-in-the-loop labelling.** Enrolment cost, staff interventions, and shrink are all measurable in baht per transaction. A PhD could build the first cost model of *when* a store should teach its system versus tolerate an abstention, using real deployment logs. Sub-field: decision-theoretic ML / operations research.
4. **Multi-camera, multi-modal fusion at scale.** The CVPR 2026 checkout-free tutorial [V12] frames retail as a canonical multi-camera systems problem. The two-camera mat is the smallest instance of it; a PhD scales it to the shelf and the cart.

## Groups and venues that publish in these areas (to read, then to write to)

Visual Geometry Group Oxford (Vaze/Zisserman, open-set); Meta FAIR (DINO); Google DeepMind Zürich (SigLIP); University of Trento MHUG (Tur/Beyan, MIMEX); University of Bologna CVLab (Tonioni/Di Stefano, retail embeddings); Nanjing University (Wei, RPC); University of Leicester (Hopkins/Beck, retail loss); Carnegie Mellon (Falcão/Pan, FAIM). Thai groups active in CV/embedded AI: NECTEC, KMUTT, Chulalongkorn, VISTEC, CMU (recalled; verify current people before contacting). Venues: PRAW (retail), CVPR/ICCV/ECCV workshops, WACV, IEEE TPAMI (open-set), Frontiers/IEEE Access for applied fusion, ECTI-CIT for the journal extension.

## What to keep from now on so the later tiers have data

- Every capture with metadata (camera, light, mat, date, product batch, scale reading, barcode).
- Every enrolment event with timestamp and view count.
- Every abstention and every staff override, with the eventual correct SKU.
- Every basket's predicted vs scanned contents.

Four log tables. They cost nothing today and are the dataset for tiers 2 and 3.
