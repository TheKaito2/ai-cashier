"""The experiments behind the paper.

Each returns a plain dict, which run.py writes to results/ and report.py turns
into a table.  No number is ever typed into the paper by hand.

Naming follows the plan: E1 closed-set baseline, E2 few-shot accuracy against k,
E3 backbone against latency, E4 temporal voting, E5 open-set rejection,
E6 multimodal fusion and item-swap detection, E7 end-to-end basket error,
E8 the cost of adding a product.
"""

from __future__ import annotations

import time
from dataclasses import asdict

import numpy as np

from recognition.calibration import auroc, energy_score, fpr_at_tpr, msp_score, pick_threshold
from recognition.embedder import OnnxEmbedder, TorchEmbedder
from recognition.fusion import (FusionConfig, SkuPrior, Status, basket_tolerance_g,
                                fuse, verify_basket)
from recognition.gallery import PcaWhitening, SkuGallery
from recognition.proposer import BackgroundSubtractionProposer
from research.dataset import ROOT, Sku, Source, Split, make_split

# how many views enrol a product by default. 5 is what the till's dialog asks for.
DEFAULT_K = 5


# ------------------------------------------------------------------ machinery

def make_embedder(name: str):
    """ONNX for anything that ships, torch for the reference backbones."""
    onnx = ROOT / "models" / f"{name}.onnx"
    if onnx.exists():
        return OnnxEmbedder(onnx)
    return TorchEmbedder(name)


def crop_views(source: Source, sku_id: str, proposer) -> list[np.ndarray]:
    """The largest proposal in each frame - one product per photograph."""
    crops = []
    for frame in source.frames(sku_id):
        proposals = proposer.propose(frame)
        if proposals:
            crops.append(max(proposals, key=lambda p: p.area_px).crop(frame))
    return crops


def embed_all(source: Source, embedder, proposer) -> dict[str, np.ndarray]:
    """Every view of every product, embedded once and reused by every experiment."""
    out = {}
    for sku in source.skus():
        crops = crop_views(source, sku.sku_id, proposer)
        out[sku.sku_id] = embedder.embed(crops) if crops else np.zeros((0, embedder.dim), np.float32)
    return out


def build_gallery(vectors: dict[str, np.ndarray], skus: list[str], k: int, dim: int) -> SkuGallery:
    g = SkuGallery(dim)
    for sku in skus:
        if len(vectors[sku]) >= 1:
            g.enrol(sku, vectors[sku][:k])
    # the till pins the centre once enough products are enrolled; score the
    # same way, so a threshold from E5 means the same thing on the till
    if len(g.skus) >= 1:
        g.freeze_centre()
    return g


def fewshot_rows(vectors: dict[str, np.ndarray], skus: list[str], dim: int,
                 ks=(1, 3, 5, 10)) -> list[dict]:
    """Top-1 accuracy against k, scored two ways: the till's nearest-view rule
    and the mean-prototype rule from the few-shot literature (docs/research/09, D8)."""
    rows = []
    for k in ks:
        gallery = build_gallery(vectors, skus, k, dim)
        correct = correct_proto = total = 0
        for sku in skus:
            for i in probe_indices(vectors, sku, k):
                q = vectors[sku][i]
                matches = gallery.match(q)
                protos = gallery.match_prototypes(q)
                correct += bool(matches and matches[0].sku_id == sku)
                correct_proto += bool(protos and protos[0].sku_id == sku)
                total += 1
        rows.append({"k": k, "accuracy": correct / total if total else float("nan"),
                     "accuracy_prototype": correct_proto / total if total else float("nan"),
                     "n_probes": total, "n_skus": len(skus)})
    return rows


def probe_indices(vectors: dict[str, np.ndarray], sku: str, k: int) -> range:
    """Views held back from enrolment - the only ones an experiment may score on."""
    return range(k, len(vectors[sku]))


def priors_for(skus: list[Sku], sizes: dict[str, tuple[float, float]] | None = None) -> dict[str, SkuPrior]:
    sizes = sizes or {}
    return {s.sku_id: SkuPrior(s.sku_id, weight_g=s.weight_g, size_mm=sizes.get(s.sku_id))
            for s in skus}


# ------------------------------------------------------------------- E2 and E4

def e2_fewshot_vs_k(source: Source, embedder, proposer, split: Split,
                    ks=(1, 3, 5, 10)) -> dict:
    """How many views does a new product need before the till knows it?

    Scored only on `split.unseen` - products the representation never trained on,
    which is the only setting where the answer means anything.
    """
    vectors = embed_all(source, embedder, proposer)
    rows = fewshot_rows(vectors, split.unseen, embedder.dim, ks)
    return {"experiment": "E2", "backbone": getattr(embedder, "name", "?"),
            "source": source.name, "unseen_skus": split.unseen, "rows": rows}


def e4_temporal_voting(source: Source, embedder, proposer, split: Split,
                       k: int = DEFAULT_K, frame_counts=(1, 3, 5)) -> dict:
    """Does watching an item for a few frames beat trusting one frame?"""
    vectors = embed_all(source, embedder, proposer)
    gallery = build_gallery(vectors, split.unseen, k, embedder.dim)
    rng = np.random.default_rng(0)
    rows = []
    for n_frames in frame_counts:
        correct = total = 0
        for sku in split.unseen:
            probes = list(probe_indices(vectors, sku, k))
            if len(probes) < n_frames:
                continue
            for _ in range(20):                       # 20 simulated scans
                picked = rng.choice(probes, size=n_frames, replace=len(probes) < n_frames)
                votes: dict[str, int] = {}
                for i in picked:
                    m = gallery.match(vectors[sku][int(i)])
                    if m:
                        votes[m[0].sku_id] = votes.get(m[0].sku_id, 0) + 1
                winner = max(votes, key=votes.get) if votes else None
                correct += winner == sku
                total += 1
        rows.append({"frames": n_frames, "accuracy": correct / total if total else float("nan"),
                     "n_scans": total})
    return {"experiment": "E4", "source": source.name,
            "backbone": getattr(embedder, "name", "?"), "rows": rows}


# ------------------------------------------------------------------------- E3

def e3_backbones(source: Source, proposer, split: Split,
                 backbones=("mobilenet_v3_small", "mobilenet_v3_large", "resnet18"),
                 k: int = DEFAULT_K) -> dict:
    """Accuracy against milliseconds. The table that decides what ships.

    Each backbone gets two rows: mean-centred (what the till does) and PCA-
    whitened with the whitening fitted on `split.seen` - products the shop is
    not recognising - so the reference frame never moves with enrolment.
    """
    rows = []
    for name in backbones:
        try:
            embedder = make_embedder(name)
        except Exception as e:                        # a backbone may not download
            rows.append({"backbone": name, "error": str(e)[:120]})
            continue
        vectors = embed_all(source, embedder, proposer)
        accuracy = fewshot_rows(vectors, split.unseen, embedder.dim, (k,))[0]["accuracy"]
        seen = np.vstack([vectors[s] for s in split.seen if len(vectors[s])]) \
            if split.seen else np.zeros((0, embedder.dim), np.float32)
        if len(seen) >= 8:
            w = PcaWhitening.fit(seen, n_components=min(len(seen) - 1, embedder.dim))
            whitened = {s: w.transform(v) if len(v) else np.zeros((0, len(w.scale)), np.float32)
                        for s, v in vectors.items()}
            # the whitened space has as many dimensions as components were kept
            accuracy_whitened = fewshot_rows(whitened, split.unseen, len(w.scale), (k,))[0]["accuracy"]
        else:
            accuracy_whitened = float("nan")          # nothing to fit on
        sample = source.frames(split.unseen[0])[0]
        crop = max(proposer.propose(sample), key=lambda p: p.area_px).crop(sample)
        embedder.embed([crop])                        # warm up before timing
        t0 = time.perf_counter()
        for _ in range(20):
            embedder.embed([crop])
        rows.append({"backbone": name, "dim": embedder.dim,
                     "runtime": type(embedder).__name__.replace("Embedder", "").lower(),
                     "accuracy": accuracy, "accuracy_whitened": accuracy_whitened,
                     "n_whitening_fit": int(len(seen)),
                     "ms_per_crop": (time.perf_counter() - t0) / 20 * 1000})

    runtimes = {r.get("runtime") for r in rows if "runtime" in r}
    return {"experiment": "E3", "source": source.name, "k": k, "rows": rows,
            "comparable_timings": len(runtimes) == 1,
            "warning": (None if len(runtimes) == 1 else
                        "timings span more than one runtime (" + ", ".join(sorted(runtimes)) +
                        ") and are NOT comparable - export every backbone with "
                        "tools/export_embedder.py before quoting this table")}


# ------------------------------------------------------------------------- E5

def e5_open_set(source: Source, embedder, proposer, split: Split,
                k: int = DEFAULT_K) -> dict:
    """Can the till tell "I have never seen this" from "this is product X"?

    Enrol half the unseen products; the other half stand in for whatever a
    customer brings to the counter that the shop does not stock.
    """
    #: below this the AUROC is dominated by which handful of products landed on
    #: which side, and reporting it would be reporting noise
    MIN_ENROLLED, MIN_STRANGERS = 4, 3

    vectors = embed_all(source, embedder, proposer)
    half = max(1, len(split.unseen) // 2)
    enrolled, strangers = split.unseen[:half], split.unseen[half:]
    if len(enrolled) < MIN_ENROLLED or len(strangers) < MIN_STRANGERS:
        return {"experiment": "E5", "source": source.name,
                "insufficient_data": True,
                "enrolled": enrolled, "strangers": strangers,
                "error": (f"need at least {MIN_ENROLLED} enrolled and {MIN_STRANGERS} "
                          f"unenrolled products; this split has {len(enrolled)} and "
                          f"{len(strangers)}. Photograph more products.")}

    gallery = build_gallery(vectors, enrolled, k, embedder.dim)

    def sims(v):                                   # best cosine to every enrolled SKU
        return np.array([m.score for m in gallery.match(v, top_k=len(enrolled))])

    known_s = [sims(vectors[s][i]) for s in enrolled for i in probe_indices(vectors, s, k)]
    unknown_s = [sims(vectors[s][i]) for s in strangers for i in range(len(vectors[s]))]

    # three abstention rules over the same similarity vectors: the retrieval
    # statistic we ship, plus the two classifier baselines from the literature
    rules = {"max_cosine": lambda x: float(x.max()),
             "energy": energy_score,
             "msp": msp_score}
    scores = {}
    for name, fn in rules.items():
        known = np.array([fn(x) for x in known_s])
        unknown = np.array([fn(x) for x in unknown_s])
        r = pick_threshold(known, unknown)
        scores[name] = {"auroc": r.auroc, "fpr_at_95_tpr": r.fpr_at_95_tpr,
                        "threshold": r.threshold, "tpr": r.tpr, "fpr": r.fpr}

    report = scores["max_cosine"]
    return {"experiment": "E5", "source": source.name,
            "backbone": getattr(embedder, "name", "?"),
            "enrolled": enrolled, "strangers": strangers,
            # the shipped rule stays at top level so older report code still reads it
            "auroc": report["auroc"], "fpr_at_95_tpr": report["fpr_at_95_tpr"],
            "threshold": report["threshold"], "tpr": report["tpr"], "fpr": report["fpr"],
            "scores": scores,
            "n_known": len(known_s), "n_unknown": len(unknown_s)}


# ------------------------------------------------------------------------- E6

def e6_fusion(source: Source, embedder, proposer, split: Split,
              k: int = DEFAULT_K, weight_noise_g: float = 3.0) -> dict:
    """What each modality is worth, and how many item swaps get caught.

    Two halves.  Identification: appearance alone, then with mass, then with
    mass and size.  Security: swap one product for another after scanning and
    see whether the basket weight notices.
    """
    skus = {s.sku_id: s for s in source.skus()}
    vectors = embed_all(source, embedder, proposer)
    gallery = build_gallery(vectors, split.unseen, k, embedder.dim)

    # sizes are measured on the rig at enrolment; approximate them here from the
    # crop's pixel dimensions so the modality is exercised on synthetic data too
    sizes: dict[str, tuple[float, float]] = {}
    for sku in split.unseen:
        crops = crop_views(source, sku, proposer)[:k]
        dims = np.array([[max(c.shape[:2]), min(c.shape[:2])] for c in crops], float)
        sizes[sku] = tuple(np.median(dims, axis=0))
    priors = priors_for([skus[s] for s in split.unseen], sizes)

    rng = np.random.default_rng(0)
    modalities = {"appearance": (False, False), "+weight": (True, False),
                  "+weight+size": (True, True)}
    rows = []
    for label, (use_w, use_s) in modalities.items():
        correct = total = ambiguous = 0
        for sku in split.unseen:
            for i in probe_indices(vectors, sku, k):
                w = (skus[sku].weight_g + rng.normal(0, weight_noise_g)) if use_w else None
                s = sizes[sku] if use_s else None
                d = fuse(gallery.match(vectors[sku][i]), priors,
                         measured_weight_g=w, measured_size_mm=s,
                         cfg=FusionConfig(reject_below_cosine=-1.0))
                correct += d.sku_id == sku
                ambiguous += d.status is Status.AMBIGUOUS
                total += 1
        rows.append({"modalities": label, "accuracy": correct / total if total else float("nan"),
                     "ambiguous_rate": ambiguous / total if total else float("nan"),
                     "n_probes": total})

    # --- item swap: ring up A, put B on the pan ---------------------------
    swap_rows = []
    ids = split.unseen
    for k_sigma in (2.0, 3.0, 4.0, 5.0):
        caught = attempts = false_alarms = honest = 0
        for a in ids:
            for b in ids:
                if a == b or skus[b].weight_g is None or skus[a].weight_g is None:
                    continue
                measured = skus[b].weight_g + rng.normal(0, weight_noise_g)
                check = verify_basket(priors, {a: 1}, measured, k_sigma=k_sigma)
                if check is not None:
                    caught += not check.ok
                    attempts += 1
            honest_measure = skus[a].weight_g + rng.normal(0, weight_noise_g)
            honest_check = verify_basket(priors, {a: 1}, honest_measure, k_sigma=k_sigma)
            if honest_check is not None:
                false_alarms += not honest_check.ok
                honest += 1
        swap_rows.append({
            "k_sigma": k_sigma,
            "tolerance_1_item_g": basket_tolerance_g(1, k_sigma),
            "swaps_detected": caught / attempts if attempts else float("nan"),
            "false_alarm_rate": false_alarms / honest if honest else float("nan"),
            "n_swaps": attempts})

    return {"experiment": "E6", "source": source.name,
            "backbone": getattr(embedder, "name", "?"),
            "identification": rows, "item_swap": swap_rows}


# ------------------------------------------------------------------------- E7

def e7_basket_error(source: Source, embedder, proposer, split: Split,
                    k: int = DEFAULT_K, n_baskets: int = 200,
                    basket_size=(1, 5), use_weight: bool = True,
                    seed: int = 0) -> dict:
    """The number that matters to a shopkeeper: how much money does it get wrong?

    Builds random baskets from the unseen products, prices them the way the till
    would, and compares with the truth.  Reported as the share of baskets priced
    exactly right and the mean error in baht.
    """
    skus = {s.sku_id: s for s in source.skus()}
    vectors = embed_all(source, embedder, proposer)
    gallery = build_gallery(vectors, split.unseen, k, embedder.dim)
    priors = priors_for([skus[s] for s in split.unseen])
    rng = np.random.default_rng(seed)

    exact = 0
    errors = []
    for _ in range(n_baskets):
        n = int(rng.integers(basket_size[0], basket_size[1] + 1))
        chosen = [split.unseen[int(i)] for i in rng.integers(0, len(split.unseen), n)]
        true_total = sum(skus[s].price for s in chosen)

        rung = 0.0
        for sku in chosen:
            probes = list(probe_indices(vectors, sku, k))
            if not probes:
                continue
            v = vectors[sku][int(rng.choice(probes))]
            w = (skus[sku].weight_g + rng.normal(0, 3.0)) if use_weight else None
            d = fuse(gallery.match(v), priors, measured_weight_g=w,
                     cfg=FusionConfig(reject_below_cosine=-1.0))
            # an unrecognised item is not silently free: staff key it in, which
            # is slower but costs the right money
            rung += skus[d.sku_id].price if d.sku_id else skus[sku].price

        error = rung - true_total
        errors.append(error)
        exact += abs(error) < 0.005

    errors = np.array(errors)
    return {"experiment": "E7", "source": source.name,
            "backbone": getattr(embedder, "name", "?"),
            "n_baskets": n_baskets, "used_weight": use_weight,
            "exact_match_rate": exact / n_baskets,
            "mean_abs_error_baht": float(np.abs(errors).mean()),
            "max_abs_error_baht": float(np.abs(errors).max()),
            "mean_signed_error_baht": float(errors.mean())}


# ------------------------------------------------------------------------- E8

def e8_enrolment_cost(source: Source, embedder, proposer,
                      k: int = DEFAULT_K,
                      retrain_hours: float | None = None) -> dict:
    """How long does adding one product take, each way?

    The proposed cost is measured here.  The closed-set cost is not something
    that can be measured in a loop - it is photographing, labelling and training
    - so it is supplied by whoever did it, and the paper cites their figure
    rather than inventing one.
    """
    from recognition.pipeline import RecognitionPipeline
    sku = source.skus()[-1].sku_id
    frames = source.frames(sku)[:k]

    pipe = RecognitionPipeline(proposer, embedder, SkuGallery(embedder.dim))
    t0 = time.perf_counter()
    views = pipe.enrol(sku, frames, weight_g=10.0)
    compute_s = time.perf_counter() - t0

    # what the operator spends: placing, turning and photographing the product
    handling_s = 6.0 * k
    return {"experiment": "E8", "source": source.name,
            "backbone": getattr(embedder, "name", "?"), "k": k, "views": views,
            "compute_seconds": compute_s,
            "operator_seconds_estimate": handling_s,
            "total_seconds_estimate": compute_s + handling_s,
            "closed_set_retrain_hours": retrain_hours,
            "note": ("closed_set_retrain_hours must be supplied from the team's "
                     "own record of building the v1 model; it is not estimated here")}


# ------------------------------------------------------------------------- E9

def e9_public_benchmark(source: Source, embedder, split: Split, k: int = DEFAULT_K) -> dict:
    """The same few-shot and open-set measurements on a public dataset.

    A reviewer's first question is "why only your own photographs?".  Point
    `run.py --source folder --root <dir>` at RPC, GroceryVision or MIMEX laid
    out one folder per SKU and this reports E2 and E5 on it, with the whole
    image as the crop (there is no mat to subtract).
    """
    from recognition.proposer import WholeFrameProposer
    proposer = WholeFrameProposer()
    e2 = e2_fewshot_vs_k(source, embedder, proposer, split, ks=(1, 3, k))
    e5 = e5_open_set(source, embedder, proposer, split, k=k)
    return {"experiment": "E9", "source": source.name,
            "backbone": getattr(embedder, "name", "?"), "k": k,
            "n_skus": len(source.skus()), "fewshot": e2["rows"],
            "openset": {key: e5[key] for key in ("scores", "insufficient_data", "error")
                        if key in e5}}
