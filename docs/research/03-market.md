# 03 — Market: who wants this, what happened to the people who tried, and what a lane costs

## 1. The global picture, in ranges

Self-checkout hardware and software is a USD 5–6 billion market in 2025 by three independent estimates, growing 11–15 % a year [M01, M02, M03]. The incumbents are NCR Voyix, Diebold Nixdorf, Toshiba Global Commerce Solutions, Fujitsu and ITAB (recalled — company names, not figures). A standard unit costs USD 4,500–8,000; a card-only kiosk from USD 3,000 (NCR's stripped-down "SCO Essentials" is advertised from USD 1,800); a full grocery lane with cash recycling reaches USD 40,000 [M15].

## 2. What happened between 2024 and 2026

This is the part a naive project misses. The story is not "self-checkout is the future". It is two stories at once.

**Story A — traditional self-checkout is being pulled back because of loss.**
- NRF's 2024 survey put US shrink at 1.68 % of revenue, about USD 112 bn [M04].
- ECR Retail Loss (39 retailers, over EUR 1 tn of turnover, published 16 Jun 2026): stores with self-checkout lose 0.42 percentage points more than stores without — a third more; each additional 1 % of transactions moved to self-checkout adds 0.030–0.048 % loss; missed scans occur in 1–4.8 % of transactions; a "walkaway" costs EUR 88 on average [M19]. The same group's earlier work found about half of self-checkout loss is *accidental* [M20].
- LendingTree, December 2025, n≈2,050 US adults: 27 % admit deliberately not scanning an item, up from 15 % in 2023; 41 % of millennials; 55 % of admitted offenders expect to do it again [M06].
- Dollar General removed self-checkout from roughly 12,000 stores in 2024; Target and Five Below restricted it; Walmart has been removing it store by store through 2025–2026; Aldi removals were reported in September 2025 [M09].

**Story B — "just walk out" was a fantasy at grocery scale, but tray-based vision checkout is winning.**
- Amazon pulled Just Walk Out from all Amazon Fresh stores on 2 Apr 2024 in favour of smart carts [M21], then in January 2026 closed every Amazon Fresh and every remaining Amazon Go store — 72 stores — most by the first weekend of February 2026 [M22]. JWO survives only as a product sold to stadiums, airports and campuses [M08].
- Grabango, USD 71 m raised, shut down in October 2024 for lack of funding [M07]. Standard AI (USD 233 m raised, USD 1 bn valuation in 2021) stopped selling checkout and became a retail-data company [M16]. Zippin (USD 45 m) and AiFi (USD 91 m; 7-Eleven US expanding AiFi stores in Feb 2026) remain, mainly in venues [M16].
- Meanwhile **Mashgin** — a camera tray you put items on, no scanning — raised at USD 1.5 bn [I07] and is being deployed to more than 7,000 Circle K stores, over 10,000 units, after five years in about 500 stores [M10]. Its pitch is exactly ours: ten-second checkout, any orientation, and a new item learned in under a minute [M10].
- NCR Voyix's answer is Halo: four cameras above a tray, up to 20 items bulk-recognised, plus Everseen's missed-scan nudge on ordinary lanes [H04].

**The lesson.** The market converged on *the tray*. Ceiling-camera stores failed on cost and complexity; barcode self-checkouts leak. The winning form factor is a fixed mat, a few cameras, and a recognition model that the store can teach. That is the form factor this project built, and the paper's motivation should say so with the citations above rather than with a generic "retail is going cashierless" sentence.

**The second lesson.** Because loss is the reason retailers are retreating, *verification* is worth as much as recognition. Everseen's entire business is telling an existing lane "you did not scan that". Our weight-and-size fusion is a verification engine. Position it as one.

## 3. Thailand

**Modern trade.** CP All operated 15,430 7-Eleven stores on 13 May 2025, second in the world after Japan; about half are franchised [M11]. Lotus's has more than 2,000 stores, Tops more than 235 [M12]. Modern trade is about 60 % of food retail and growing 5–5.5 % a year; convenience stores are the fastest format at about 11 % CAGR to 2030 [M12]. Self-checkout kiosks exist in 7-Eleven and Tops; Big C's "Scan & Pay" is phone-based [M14]. (That last source is a 2020 user write-up; the chains' current deployments should be checked in-store.)

**Traditional trade.** More than 400,000 โชห่วย (family grocery shops) remain, still about 40 % of food retail but shrinking around 2 % a year [M12, M17]. The Department of Business Development's "Smart Chohuay" programme trained 2,917 shops in 2025 and upgraded 300 to POS-equipped "smart" shops — the government is explicitly trying to put point-of-sale technology into these stores [M17].

**Labour.** The minimum daily wage is THB 337–400 by province (THB 400 in Bangkok, Chonburi and the eastern seaboard), about THB 10,400 a month at 26 days [M13]. Thailand is an aged society — 21.5 % over 60 in September 2025 — with a structural labour shortage and employers redeploying seniors to cashier and greeter roles [M18].

**Barcodes.** GS1 Thailand charges THB 7,000 to join plus an annual fee [H11]. National brands are barcoded; the long tail of local snacks, bakery, prepared food and repacked goods in a โชห่วย is not — which is precisely where vision recognition earns its place.

## 4. Who is the customer

| Segment | Buys from | Will they buy this? | Why / why not |
|---|---|---|---|
| CP All / Lotus's / Big C / Central | NCR, Toshiba, Diebold, in-house | No | Procurement scale, support contracts, integration with their ERP. They are the *benchmark*, not the customer. |
| Mid-size chains, campus shops, hospital kiosks, hotel minibars | Local integrators | Maybe | Want a cheap tray checkout; can tolerate a Pi. Venues are where Amazon and Zippin went too. |
| โชห่วย with one owner and no IT | Nobody, or a THB 5,000 tablet POS | **Yes, if it is cheap and teaches itself** | 400,000 shops; no data team; SKUs change weekly; a barcode scanner does not cover half their stock. Few-shot enrolment is the only approach that fits. The government is subsidising POS adoption in exactly this segment [M17]. |

This is the paper's motivation and the competition's "who is it for". Everything in the hardware spec follows from it: a Pi 5, a webcam and a THB-300 load cell because the buyer's whole month of profit is a few thousand baht.

## 5. Unit economics, first cut

| Item | Figure | Source |
|---|---|---|
| Incumbent standard self-checkout unit | USD 4,500–8,000 (≈ THB 150,000–270,000 at ~33 THB/USD, recalled rate) | [M15] |
| Card-only kiosk floor | USD 1,800–3,000 | [M15] |
| This rig (Pi 5 8 GB + 14″ touchscreen already owned; buy list) | ≈ THB 2,300–4,600 in parts, plus the Pi and screen if bought (≈ THB 6,000–8,000 more, recalled) | `docs/HARDWARE.md` |
| Cashier, Bangkok minimum wage | THB 400/day ≈ THB 10,400/month | [M13] |
| Loss exposure the till must not create | +0.42 pp of sales in SCO stores | [M19] |

Reading: a THB-10,000 rig costs one month of one cashier. It does not replace the cashier in a โชห่วย (the owner is the cashier); it lets one person serve a queue faster and stops the two most common errors — wrong item and wrong quantity — at the moment of sale. That is the honest value proposition. "Replace staff" is not, and the loss data says retailers no longer believe it either.

## 6. Numbers to put in the paper's introduction (all with ledger ids)

- Circle K / Mashgin: >10,000 units, >7,000 stores, learns a new item in under a minute [M10].
- Amazon Fresh/Go closures 2024–2026 [M21, M22]; Grabango closure [M07].
- ECR 2026: +0.42 pp loss in SCO stores; missed scans 1–4.8 % [M19].
- LendingTree 2025: 27 % admit not scanning [M06].
- Thailand: 15,430 7-Elevens [M11]; >400,000 traditional shops [M17]; THB 400/day wage [M13]; 21.5 % over 60 [M18].
