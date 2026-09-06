# The pipeline — a frame becomes a line on the receipt

One sentence: **background subtraction finds the things on the mat, a frozen
convolutional trunk turns each crop into a 576-dimensional vector, cosine
similarity against a handful of enrolled views names it, weight and size break
ties, a tracker makes sure one packet is charged once, and everything below a
measured threshold is refused rather than guessed at.**

Nothing is retrained to add a product.  That is the whole claim.

## The twelve hops

| # | What happens | Where |
|---|---|---|
| 1 | A background thread pulls frames off the camera; the UI reads the latest | `scanner/detection/camera.py:VideoStream` |
| 2 | The cashier presses Scan; a `ScanWorker` moves onto a QThread so the window never freezes | `scanner/ui/main_window.py:ScanWorker` |
| 3 | The scale is read.  `read_stable_grams` returns `None` rather than a misleading zero if the reading has not settled | `recognition/scale.py:read_stable_grams` |
| 4 | The new item's mass is the change since the last item went down, not the whole pan | `recognition/fusion.py:item_weight_for_scan` |
| 5 | The empty mat is subtracted; shadow pixels are dropped by chromaticity, not brightness | `recognition/proposer.py:propose` |
| 6 | Boxes are matched to existing tracks; a settled track is not re-embedded | `recognition/tracker.py:update` |
| 7 | Every unsettled crop is embedded in one batch | `recognition/embedder.py:OnnxEmbedder` |
| 8 | The query is L2-normalised, the gallery centre subtracted, normalised again, then scored against every enrolled view | `recognition/gallery.py:project` and `recognition/gallery.py:match` |
| 9 | Appearance, mass and size are summed as log-likelihoods; anything under τ abstains | `recognition/fusion.py:fuse` |
| 10 | Several frames vote; the verdict is a `RecognisedItem` with a status | `recognition/pipeline.py:RecognisedItem` |
| 11 | Legal gate, then the cart | `server/services/restrictions.py:sale_gate`, `scanner/models/cart.py:ShoppingCart` |
| 12 | Basket weight check, payment, receipt, database | `recognition/fusion.py:verify_basket`, `server/services/checkout.py:create_payment` |

The orchestration for hops 5–10 is one function: `recognition/pipeline.py:process`.
Teaching a product is the same machinery run backwards — `recognition/pipeline.py:enrol`
crops k views, embeds them and hands the vectors to `recognition/gallery.py:enrol`.

## Three things that are easy to get wrong

**The centre must be subtracted from a normalised query.** `project` normalises,
subtracts the frozen centre, then normalises again.  Subtracting a unit-length
centre from an un-normalised query is a different operation and it silently
degrades every score — this was fault F5 in `docs/research/09-architecture-review.md`,
found by the Swift port, and it moved τ from 0.38 to 0.75.

**The centre freezes.** Once `MIN_SKUS_TO_FREEZE` products are enrolled the centre
stops moving, so enrolling product 20 does not change what product 3 scores.  See
`recognition/gallery.py:freeze_centre`.

**τ is measured, never chosen.** `recognition/fusion.py:FusionConfig` ships
`reject_below_cosine = 0.75` as a placeholder.  The real value comes from E5 via
`recognition/calibration.py:pick_threshold` and is written into the database by
`tools/set_threshold.py`.  It is anchored on the true-positive rate rather than
accuracy because the costs are not symmetric: refusing a stocked product annoys a
queue, charging an unknown item as something else takes the wrong money.

## Payment and receipt

`server/services/checkout.py:create_payment` merges the cart, prices it, checks
stock, runs the legal gate, builds a real EMVCo PromptPay payload
(`server/services/promptpay.py:build_payload`) and stores a pending payment.  **It
does not touch stock.**  Stock moves only inside
`server/services/database.py:process_pending_payment`, one `BEGIN IMMEDIATE`
transaction that decrements stock, writes the sale and its lines, and closes the
payment together or not at all.  `server/services/checkout.py:confirm_payment`
verifies the slip first and attaches `server/services/receipt.py:render`.

## The Swift port

The iPhone app is a second implementation of the same algorithm, not a client of
the first.  It exists partly as a product and partly as a check: two independent
ports that must agree, and disagreement has already found a real bug.

| Python | Swift | Notes |
|---|---|---|
| `recognition/proposer.py` | `ios/AICashier/Sources/Recognition/Proposer.swift:propose` | Blur, morphology and connected components are hand-written; there is no OpenCV |
| `recognition/embedder.py` | `ios/AICashier/Sources/Recognition/Embedder.swift:CoreMLEmbedder` | Core ML `.mlpackage`, worst-case cosine 0.9994 against the ONNX graph |
| `recognition/gallery.py:project` | `ios/AICashier/Sources/Recognition/Gallery.swift:project` | Must stay identical; this is where F5 lived |
| `recognition/fusion.py:fuse` | `ios/AICashier/Sources/Recognition/Fusion.swift:fuse` | Appearance only — the phone has no load cell and no marker mat |
| `recognition/tracker.py` | `ios/AICashier/Sources/Recognition/Tracker.swift:update` | |
| `recognition/pipeline.py:process` | `ios/AICashier/Sources/Recognition/Pipeline.swift:process` | |
| `server/services/promptpay.py` | `ios/AICashier/Sources/Data/PromptPay.swift` | Byte-for-byte equal payloads, asserted in tests |
| `server/services/receipt.py:render` | `ios/AICashier/Sources/Data/Receipt.swift:render` | Both legal forms, 32 columns |
| `server/services/restrictions.py` | `ios/AICashier/Sources/Data/Restrictions.swift` | Same hours, same tobacco rule |
| `server/services/database.py:process_pending_payment` | `ios/AICashier/Sources/Data/AppDatabase.swift:processPending` | GRDB instead of sqlite3 |

**How they are kept in step.** `tools/export_fixtures.py` writes
`ios/AICashier/Tests/Fixtures/fixtures.json` — crops, embeddings, gallery vectors,
expected matches, scene boxes, PromptPay payloads and the CRC check value, all
produced by the Python side.  The XCTest suite asserts the Swift port reproduces
them.  If you change any row in the table above, regenerate the fixtures and run
the Swift tests; a silent divergence between the two ports is the most expensive
kind of bug this project can have.

The phone deliberately drops mass and size: `FusionConfig` there is
appearance-only.  Do not "fix" that by adding the weight terms — there is no
scale in a phone.
