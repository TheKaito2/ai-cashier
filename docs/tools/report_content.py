"""Content for the eight EDI progress reports (10-28 August 2026)."""

TEAM = "Punn, Pleum, Athens, Kit, Bible, Pokpong"
GROUP = "Group 3 (G12IS)"
TITLE = "Project Progress Report: AI Cashier System (Version 3 Upgrade)"

DATES = ["10/8/2026", "14/8/2026", "17/8/2026", "19/8/2026",
         "21/8/2026", "24/8/2026", "26/8/2026", "28/8/2026"]
SHOT_DIRS = ["aug10", "aug14", "aug17", "aug19", "aug21", "aug24", "aug26", "aug28"]

GOAL = (
    "A self-checkout cashier system that recognises products with a camera using a YOLO "
    "object-detection model instead of barcodes, adds them to a cart, calculates the total, "
    "and records every sale to a web dashboard so the shop owner sees sales and stock in real "
    "time. Version 1 is built and demonstrated. This phase has two halves: a hardware upgrade "
    "(larger touchscreen, a second front-facing camera so tall items such as water bottles and "
    "cans can be identified, and load-cell weight verification), and a software rebuild that "
    "turns the two-program hybrid into a single application with one product database."
)
AUDIENCE = (
    "Small and medium retail shops, school canteens and campus stores that lose time and money "
    "to slow queues, mis-typed prices and failed barcode scans - and the shop owners who need "
    "live sales and stock figures without manual counting."
)

# C = Completed, P = In Progress, N = Not Started, B = Blocked. One letter per report date.
STATUS = {"C": "Completed", "P": "In Progress", "N": "Not Started", "B": "Blocked"}
TASKS = [
    ("Dataset collection and labelling of snack products",                 "Athens",       "CCCCCCCC"),
    ("YOLO model training and accuracy evaluation (v1)",                   "Kit",          "CCCCCCCC"),
    ("PyQt cashier application and web backend (v1)",                      "Kit",          "CCCCCCCC"),
    ("Raspberry Pi assembly, aluminium stand and camera mount (v1)",       "Pokpong",      "CCCCCCCC"),
    ("Code audit of the version 1 hybrid build",                           "Kit / Pleum",  "PCCCCCCC"),
    ("Merge the two product databases into one file",                      "Kit",          "NPCCCCCC"),
    ("Collapse the two-process hybrid into one application",               "Kit",          "NNPCCCCC"),
    ("Rebuild the till screen for the larger touchscreen",                 "Punn",         "NNNPCCCC"),
    ("Landing page for the web dashboard",                                 "Pleum",        "NNNNPCCC"),
    ("Inventory and analytics page redesign",                              "Pleum",        "NNNNNPCC"),
    ("Automated test suite over the checkout path",                        "Pleum",        "NNNNNNPC"),
    ("Setup guide and one-command run",                                    "Kit / Pleum",  "NNNNNNNC"),
    ("Fit the larger touchscreen to the stand",                            "Punn",         "PPPPCCCC"),
    ("Second front-facing camera for water bottles and cans",              "Pokpong",      "PPPPPPCC"),
    ("Dataset collection and retraining for bottles and cans",             "Athens",       "NNNPPPPP"),
    ("Load-cell weight verification (HX711) - parts not ordered",          "Bible",        "BBBBBBBB"),
    ("Security hardening: staff login, transaction log, mismatch alerts",  "Kit / Athens", "NNNNNPPP"),
]

HELP_HARDWARE = (
    "Purchase approval and ordering for the HX711 amplifier and load cells, a second USB webcam "
    "plus a powered USB hub for it, and a stable 5V/3A power supply. Workshop time and teacher "
    "guidance for mounting the front camera bracket and the weighing plate on the aluminium frame."
)

REPORTS = [
    # ---------------------------------------------------------------- 10 Aug
    dict(
        recent=(
            "We demonstrated the full version 1 loop end to end: the camera detects the snack, the "
            "desktop application builds the cart and takes payment, and the web backend updates the "
            "sales record and the stock count. Before adding any version 2 hardware we then read "
            "through the whole repository, because the same feature appeared to exist in more than "
            "one place. This report is the baseline the rest of the upgrade is measured against."
        ),
        wins=(
            "Version 1 works: the trained model separates snack flavours that look almost identical "
            "on the shelf, and detecting products by vision removed the failed-scan problem that "
            "started the project. The audit was the more useful result. In 8,834 lines of Python "
            "across 59 files we found: two copies of the till screen (1,040 and 1,245 lines) that "
            "have to be edited in parallel; three copies of the trained weights, where the chips "
            "model used by the web server is a different file from the one used by the scanner; two "
            "separate product databases with different formats; two pages that exist as files but "
            "have no address, so nothing can reach them; a configuration file that hard-codes a "
            "Windows path from one member's laptop; and no automated tests at all."
        ),
        bottleneck=(
            "The load cells and HX711 amplifier have not been ordered, so all weight-verification "
            "work is blocked. The single overhead camera still struggles with tall items such as "
            "bottles and cans, because from above they are mostly a cap. On top of those, the code "
            "itself has become a bottleneck: the larger touchscreen needs a new layout, and with two "
            "copies of the till screen that layout would have to be written twice and kept in step."
        ),
        solution=(
            "Submit the parts list and order the HX711 and load cells so calibration can start as "
            "soon as they arrive. Before writing any new feature, consolidate: one product database, "
            "one copy of the weights, one till screen, and one command to start the system. Only "
            "then fit the larger screen and add the second camera, so each change is made once."
        ),
        help=HELP_HARDWARE + " We also need the correct shelf prices confirmed, because the two "
             "product files in the current build do not agree with each other.",
        next=[
            "Merge the two product databases into one file and decide which price is correct where "
            "they disagree.",
            "Delete the duplicated till screen, the backup files and the path-hunting setup scripts, "
            "and give the two orphaned pages an address.",
            "Replace the two-program launcher with a single application, then rebuild the till screen "
            "for the larger touchscreen.",
        ],
        shots=[
            ("01-inventory-baseline.png", "Version 1 inventory page. This is what the root address showed a visitor: the stock table."),
            ("02-cart-baseline.png", "Version 1 cart page, waiting for the desktop scanner to push items to it over HTTP."),
            ("05-pyqt-scanner-baseline.png", "Version 1 till screen. Two accent colours, white scrollbars on a dark background, and labels clipped mid-word."),
            ("06-tree-before.png", "The repository on 10 August: 59 files, three copies of the trained weights, two product databases."),
        ],
    ),
    # ---------------------------------------------------------------- 14 Aug
    dict(
        recent=(
            "Consolidation. The two product databases were merged into one file, the duplicated till "
            "screen and the backup files were deleted, the trained weights were reduced to a single "
            "copy, and the two pages that had no address were given one. The project was also "
            "restructured into two clear folders, server and scanner, with the shared data outside "
            "both of them."
        ),
        wins=(
            "Comparing the two product files line by line found a defect we would not have caught in "
            "a demonstration. Five of the fourteen products were priced differently in the two files: "
            "Lay's Nori Seaweed was 25 baht in the file the payment endpoint uses and 20 baht in the "
            "file the scanner displays, and Tasto Original was 22 against 20. The customer would have "
            "been shown one price on the screen and charged another. Two more products, Atreus and "
            "Enter, existed only in the scanner's file, so the server could never have sold them. The "
            "merged file keeps the server prices, because those are the ones the till actually charges, "
            "and recovers the two missing products. We also found the baht symbol in the settings had "
            "been saved through the wrong text encoding and was displaying as three Thai letters."
        ),
        bottleneck=(
            "Deciding which of the two prices was correct is not a programming question, and we do not "
            "want to guess before the demonstration. The two files also stored products in different "
            "shapes - one a flat list, the other grouped by category with different field names - so "
            "the scanner had to be rewritten to read the merged file. Load cells are still not ordered."
        ),
        solution=(
            "We kept the server price in every case of disagreement, on the grounds that it is the price "
            "the payment endpoint has been charging, and recorded the full comparison so a teacher can "
            "check it. The scanner now reads the same file as the dashboard through the same code, so "
            "the two can no longer drift apart again."
        ),
        help="Confirmation of the correct shelf price for the five products where the two files "
             "disagreed. " + HELP_HARDWARE,
        next=[
            "Replace the two-program launcher with a single application that starts the web server "
            "inside the same process as the till window.",
            "Rebuild the till screen for the larger touchscreen once the screen is fitted.",
            "Begin collecting and labelling the bottle and can dataset for the second camera.",
        ],
        shots=[
            ("02-price-drift.png", "The two product files compared. Five products were priced differently and two existed on only one side."),
            ("01-tree-after.png", "After consolidation: one database, one copy of the weights, one till screen, two clear folders."),
            ("03-routes.png", "Route audit. Two pages that returned 404 in version 2 now answer, and the trained weights are no longer downloadable."),
            ("04-checkout-page-restored.png", "The browser till page. It had existed as a file since version 1 but no address pointed at it."),
        ],
    ),
    # ---------------------------------------------------------------- 17 Aug
    dict(
        recent=(
            "The hybrid is now one program. A single entry point starts the web server on a background "
            "thread inside the same process as the till window, waits until the server answers, and then "
            "opens the window. The old launcher, the path-hunting setup script and four shell and batch "
            "start files were deleted."
        ),
        wins=(
            "Starting the system went from two commands in a fixed order, with a five-second wait "
            "between them and a configuration file holding an absolute path from one member's laptop, "
            "to one command that works from any folder. While moving the code we also discovered why "
            "the larger of the two till screens had never been the one running: a method body inside it "
            "had been indented out of its class, so those lines executed while the class was being "
            "defined and the file could not be imported at all. Once re-indented, the features that had "
            "been sitting unused in that file - a server-status indicator and a batch upload of scanned "
            "items - work for the first time."
        ),
        bottleneck=(
            "The window must not open before the server is answering, or the till shows a connection "
            "error on startup. We also had to decide whether the till should still talk to the server "
            "over HTTP now that they share a process, or call the cart functions directly."
        ),
        solution=(
            "The launcher polls the server's status endpoint for up to thirty seconds before opening the "
            "window. We kept the HTTP interface deliberately: the browser till and the desktop till then "
            "go through exactly the same code path, so a bug found on one is fixed for both, and the "
            "dashboard can still be opened on a second screen or a phone."
        ),
        help=HELP_HARDWARE,
        next=[
            "Rebuild the till screen for the larger touchscreen: bigger targets, one accent colour, and "
            "a confirmation step before an item reaches the cart.",
            "Add a landing page so the root address explains the system instead of showing the stock table.",
            "Continue labelling the bottle and can dataset.",
        ],
        shots=[
            ("01-single-process.png", "One command, one process. Version 2 needed a setup script, then a launcher that spawned two programs in order."),
            ("02-scanner-one-process.png", "The recovered till screen running against the server inside its own process. The status bar reads API: Connected."),
        ],
    ),
    # ---------------------------------------------------------------- 19 Aug
    dict(
        recent=(
            "The till screen was rebuilt for the larger touchscreen. The camera view and the cart now sit "
            "side by side, everything a finger has to hit is at least 44 pixels, and the running total is "
            "always on screen. Payment moved onto the till itself: pressing PAY asks the server for a "
            "payment, shows the QR code it returns, and only writes the sale when the cashier confirms."
        ),
        wins=(
            "The screen now defends against mis-scans, which was one of the security problems named in "
            "the last report. Detected products appear in a holding area first, each with its name, price "
            "and match confidence, and a wrong read is removed with one tap before it can reach the cart. "
            "Nothing is charged for until the cashier has seen what the camera thought it saw. The rebuild "
            "also cut the till screen from 1,238 lines to 558 by moving every colour and size into one "
            "small theme file, and fixed two more defects on the way: a method defined twice, where the "
            "second copy silently replaced the first, and list refreshes that left the old rows painted "
            "on top of the new ones."
        ),
        bottleneck=(
            "The old file set colours and sizes on almost every widget individually, which is how it ended "
            "up with teal buttons next to orange ones and white scrollbars on a dark background. Those "
            "settings were spread through more than a thousand lines and could not be changed in one place."
        ),
        solution=(
            "Every colour, size and state now lives in one theme file that the whole window reads. Changing "
            "the accent colour, or making the buttons bigger for the new screen, is a one-line edit."
        ),
        help="The larger touchscreen fitted to the stand, so the new layout can be checked at its real "
             "size and the touch targets tested with a finger rather than a mouse. " + HELP_HARDWARE,
        next=[
            "Add a landing page at the root address and move the stock table to its own address.",
            "Redesign the inventory and analytics pages to match.",
            "Retrain the model once the bottle and can images are labelled.",
        ],
        shots=[
            ("01-till-redesigned.png", "The rebuilt till. Detected items wait in a holding area with their match confidence before anything is charged for."),
            ("02-till-with-cart.png", "The same screen after the items are accepted. Subtotal, 7% VAT and total are calculated from the shared product file."),
            ("03-till-payment.png", "Payment on the till. The QR code is generated by the server; the sale is only written when the cashier confirms."),
        ],
    ),
    # ---------------------------------------------------------------- 21 Aug
    dict(
        recent=(
            "The web side now has a front door. The root address is a landing page that explains what the "
            "system is and shows live figures from the running till, and the stock table moved to its own "
            "address. The larger touchscreen was fitted to the stand this period and the new till layout "
            "was checked on it."
        ),
        wins=(
            "Until now, anyone opening the system saw a spreadsheet of stock levels with no explanation - "
            "which is a poor first thing for a judge or a shop owner to look at. The landing page states "
            "the idea in one line, explains the three steps of a sale, and carries a live panel showing "
            "whether the till is online, how many products the model recognises, how many sales have been "
            "made today and what has been taken. Those numbers come from the same endpoint the analytics "
            "page uses, so the page cannot show a stale figure. It works in both the light and the dark "
            "theme, and the animation respects the reduced-motion setting."
        ),
        bottleneck=(
            "Two risks with a page like this: it can end up looking like every other template, and it can "
            "quietly break one of the two themes. The system already had a colour token set for light and "
            "dark, but the existing pages hard-coded colours in the markup instead of using it."
        ),
        solution=(
            "The landing page is built only from the existing colour tokens, so both themes stay correct "
            "automatically, and the layout deliberately avoids a row of identical cards - an oversized "
            "headline, a status panel that overlaps the headline baseline, staggered numbered steps and "
            "destination rows rather than boxes."
        ),
        help=HELP_HARDWARE,
        next=[
            "Rebuild the inventory and analytics pages on the same design.",
            "Write an automated test suite over the checkout path before the final demonstration.",
            "Finish labelling the bottle and can dataset and retrain.",
        ],
        shots=[
            ("01-landing-dark.png", "The new landing page. The status panel reads live from the running till."),
            ("03-landing-full-dark.png", "The whole page, dark theme: what the system is, how a sale runs, and where to go."),
            ("04-landing-full-light.png", "The same page in the light theme. Both themes come from one token set, so neither can fall behind."),
        ],
    ),
    # ---------------------------------------------------------------- 24 Aug
    dict(
        recent=(
            "The inventory and analytics pages were rebuilt to match the landing page. Both now share a "
            "single navigation bar generated by one script, and all styling moved out of the markup into "
            "stylesheets."
        ),
        wins=(
            "Two real defects came out of this. First, the analytics page had an unclosed button tag in "
            "its navigation, so one of its links had swallowed the next one and pointed at the wrong page "
            "- exactly the kind of fault that copying a header between five files produces, and the reason "
            "the header is now generated once. Second, every page in the system was downloading its icons "
            "from an internet CDN. The till is meant to sit on a shop counter, and a shop with no internet "
            "would have shown a screen covered in empty boxes. The icons are now local, and there is now "
            "no request to any outside address anywhere in the web interface. The inventory table also "
            "shows the pack size and minimum stock level that were recovered when the two databases were "
            "merged, which had been sitting unused in the scanner's file."
        ),
        bottleneck=(
            "The page scripts wrote styling directly into the markup as they built each row, so the "
            "appearance was split between the stylesheet and the JavaScript. The scripts also depend on "
            "specific element names, so the pages could not simply be rewritten from scratch."
        ),
        solution=(
            "The element names the scripts rely on were kept exactly as they were, and the scripts now "
            "only add or remove a class. All appearance is in the stylesheets. Both pages were checked in "
            "the light and dark themes and the browser console is clean on all six pages."
        ),
        help=HELP_HARDWARE,
        next=[
            "Write the automated test suite over the cart, tax, stock and payment path.",
            "Write the setup guide and confirm the system starts from one command on a clean machine.",
            "Begin the staff login and transaction log for the security requirement.",
        ],
        shots=[
            ("01-inventory-dark.png", "The rebuilt inventory page. Pack size and minimum stock come from data recovered during the database merge."),
            ("03-analytics-dark.png", "Analytics, dark theme: takings, growth against yesterday, best sellers and recent transactions."),
            ("04-analytics-light.png", "The same page in the light theme."),
        ],
    ),
    # ---------------------------------------------------------------- 26 Aug
    dict(
        recent=(
            "A test round over the parts of the system that handle money and stock. Twenty-six automated "
            "checks now cover the cart arithmetic, the 7% VAT, the stock decrement, refusal of unknown "
            "products, refusal of a basket larger than the shelf holds, refusal of a second confirmation "
            "on the same payment, and the presence of every page the navigation points at."
        ),
        wins=(
            "The round found a defect that had been in the system since version 1. Every completed sale "
            "was given an identification number built from the date and time to the nearest second, so "
            "four sales rung up inside the same second were all written with the same number. On a busy "
            "till that makes the sales record unusable for tracing a transaction. The payment "
            "identifier is already unique, so the sale number now carries part of it. We also checked "
            "that the tests are worth having: putting each defect back into the code makes its test fail, "
            "and taking it out again makes the test pass. That includes the internet-icons defect from the "
            "last report, which now has a test that fails if anyone reintroduces an outside address."
        ),
        bottleneck=(
            "The system stores its products, sales and settings in one JSON file, so a test that wrote to "
            "it would change the shop's real stock levels."
        ),
        solution=(
            "Every test copies the file to a temporary folder first and runs against the copy. The whole "
            "suite finishes in about one second, so it can be run before every change."
        ),
        help=HELP_HARDWARE,
        next=[
            "Write the setup guide and verify the one-command start on a clean machine.",
            "Run a full end-to-end sale on the finished build and record the result.",
            "Calibrate the load cells as soon as the parts arrive, then add the weight cross-check "
            "against the product weight table before payment is allowed.",
        ],
        shots=[
            ("01-tests.png", "The test suite. Twenty-six checks over the cart, VAT, stock and payment path, finishing in about a second."),
        ],
    ),
    # ---------------------------------------------------------------- 28 Aug
    dict(
        recent=(
            "Final pass on the software side of the upgrade: a setup guide, a check that the system starts "
            "from one command on a clean machine, and a recorded end-to-end sale on the finished build."
        ),
        wins=(
            "The end-to-end run passes: two products scanned, the cart priced at 44.00 baht with 3.08 baht "
            "VAT, a QR code generated, the payment confirmed, both stock levels reduced by one and the "
            "analytics page moved to match. All six pages load with no console errors and no failed "
            "requests. Measured against the 10 August baseline the application code went from 8,834 lines "
            "to 2,102 with 195 lines of tests added, from 59 files to 43, from three copies of the trained "
            "weights to one, from two product databases to one, from two processes and two commands to one "
            "of each, and from no tests to twenty-six. The software is ready to demonstrate."
        ),
        bottleneck=(
            "The hardware half of the upgrade is not finished. The load cells and HX711 amplifier still "
            "have not been ordered, so weight verification cannot be started, let alone calibrated. The "
            "bottle and can dataset is still being labelled, so the second camera is mounted but the model "
            "cannot yet name what it sees through it. Staff login and mismatch alerts are started but not "
            "complete."
        ),
        solution=(
            "Order the HX711 and load cells this week; calibration is roughly a day's work once they are "
            "in hand and the software side is ready to receive the readings. Athens continues labelling "
            "the bottle and can images, after which retraining is an overnight run. The remaining security "
            "work is on the staff login and the mismatch alert, and the transaction log it depends on is "
            "already written by the payment path."
        ),
        help="Purchase approval and ordering for the HX711 amplifier and load cells - this is the only "
             "item now holding back a whole feature. Workshop time to mount the weighing plate on the "
             "aluminium frame once the parts arrive.",
        next=[
            "Order the load cells and HX711, then calibrate them and cross-check the measured weight of "
            "each detected item against a product weight table before payment is allowed.",
            "Finish labelling the bottle and can dataset, retrain, and merge the two camera streams so one "
            "physical item produces only one cart entry.",
            "Complete the staff login and the mismatch alert, then run a full mis-scan and item-swap test "
            "round before the final demonstration.",
        ],
        shots=[
            ("04-endtoend.png", "An end-to-end sale on the finished build: scan, cart, VAT, QR, confirmation and stock decrement."),
            ("06-measures.png", "Version 2 against version 3, measured."),
            ("05-till-final.png", "The finished till screen."),
            ("01-cart-dark.png", "The browser cart, kept working alongside the desktop till because both go through the same interface."),
        ],
    ),
]
