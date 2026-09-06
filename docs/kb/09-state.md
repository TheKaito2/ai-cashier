# State — done, open, and unverifiable

Last reviewed 6 September 2026, at commit `ecfedba`, version 4.2.0.

`docs/research/08-action-items.md` is the numbered ledger and stays authoritative.
This page adds what a ledger row cannot say: what is blocked on what, and what
this laptop physically cannot check.

## Shipped

Recognition, till, dashboard, checkout with a real PromptPay payload, legal gating,
enrolment, the research harness E1–E9, the Swift port with nineteen fixture-backed
tests, a Windows installer built by CI, a landing page on Cloudflare, and one
visual identity across all four surfaces.  The till's decision surface - the sellability gate, the basket weight
check, checkout, disambiguation and the scan worker - is covered behaviourally by
`tests/test_main_window.py`.  210 Python tests are green; so are the iPhone ones.

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
| 37 | **E1 has never run on a photograph.**  `research/experiments.py:e1_closed_set_baseline` exists and is tested, but it needs the twelve legacy products photographed with `capture.py --in-legacy-model`, ultralytics installed, and the gitignored AGPL `models/*.pt` present.  Until then it returns `insufficient_data` and `paper/tables/e1_closed_set.tex` is a "NOT RUN" stub | `docs/kb/05-research.md` |
| — | `tools/export_embedder.py`, `tools/export_coreml.py`, `tools/export_fixtures.py`, `tools/seed_demo.py` and `tools/make_marker.py` still have no tests — each writes into the repository, so testing them needs the output paths made injectable first | — |
| — | `tools/seed_demo.py` writes the mat and the gallery to the repository's own `data/` rather than to `paths.py:data_dir`, so it ignores `AI_CASHIER_DATA`.  Harmless for a dev demo, wrong for a frozen install, and it is why the script has no test | — |

Closed on 6 September 2026: the Cloudflare account id and account email that were
committed in `site/.wrangler/cache/wrangler-account.json` are gone from the whole
history — `git filter-repo` over every ref, force-pushed, tags rewritten, the
release assets intact.  GitHub no longer serves the blob at any old revision.  A
clone or fork taken before that push still contains it, and the pre-rewrite
commit objects may linger on GitHub until it garbage-collects; the account id is
an identifier rather than a credential, so nothing needs rotating.

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
