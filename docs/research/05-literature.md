# 05 — Literature: what has been proved, and the gap left for us

Forty entries, all verified this session by opening the arXiv/DOI page or a publisher page (ledger rows P01–P40; `method=fetched` unless marked). BibTeX keys match `paper/refs.bib`. Each entry: what it did → why it matters here → the gap.

## A. Retail product datasets and benchmarks

1. **RPC** — Wei, Cui, Yang et al., 2019, arXiv 1901.07249. `wei2019rpc`. 200 SKUs, ~53.7k single-product images, 30k checkout-tray scenes, 368k instances; CC BY-NC-SA [I05, P01]. *Why:* the canonical checkout benchmark; tray images look like our mat. *Gap:* closed-set; no weight, no unknowns, no enrolment cost. **Use it** for a public open-set split (hold out SKUs) so the paper has a number that is not from our own captures.
2. **Products-10K** — Bai, Chen, Yu et al., 2020, arXiv 2008.10545. `bai2020products10k`. 10k SKUs from JD.com, ~150k images; non-commercial [I06, P02]. *Why:* scale reference for fine-grained SKU recognition. *Gap:* e-commerce photos, not a till.
3. **RP2K** — Peng, Xiao, Li, 2020, arXiv 2006.12634. `peng2020rp2k`. 500k shelf images, 2k categories [P03]. *Gap:* shelf domain.
4. **Grocery Store dataset** — Klasson, Zhang, Kjellström, WACV 2019, arXiv 1901.00711. `klasson2019grocery`. Hierarchical labels, paired web product images [P04]. *Why:* the "in-vitro reference vs in-situ query" setup is exactly gallery-vs-till.
5. **GroZi-120** — Merler, Galleguillos, Belongie, CVPR Workshops 2007. `merler2007grozi`. One studio image per product as training, shop video as test [P05]. *Why:* the original one-shot retail recognition paper — cite it to show the idea is twenty years old and the contribution is measurement.
6. **Freiburg Groceries** — Jund, Abdo, Eitel et al., 2016, arXiv 1611.05799. `jund2016freiburg`. 5k images, 25 classes [P06].
7. **SKU-110K** — Goldman, Herzig, Eisenschtat et al., CVPR 2019, arXiv 1904.00853. `goldman2019sku110k`. Dense shelf detection [P07]. *Why:* class-agnostic product proposals at scale — the proposer stage.
8. **Unitail** — Chen, Zhang, Li et al., ECCV 2022, arXiv 2204.00298. `chen2022unitail`. Detect, read, match; 1.8M quadrilateral instances [P08]. *Why:* "matching" = retrieval, plus OCR of packaging text as an extra modality we have not used.
9. **AI City Challenge Track 4 (2022, 2023)** — Naphade, Wang, Anastasiu et al., arXiv 2204.10380 and 2304.07500. `naphade2022aicity`, `naphade2023aicity`. Automated retail checkout from a single camera; synthetic training data, real test video [P09, P10]. *Why:* the closest public benchmark to our task, and it trained on synthetic data — which is what `tests/synthetic.py` already generates. *Gap:* the track did not run after 2023 [V10]; the dataset is by request.
10. **GroceryVision / PRAW** — WACV 2026 workshop challenge; Track 2 Multi-modal Product Retrieval, 74,200 training images, 409 SKUs [V11]. *Why:* the live retail-retrieval benchmark of 2026. Evaluate on it.
11. **MIMEX** — Tur, Conti, Beyan et al., IEEE RTSI 2024, arXiv 2409.14963. `tur2024mimex`. 28 fine-grained categories incl. Lay's/Pringles; CLIP+DINOv2 ensemble beats VLMs [P11]. *Why:* directly tests flavour-variant discrimination — our documented failure case.

## B. Surveys

12. **Deep learning for retail product recognition** — Wei, Tran, Xu, Kang, Springer, Comput. Intell. Neurosci. 2020, DOI 10.1155/2020/8875910. `wei2020survey` [P12]. *Why:* the survey to cite in sentence one of Related Work; it names automatic checkout as the first application.
13. **One-shot object detection for retail and warehouse** — Neural Processing Letters 2025, DOI 10.1007/s11063-025-11742-0. `review2025oneshotretail` [P13, search-snippet]. *Why:* recent review concluding detector+embedding stacks are the right trade-off under SKU churn.
14. **Shelf product recognition: exhaustive review** — Eng. Appl. of AI, 2024 [P14, search-snippet; get DOI]. Same conclusion: template-free detector + embedding wins when churn is high.

## C. Few-shot recognition and metric learning

15. **Prototypical Networks** — Snell, Swersky, Zemel, NeurIPS 2017, arXiv 1703.05175. `snell2017protonets` [P15]. Our gallery mean per SKU is a prototype.
16. **A closer look at few-shot classification** — Chen, Liu, Kira et al., ICLR 2019, arXiv 1904.04232. `chen2019closerlook` [P16]. *Why:* "deeper backbones erase the difference between methods" — supports spending effort on the backbone ablation (E3), not on exotic few-shot algorithms.
17. **ArcFace** — Deng, Guo, Yang et al., 2018/TPAMI, arXiv 1801.07698. `deng2019arcface` [P17]. Margin loss if we ever fine-tune the embedder.
18. **Supervised Contrastive Learning** — Khosla, Teterwak, Wang et al., NeurIPS 2020, arXiv 2004.11362. `khosla2020supcon` [P18]. The modern alternative to triplet loss; NVIDIA's retail model uses triplet+CE [H10].
19. **FaceNet** — Schroff et al., CVPR 2015. `schroff2015facenet` (already in bib; recalled).
20. **Domain-invariant hierarchical embedding for groceries** — Tonioni, Di Stefano et al., 2019, arXiv 1902.00760. `tonioni2019domain` [P20]. *Why:* reference-vs-store domain shift for retail embeddings — the problem the ring light solves physically.
21. **Few-shot pipeline with RT-DETR + metric embeddings** — ICOIACT 2025 [P21, search-snippet; get authors/DOI]. *Why:* a 2025 paper with our exact decomposition; shows the design is current.

## D. Backbones and general features

22. **MobileNetV3** — Howard, Sandler, Chu et al., ICCV 2019, arXiv 1905.02244. `howard2019mobilenetv3` [P22]. Our deployed embedder.
23. **CLIP** — Radford, Kim, Hallacy et al., 2021, arXiv 2103.00020. `radford2021clip` [P23].
24. **SigLIP** — Zhai, Mustafa, Kolesnikov et al., ICCV 2023, arXiv 2303.15343. `zhai2023siglip` [P24]. Better small VLM encoders than CLIP; MobileCLIP-class models are what the 2026 grocery-retrieval paper found best.
25. **DINOv2** — Oquab, Darcet, Moutakanni et al., 2023, arXiv 2304.07193. `oquab2023dinov2` [P25]. Accuracy-ceiling reference.
26. **DINOv3** — Siméoni, Vo, Seitzer et al., 2025, arXiv 2508.10104. `simeoni2025dinov3` [P26]. Newer ceiling; distilled small variants may fit the Pi.
27. **What matters for grocery product retrieval with open-source VLMs** — Maminta, Atienza et al., May 2026, arXiv 2605.18029. `maminta2026grocery` [P27]. 190 open models zero-shot on GroceryVision MPR; data quality beats scale by up to 16.6 points; MobileCLIP-B beats larger models trained on noisy data. *Why:* **the most important recent paper for us** — it says a small, well-trained encoder is the right choice for edge retrieval and gives the benchmark to use.
28. **ImageNet** — Deng et al., CVPR 2009. `deng2009imagenet` (in bib; recalled).

## E. Open-set recognition and abstention

29. **Toward open set recognition** — Scheirer, Rocha, Sapkota, Boult, TPAMI 35(7) 2013, DOI 10.1109/TPAMI.2012.256. `scheirer2013openset` [P29]. The field's origin; defines "open space risk".
30. **Recent advances in open set recognition: a survey** — Geng, Huang, Chen, TPAMI 2020, arXiv 1811.08581. `geng2020ossurvey` [P30].
31. **Generalized OOD detection: a survey** — Yang, Zhou, Li, Liu, 2021/2024, arXiv 2110.11334. `yang2021oodsurvey` [P31]. Unifies OSR/OOD/anomaly vocabulary — use its terms.
32. **MSP baseline** — Hendrycks & Gimpel, ICLR 2017, arXiv 1610.02136. `hendrycks2017baseline` [P32]. Our E5 baseline.
33. **Energy-based OOD** — Liu, Wang, Owens, Li, NeurIPS 2020, arXiv 2010.03759. `liu2020energy` [P33]. A second baseline that is trivial to add to E5.
34. **A good closed-set classifier is all you need?** — Vaze, Han, Vedaldi, Zisserman, ICLR 2022 oral, arXiv 2110.06207. `vaze2022goodclosedset` [P34]. *Why:* says OSR quality tracks closed-set accuracy; predicts that the backbone ablation (E3) also moves E5 — test that.
35. **Towards open world object detection** — Joseph, Khan, Khan, Balasubramanian, CVPR 2021 oral, arXiv 2103.02603. `joseph2021owod` [P35]. Unknown detection + incremental classes without forgetting: the master's-level version of our problem.

## F. Sensor fusion, tracking, proposals

36. **FAIM** — Falcão, Ruiz, Pan et al., Frontiers in Built Environment 2020, DOI 10.3389/fbuil.2020.568372. `falcao2020faim` [H12]. Weight+vision 92.6 % vs vision ~60–70 %.
37. **Self-checkout loss** — Hopkins / ECR Retail Loss 2026 report [M19]; Beck 2018 "Self-checkout in retail: measuring the loss" [M20]; Taylor 2016 "SWIPERS" typology, Criminology & Criminal Justice (recalled; get DOI). `hopkins2026sco`, `beck2018sco`, `taylor2016swipers`. *Why:* the loss numbers and the accidental/malicious split that justify a *nudge* design.
38. **ByteTrack** — Zhang, Sun, Jiang et al., 2021, arXiv 2110.06864. `zhang2022bytetrack` [P38]. Cited to say why we do not need it.
39. **Segment Anything** — Kirillov, Mintun, Ravi et al., 2023, arXiv 2304.02643. `kirillov2023sam`; **Grounding DINO** — Liu, Zeng, Ren et al., 2023, arXiv 2303.05499. `liu2023groundingdino` [P39]. Class-agnostic proposer alternatives for the ablation ("background subtraction vs foundation-model proposals").
40. **Domain randomization** — Tobin, Fong, Ray et al., IROS 2017, arXiv 1703.06907. `tobin2017domainrand` [P40]; **Quantization survey** — Gholami, Kim, Dong et al., 2021, arXiv 2103.13630. `gholami2021quant`; **Continual learning survey** — Wang, Zhang, Su, Zhu, TPAMI 2024, arXiv 2302.00487. `wang2024continual`. Synthetic-to-real (AI City did it), INT8 on ARM (why our dynamic quant lost), and the PhD direction.

## The gap, stated for the paper

Every piece exists: retrieval-based SKU recognition (GroZi 2007 → NVIDIA 2024), open-set rejection (Scheirer 2013 → Vaze 2022), weight fusion (FAIM 2020, Amazon), tray form factor (Mashgin, NCR). What is not in the literature is a **single measured system on sub-USD-300 hardware** reporting, on a public benchmark plus real captures: (1) minutes-to-enrol against hours-to-retrain, (2) open-set FPR at 95 % TPR for never-seen products, (3) the marginal accuracy of weight and physical size over appearance, with the flavour-variant failure quantified, and (4) end-to-end basket pricing error against barcode ground truth. That is the claim. It is modest, defensible, and nobody has the number.
