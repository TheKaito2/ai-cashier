# 02 — Legal: software licences, data release, trademarks, patents

## 1. Licence audit of v4 as it ships

| Component | Where used | Licence | Effect on us |
|---|---|---|---|
| PyQt5 | `scanner/ui/*` (till) | GPL v3, or paid Riverbank licence | Anything distributed with it must be GPL, or you buy a licence [I01] |
| PySide6 | not yet used | LGPL v3 | Proprietary or Apache-licensed app is fine; only changes to Qt itself must be shared [I01] |
| ultralytics | `requirements-research.txt`, `tools/`, `research/` (E1 baseline), legacy `.pt` models | AGPL-3.0 | Any derivative that is distributed *or offered as a network service* must be AGPL, including weights; commercial use needs an Enterprise licence [I02] |
| torchvision MobileNetV3 weights | embedder | BSD-3 | Permissive (recalled — check the torchvision LICENSE file) |
| onnxruntime | till | MIT | Permissive (recalled) |
| opencv-contrib-python | till (ArUco) | Apache-2.0 | Permissive (recalled) |
| FastAPI, uvicorn, numpy, qrcode, pillow, requests | server/till | MIT / BSD / HPND | Permissive (recalled) |
| lgpio | Pi only | Unlicense (public domain), recalled — verify | The HX711 is bit-banged in our own code over lgpio; the PyPI `hx711` package (RPi.GPIO, MIT) is no longer used [A01, A03] |

**The two problems.**

1. **PyQt5 makes the till GPL.** For a competition that is harmless. For a paper that says "code available under Apache-2.0" it is false, and for any shop deployment it means either publishing the whole till under GPL or paying Riverbank. PySide6 is the same Qt under LGPL and the port is mostly import renames plus `exec()` for `exec_()` and enum scoping. This is the single highest-value legal fix and it is a mechanical one.
2. **ultralytics is AGPL and reaches further than people think.** Phase 2 already removed it from the till and server import path; that was the right move and must stay true — a test that fails if `ultralytics` is importable from `scanner/` or `server/` is worth keeping. The surviving `chips_model.pt` / `drinks_model.pt` are AGPL-derived weights: they can be used as the E1 baseline and as an auto-labelling tool, but they cannot ship inside a proprietary product and must not be described as "ours" in a licence sense.

**Recommended licences.** Code: Apache-2.0 (patent grant, business-friendly, what judges expect). Paper: whatever the venue requires (IEEE copyright, or CC BY on arXiv). Dataset: CC BY-NC-SA 4.0 — the same terms RPC uses [I05] — unless the team wants companies to be able to use it, in which case CC BY 4.0. Products-10K is non-commercial-only [I06]; if the paper reports numbers on it, that is research use and fine.

## 2. Releasing a product dataset

- **Trademarks and packaging.** RPC, Products-10K, RP2K and GroceryVision all publish photographs of branded packaging under research licences; nobody has been sued for it. Trademark law concerns confusion in trade, not photographs used to train a classifier. Copyright in packaging artwork exists, but research datasets of product photos are common practice; a non-commercial licence and a takedown contact are the norm. (This paragraph is practice, not a legal opinion.)
- **People.** No faces, no hands with identifying marks, no reflections showing a person. PDPA applies to research data too [L01, L11].
- **Provenance.** Record camera, lighting, mat, date and product batch for every capture. Reviewers ask; and the same metadata makes the E3/E4 tables reproducible.
- **Ground truth.** Barcode scans of every item in every basket are the ground truth for E7 and the only defensible labelling for a checkout dataset. The NVIDIA reference design does exactly this: it validates vision predictions against a barcode scanner and flags disagreements as "unseen" [H09].

## 3. Patents — what exists, so the claim is phrased correctly

This is a landscape, not a freedom-to-operate opinion.

- **Vision self-checkout is old.** US7909248B1 / US8196822B2 "Self checkout with visual recognition" and US20130304595A1 "Automatic learning in a merchandise checkout system with visual recognition" predate every startup below [I04]. The second is directly relevant: it describes a checkout that *learns new items automatically*. The idea of enrolling products at the till is not new and the paper must not claim it is.
- **Mashgin.** US20150109451A1 "Automated object recognition kiosk for retail checkouts" (multiple images of one product, feature extraction, model-based recognition) and application 16/104087 "Fast item identification for checkout counter" (items in motion, several cameras) [I03]. Mashgin raised USD 62.5 m at a USD 1.5 bn valuation in 2022 [I07] and is deploying more than 10,000 units to Circle K [M10]. They claim under-a-minute enrolment [M10] — which is our headline feature, validated by the market leader.
- **Amazon.** The Just Walk Out family covers ceiling cameras plus shelf weight sensors and multimodal fusion [H03]. Our fusion is at the till, on a single mat, with a single load cell — a different apparatus, but the same principle of weight resolving visual ambiguity.
- **Weight + vision fusion.** US11017641 / US11908290 / US12283165 "Visual recognition and sensor fusion weight detection system and method" [H12 search] cover weighed goods in cashierless stores. Worth reading before the paper claims novelty for fusion; the academic prior art (FAIM, 2020) already reports weight+vision fusion at 92.6 % [H12].
- **Everseen / NCR Voyix** hold patents on scan-verification nudges and the four-camera Halo tray [H04].

**So what for us.** The defensible claim is *measurement*, not mechanism: enrolment cost, open-set rejection quality, and fusion benefit, all on a THB-8,000 rig, reported with a public benchmark. That claim infringes nothing because it asserts nothing about owning the idea. For a competition, say "we implement the approach the industry converged on and quantify it on low-cost hardware".

## 4. Competition rules on IP

- **ISEF** requires ethical handling of intellectual property but does not take ownership; students keep their IP. Teams of at most three; one project per student per season; twelve months of research maximum [L16]. *Note: the current group has six members. An ISEF/YSC entry would carry three names.*
- **YSC** follows ISEF rules for the projects it sends abroad (recalled — verify in the YSC 2027 manual).
- **Samsung Solve for Tomorrow** terms differ by country; the Thai terms were not found online this session. Read the entry terms for licence-back clauses before submitting.
- **TICTA/APICTA** judge on commercial potential and expect a demo; no IP transfer (recalled — verify).

## 5. Open questions for a lawyer (keep this list short and specific)

1. Is a load cell used only to flag a mismatch a "weighing instrument used in trade" under the Weights and Measures Act? (Our reading: no.)
2. Does an attended self-checkout with a staff ID-confirmation step satisfy the amended Alcohol Act, or must alcohol be removed from self-service entirely until the Committee's vending-machine rules issue?
3. Is a CCTV notice sufficient for a camera that never stores frames, or is a notice even required when nothing is retained?
4. Does the school, the students, or the instructor own the code and the paper? Put it in writing before the competition.
