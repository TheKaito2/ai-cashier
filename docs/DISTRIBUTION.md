# Distribution: how the installers and the page are made

## Where things live

| Thing | Where | How it gets there |
|---|---|---|
| Source | https://github.com/TheKaito2/ai-cashier | `git push` |
| Windows installer | GitHub Releases, asset `AI-Cashier-Setup-Windows.exe` (+ `.sha256`) | `.github/workflows/release.yml` on a `v*` tag |
| Landing page | Cloudflare Worker `ai-cashier-site` (static assets) | `cd site && npx wrangler deploy` from a logged-in machine |
| iPhone app | built by the user with Xcode | `ios/README.md` |
| Raspberry Pi | the checkout itself | `docs/HARDWARE.md` |

The page's download button points at
`https://github.com/TheKaito2/ai-cashier/releases/latest/download/AI-Cashier-Setup-Windows.exe`,
which always resolves to the newest release, and the page asks the GitHub API
for the tag, size and date. Nothing on the page needs editing for a release.

## Cutting a release

1. Bump `VERSION` (one place; `app.py`, the dashboard, the installer and the tests read it).
2. `python -m pytest tests/ -q` green; `pyinstaller --noconfirm --workpath build/pyinstaller --distpath dist build/windows/AICashier.spec` on the Mac and `dist/AICashier/AI\ Cashier --self-test` as a rehearsal of the spec.
3. Commit, `git tag -a vX.Y.Z -m "..."`, `git push origin main vX.Y.Z`.
4. `gh run watch` the *release* workflow: it freezes on `windows-latest`, runs `build/windows/smoke.ps1` on the frozen exe (self-test on the bundled demo frame, then the dashboard answering and a checkout going through), builds the Inno Setup installer, hashes it and attaches both files to the release.
5. `curl -sI …/releases/latest/download/AI-Cashier-Setup-Windows.exe | head -1` → `HTTP/2 302`.

A Windows exe cannot be built on a Mac; PyInstaller does not cross-compile. The
runner image (Windows Server 2025) has Python 3.12 and Inno Setup 6.7 preinstalled.

## What the installer contains

A one-folder PyInstaller build (windowed, no console): the till, the dashboard
server, ONNX Runtime with the 576-d MobileNetV3-Small embedder, OpenCV, Qt.
About 400 MB unpacked. It installs per user under
`%LOCALAPPDATA%\Programs\AI Cashier` with no admin prompt, and keeps its data
(database, gallery, settings, logs) in `%LOCALAPPDATA%\AI Cashier`. The Start
menu gets *AI Cashier* and *AI Cashier (demo, no camera needed)*.

On Windows the camera opens through DirectShow (the default MSMF backend can
take many seconds to open a webcam); `lock_exposure` uses DirectShow's
semantics, which differ from the Pi's V4L2, and stays off by default.

## SmartScreen

The installer is not code-signed. Windows shows "Windows protected your PC" the
first time; the user clicks **More info → Run anyway**. Signing was looked at
and left out: Azure Trusted Signing is open only to individuals in the US,
Canada, the EU and the UK, and a traditional OV certificate costs more per year
than the rig. If the project ever ships to strangers at scale, that is the
first thing to revisit. Until then the page says exactly what the prompt means
and where the only trustworthy download is.

## The landing page

`site/public` is plain HTML and CSS; `site/wrangler.jsonc` makes it an
assets-only Cloudflare Worker (Cloudflare's current path for a static site;
Pages is the legacy one, same dashboard). Deploy from a machine where
`wrangler whoami` shows the account. No secrets live in the repository and CI
does not deploy the page; it changes rarely and a local deploy takes seconds.

## The iPhone app

There is no download. A free Apple ID cannot distribute an app, only install it
on the developer's own phone from Xcode, for seven days at a time. The page and
`ios/README.md` say so. The paid Apple Developer Program (USD 99/year) would
allow TestFlight and the App Store; the app has no dependency that would block
that (SwiftUI, GRDB, Core ML, no private API).
