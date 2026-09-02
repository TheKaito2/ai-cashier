# Research dossier — AI Cashier v4

Written 2 Sep 2026. Purpose: give the project the depth a competition judge, a paper reviewer, or a graduate supervisor expects — what the law requires, what the market actually did, how the commercial systems work, what the literature already proved, and where this project can still say something new.

## How to read

| File | Question it answers |
|---|---|
| `01-legal-thailand.md` | Can this be switched on in a Thai shop? What must it refuse to sell, record, or show? |
| `02-legal-software-ip.md` | Can the code, the model, and the dataset be released or sold? |
| `03-market.md` | Who wants this, what happened to the companies that tried, what does a lane cost? |
| `04-how-it-works.md` | The whole checkout stack: barcodes, vision systems, scales, payments, receipts. |
| `05-literature.md` | The 40 papers that matter, what each proved, and the gap left for us. |
| `06-competitions-venues.md` | Where to enter and where to publish, with dates as of Sep 2026. |
| `07-research-roadmap.md` | The ladder from competition entry to master's to PhD questions. |
| `08-action-items.md` | Ranked changes to code, paper and rig that fall out of 01–07, mapped to files. |
| `09-architecture-review.md` | Every design decision in v4 questioned: why it was made, the alternatives with evidence, and what was kept, changed or left to measure on the Pi. |
| `claims.csv` | The evidence ledger. Every number or legal statement in 01–07 has a row. |

## Ledger rules

- Every row has an id (`L`=law, `I`=IP, `M`=market, `H`=how-it-works, `P`=paper, `V`=venue, `A`=architecture). Docs cite rows as `[L03]`.
- `method` is `fetched` (page opened and read), `search-snippet` (from a search engine summary of the page), or `recalled` (from memory, not verified). Treat `recalled` and `low` confidence rows as things to check before quoting.
- Thai statutes are cited from law-firm alerts and official translations, not from the Royal Gazette directly. Section numbers are as those sources give them.
- Market sizes come from paid research firms whose methods differ. They are reported as ranges, never as one number.

## What this dossier is not

It is not legal advice. Nobody who wrote it is a lawyer. Where a line says "must", it means "the cited source says the statute requires". Before any commercial deployment the items in 01 and 02 need a Thai lawyer, and the items marked `recalled` need a primary source.

## Link check, 2 Sep 2026

All 108 ledger URLs were requested with curl. 90 returned 2xx/3xx. 17 returned 403 and one refused the connection; all 18 are sites that block automated clients (BusinessWire, Medium, Siam Legal, Securiti, Baker McKenzie, Lexology, Fortune Business Insights, LendingTree, QSR Magazine, Wiley, ResearchGate, ecti-con2027.org, HoneyKids). Of those, Baker McKenzie [L04] and ecti-con2027.org [V06] were opened and read successfully during research; the rest were seen through search-engine summaries only, which is why their `method` is `search-snippet`. None is known to be dead. Open them in a normal browser before quoting.

## Link check, architecture rows (A01–A21), 2 Sep 2026

16 of 21 returned 200. A11 (raspberrypi.com), A12 (Raspberry Pi forums), A13 and A15 (docs.opencv.org) and A19 (Real Python) returned 403 to curl; A11 and A12 were opened and read during research (`fetched`), the other three are `search-snippet` rows. None is known to be dead.
