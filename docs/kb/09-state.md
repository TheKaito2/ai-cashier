# State — done, open, and unverifiable

Last reviewed 6 September 2026, at commit `ecfedba`, version 4.2.0.

`docs/research/08-action-items.md` is the numbered ledger and stays authoritative.
This page adds what a ledger row cannot say: what is blocked on what, and what
this laptop physically cannot check.

## Shipped

Recognition, till, dashboard, checkout with a real PromptPay payload, legal gating,
enrolment, the research harness E1–E9 with three encoders measured on a public benchmark, the Swift port with nineteen fixture-backed
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
| 40 | **The best encoder is not the shipped one, and now the price is known.**  Under ONNX on an M1: 7.9 ms for the shipped MobileNetV3 at 45.8 %, 203 ms for MobileCLIP2-S0 at 79.9 %, 584 ms for MobileCLIP-B at 89.6 %.  Twenty-six to seventy-four times the cost for the accuracy.  **Half closed on 24 September 2026**: the shipped encoder is 8.2 ms on a real Pi 5 against 7.9 ms on the M1, so the Pi is not "several times slower" as this page assumed.  What the CLIP encoders cost on the Pi is still unmeasured, and now costs nothing but an afternoon.  **Quantisation is not the escape route**: MobileCLIP-S1 fails both INT8 paths, so its float cost is its only cost | `docs/kb/05-research.md` |
| 41 | **Zero-capture enrolment** reaches 82.9 % top-1 on public photographs with MobileCLIP-B — enrolling from the manufacturer's image with no capture at all.  Whether that survives the rig's own lighting and mat is unmeasured, and it would remove the capture step from enrolment entirely | `docs/kb/05-research.md` |
| 37 | **E1 has never run on a photograph.**  `research/experiments.py:e1_closed_set_baseline` exists and is tested, but it needs the twelve legacy products photographed with `capture.py --in-legacy-model`, ultralytics installed, and the gitignored AGPL `models/*.pt` present.  Until then it returns `insufficient_data` and `paper/tables/e1_closed_set.tex` is a "NOT RUN" stub | `docs/kb/05-research.md` |
| — | **The escalation threshold has a curve but not a real one.**  `research/experiments.py:_escalation_sweep` now measures what each baht line buys, and `paper/tables/e6_escalation.tex` prints it — but on synthetic products with three unseen SKUs.  The shape is right; the numbers need the capture session | `docs/kb/06-decisions.md` |
| — | `tools/export_coreml.py` has no test: it needs `.venv-coreml` and coremltools, which CI does not have.  Everything else under `tools/` is now covered | — |

Closed on 6 September 2026: the Cloudflare account id and account email that were
committed in `site/.wrangler/cache/wrangler-account.json` are gone from the whole
history — `git filter-repo` over every ref, force-pushed, tags rewritten, the
release assets intact.  GitHub no longer serves the blob at any old revision.  A
clone or fork taken before that push still contains it, and the pre-rewrite
commit objects may linger on GitHub until it garbage-collects; the account id is
an identifier rather than a credential, so nothing needs rotating.

**A note on the baseline.**  The plan is to retrain the closed-set detector
rather than reuse the version 1 weights, whose training time nobody recorded.
`tools/export_labels.py` turns a capture session into its training set in one
command, so the retrain costs no manual labelling — which is worth knowing
because it changes what E8 is really claiming.  If labelling is free, the
argument is not labour but **recurrence**: adding product twenty-one means
retraining the detector and revalidating the other twenty, against appending
five vectors and touching nothing.  That is the comparison that survives
scrutiny, and it is what E8 should be written to say.

**The second camera is designed, not built.**  `docs/HARDWARE.md` described two
views being combined by track id as though it worked; it does not — the till
reads one camera source and nothing combines two.  Corrected on 19 September 2026,
and the second webcam and powered hub moved to a "not yet" list so nobody buys
hardware the software cannot use.

## Reached the Pi on 24 September 2026

The rig is no longer hypothetical.  A Raspberry Pi 5 8 GB on Bookworm runs the
till from `deploy/install.sh`, autostarted with the desktop, with a Sunplus USB
webcam at `/dev/video0` doing MJPG 1280×720 at 30 FPS — exactly what
`config/settings.json` already asked for.  Scan latency is measured there and
written up in `docs/kb/05-research.md`.

Four things had to be fixed to get there, all of them in the deployment rather
than the software: a systemd user unit that hung off `graphical-session.target`,
which labwc never activates, so it stayed `enabled` and `inactive (dead)` with no
log at all; `pip --quiet` hiding a half-hour install; a Qt platform plugin chosen
from `WAYLAND_DISPLAY` at install time, which is never set over SSH; and a
hardcoded port 8000 already held by an unrelated project on the same Pi.

## What this laptop cannot verify

Stated here so no future session claims otherwise.

- The lgpio HX711 reader on a real Raspberry Pi 5.  No load cell is wired.
- Shadow behaviour under real shop lighting.
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
