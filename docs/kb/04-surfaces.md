# The surfaces

Six things get built out of this repository.  All of them wear the same identity,
defined once in `docs/DESIGN.md` and hand-copied into four files — there is no
generator, and that is a deliberate choice recorded in `docs/kb/06-decisions.md`.

## 1. The till — PySide6, dark, touch

The thing a cashier uses.  Entry: `python app.py`, which starts uvicorn on a
daemon thread and the Qt window in the same process.

| | |
|---|---|
| Entry | `app.py:main` |
| Window | `scanner/ui/main_window.py:MainWindow` |
| Theme | `scanner/ui/theme.py:TOKENS`, QSS built by `string.Template`; `scanner/ui/theme.py:load_fonts` registers the bundled Plex faces |
| Flags | `--server-only`, `--lan`, `--demo`, `--fullscreen`, `--self-test`, `--scale {simulated,hx711,none}` |
| Screenshots | `docs/tools/shoot_qt.py`, offscreen, into `docs/shots/v4d/` |

The camera is the hero: boxes and prices are painted onto the frame itself, the
viewfinder border carries the state colour, and the cart is a paper receipt strip
with a torn bottom edge that grows line by line.  `--self-test` runs the whole
recognition path headless against `docs/assets/demo_frame.jpg` and exits non-zero
if it finds fewer than two products — this is what the Windows smoke test runs
against the frozen executable.

## 2. The owner's dashboard — FastAPI + four static pages

Read-mostly.  Served by the same process as the till, or alone with
`--server-only`.  Light paper by default, dark available, theme persisted to the
shop settings and synchronised across tabs.

| Page | What it shows |
|---|---|
| `server/static/index.html` | Overview: till state pill, headline figures, a receipt tear |
| `server/static/inventory.html` | The ledger, stock cover chart, restock modal — the only page that writes |
| `server/static/admin.html` | Takings by day, sales by hour, best sellers, recent sales |
| `server/static/monitor.html` | Status board: events by kind, refusals by day, the event log |

One stylesheet, `server/static/css/style.css`.  Six JavaScript modules and no
libraries: `server/static/js/mast.js` renders the single masthead,
`server/static/js/theme.js` the light/dark switch, `server/static/js/charts.js`
draws every chart as inline SVG assembled as an HTML string, and
`server/static/js/admin.js`, `server/static/js/inventory.js` and
`server/static/js/monitor.js` are one per page.

Charts are strings, not DOM nodes built with `createElementNS`, because
`tests/test_pages.py` refuses any `http(s)://` in the static folder — the shop
counter may have no internet, and the namespace URL would have tripped the test.
That is a constraint, not an accident.

## 3. The iPhone app — SwiftUI, GRDB, Core ML

A second implementation of the algorithm; see the port table in
`docs/kb/02-pipeline.md`.  Built with xcodegen — there is no checked-in Xcode
project, so `xcodegen generate` comes before every build, and resources added
after generation will not be in the bundle.

| | |
|---|---|
| Entry | `ios/AICashier/Sources/AICashierApp.swift` |
| Shared state | `ios/AICashier/Sources/Store.swift:Store` |
| Screens | `ios/AICashier/Sources/UI/TillView.swift`, `ios/AICashier/Sources/UI/PaymentView.swift`, `ios/AICashier/Sources/UI/EnrolView.swift`, `ios/AICashier/Sources/UI/ShopViews.swift` |
| Theme | `ios/AICashier/Sources/Theme.swift` |
| Definition | `ios/AICashier/project.yml` — GRDB 7, iOS 17, whole-module `-O` |
| Launch flags | `--demo-seed`, `--demo-scan`, `--tab` |
| Build guide | `ios/README.md` |

`SWIFT_COMPILATION_MODE: wholemodule` and `-O` are not cosmetic: the pure-Swift
proposer takes roughly eighteen seconds per frame in an unoptimised Debug build.

Nineteen XCTest cases across seven classes, and every one of them asserts the
Swift port reproduces a Python-generated fixture.

## 4. The landing page — an assets-only Cloudflare Worker

`site/public/index.html` plus `site/public/style.css`, seven images and the same
seven Plex faces served locally.  `site/wrangler.jsonc` declares an assets-only
Worker named `ai-cashier-site`: no Worker script, no bindings, no secrets.  Deploy
with `npx wrangler deploy` from `site/`.

The download button points at GitHub's `releases/latest/download/` URL, so cutting
a release updates the page without touching it.  A small inline script fetches the
release metadata to fill in the version, size and date, and falls back to "see
GitHub releases" if the fetch fails.

## 5. The Windows installer

Tag `v*` → `.github/workflows/release.yml` on `windows-latest` → PyInstaller
one-folder build from `build/windows/AICashier.spec` → smoke test → Inno Setup
(`build/windows/installer.iss`) → `AI-Cashier-Setup-Windows.exe` and a `.sha256`
sidecar attached to the release.

`PrivilegesRequired=lowest`, so it installs per user with no UAC prompt.  The
installer is unsigned, and `docs/DISTRIBUTION.md` explains why.  The spec
`collect_all`s `onnxruntime`, `cv2` and `uvicorn` because all three load parts of
themselves by name at runtime, and bundles the model, `config/settings.json`,
`data/products.json`, the demo images, all of `server/static/` and `assets/fonts/`.

`build/windows/smoke.ps1` is the gate: it runs the frozen executable with
`--self-test`, greps the log for `self-test ok`, then starts `--server-only`, waits
for `/api/system-status`, checks three pages return 200 and drives a real checkout
through the API.

## 6. The school deliverable

Easy to forget, because it is not part of the product.  `docs/tools/make_reports.py`
builds the eight EDI progress reports from `docs/tools/report_content.py`;
`docs/tools/measure.py` counts one version against another;
`docs/tools/compare_databases.py` is the script that found the v2 price
disagreements; `docs/tools/shoot_term.py` renders `docs/evidence/*.txt` to images.
The dated screenshot sets `docs/shots/aug10` through `docs/shots/aug28` are the
figures in those reports and should be treated as a submitted record — do not
regenerate them.  `docs/shots/README.md` says what every image shows and which
sets are still current.
