# Knowledge base — start here

This folder exists so that a person or an agent picking the project up cold does
not have to re-derive what is already known.  It holds the things the source code
cannot say for itself: why a decision was taken, what a number was measured to be,
what broke once and how, and what is still blocked on what.

Read `CLAUDE.md` at the repository root first — it is short, it is loaded
automatically by Claude Code, and it carries the invariants.  Come here when you
need depth.

## The pages

| Page | Read it when |
|---|---|
| `docs/kb/01-repo-map.md` | You are looking for where something lives |
| `docs/kb/02-pipeline.md` | You are changing recognition, or the Swift port |
| `docs/kb/03-data-and-contracts.md` | You are touching the database, a settings key, a REST route or a result JSON |
| `docs/kb/04-surfaces.md` | You are working on the till, the dashboard, the phone, the site, the installer or the school reports |
| `docs/kb/05-research.md` | You are running an experiment, reading a result, or writing the paper |
| `docs/kb/06-decisions.md` | You are about to change something and want to know why it is the way it is |
| `docs/kb/07-gotchas.md` | Something is behaving strangely.  Check here before debugging |
| `docs/kb/08-workflows.md` | You need the exact command for a task |
| `docs/kb/09-state.md` | You want to know what is done, what is open, and what this laptop cannot verify |
| `docs/kb/10-glossary.md` | A term in the code or the paper is unfamiliar |

## What is authoritative where

This knowledge base does not restate documents that already exist.  When the two
disagree, the document named below wins and this folder is the thing to fix.

| Subject | Authority |
|---|---|
| Colour and type tokens | `docs/DESIGN.md` |
| Thai law, market, literature, venues, roadmap | `docs/research/01-legal-thailand.md` … `docs/research/07-research-roadmap.md` |
| Every external claim, with its source and date | `docs/research/claims.csv` |
| Architecture decisions D1–D19 and faults F1–F5 | `docs/research/09-architecture-review.md` |
| Numbered action items and their status | `docs/research/08-action-items.md` |
| The physical rig | `docs/HARDWARE.md` |
| What the cameras see and keep | `docs/PRIVACY.md` |
| Releases and the landing page | `docs/DISTRIBUTION.md` |
| The capture session | `research/PROTOCOL.md` |
| Building and running the iPhone app | `ios/README.md` |

## How code is referenced here

A reference is written as inline code: a repository-relative path, optionally a
colon and a symbol name — `recognition/gallery.py:project`, `docs/DESIGN.md`.

Never a line number.  Line numbers rot on the next edit; symbol names survive
one.  `tools/check_kb.py` walks every page in this folder and the root
`CLAUDE.md`, asserts each path exists and each named symbol still appears in its
file, and `tests/test_kb_links.py` runs it with the rest of the suite.  A rename
that orphans a reference here fails CI instead of quietly misleading the next
session.

## The graph

`graphify` builds a call-and-import graph of the whole tree — 1,542 nodes and
3,296 edges over 108 source files, from local tree-sitter parsing at no API cost.
It lives in `graphify-out/`, which is gitignored: it is regenerable, and it is
specific to the machine that built it.

```
graphify update .                    # after code changes; no API key needed
graphify query "how does a frame become a cart line" --budget 2000
graphify affected "SkuGallery"       # what breaks if this changes
graphify path "MainWindow" "Database"
graphify god-nodes --top 20          # the architectural hubs
```

`graphify-out/wiki/index.md` is the crawlable entry point; `graphify-out/GRAPH_REPORT.md`
records the commit the graph was built from, so a stale graph is detectable with
`git rev-parse HEAD`.

Two limits worth knowing.  Community names come from hub symbols, not from a
language model, because no `ANTHROPIC_API_KEY` is set on this machine — the graph
is complete, only the cluster names are plainer than they could be.  And Swift
framework imports (`Foundation`, `SwiftUI`, `UIKit`, `XCTest`) collapse into a
single node each across files, which the extractor warns about; it affects only
those import nodes, not our own symbols.
