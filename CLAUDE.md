# AI Cashier — working notes for agents

A self-checkout till that learns a new product from five photographs instead of a
retrained model.  A camera looks down at a mat; background subtraction finds what
is on it; a frozen MobileNetV3 trunk turns each crop into a vector; cosine
similarity against a handful of enrolled views names it; weight and size break
ties; anything below a measured threshold is refused rather than guessed at.

Group 3, Engineering Design and Innovation, Assumption College Sriracha.
Apache-2.0.  The same algorithm ships five ways: a Qt till, a web dashboard for
the owner, an iPhone app, a landing page, and a Windows installer — plus a
research harness and a paper behind all of it.

## Invariants

These are not preferences.  Breaking one of them breaks something that matters.

1. **τ is measured, never typed.**  `reject_below_cosine` comes from experiment E5
   via `tools/set_threshold.py`.  The `0.75` in `recognition/fusion.py:FusionConfig`
   is a placeholder, and the till must not take real money on it.
2. **No number in the paper is hand-written.**  `research/run.py` writes JSON,
   `research/report.py` writes the LaTeX, `paper/main.tex` only `\input`s it.
3. **`recognition/` writes no file and imports no Qt.**  Enforced by
   `tests/test_privacy.py`.
4. **`server/static/` contains no external URL.**  A shop counter may have no
   internet; `tests/test_pages.py` fails on any `http(s)://`.
5. **Never commit** `models/*.pt` (AGPL YOLO weights, quarantined in `NOTICE`),
   `data/*.sqlite3`, `data/gallery.npz`, `research/data/`, or `graphify-out/`.
6. **Never seed a real `promptpay_id`.**  Absent, the QR is marked not payable.
7. **Never modify `~/Downloads/AI-Cashier-v3`** — it matches the eight submitted
   school reports.  Likewise `docs/shots/aug10` … `docs/shots/aug28`: they are the
   figures in those reports, a record and not a current artefact.
8. **The Python and Swift ports must agree.**  Change one side of the recognition
   or money path and regenerate `ios/AICashier/Tests/Fixtures/fixtures.json` with
   `tools/export_fixtures.py`, then run the Swift tests.
9. **`VERSION`, the git tag and `ios/AICashier/project.yml` must agree.**  Bump
   `VERSION` first when cutting a release.

## Orientation

| Directory | Owns | Start at |
|---|---|---|
| `recognition/` | The algorithm.  No Qt, no database, no disk | `recognition/pipeline.py` |
| `scanner/` | The till a cashier touches | `scanner/ui/main_window.py` |
| `server/` | Records, money, the owner's dashboard | `server/services/checkout.py` |
| `research/` | The experiments | `research/experiments.py` |
| `ios/` | The Swift port of the same algorithm | `ios/AICashier/Sources/Store.swift` |
| `tools/` | Operator scripts: export, calibrate, seed, threshold | — |
| `docs/` | Everything known | `docs/kb/00-index.md` |
| `paper/` | The write-up | `paper/main.tex` |
| `site/`, `build/` | Landing page; Windows installer | `docs/DISTRIBUTION.md` |

Entry point for everything runnable is `app.py`.  Filesystem locations are resolved
in exactly one place, `paths.py`.

## The ten commands

```bash
python -m pytest tests/ -q                  # the suite; CI runs this exact line
python app.py --demo                        # the till, no camera needed
python app.py --server-only                 # dashboard on :8000
python research/run.py --source synthetic   # the experiments
python research/report.py                   # tables and figures into paper/
python tools/set_threshold.py --dry-run     # what E5 says tau should be
cd paper && make                            # build the PDF (tectonic)
python docs/tools/shoot_qt.py               # screenshot the till offscreen
cd site && npx wrangler deploy              # publish the landing page
python tools/check_kb.py                    # keep docs/kb/ references honest
```

Long form, with what success looks like: `docs/kb/08-workflows.md`.

## Where to look next

| Question | Page |
|---|---|
| Where does X live? | `docs/kb/01-repo-map.md` |
| How does a frame become a receipt line? | `docs/kb/02-pipeline.md` |
| What is in the database / what does this route return? | `docs/kb/03-data-and-contracts.md` |
| How do I run or screenshot surface X? | `docs/kb/04-surfaces.md` |
| What have we actually measured? | `docs/kb/05-research.md` |
| Why is it like this? | `docs/kb/06-decisions.md` and `docs/research/09-architecture-review.md` |
| Something is behaving strangely | `docs/kb/07-gotchas.md` |
| What is done, open, or unverifiable here? | `docs/kb/09-state.md` |
| What does this word mean? | `docs/kb/10-glossary.md` |

## Ask the graph before reading twenty files

`graphify` keeps a call-and-import graph of the tree — 1,542 nodes over 108 source
files, built by local tree-sitter parsing at no API cost.  It is in `graphify-out/`,
which is gitignored and regenerable.

```bash
graphify update .                                  # after code changes
graphify query "where is the rejection threshold read" --budget 2000
graphify affected "SkuGallery"                     # what a change would touch
graphify path "MainWindow" "Database"
```

`graphify-out/GRAPH_REPORT.md` names the commit it was built from; compare with
`git rev-parse HEAD` to spot a stale graph.

## Conventions

Comments explain *why*, not what; several modules open with a paragraph of
reasoning and that is deliberate.  Prose in documentation is full sentences.  Code
references in `docs/kb/` are written as a repository-relative path with an optional `:symbol` suffix — never a line
number, because line numbers rot and `tools/check_kb.py` checks these.  Design
tokens change in `docs/DESIGN.md` first, then in the four files that copy them.
