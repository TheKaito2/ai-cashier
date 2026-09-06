# Decisions, and why

The architecture review, `docs/research/09-architecture-review.md`, is already an
ADR log in all but name: nineteen decisions D1–D19 and five faults F1–F5, each
written as *what version 4 did → why → the alternatives with evidence → verdict*.
**Read that first for anything about the rig, the scale, the proposer or the
gallery.**  This page holds the decisions that sit above or after it, so nothing
important lives only in a commit message.

---

### Recognition by retrieval, not by retraining
*Standing decision; it is the thesis.*

A closed-set detector has to be retrained to learn a new product, which means a
labelled dataset, a GPU and hours.  Retrieval enrols a product from five
photographs in under a minute, and adding one changes nothing about the others.

**Rules out** anything that requires touching model weights at the shop counter.
**Costs** an accuracy ceiling set by whatever the frozen trunk already knows — and
`docs/kb/05-research.md` shows that ceiling is real: 45.8 % top-1 on public
carton photographs.  Improving the encoder is the lever; retraining per shop is
not on the table.

### The gallery centre freezes after four products
*`recognition/gallery.py:freeze_centre`, `MIN_SKUS_TO_FREEZE`.*

Mean-centring the embedding space measurably improves cosine retrieval, but a
centre that keeps moving means enrolling product twenty silently changes what
product three scores — and invalidates any threshold measured before it.  Freezing
buys reproducibility at the cost of a slightly stale centre.

### τ is measured, never chosen
*`recognition/calibration.py:pick_threshold`, `tools/set_threshold.py`.*

The rejection threshold depends on the backbone, the rig and the light, so it is
picked from a validation split and anchored on the true-positive rate rather than
on accuracy: refusing a stocked product annoys a queue, charging an unknown item
as something else takes the wrong money.  The shipped `0.75` in
`recognition/fusion.py:FusionConfig` is a placeholder and the till must not take
real money on it.

### The query is normalised before the centre is subtracted
*Fault F5, 3 September 2026, found by the Swift port.*

`recognition/gallery.py:project` normalises, subtracts, normalises again.  The
earlier code subtracted a unit-length centre from an un-normalised query, which is
a different operation; it invalidated every open-set threshold and moved τ from
0.38 to 0.75.  It was found because two independent implementations disagreed —
which is the argument for keeping both.

### A Qt till and a web dashboard, not one web app
*From the architecture review.*

The till must work with no network and must talk to a camera and a load cell; the
owner's dashboard is read-mostly and wants to open on a phone.  Those are different
programs.  They share one process and one database, and the till calls
`server/services/checkout.py` directly rather than over HTTP.

### Nothing leaves the shop
*`docs/PRIVACY.md`, enforced by `tests/test_privacy.py`.*

`recognition/` writes no file, and the static folder may contain no external URL —
`tests/test_pages.py` fails on any `http(s)://`.  This is a legal position under
PDPA as much as an engineering one, and it is why the dashboard's charts are
hand-drawn SVG instead of a charting library from a CDN.

### PromptPay, as a real EMVCo payload
*`server/services/promptpay.py:build_payload`.*

Version 3 wrote `PAYMENT|68.48|<uuid>` into a QR code, which no bank app can read.
The payload is now byte-correct EMVCo with a CRC, verified against the published
check value, and the Swift port must produce the same bytes.  Slip verification is
a hook (`server/services/slip_verify.py:from_settings`) because the confirmation
gap is real and a shop may or may not pay for a verifier.

### Stock moves in exactly one transaction
*`server/services/database.py:process_pending_payment`.*

Decrement, sale, lines and payment close together or not at all.  Everything else
in the money path is a plain function over a database handle, which is what makes
it testable without a UI.

### A Swift port, kept honest by exported fixtures
*`tools/export_fixtures.py`.*

The phone app is a product, and it is also a second opinion.  Two independent
implementations of one algorithm, tied together by a generated fixture file, catch
the class of bug that unit tests written against your own assumptions never do.
F5 is the proof.

### Public datasets are symlinked, never copied
*`research/prepare_grocerystore.py`.*

The Grocery Store clone stays where it was cloned; the three prepared views are
directories of symlinks.  Zero disk cost, and `research/data/` is gitignored so
nothing large ever reaches the public repository.

### One token table, hand-copied to four files
*`docs/DESIGN.md`.*

The colours and type scale live in exactly one document and are copied by hand
into `scanner/ui/theme.py`, `server/static/css/style.css`,
`ios/AICashier/Sources/Theme.swift` and `site/public/style.css`.  A build step that
generated all four would be less error-prone and was rejected anyway: four
different languages, four different build systems, and a generator nobody runs is
worse than a table somebody reads.  The cost is discipline — change the table
first, then the four files.

### "Receipt and instrument" as the visual identity
*4 September 2026.*

The till is a measuring instrument that ends every sale by printing a receipt, so
those two artefacts are the only motifs: the viewfinder with boxes drawn on the
frame, and the receipt with its torn edge.  IBM Plex Sans Thai carries Latin and
Thai in one family because product names are Thai; Plex Mono is every readout and
price column.  One accent colour, used for state and never for decoration.

### Fonts are bundled, never fetched
*`assets/fonts/`, OFL.*

Seven faces shipped in the repository, registered with Qt by
`scanner/ui/theme.py:load_fonts`, declared to iOS in `ios/AICashier/project.yml`,
and served locally by both web surfaces.  A shop counter may have no internet, and
a silently substituted fallback font breaks the 32-column receipt alignment.

### The knowledge base is committed; the graph is not
*6 September 2026, this folder.*

`docs/kb/` is versioned with the code it describes, so it survives this machine and
travels with the repository.  `graphify-out/` is regenerable from a single command
and is gitignored.  A checker in the test suite keeps the references in these pages
resolving, so the knowledge base fails loudly instead of rotting quietly.
