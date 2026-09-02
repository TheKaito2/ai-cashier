# 04 — How everything works: the checkout stack from barcode to bank

Written so a team member can answer any "but how does a real one do it?" question from a judge. Each section ends with how it maps onto our pipeline (`proposer → embedder → gallery → tracker → fusion`).

## 1. The barcode point-of-sale, which everything else is measured against

- **Identifiers.** A packaged product carries a GTIN (EAN-13 in Thailand, UPC-A in the US), issued through the national GS1 member organisation. GS1 Thailand charges THB 7,000 to join plus an annual fee and issues GTINs and a GLN (location number) [H11]. Loose produce uses 4–5-digit PLU codes on stickers, typed or scanned at the till. A retailer's *SKU* is its own internal identifier; one GTIN may map to one SKU, but repacks, bundles and local goods have SKUs with no GTIN — those are the items no scanner can ring up.
- **Price lookup.** The scanner returns the GTIN; the POS looks it up in its product table for price, tax class and, on self-checkouts, the expected weight. Our `products` table (SQLite, `server/services/database.py`) plays that role, with `weight_g`, `size_mm_long/short` and `barcode` columns already present.
- **Peripherals.** Receipt printers speak ESC/POS over USB or serial; the cash drawer is kicked by a pulse from the printer's drawer port; customer displays are serial. (Recalled, standard.) None of this is in v4 and none of it is research; it is a week of integration when a pilot needs it.
- **Why vision at all, when barcodes work?** Because (a) the long tail has no barcode, (b) barcodes need orientation and a free hand, (c) barcodes are the attack surface — the scanner cannot tell you scanned the cheap item's code while bagging the expensive one — and (d) a scan takes a second per item while a tray photograph takes a second per basket. Everseen exists to fix (c) on lanes that already have scanners [H04].

## 2. How the commercial vision systems work, and where they sit relative to ours

| System | Sensing | Recognition | New product | Our equivalent |
|---|---|---|---|---|
| **Mashgin** [I03, M10] | Several cameras (colour + 3D) over a fixed tray; item placed, not scanned | Multi-view feature extraction against product models; claims 99.9 % | "Learns new objects in under a minute", synced across stores | Same form factor. Our single overhead camera + planned side camera is the two-view budget version; enrolment is the same idea (`EnrolDialog` → `SkuGallery.enrol`). |
| **NCR Voyix Halo + Everseen** [H04] | Four cameras above a tray; bulk-recognises up to 20 items in any orientation | Detection + classification; Everseen's Evercheck nudges "missed scan" within ~300 ms on ordinary lanes | Vendor retrain | Our tracker + gallery does the tray part; our weight check is the verification part. |
| **Amazon Just Walk Out** [H03] | Ceiling RGB cameras on rails + shelf load cells; transformer-based multimodal model; synthetic video for training | Who-took-what across a whole store | Vendor pipeline | Different problem (store-wide tracking). Same *principle* as our fusion: weight resolves what vision cannot. |
| **NVIDIA reference design** [H09, H10] | One camera over a lane + barcode scanner as ground truth | Detector → embedding (448-d, FAN-Base-Hybrid, triplet loss) → L2 retrieval against a reference database; 20–30 reference images per class recommended; ~86 % retrieval with 100 refs | Disagreements with the scanner flagged "unseen"; feedback endpoint re-embeds | **This is our architecture**, published by NVIDIA as their reference. Cite it. Our k=5 views vs their 20–30 is a real difference to measure (E2). |
| **FAIM (academic)** [H12] | Shelf weight + in-hand camera | Adaptive fusion | n/a | Weight+vision fusion at 92.6 % vs vision-only ~60–70 %: the literature already shows fusion is where the accuracy is. |
| **Shekel / SAI weight shelves** | Load cells in every shelf | Weight-only identification with layout prior | Planogram update | Weight alone; no appearance. Our fusion includes their signal as one term. |
| **Tiliter** | Camera at the scale for produce | Produce classifier | Vendor | Produce-by-weight: the case our rig deliberately does *not* handle (see 01 §3). |

The pattern: everyone who survived put items on a tray under fixed cameras, and everyone who verifies uses a second signal (weight, scanner, shelf). Our design matches both.

## 3. Loss prevention mechanics at a self-checkout

- **The bagging scale.** The POS knows the expected weight for each scanned GTIN and compares it to the bagging-area scale after each scan; a mismatch is "unexpected item in the bagging area" [H05]. Retailers loosened or disabled it because light items, price-marked packs and reusable bags cause false alarms that need staff [H05]. This is the exact tolerance problem our quadrature model in `recognition/fusion.py` (`basket_tolerance_g`) addresses: tolerance grows with the *square root* of item count, not linearly, so a ten-item basket does not need a 40 g window that lets a swap through.
- **Fraud taxonomy** (ECR / criminology literature [M19, M20; P37]): skip-scan (item never scanned), item switch (scan cheap, bag dear), quantity fraud (scan one, bag three), the "banana trick" (weigh an expensive produce item as a cheap PLU), walkaway. Half is accidental.
- **What our fusion catches.** Skip-scan → basket weight exceeds expected (caught). Item switch of different weight → caught (the Lay's 75 g vs 98 g case). Item switch of same weight and different size → size term catches it. Quantity fraud → weight. Same weight, same size, different appearance → appearance term. Same weight, same size, near-identical appearance (flavour variants) → **not caught**; that is the documented limitation and the reason to measure it rather than hide it.
- **The nudge, not the alarm.** Everseen's finding is that a 300 ms on-screen nudge lets the shopper fix the mistake without staff [H04]. Our `AMBIGUOUS` state with a "Choose" button is that nudge. Keep the UI tone neutral: most mismatches are accidents [M20].

## 4. Payment in Thailand: what the QR actually is, and why the till cannot yet know it was paid

- **Thai QR is EMVCo TLV.** Tag 29 carries the PromptPay credit-transfer template (AID `A000000677010111`; sub-tags for mobile number, national ID, e-wallet). Tag 30 is the Bill Payment template for registered billers (biller ID, ref 1, ref 2) [H01]. `server/services/promptpay.py` builds tag 29 with amount and CRC-16/CCITT-FALSE; that is what a personal or small-merchant PromptPay uses. Tag 30 requires registering as a biller with a bank and is what chains use because the references reconcile automatically.
- **The confirmation gap.** A static QR tells the phone where to send money; it tells the till nothing. Today the till marks the sale paid when a staff member presses confirm after looking at the customer's slip. Fake slips are common enough that Kasikornbank publishes advice on spotting them, and AI-generated slips have made forgery trivial [H02]. Options, cheapest first: (1) slip verification API (EasySlip covers 18+ banks; bank APIs exist) — the customer shows the slip QR, the till verifies the transaction reference and amount server-side [H02]; (2) bank webhook on a merchant account (tag 30) — the bank tells the till when money lands; (3) a payment gateway (Omise/2C2P/GB Prime Pay, recalled) that handles all of it for a fee.
- **So what for us.** A `verify_slip()` hook behind `process_pending_payment` that accepts a slip QR string, calls a verifier, and refuses to mark the sale paid on mismatch. Ship with a `NullVerifier` so the demo still works; the interface is the deliverable. It turns "we generate a QR" into "we close the loop".

## 5. Receipts and tax (mechanics only; law in 01 §4)

A VAT-registered shop prints an abbreviated tax invoice: the words "ใบกำกับภาษีอย่างย่อ / Tax Invoice (ABB)", seller name, address, TIN, running number, date, items with quantities and amounts, and a line stating VAT is included [H08]. A non-registered shop prints a receipt without VAT lines. E-receipts by email fall under the Revenue Department's e-Tax invoice by email scheme [H08]. Our `sales` table already has a sequential id and timestamp; a `receipt.py` that renders either format from a sale row is the whole job.

## 6. The scale: what a load cell really does

- A bar load cell is a strain-gauge Wheatstone bridge; the HX711 is a 24-bit ADC with a programmable-gain amplifier reading it at 10 or 80 samples/s. Datasheet-class figures for a cheap cell: hysteresis 0.02 % of full scale, creep 0.02 % FS per 10 min, zero drift 0.03 % FS per 10 °C, span drift 0.02 % FS per 10 °C [H06]. On a 5 kg cell that is 1 g of creep in ten minutes and 1.5 g of zero drift for a 10 °C change — the same order as the item tolerance we care about. Hence: tare before every basket (zero drift cancels), use a 5 kg cell not a 200 kg kit (resolution at 75 g), moving-average with a settling test (`_FilteredScale.is_settled`), and a two-point calibration with a known mass (`tools/calibrate_scale.py`).
- Legal metrology classifies trade scales (OIML R76 class III for retail); Thailand verifies non-automatic weighing instruments and exempts kitchen scales [L14]. Our cell is a sensor, not a trade scale (01 §3).

## 7. Cameras and light

Domain shift is the enemy of a retrieval system: the gallery was enrolled under one illumination and the query arrives under another. A diffused ~5000 K ring light and a matte mat make illumination constant, which is the cheapest accuracy available (`docs/HARDWARE.md`). Lock exposure and white balance in the webcam driver once the ring is on; auto-exposure changes the embedding of an unchanged product frame to frame. The ArUco marker on the mat gives a homography so a pixel box becomes millimetres (`recognition/metrology.py`), and because enrolment stores the *measured* size under the same camera, projection bias cancels.

## 8. Edge inference

- **CPU.** ONNX Runtime on the Pi 5's four Cortex-A76 cores. Our measured M1 numbers (0.3 MB model, 6.1 ms per crop FP32; INT8 dynamic quantisation was 2.2× *slower* and lost cosine fidelity) say: ship FP32, thread count = 4, and re-measure on the Pi with `research/bench.py`. Static INT8 with calibration data is the next thing to try; dynamic INT8 on a tiny convnet is known to lose [P34].
- **Accelerator.** The Raspberry Pi AI HAT+ is USD 70 for 13 TOPS (Hailo-8L) or USD 110 for 26 TOPS; YOLOv8n runs ~60 fps on it versus 3–5 fps on the CPU [H07]. For a research paper it is a legitimate ablation row ("with/without accelerator"); for the โชห่วย buyer it doubles the rig cost, so the CPU-only number is the headline.
- **Thermals.** A Pi 5 under sustained inference throttles without a cooler; the active cooler is mandatory in the BOM and `research/bench.py` records CPU temperature for that reason.
