# Glossary

Terms used by the code, the paper and the dossier, in the sense this project means
them.

**SKU** — a stock-keeping unit: one product as the shop sells it.  The id is a slug
(`lays-flat-original`), used as a folder name, a gallery key and a database primary
key.  Two flavours of the same crisp are two SKUs.

**Enrolment** — teaching the till a product by photographing it k times.  No weights
change; the vectors are appended to the gallery.  `recognition/pipeline.py:enrol`.

**Gallery** — the store of reference vectors, k per SKU.  `recognition/gallery.py:SkuGallery`.
Persisted to `data/gallery.npz`.

**View** — one photograph of a product used for enrolment.  The protocol takes
fourteen and enrols from the first five, so the rest can be scored on.

**Probe** — a held-out photograph used to test recognition.  A product with no
held-out views cannot be scored.

**Proposal** — a candidate box: somewhere on the mat that is not mat.  Produced by
`recognition/proposer.py:propose`, class-agnostically — the proposer never knows
what a thing is, only that it is there.

**Prototype** — the mean of a SKU's enrolled vectors.  Scoring against the
prototype is an alternative to scoring against the nearest single view; the till
uses nearest-view, and E2 reports both.

**Centre** — the mean of every enrolled vector, subtracted before scoring.
Frozen once four SKUs exist so that later enrolments cannot move earlier scores.

**τ (`reject_below_cosine`)** — the abstention threshold.  Below it the till says it
does not know rather than naming the nearest product.  Measured by
`recognition/calibration.py:pick_threshold`, never chosen by feel.

**Abstention** — the till refusing to name something.  Logged as an event, because
how often it happens is a result.

**Open-set recognition** — the problem of being tested on classes that were never
enrolled.  A closed-set classifier must answer with one of its classes; an open-set
system may decline.  This is what makes a shop realistic: the world contains
products the till has never met.

**AUROC** — the probability that a known product scores higher than an unknown one.
0.5 is a coin.  `recognition/calibration.py:auroc`.

**FPR@95TPR** — how many unknown products slip through when you insist on accepting
95 % of the known ones.  The number that matters operationally, and usually the
less flattering one.

**MSP** — maximum softmax probability, the classifier's own confidence, used as an
open-set baseline.  **Energy score** — a free-energy alternative that tends to
separate better.  Both in `recognition/calibration.py`.

**Seen / unseen split** — which products a representation may learn from and which
only ever get enrolled.  `research/dataset.py:make_split`.  Few-shot claims are
only interesting on the unseen half.

**Iconic image** — the manufacturer's pack shot, as opposed to a photograph of the
product in a shop.  Enrolling from one is "zero-capture enrolment".

**Fusion** — combining appearance, mass and size into one decision by summing log
likelihoods.  `recognition/fusion.py:fuse`.

**Basket check** — weighing the whole basket against the sum of what was rung up,
with a tolerance that grows in quadrature with the number of items.
`recognition/fusion.py:verify_basket`.  It returns nothing rather than a false
verdict when a check cannot be performed.

**Track** — one physical item followed across frames so it is charged once.
`recognition/tracker.py:CentroidTracker`.

**Metrology** — turning pixels into millimetres using printed ArUco markers of known
size.  `recognition/metrology.py`.

**Verification scale** — a scale used to check a transaction rather than to price
by weight.  The distinction keeps the rig outside the Weights and Measures Act;
see `docs/research/01-legal-thailand.md`.

**PromptPay** — Thailand's national QR payment standard, an EMVCo merchant-presented
payload.  `server/services/promptpay.py`.

**Abbreviated tax invoice** — what a VAT-registered Thai shop must print instead of a
plain receipt.  Switched by the `vat_registered` setting.

**Synthetic source** — rendered packets from `tests/synthetic.py`.  They prove the
harness runs.  They are not evidence about real products, and every table generated
from them says so in the file.
