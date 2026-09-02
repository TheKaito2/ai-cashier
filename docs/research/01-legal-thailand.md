# 01 — Legal: deploying an AI checkout in Thailand

Scope: a camera-and-scale till in a physical shop in Thailand, operated by the shop, selling packaged goods. Each section ends with **So what for us**. Ledger ids in brackets.

## 1. Cameras and shoppers — PDPA B.E. 2562

**What the law says.** The Personal Data Protection Act treats any image from which a person can be identified as personal data. Biometric data used for identification is *sensitive* personal data under section 26 and needs explicit consent or a specific exception [L01]. Ordinary CCTV in a shop is run under the "legitimate interest" basis by every practitioner we found: no consent, but a visible notice sign and a CCTV privacy policy are required [L12]. Section 23 requires the controller to tell data subjects, before or at collection, the purpose, legal basis, retention period, recipients, the controller's contact, and their rights [L11]. The PDPC's formal CCTV guideline was in public consultation in March–April 2026 and is expected in the second half of 2026 [L02] — so the rules are about to become more specific, not less.

**Where our system sits.** The overhead camera points at a mat, not at a face. The front camera (planned for bottles) points across the mat at product height and could catch a shopper's torso or hands. Crops that reach the embedder are product boxes. Nothing is retained after the sale unless a research capture is running.

**So what for us.**
- Design rule, written into the software: *the recognition path never stores a frame.* Only the crop of a confirmed product proposal is embedded, and the embedding is a 576-float vector that cannot be inverted to a face. State this in the paper; it is a genuine privacy property of the retrieval design.
- If the front camera is added, mask everything above the mat plane in software before any processing. Document the mask.
- A research capture session in a real shop is a different activity from running the till: it retains images, so it needs the section 23 notice, a sign, and a retention period. The capture protocol (`research/PROTOCOL.md`) should say "no people in frame; if a person is in frame, the frame is deleted before the dataset is built".
- Never add face recognition for loyalty or age. It moves the system from "legitimate interest" to "sensitive data with explicit consent" and every deployment conversation gets harder.
- The PDPA has no explicit DPIA duty but requires a risk assessment when new technology is adopted [L11]. A one-page DPIA in `docs/` costs nothing and is the kind of thing a judge from industry notices.

## 2. Age- and time-restricted goods

### Alcohol — Alcoholic Beverage Control Act (No. 2) B.E. 2568

Published 9 Sep 2025, in force 8 Nov 2025 [L03]. Sellers must verify buyer age (20+) and sobriety; a seller who sells negligently and causes harm can be civilly liable [L03, L13]. Sale hours were split (11:00–14:00, 17:00–24:00) until regulations of 1 Dec 2025 opened 11:00–24:00 with the afternoon window provisional to 31 May 2026 [L04]; a Committee notice published 28 May 2026, effective 29 May 2026, made 11:00–24:00 permanent [L05]. The amended Act also permits vending machines that can verify the buyer's identity, pending Committee rules that have not yet been issued [L03, L13]. Religious holidays and election-day bans continue under separate notices (recalled; verify).

**So what for us.** A self-checkout is functionally a vending machine with a bigger screen. Until the Committee's identity-verification rules exist, the safe reading is that an *unattended* till must not complete an alcohol sale at all, and an *attended* till must (a) refuse outside 11:00–24:00 by the Pi's clock, and (b) stop and require a staff member to confirm an ID check before the item can be added. The product table needs a `restricted` flag (alcohol / tobacco / none); `_sellable()` in the till must consult it. This is a concrete, Thai-specific feature no generic open-source checkout has, and it demonstrates the team read the law.

### Tobacco — Tobacco Products Control Act B.E. 2560

In force 5 Jul 2017. No sale under 20; no retail display; no vending machines; no sale through electronic media or computer networks; up to 3 months and THB 30,000 for age violations [L06].

**So what for us.** Cigarettes cannot be sold through an unattended machine, full stop, and they cannot be displayed. The till should treat `restricted=tobacco` as "staff-only sale, item never shown in the product browser". Same code path as alcohol, stricter setting.

## 3. Scales used in trade — Weights and Measures Act B.E. 2542

The Central Bureau of Weights and Measures (Department of Internal Trade, Ministry of Commerce) is the legal metrology authority, with 28 local offices [L07]. Non-automatic weighing instruments used in trade must be verified; kitchen scales and automatic weighing instruments are exempt; manufacturer-verified instruments are valid two years; fees are small [L14].

**Where our scale sits.** The load cell does not determine a price. It verifies that the basket weight is consistent with what the camera recognised. No customer is charged by weight. That is the distinction that matters: a scale that sets a price is "used in trade"; a scale that only raises a flag is a sensor. (Interpretation, not sourced — a lawyer should confirm.)

**So what for us.**
- Keep it that way. The moment the system sells loose produce by weight, the cell, the ADC and the enclosure become a legal weighing instrument and must be a verified, class III unit — a cheap bar cell and HX711 will not pass.
- Write the distinction into `docs/HARDWARE.md` and the paper's system section: "verification scale, not a trade scale".
- Even as a sensor, temperature drift and creep [H06] are real; the two-point calibration and settling filter already in `recognition/scale.py` are the right engineering answer. Report drift measurements from the Pi in the paper rather than hiding them.

## 4. Prices, receipts and tax

**Price display.** The Prices of Goods and Services Act B.E. 2542, section 28, requires prices displayed per unit in Arabic numerals; the heaviest penalties (up to 7 years / THB 140,000) attach to sections 29–31 on unfair pricing; most enforcement is for missing price tags [L08]. The till screen showing the unit price when an item is recognised is the compliant behaviour, and the product browser must show prices.

**VAT.** Registration is mandatory above THB 1.8 million annual turnover [L09]. A registered seller must issue a tax invoice; retail sellers may issue an *abbreviated* tax invoice (section 86/6) with Director-General approval; required fields include the words "Tax Invoice", seller name, address and TIN, a running number, goods, amount, VAT and date [H08]. A shop below the threshold issues an ordinary receipt. The current till has `tax_rate` in settings but its receipt is a demo receipt.

**So what for us.** Add a `vat_registered` setting; when true, the receipt carries the abbreviated-tax-invoice fields and the sequential number comes from the `sales` table. When false, print a plain receipt. Small change, and it means a judge who runs a business cannot say "this cannot issue a legal receipt".

## 5. Theft, evidence and the tension with privacy

Theft under Criminal Code section 334 carries up to 3 years and THB 60,000 and is prosecuted regardless of value [L10]. Retailers want evidence; PDPA wants minimal retention. The self-checkout literature (ECR 2026) finds most loss is accidental, not malicious [M19, M20].

**So what for us.** The system's job is to *prevent* the mismatch at the moment of sale — that is what weight and size fusion do — not to build a surveillance archive. If a basket fails the weight check, the till holds the transaction for staff; it does not save the frame. Say this in the paper's ethics paragraph. It is also the honest answer to "does your system spy on customers".

## 6. Human participants and ethics review

Any evaluation where people other than the student use the prototype counts as human-participants research under ISEF rules and needs IRB pre-approval and Form 4; a student testing their own prototype alone is exempt [L15]. YSC follows the same logic for its ISEF track. Thai universities have their own ethics committees; a school does not.

**So what for us.** Experiment E7 (baskets rung up by real users against barcode ground truth) is human-participants research the moment a classmate does the scanning. Options: run E7 with team members only and say so, or get a university partner's ethics approval before recruiting. Decide before the capture session, not after.

## 7. Checklist for a real pilot (one page, for a shop owner)

1. CCTV notice sticker at the till; one-page CCTV privacy notice at the counter [L12].
2. No frames stored; embeddings only. Front camera masked above the mat.
3. Alcohol: 11:00–24:00 gate; staff ID confirmation; never unattended [L03–L05, L13].
4. Tobacco: staff-only; never displayed in the product browser [L06].
5. Scale used for verification only; no sale by weight [L14].
6. Prices shown per unit on screen and in the browser [L08].
7. Receipt mode set to match VAT registration [L09, H08].
8. Weight-check failure holds the sale for staff; it does not photograph the customer.

*Statutes change. Items 3 and 1 changed within the last twelve months. Check for amendments after 2026-09-02, and confirm all of the above with a Thai lawyer before commercial use.*
