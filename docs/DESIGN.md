# Design: receipt & instrument

The till is a measuring instrument (a camera, a scale, a ruler) that ends every
sale by printing a receipt. Those two artefacts, the viewfinder and the receipt,
are the only visual motifs. Nothing else decorates.

Four surfaces share one identity: the Qt till (dark, customer-facing), the
owner dashboard (light by default, dark available), the iPhone app (follows the
phone), and the landing site. The tokens below are copied by hand into
`scanner/ui/theme.py`, `server/static/css/style.css`,
`ios/AICashier/Sources/Theme.swift` and `site/public/style.css`. There is no
generator; change the table, then the four files.

## Colour

| token | paper (light) | instrument (dark) | used for |
|---|---|---|---|
| bg | `#F3F1EC` | `#131110` | page / panel ground. Thermal-paper grey-white, deliberately not cream |
| surface | `#FBFAF7` | `#1C1917` | cards, table rows, the receipt strip |
| surface-2 | `#EAE7E0` | `#262220` | hover, inputs, secondary buttons |
| line | `#D6D2C9` | `#3A342F` | rules and borders |
| ink | `#1A1714` | `#F2EDE4` | text |
| muted | `#6B655C` | `#A39B8F` | secondary text, eyebrows |
| accent | `#FF7A18` | `#FF7A18` | the one accent: primary action, scanning state, brand mark |
| accent-ink | `#B4500A` | `#FFA45C` | accent used as text on the ground |
| on-accent | `#1A1714` | `#1A1714` | text on an accent fill |
| ok | `#1E8E4E` | `#3DD68C` | ready to pay, paid, in stock |
| warn | `#C27C0E` | `#F2B33D` | low stock, needs staff |
| bad | `#C93A3E` | `#F0575B` | refused, error, clear |
| info | `#2F6FD6` | `#6FA8FF` | ambiguous ("which one?") |
| viewfinder | `#0A0908` | `#0A0908` | behind the camera frame |

Semantic colours carry state, never decoration: scanning = accent, unknown =
accent box with an *Enrol* tab, ambiguous = info, ready to pay = ok.

## Type

- **IBM Plex Sans Thai** — display and body. One family covers Latin and Thai,
  so a Thai product name sets in the same face as the price beside it.
  Weights 400 / 500 / 600 / 700.
- **IBM Plex Mono** — every readout, price column, eyebrow, and the receipt
  itself. Always `tabular-nums`. Weights 400 / 500 / 600. Plex Mono has no Thai
  glyphs, so the stack is `"IBM Plex Mono", "IBM Plex Sans Thai", monospace`.
- Scale: 12 / 14 / 16 / 20 / 28 / 44 / 64. Eyebrows are 12 mono, uppercase,
  letter-spaced 0.08em.

Files: `assets/fonts/*.ttf` (Qt, iOS), `server/static/fonts/*.woff2`
(dashboard), `site/public/fonts/*.woff2` (site). SIL OFL 1.1; the licence
travels with the files.

## Layout

- **Till.** The camera is the hero: a full-bleed viewfinder with the detection
  boxes and name/price labels drawn on the frame. To its right, the receipt
  strip: a paper-coloured column in mono, 32 characters wide, that grows a line
  at a time and ends in a torn edge. The total is the largest number on screen.
  One primary button whose colour is the state. Instrument readouts (weight,
  mat, frames agreed) sit in a thin mono status rail.
- **Dashboard.** A ledger: masthead, figures set like receipt totals, one wide
  column (max 1120 px), inline-SVG charts drawn from the existing endpoints.
  Light by default because a shop is bright; dark for the evening count.
- **iPhone.** The same receipt cart and the same overlay boxes; native tab bar.
- **Site.** Receipt paper with the till's own screenshots.

Touch targets stay at 56 px minimum (84 px for the primary action) on the till
and the phone.
