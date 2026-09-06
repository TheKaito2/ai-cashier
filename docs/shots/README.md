# Screenshots — what each one shows, and which are current

Sixty-one images in thirteen directories, accumulated over four months.  Without
this page it is impossible to tell which are evidence and which are stale, so the
rule is stated once here:

- **`aug10` … `aug28` are a submitted record.  Do not regenerate them.**  They are
  the figures inside the eight EDI progress reports, built by
  `docs/tools/make_reports.py` from the list in `docs/tools/report_content.py`.
  Replacing one would change a document that has already been handed in.
- **`v4` … `v4d` and `ios` are the current surfaces.**  Regenerate these freely;
  `v4d` and `ios` are what the landing page and the README use today.

## The submitted record

Generated during versions 2 and 3.  Terminal images come from
`docs/tools/shoot_term.py` rendering the matching transcript in `docs/evidence/`.

| Directory | Shows | Notes |
|---|---|---|
| `aug10` | The version 2 baseline: inventory, cart, analytics, monitor, the PyQt scanner, and the file tree before the merge | `06-tree-before.png` renders `docs/evidence/aug10-tree-before.txt` |
| `aug14` | The tree after the merge, the price disagreements between the two databases, the route list, and the restored checkout page | `02-price-drift.png` is the output of `docs/tools/compare_databases.py` |
| `aug17` | One process instead of two — the server and the till in a single program | Renders `docs/evidence/aug17-single-process.txt` |
| `aug19` | The till after its first redesign: idle, with a cart, and at payment | |
| `aug21` | The landing page, dark and light, viewport and full page | |
| `aug24` | Inventory and analytics in both themes | |
| `aug26` | The test suite passing | Renders `docs/evidence/aug26-tests.txt` |
| `aug28` | The version 3 finish: cart, browser till, monitor, an end-to-end run, the final till, and the measurement table | `04-endtoend.png` and `06-measures.png` render the matching `docs/evidence/` files |

## The current surfaces

| Directory | Shows | Made by |
|---|---|---|
| `v4` | The first version 4 till — scanning, an unknown item, the enrol dialog — plus landing, inventory and analytics | `docs/tools/shoot_qt.py`, `docs/tools/shoot_web.py` |
| `v4b` | The PySide6 port of the till, and enrolment | `docs/tools/shoot_qt.py` |
| `v4c` | The till, enrolment and payment before the identity redesign | `docs/tools/shoot_qt.py` |
| `v4d` | **Current.**  The receipt-and-instrument till (idle, enrol, payment, paid receipt), and the dashboard: overview light and dark, inventory, analytics light and dark, monitor, plus the landing page | `docs/tools/shoot_qt.py` and `docs/tools/shoot_web.py` |
| `v4d/m` | The same dashboard pages at a 390-pixel phone width — overview, inventory, analytics, and the site in dark | `SHOT_W=390 SHOT_H=844 python docs/tools/shoot_web.py` |
| `ios` | The iPhone app: a scan in progress, detections on the frame, the till, takings, inventory, and the till in dark | `xcrun simctl io booted screenshot`, with `--demo-seed` and `--demo-scan` |

## Where they are used

- `site/public/img/` is copied from `v4d` (till, enrol, payment, paid, dashboard)
  and from `ios` (the phone).  It is a copy, not a link — the Worker serves only
  what is inside `site/public/`.
- `README.md` and `docs/DISTRIBUTION.md` link to `v4d`.
- `docs/tools/report_content.py` names every `aug*` image, one per report.

Regenerating the current sets is one command each; see `docs/kb/08-workflows.md`.
