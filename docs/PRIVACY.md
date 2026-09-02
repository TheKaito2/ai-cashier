# Privacy: what the till sees, keeps, and never keeps

Written against Thailand's PDPA B.E. 2562 as summarised in
`docs/research/01-legal-thailand.md` (section 1). Not legal advice.

## What the cameras see

| Camera | Points at | Can it see a person? |
|---|---|---|
| Overhead | the mat, from above | hands only, briefly, while placing items |
| Front (planned) | across the mat at product height | a torso or face at the top of the frame |

## What the software does with a frame

1. The proposer subtracts the empty mat and finds boxes that were not there before.
2. Each box is cropped and turned into a 576-number vector by the embedder.
3. The vector is compared with the gallery. The crop is discarded.
4. Nothing is written to disk. `recognition/pipeline.py` contains no file write;
   `tests/test_privacy.py` fails if one is added.
5. The front camera's frame is blacked out above the mat plane
   (`recognition.proposer.mask_above_mat`) before step 1, so the part of the frame that
   could contain a person is never processed.

There is exactly one process that ever holds a frame: the till. The browser
till that pushed camera frames to the server over a websocket was removed in the
architecture review (`docs/research/09`, D1); the dashboard the shopkeeper opens
on a phone receives product rows and sales totals, never pixels.

The only things that persist are: the gallery of product vectors (`data/gallery.npz`),
the empty-mat photograph taken by staff with nobody in shot (`data/mat_background.png`),
and the sale records (`data/checkout.sqlite3`: what was bought, when, for how much,
with no customer identity). A product vector cannot be inverted into a picture of a
shopper: it was computed from a crop of a packet.

## Legal basis

Shop cameras run under **legitimate interest** (PDPA s.24(5)), the basis every Thai
practitioner we found applies to CCTV. A visible notice is still required
(`docs/notice-th.md`). No **biometric** processing takes place, so PDPA s.26 (sensitive
data, explicit consent) is not engaged. The system must never be extended with face
recognition for loyalty, age estimation or loss prevention without re-doing this
assessment.

## Research captures are different

`research/capture.py` **does** store images. Those sessions are run by the team with
no customers present; the protocol (`research/PROTOCOL.md`) requires any frame with a
person in it to be deleted before the dataset is built.

## Data protection impact assessment (one page)

| | |
|---|---|
| Processing | Live recognition of packaged goods on a checkout mat |
| Data | Video frames in memory only; product embedding vectors; sales without identity |
| Subjects | Shoppers at the till, incidentally; staff enrolling products |
| Purpose | Price the basket; verify it by weight and size |
| Necessity | A camera is the only way to recognise unbarcoded goods; no frame retention is needed for that purpose |
| Retention | Frames: none. Vectors: until the product is removed. Sales: as the Revenue Code requires (5 years for tax records, recalled — verify) |
| Risks | Front camera captures a face (mitigated: masked above mat plane); research capture retains a person (mitigated: protocol deletion rule); future feature creep to biometrics (mitigated: this document, and the notice promises no face recognition) |
| Rights | Nothing identifies a subject, so access/erasure requests have nothing to return; the notice says so |
| Review | Whenever a camera is added or moved, or the PDPC's CCTV guideline (expected H2 2026) is published |
