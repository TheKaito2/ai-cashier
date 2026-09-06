# State — done, open, and unverifiable

Last reviewed 6 September 2026, at commit `76230d6`, version 4.2.0.

`docs/research/08-action-items.md` is the numbered ledger and stays authoritative.
This page adds what a ledger row cannot say: what is blocked on what, and what
this laptop physically cannot check.

## Shipped

Recognition, till, dashboard, checkout with a real PromptPay payload, legal gating,
enrolment, the research harness E2–E9, the Swift port with nineteen fixture-backed
tests, a Windows installer built by CI, a landing page on Cloudflare, and one
visual identity across all four surfaces.  The Python suite is green; so is the
iPhone suite.

## The one thing everything else waits on

**There are no photographs of real products.**  `research/data/` does not exist.

Blocked by it: a measured τ (so the till must not take real money yet); E1 and
E5 through E8 on anything but rendered images; eleven `\todo{}` holes in
`paper/main.tex`, including five of the six numbers in the abstract and the entire
prose of the Results section; and the "NOT RUN" stub at `paper/tables/e5_openset.tex`.

Not blocked by it, and already done instead: E9 on a public dataset, which is why
`docs/kb/05-research.md` has real numbers to report at all.

## Open

| | What | Where it is written down |
|---|---|---|
| 33 | Rerun E9 with MobileCLIP-B or DINOv2 — the public rows say the encoder is the lever, not the number of views.  Needs the weights downloaded | `docs/research/08-action-items.md` |
| — | **E1 does not exist.**  It is cited in `paper/main.tex`, `research/PROTOCOL.md` and `NOTICE`, but there is no `e1_*` function and no E1 result file.  Either write it or stop citing it | `docs/kb/05-research.md` |
| — | `scanner/ui/main_window.py` has no behavioural tests.  Its decision surface — the sellability gate, the basket weight check, checkout, disambiguation, the scan worker — is only smoke-imported.  The largest coverage gap in the tree | — |
| — | `research/report.py`, `research/bench.py`, `research/capture.py` and seven of the eight `tools/` scripts have no tests at all | — |
| — | `server/services/database.py:get_theme` defaults to `light` while `DEFAULT_SETTINGS` says `dark`.  Harmless today, untested, and exactly the kind of thing that surprises someone later | — |
| — | `detection_confidence` is seeded into the settings table and read by nothing.  A leftover from the version 3 detector | `docs/kb/03-data-and-contracts.md` |
| — | `docs/shots/` has 60 images across 13 directories and no manifest saying which shot shows what or which are current | `docs/kb/04-surfaces.md` |
| — | The Cloudflare account id and account email were committed in `site/.wrangler/cache/wrangler-account.json`.  Untracked and gitignored on 6 September 2026, but **they remain in the git history** of a public repository.  Removing them needs a history rewrite and a force push, which is the owner's call | — |

## What this laptop cannot verify

Stated here so no future session claims otherwise.

- The lgpio HX711 reader on a real Raspberry Pi 5, and scan latency on it.  Every
  latency figure on record is from an M1 and is labelled as such.
- A USB webcam on the Pi, and shadow behaviour under real shop lighting.
- The Windows installer against a real webcam — CI proves it starts, serves and
  completes a checkout, not that it sees anything.
- The iPhone app on a physical phone.  A free Apple ID gives seven-day sideloading
  only; everything on record is from the simulator.
- Anything requiring the camera from an agent's process: the macOS grant is
  per-terminal.

## Version and naming

`VERSION`, the git tag and `ios/AICashier/project.yml` must agree.  They drifted
once — the file said 4.1.1 while the tag and the phone said 4.2.0, so the shipped
installer reported the wrong version.  `docs/DISTRIBUTION.md` puts bumping
`VERSION` as step one of a release for this reason.

`README.md` still carries two different test counts in two sections.  Trust
`python -m pytest tests/ -q` over any number written in prose, including on this page.
