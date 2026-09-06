"""The till's decision surface, without a camera, a scale or an operator.

`scanner/ui/main_window.py` is where the recognition verdict, the law, the pan
and the money meet, and until now nothing but an import touched it.  These tests
drive the decisions the shop cannot take back - what may be sold, whether the
basket weighs what it should, what reaches `create_payment`, and what a person
chose when the camera could not - and check that each one reaches the events
table, because the deployment log is the only record afterwards.

Everything the till talks to except the database is a stand-in: a still frame
for the camera, a stub cell behind the real `ScaleStream`, and a `QMessageBox`
that presses a button instead of waiting for somebody.  The database is a
throwaway copy and `AI_CASHIER_DATA` points the settings, the gallery and the
mat at a temporary directory - a test that skipped that would write into the
shop's own data (docs/kb/07-gotchas.md).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # before Qt is imported

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog, QMessageBox, QSizePolicy

import paths
import server.services.database as database
import server.services.restrictions as restrictions
from recognition.fusion import Decision, FusedCandidate, Status
from recognition.gallery import MIN_SKUS_TO_FREEZE, SkuGallery
from recognition.pipeline import RecognisedItem, priors_from_products
from scanner.ui import main_window as mw

FRAME = np.zeros((480, 640, 3), np.uint8)


# ------------------------------------------------------------- the hardware

class StubVideo:
    """The camera, replaced by one still frame."""

    def __init__(self, *args, **kwargs):
        self.reads = 0

    def read(self):
        self.reads += 1
        return True, FRAME.copy()

    def stop(self):
        pass


class StubCell:
    """A load cell whose reading the test sets.

    The till wraps whatever it is given in the real `ScaleStream`, so this
    exercises the same path the HX711 takes.
    """

    def __init__(self, grams=None, settled=True):
        self.grams, self.settled = grams, settled

    def read_grams(self):
        return self.grams or 0.0

    def value(self):
        return self.grams

    def is_settled(self):
        return self.settled

    def read_stable_grams(self, min_g=None):
        return self.grams if self.settled else None

    def tare(self):
        pass


# -------------------------------------------------------------- the fixtures

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def till(qapp, tmp_path, monkeypatch):
    """Build a till whose shop, gallery and mat are all throwaway."""
    monkeypatch.setenv("AI_CASHIER_DATA", str(tmp_path))
    paths.first_run_seed()                       # settings.json, products.json
    # DEFAULT_DB is read at import, so the environment alone does not move it
    monkeypatch.setattr(database, "DEFAULT_DB", tmp_path / "checkout.sqlite3")
    monkeypatch.setattr(mw, "VideoStream", StubVideo)

    windows = []

    def build(scale=None):
        window = mw.MainWindow(scale=scale)
        assert str(tmp_path) in window.db.db_path, "the till opened the shop's own database"
        windows.append(window)
        return window

    yield build
    for window in windows:
        window.close()


class Operator:
    """The person at the till: presses one button, and remembers what it read."""

    def __init__(self):
        self.presses = ""          # part of the label of the button pressed
        self.pays = True
        self.shown: list[str] = []

    def told(self, fragment: str) -> bool:
        return any(fragment.lower() in text.lower() for text in self.shown)


@pytest.fixture
def operator(monkeypatch):
    """Answer the till's modal dialogs instead of waiting for a person."""
    op = Operator()

    class Box(QMessageBox):
        def exec(self):
            op.shown.append(f"{self.text()} {self.informativeText()}")
            for button in self.buttons():
                if op.presses and op.presses.lower() in button.text().lower():
                    button.click()
                    break
            return 0

    class Payment(mw.PaymentDialog):
        def exec(self):
            return QDialog.Accepted if op.pays else QDialog.Rejected

    class Receipt(mw.ReceiptDialog):
        def exec(self):
            op.shown.append(self.windowTitle())
            return QDialog.Accepted

    monkeypatch.setattr(mw, "QMessageBox", Box)
    monkeypatch.setattr(mw, "PaymentDialog", Payment)
    monkeypatch.setattr(mw, "ReceiptDialog", Receipt)
    return op


# --------------------------------------------------------------- the helpers

def seen(sku_id, status=Status.ACCEPTED, second=None):
    """A RecognisedItem shaped like the ones the pipeline hands the window."""
    candidates = [FusedCandidate(sku_id, 12.0, 12.0, 0.0, 0.0)]
    if second:
        candidates.append(FusedCandidate(second, 11.8, 11.8, 0.0, 0.0))
    decision = Decision(status, None if status is Status.UNKNOWN else sku_id,
                        candidates, 0.2 if second else 0.0)
    return RecognisedItem(track_id=0, box=(10, 10, 110, 130), decision=decision,
                          agreement=1.0, size_mm=None, hits=5)


def shelve(window, **product):
    """Put a product on the shelf, with the fusion prior `on_enrol` gives it."""
    product.setdefault("category", "other")
    product.setdefault("stock", 10)
    row = window.db.upsert_product(product)
    window.pipeline.priors.update(priors_from_products(window.db.get_products()))
    return row


def put_in_cart(window, sku_id, quantity=1):
    window.cart.add_product(window._product_for(seen(sku_id)), quantity)
    window._refresh_cart()


# ------------------------------------------------------- what may be sold

def test_a_recognised_and_priced_item_is_sellable(till):
    window = till()
    window.detected = [seen("pepsi")]
    assert [p.id for _, p in window._sellable()] == ["pepsi"]


def test_an_unknown_item_and_an_unpriced_sku_are_not_sellable(till):
    window = till()
    window.detected = [seen("pepsi", status=Status.UNKNOWN), seen("not-a-product")]
    assert window._sellable() == []


def test_alcohol_outside_the_legal_hours_is_dropped_with_the_reason(till, monkeypatch):
    window = till()
    shelve(window, id="chang-330", name="Chang 330 ml", price=45.0, restricted="alcohol")
    monkeypatch.setattr(restrictions, "alcohol_hours_open", lambda now=None: False)
    window.detected = [seen("chang-330")]

    assert window._sellable() == []
    assert "11:00" in window.status.text()


def test_alcohol_inside_the_legal_hours_stays_for_the_staff_to_check(till, monkeypatch):
    window = till()
    shelve(window, id="chang-330", name="Chang 330 ml", price=45.0, restricted="alcohol")
    monkeypatch.setattr(restrictions, "alcohol_hours_open", lambda now=None: True)
    window.detected = [seen("chang-330")]

    assert [p.id for _, p in window._sellable()] == ["chang-330"]


def test_a_restricted_item_reaches_the_cart_once_the_staff_confirm_the_id_check(till, operator):
    """Tobacco is staff-only at any hour, so this needs no clock."""
    window = till()
    shelve(window, id="krongthip", name="Krongthip 90", price=72.0, restricted="tobacco")
    window.detected = [seen("krongthip")]
    operator.presses = "ID checked"

    window.on_add_to_cart()

    assert [i.product.id for i in window.cart.get_items()] == ["krongthip"]
    # get_events puts the row's kind over the payload's, so an override is told
    # apart by its fields rather than by payload["kind"]
    event = window.db.get_events("override")[0]
    assert event["confirmed"] is True and event["products"] == ["krongthip"]


def test_a_restricted_item_the_staff_will_not_confirm_stays_out_of_the_cart(till, operator):
    window = till()
    shelve(window, id="krongthip", name="Krongthip 90", price=72.0, restricted="tobacco")
    window.detected = [seen("krongthip")]
    operator.presses = "Cancel"

    window.on_add_to_cart()

    assert window.cart.get_items() == []
    event = window.db.get_events("override")[0]
    assert event["confirmed"] is False and event["products"] == ["krongthip"]


# ---------------------------------------------------- what the pan says

def test_a_basket_that_matches_the_pan_passes_and_is_on_the_record(till):
    window = till(scale=StubCell(75.0))
    put_in_cart(window, "lays-flat-original")            # a 75 g pack label

    assert window._basket_weight_ok() is True
    event = window.db.get_events("basket_check")[0]
    assert event["ok"] is True
    assert event["expected_g"] == 75.0 and event["measured_g"] == 75.0


def test_a_mismatch_the_staff_will_not_override_refuses_the_sale(till, operator):
    window = till(scale=StubCell(400.0))
    put_in_cart(window, "lays-flat-original")
    operator.presses = "Go back"

    assert window._basket_weight_ok() is False
    assert window.db.get_events("basket_check")[0]["ok"] is False
    assert window.db.get_events("override") == []
    assert operator.told("400 g")


def test_a_mismatch_a_member_of_staff_overrides_goes_through_and_is_recorded(till, operator):
    window = till(scale=StubCell(400.0))
    put_in_cart(window, "lays-flat-original")
    operator.presses = "Staff override"

    assert window._basket_weight_ok() is True
    event = window.db.get_events("override")[0]
    assert event["expected_g"] == 75.0 and event["measured_g"] == 400.0


def test_a_check_that_could_not_be_performed_is_not_reported_as_passing(till):
    """A product with no reference weight makes `verify_basket` return None."""
    window = till(scale=StubCell(75.0))
    shelve(window, id="mystery-box", name="Mystery box", price=30.0)   # no pack label
    put_in_cart(window, "mystery-box")

    assert window._basket_weight_ok() is True
    assert window.db.get_events("basket_check") == []
    assert "no reference weight" in window.status.text()


# --------------------------------------------------------------- the money

def test_the_cart_on_screen_is_what_is_charged_for(till, operator):
    window = till()
    window.db.set_setting("promptpay_id", "0812345678")
    before = window.db.get_product("pepsi")["stock"]
    put_in_cart(window, "pepsi", 2)

    window.on_checkout()

    sale = window.db.get_sales(limit=1)[0]
    assert [(i["product_id"], i["quantity"]) for i in sale["items"]] == [("pepsi", 2)]
    assert sale["total"] == pytest.approx(28.0 * 1.07)
    assert window.db.get_product("pepsi")["stock"] == before - 2
    assert window.cart.get_items() == []


def test_an_empty_cart_is_refused_before_any_payment_exists(till, operator):
    window = till()
    # the throwaway shop arrives with version 3's sales migrated into it
    sales = len(window.db.get_sales())

    window.on_checkout()

    assert operator.told("Cart is empty")
    assert len(window.db.get_sales()) == sales


def test_a_product_that_sold_out_since_it_was_scanned_is_refused(till, operator):
    """The shelf is checked again at PAY: another till may have taken the last one."""
    window = till()
    put_in_cart(window, "pepsi", 2)
    sales = len(window.db.get_sales())
    window.db.update_stock("pepsi", window.db.get_product("pepsi")["stock"], "remove")

    window.on_checkout()

    assert operator.told("stock")
    assert len(window.db.get_sales()) == sales
    assert len(window.cart.get_items()) == 1        # nothing was charged or cleared


# ------------------------------------------------- when the camera cannot tell

def test_the_operator_picks_between_two_candidates_and_the_choice_is_recorded(till, operator):
    window = till()
    window.detected = [seen("lays-flat-original", status=Status.AMBIGUOUS,
                            second="lays-ridged-original")]
    operator.presses = "Ridged"

    window.on_disambiguate(0)

    item = window.detected[0]
    assert item.sku_id == "lays-ridged-original" and item.status is Status.ACCEPTED
    event = window.db.get_events("override")[0]
    assert event["chosen"] == "lays-ridged-original"
    assert event["candidates"] == ["lays-flat-original", "lays-ridged-original"]


def test_cancelling_the_choice_leaves_the_item_ambiguous(till, operator):
    window = till()
    window.detected = [seen("lays-flat-original", status=Status.AMBIGUOUS,
                            second="lays-ridged-original")]
    operator.presses = "Cancel"

    window.on_disambiguate(0)

    assert window.detected[0].status is Status.AMBIGUOUS
    assert window.db.get_events("override") == []


# ------------------------------------------------------------- the gallery

def test_the_gallery_centre_freezes_at_the_threshold_and_not_before():
    """Until it is pinned, every enrolment moves every score (docs/research/09, D7)."""
    rng = np.random.default_rng(0)
    gallery = SkuGallery(8)

    for i in range(MIN_SKUS_TO_FREEZE - 1):
        gallery.enrol(f"sku-{i}", rng.random((1, 8), dtype=np.float32))
        mw.MainWindow._freeze_if_ready(gallery)
        assert not gallery.frozen, f"froze over {len(gallery.skus)} products"

    gallery.enrol("sku-last", rng.random((1, 8), dtype=np.float32))
    mw.MainWindow._freeze_if_ready(gallery)
    assert gallery.frozen and len(gallery.skus) == MIN_SKUS_TO_FREEZE

    centre = gallery.centre.copy()
    gallery.enrol("sku-after", rng.random((1, 8), dtype=np.float32))
    mw.MainWindow._freeze_if_ready(gallery)
    assert np.array_equal(gallery.centre, centre), "a second freeze moved the centre"


# ---------------------------------------------------------------- the scan

class StubPipeline:
    """Propose -> embed -> match, replaced by whatever the test wants back."""

    def __init__(self, items, on_mat=1):
        self.items = items
        self.proposer = type("P", (), {"propose": lambda _self, frame: [None] * on_mat})()
        self.weights = []
        self.resets = 0

    def reset(self):
        self.resets += 1

    def process(self, frame, weight_delta_g=None):
        self.weights.append(weight_delta_g)
        return self.items


def test_a_scan_hands_back_what_the_pipeline_recognised(qapp):
    items = [seen("pepsi")]
    pipeline = StubPipeline(items)
    worker = mw.ScanWorker(pipeline, StubVideo(), StubCell(340.0), baseline_g=0.0, frames=5)
    emitted = []
    worker.done.connect(lambda *args: emitted.append(args))

    worker.run()

    assert emitted == [(items, 340.0, None)]
    assert pipeline.resets == 1
    # one object on the mat, so the whole pan is that item's mass
    assert pipeline.weights == [340.0] * 5


def test_a_scan_with_no_camera_frame_says_so_rather_than_leaving_the_button_dead(qapp):
    class Blind(StubVideo):
        def read(self):
            return False, None

    worker = mw.ScanWorker(StubPipeline([]), Blind(), None, 0.0, 5)
    emitted = []
    worker.done.connect(lambda *args: emitted.append(args))

    worker.run()

    assert emitted == [([], None, "No camera frame - check the camera cable")]


# ------------------------------------------------------------- the viewfinder

def test_the_viewfinder_may_shrink_below_the_frame_it_last_showed(till):
    """A QLabel holding a pixmap otherwise refuses to shrink and pushes the cart
    off the screen (docs/kb/07-gotchas.md)."""
    window = till()
    policy = window.view.sizePolicy()
    assert policy.horizontalPolicy() == QSizePolicy.Ignored
    assert policy.verticalPolicy() == QSizePolicy.Ignored
