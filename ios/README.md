# AI Cashier for iPhone

The whole till on a phone: the iPhone camera is the camera. Teach a product
from five views, scan, unknown and ambiguous states, cart, the Thai
restricted-goods gate, a PromptPay QR, receipts in both legal forms, inventory
and takings. No load cell, so there is no weight check; everything else is the
Python till, ported (`ios/AICashier/Sources`).

## Build it

You need a Mac with Xcode 26 and an Apple ID. A free Apple ID is enough to run
it on your own phone; it is not on the App Store.

    brew install xcodegen
    cd ios/AICashier
    xcodegen generate
    open AICashier.xcodeproj

Then, in Xcode:

1. **Xcode → Settings → Accounts**: add your Apple ID.
2. Select the `AICashier` target → **Signing & Capabilities** → tick *Automatically manage signing* and pick your personal team.
3. Plug in the iPhone. On the phone: **Settings → Privacy & Security → Developer Mode** on (iOS 16+), then trust the Mac when asked.
4. Choose the phone as the run destination and press **Run**.

A free Apple ID signs the app for seven days at a time and allows three such
apps per phone; rerun from Xcode to renew. The paid Apple Developer Program
(USD 99/year) removes both limits and unlocks TestFlight and the App Store.

## Try it without a phone

    xcodebuild -scheme AICashier -destination 'platform=iOS Simulator,name=iPhone 17' test

The Simulator has no camera; the app uses the bundled demo image instead
(Shop tab → *Use the demo image*). Calibrate on it once, then SCAN finds the two
demo packets as *unknown*, and *Teach* enrols them.

## What the tests prove

`Tests/Fixtures` is written by `tools/export_fixtures.py` from the Python
implementation. The XCTests assert that the Swift port reproduces it:

- the Core ML embedder's vector for each crop is within cosine 0.98 of the ONNX one;
- the gallery's frozen centre, top-1 and score for every query equal Python's;
- the proposer finds the two packets on the fixture scene within 12 px of the Python boxes, and nothing on the empty mat;
- every PromptPay payload is byte-equal to Python's and the CRC check value holds;
- checkout arithmetic, stock, refusals and the receipt's 32 columns.

## Model

`Resources/MobileNetV3Small.mlpackage` is exported by `tools/export_coreml.py`
(coremltools 9, torch 2.7) from the same torchvision trunk the till runs in
ONNX Runtime, with the ImageNet normalisation folded in. Measured cosine
against the ONNX embedder on synthetic crops: worst 0.9994.

## Privacy

No frame is ever written. The one picture the app keeps is the empty mat,
photographed by staff. `docs/PRIVACY.md` applies.
