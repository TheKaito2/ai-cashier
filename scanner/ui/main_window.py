"""The till screen.

Replaces the v2 scanner window, which carried two conflicting accent colours,
white scrollbars, clipped labels and a broken API-status method.  Layout is
built for the larger touchscreen: camera on the left, cart on the right,
nothing tappable smaller than 44 px.

Recognition is no longer a closed-set classifier.  The till proposes objects,
embeds them and looks them up in a gallery, which means it can be taught a new
product on the spot and can say "I do not know" instead of charging an unseen
item as whatever it resembles.  Both of those are visible here: an unrecognised
item gets an amber chip with an Enrol button, not a silent drop.
"""

import base64
import json
import logging
from dataclasses import replace
from datetime import datetime

import cv2
from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from recognition.embedder import OnnxEmbedder
from recognition.fusion import FusionConfig, Status, item_weight_for_scan, verify_basket
from recognition.gallery import MIN_SKUS_TO_FREEZE, SkuGallery
from recognition.pipeline import RecognitionPipeline, RecognisedItem, priors_from_products
from recognition.proposer import BackgroundSubtractionProposer
from recognition.scale import ScaleStream
from scanner.detection.camera import VideoStream
from scanner.models.cart import ShoppingCart
from scanner.models.product import Product
from scanner.ui import theme
from scanner.ui.enrol_dialog import EnrolDialog
# the till reads the same database the dashboard reads
from server.services.checkout import CheckoutError, confirm_payment, create_payment
from server.services.database import Database
from server.services.restrictions import sale_gate

import paths

logger = logging.getLogger(__name__)
BAHT = "฿"


# ---------------------------------------------------------------- small parts

def _label(text, obj_name=None, wrap=False):
    lab = QLabel(text)
    if obj_name:
        lab.setObjectName(obj_name)
    lab.setWordWrap(wrap)
    return lab


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            # unparent now: deleteLater alone leaves the old widget painted
            # over the new list until the event loop gets round to it
            w.setParent(None)
            w.deleteLater()


def _repolish(widget):
    """Re-read the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _card(title=None):
    """A surface that sits above the page, with an optional eyebrow title."""
    box = QFrame()
    box.setObjectName("card")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(20, 18, 20, 20)
    lay.setSpacing(14)
    if title:
        lay.addWidget(_label(title.upper(), "cardTitle"))
    return box, lay


class DetectedChip(QFrame):
    """One thing the camera found, before it reaches the cart.

    Three outcomes, and the customer can see which is which:
      recognised - name and price;
      not sure   - two candidates too close to call, so the operator picks;
      unknown    - nothing in the gallery looks like this, so offer to enrol it
                   rather than charge it as the nearest thing.
    """

    dismissed = Signal(int)
    enrol_requested = Signal(int)
    disambiguate = Signal(int)

    def __init__(self, item: RecognisedItem, product: Product | None, index: int):
        super().__init__()
        self.setObjectName("chip")
        self.setProperty("state", item.status.value)
        self.index = index

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 10, 10)
        lay.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(2)
        top = item.decision.top
        confidence = top.appearance if top else 0.0

        if item.status is Status.UNKNOWN:
            text.addWidget(_label("Unknown item", "chipName"))
            text.addWidget(_label("not in the gallery - enrol it or call staff", "chipMeta"))
        elif product is None:
            text.addWidget(_label(item.sku_id or "Unknown item", "chipName"))
            text.addWidget(_label("recognised, but not priced in the database", "chipMeta"))
        else:
            text.addWidget(_label(product.name, "chipName"))
            detail = f"{product.category}  ·  {item.agreement * 100:.0f}% of frames agreed"
            if getattr(product, "restricted", "none") != "none":
                detail = f"{product.restricted.upper()} - staff must check ID (20+)"
            if item.status is Status.AMBIGUOUS and len(item.decision.candidates) > 1:
                other = item.decision.candidates[1].sku_id
                detail = f"not sure - could be {other}"
            text.addWidget(_label(detail, "chipMeta"))
        lay.addLayout(text)
        lay.addStretch(1)

        if product is not None and item.status is not Status.UNKNOWN:
            lay.addWidget(_label(f"{BAHT}{product.price:.0f}", "chipPrice"))

        if item.status is Status.UNKNOWN:
            enrol = QPushButton("Enrol")
            enrol.setCursor(Qt.PointingHandCursor)
            enrol.setToolTip("Teach the till this product - about half a minute")
            enrol.clicked.connect(lambda: self.enrol_requested.emit(self.index))
            lay.addWidget(enrol)
        elif item.status is Status.AMBIGUOUS:
            pick = QPushButton("Choose")
            pick.setCursor(Qt.PointingHandCursor)
            pick.clicked.connect(lambda: self.disambiguate.emit(self.index))
            lay.addWidget(pick)

        drop = QPushButton("×")
        drop.setObjectName("step")
        drop.setCursor(Qt.PointingHandCursor)
        drop.setToolTip("Not this one - remove")
        drop.clicked.connect(lambda: self.dismissed.emit(self.index))
        lay.addWidget(drop)


class TornEdge(QWidget):
    """The bottom of the receipt, the way the printer's tear bar leaves it."""

    def __init__(self, colour: str, tooth: int = 7, height: int = 9):
        super().__init__()
        self.colour, self.tooth = QColor(colour), tooth
        self.setFixedHeight(height)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        points, x, down = [QPoint(0, 0)], 0, True
        while x < w:
            x = min(x + self.tooth, w)
            points.append(QPoint(x, h if down else 0))
            down = not down
        points.append(QPoint(w, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(self.colour)
        p.drawPolygon(QPolygon(points))
        p.end()


class ReceiptLine(QWidget):
    """One item as the printer sets it: the name, then quantity x price and the total,
    with steppers big enough for a finger."""

    changed = Signal(str, int)   # product_id, new quantity

    def __init__(self, item):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 5, 0, 5)
        lay.setSpacing(8)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(_label(item.product.name, "rcp", wrap=True))
        money = QHBoxLayout()
        money.addWidget(_label(f"  {item.quantity} x {item.product.price:.2f}", "rcpMuted"))
        money.addStretch(1)
        money.addWidget(_label(f"{item.subtotal:.2f}", "rcp"))
        text.addLayout(money)
        lay.addLayout(text, 1)
        for glyph, delta in (("−", -1), ("+", +1)):
            b = QPushButton(glyph)
            b.setObjectName("rcpStep")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(
                lambda _, d=delta: self.changed.emit(item.product.id, max(0, item.quantity + d))
            )
            lay.addWidget(b)


class ReceiptStrip(QFrame):
    """The cart, set the way the receipt will print: paper on the panel, mono,
    a torn edge.  What the customer sees on screen is what they will hold."""

    quantity_changed = Signal(str, int)

    def __init__(self, settings: dict, tax_rate: float):
        super().__init__()
        self.setObjectName("receipt")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QFrame()
        body.setObjectName("receiptBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(18, 16, 18, 10)
        lay.setSpacing(3)
        outer.addWidget(body, 1)
        outer.addWidget(TornEdge(theme.TOKENS["paper"]))

        vat = bool(settings.get("vat_registered"))
        for text, name in ((settings.get("store_name", "Store").upper(), "rcp"),
                           ("TAX INVOICE (ABB)" if vat else "ใบเสร็จรับเงิน / RECEIPT", "rcpMuted")):
            lab = _label(text, name)
            lab.setAlignment(Qt.AlignCenter)
            lay.addWidget(lab)
        self.when = _label("", "rcpMuted")
        self.when.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.when)
        lay.addWidget(self._rule())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        self.lines = QVBoxLayout(host)
        self.lines.setContentsMargins(0, 4, 0, 4)
        self.lines.setSpacing(0)
        scroll.setWidget(host)
        lay.addWidget(scroll, 1)
        lay.addWidget(self._rule())

        self.sub_val, self.tax_val = _label("", "rcp"), _label("", "rcp")
        for name, widget in (("Subtotal", self.sub_val),
                             (f"VAT {tax_rate * 100:.0f}%", self.tax_val)):
            row = QHBoxLayout()
            row.addWidget(_label(name, "rcpMuted"))
            row.addStretch(1)
            row.addWidget(widget)
            lay.addLayout(row)
        total = QHBoxLayout()
        total.addWidget(_label("TOTAL", "rcp"))
        total.addStretch(1)
        self.total_val = _label("", "rcpTotal")
        total.addWidget(self.total_val)
        lay.addLayout(total)
        thanks = _label("ขอบคุณค่ะ / THANK YOU", "rcpMuted")
        thanks.setAlignment(Qt.AlignCenter)
        lay.addWidget(thanks)

    @staticmethod
    def _rule():
        rule = QFrame()
        rule.setObjectName("rcpRule")
        rule.setFixedHeight(1)
        return rule

    def set_cart(self, items, summary: dict) -> None:
        _clear_layout(self.lines)
        if not items:
            note = _label("NOTHING SCANNED YET", "rcpMuted")
            note.setAlignment(Qt.AlignCenter)
            self.lines.addWidget(note)
        for item in items:
            line = ReceiptLine(item)
            line.changed.connect(self.quantity_changed)
            self.lines.addWidget(line)
        self.lines.addStretch(1)
        n = summary["item_count"]
        self.when.setText(f"{datetime.now():%d/%m/%Y %H:%M}   {n} item{'' if n == 1 else 's'}")
        self.sub_val.setText(f"{summary['subtotal']:,.2f}")
        self.tax_val.setText(f"{summary['tax']:,.2f}")
        self.total_val.setText(f"{BAHT}{summary['total']:,.2f}")


class ReceiptDialog(QDialog):
    """What the printer prints, shown once the money has been confirmed."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paid")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(16)
        lay.addWidget(_label("PAID", "cardTitle"))

        strip = QFrame()
        strip.setObjectName("receipt")
        outer = QVBoxLayout(strip)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QFrame()
        body.setObjectName("receiptBody")
        inner = QVBoxLayout(body)
        inner.setContentsMargins(22, 18, 22, 14)
        printed = _label(text, "rcp")
        printed.setTextInteractionFlags(Qt.TextSelectableByMouse)
        inner.addWidget(printed)
        outer.addWidget(body)
        outer.addWidget(TornEdge(theme.TOKENS["paper"]))
        lay.addWidget(strip)

        done = QPushButton("Done")
        done.setObjectName("pay")
        done.clicked.connect(self.accept)
        lay.addWidget(done)


class PaymentDialog(QDialog):
    """Shows the QR the server generated for a pending payment."""

    def __init__(self, payment: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scan to pay")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(16)
        lay.addWidget(_label("SCAN TO PAY", "cardTitle"))

        amount = _label(f"{BAHT}{payment['total']:,.2f}", "totValue")
        amount.setAlignment(Qt.AlignCenter)
        lay.addWidget(amount)

        qr = QLabel()
        qr.setAlignment(Qt.AlignCenter)
        raw = payment.get("qr_code", "")
        if "," in raw:
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(raw.split(",", 1)[1]))
            qr.setPixmap(pix.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(qr)

        lay.addWidget(_label(f"Payment {payment['payment_id'][:8]}  ·  "
                             f"{len(payment['items'])} lines", "rowMeta"))

        done = QPushButton("Payment received")
        done.setObjectName("pay")
        done.clicked.connect(self.accept)
        lay.addWidget(done)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        lay.addWidget(cancel)


class ScanWorker(QObject):
    """One SCAN, off the UI thread.

    Five frames through propose -> embed -> match cost 191 ms cold on an M1
    (research/bench.py, `scan_5_frames`) and several times that on a Pi 5, which
    is long enough for a touchscreen to feel dead.  So the scan runs here, on a
    QThread, and hands its verdict back through a signal (docs/research/09, D4).
    Nothing else touches the pipeline while a scan is running: the till
    disables SCAN and the enrol dialog cannot open.
    """

    done = Signal(object, object, object)      # items, weight_used, error text

    def __init__(self, pipeline, video, scale, baseline_g: float, frames: int):
        super().__init__()
        self.pipeline, self.video, self.scale = pipeline, video, scale
        self.baseline_g, self.frames = baseline_g, frames

    def run(self):
        try:
            # only a settled, non-empty pan may speak.  A reading of "about
            # zero" is not evidence that the item is light, it is the absence of
            # evidence.  And the pan's total is one item's mass only when one
            # item was added since the cart last changed.
            pan = self.scale.read_stable_grams() if self.scale else None
            ok, first = self.video.read()
            if not ok or first is None:
                self.done.emit([], None, "No camera frame - check the camera cable")
                return
            on_mat = len(self.pipeline.proposer.propose(first))
            weight = item_weight_for_scan(pan, self.baseline_g, on_mat)
            self.pipeline.reset()
            items = []
            for _ in range(self.frames):
                ok, frame = self.video.read()
                if not ok or frame is None:
                    self.done.emit([], None, "No camera frame - check the camera cable")
                    return
                items = self.pipeline.process(frame, weight_delta_g=weight)
            self.done.emit(items, weight, None)
        except Exception as e:                       # never leave the button dead
            logger.exception("scan failed")
            self.done.emit([], None, f"Scan failed: {e}")


# ---------------------------------------------------------------- main window

class MainWindow(QMainWindow):

    def __init__(self, scale=None, dashboard_url="http://127.0.0.1:8000"):
        super().__init__()
        theme.load_fonts()
        with open(paths.settings_path(), encoding="utf-8") as f:
            self.settings = json.load(f)

        self.dashboard_url = dashboard_url
        self.db = Database()
        self.cart = ShoppingCart(tax_rate=self.db.get_settings().get("tax_rate", 0.07))
        self.detected: list[RecognisedItem] = []
        #: (box, colour token, label) per detected item, painted on the frame
        self._overlay: list[tuple] = []
        self.pending_payment = None
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        #: no scale is a supported configuration; the basket check simply says
        #: it could not be performed rather than pretending it passed.  With
        #: one, it is read on its own thread so the filter is always warm.
        self.scale = ScaleStream(scale) if scale is not None else None
        #: pan mass when the cart last changed; the next single item's mass is
        #: the difference (docs/research/09, D6)
        self._pan_baseline_g = 0.0

        self.pipeline = self._build_pipeline()

        cam = self.settings["camera"]
        res = cam.get("resolution") or {}
        self.video = VideoStream(
            cam["ip_camera_url"] if cam["use_ip_camera"] else cam["default_source"],
            fourcc=cam.get("fourcc"),
            size=(res.get("width"), res.get("height")) if res else None,
            lock_exposure=bool(cam.get("lock_exposure")))

        self._build()
        self.setStyleSheet(theme.QSS)
        self._refresh_cart()
        self._refresh_detected()

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self._draw_frame)
        self.frame_timer.start(int(1000 / self.settings["display"].get("fps", 30)))

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(1000)
        self._tick()

        self._show_dashboard()

    # ------------------------------------------------------------ recognition

    def _build_pipeline(self) -> RecognitionPipeline:
        """Assemble propose -> embed -> match, restoring anything already learnt."""
        if not paths.EMBEDDER.exists():
            raise SystemExit(
                f"{paths.EMBEDDER} is missing. Run:  python tools/export_embedder.py")

        embedder = OnnxEmbedder(paths.EMBEDDER)
        gallery_path = paths.gallery_path()
        gallery = (SkuGallery.load(gallery_path) if gallery_path.exists()
                   else SkuGallery(embedder.dim))
        self._freeze_if_ready(gallery)
        cfg = FusionConfig()
        threshold = self.db.get_settings().get("reject_below_cosine")
        if threshold is not None:
            cfg.reject_below_cosine = float(threshold)

        pipeline = RecognitionPipeline(
            BackgroundSubtractionProposer(), embedder, gallery,
            priors=priors_from_products(self.db.get_products()), cfg=cfg)

        mat_path = paths.mat_path()
        if mat_path.exists():
            background = cv2.imread(str(mat_path))
            if background is not None:
                rig = self.settings.get("rig", {})
                pipeline.calibrate(background, marker_mm=rig.get("marker_mm"),
                                   marker_layout_mm=rig.get("marker_positions_mm"))
        return pipeline

    @staticmethod
    def _freeze_if_ready(gallery: SkuGallery) -> None:
        """Pin the centring reference once there is enough to centre on, so the
        rejection threshold stops moving each time a product is enrolled
        (docs/research/09, D7)."""
        if not gallery.frozen and len(gallery.skus) >= MIN_SKUS_TO_FREEZE:
            gallery.freeze_centre()
            logger.info("gallery centre frozen over %d products", len(gallery.skus))

    def _save_gallery(self) -> None:
        self._freeze_if_ready(self.pipeline.gallery)
        self.pipeline.gallery.save(paths.gallery_path())

    # ------------------------------------------------------------ scaffolding

    def _build(self):
        self.setWindowTitle("AI Cashier - Group 3")
        self.setMinimumSize(1180, 760)

        page = QWidget()
        page.setLayout(QVBoxLayout())
        page.layout().setContentsMargins(0, 0, 0, 0)
        page.layout().setSpacing(0)
        page.layout().addWidget(self._top_bar())

        body = QHBoxLayout()
        body.setContentsMargins(22, 20, 22, 16)
        body.setSpacing(20)
        body.addWidget(self._camera_column(), 3)
        body.addWidget(self._cart_column(), 2)
        holder = QWidget()
        holder.setLayout(body)
        page.layout().addWidget(holder, 1)

        page.layout().addWidget(self._status_bar())
        self.setCentralWidget(page)

    def _top_bar(self):
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(74)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(16)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(_label("AI CASHIER", "brandMark"))
        brand.addWidget(_label(self.db.get_settings().get("store_name", "Store")
                               + "  ·  Group 3, Assumption College Sriracha", "brandSub"))
        lay.addLayout(brand)
        lay.addStretch(1)

        calibrate = QPushButton("Calibrate mat")
        calibrate.setCursor(Qt.PointingHandCursor)
        calibrate.setToolTip("Photograph the empty mat. Do this once per setup, "
                             "and again if the rig or the lighting moves.")
        calibrate.clicked.connect(self.on_calibrate_mat)
        lay.addWidget(calibrate)

        add = QPushButton("Add product")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: self.on_enrol())
        lay.addWidget(add)

        self.server_pill = _label("dashboard", "pill")
        self.server_pill.setProperty("state", "off")
        lay.addWidget(self.server_pill)

        self.clock = _label("", "clock")
        lay.addWidget(self.clock)
        return bar

    def _camera_column(self):
        col = QVBoxLayout()
        col.setSpacing(14)

        # the camera is the hero: no card around it, the frame is the surface
        self.view = QLabel()
        self.view.setObjectName("viewfinder")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumHeight(320)
        # Ignored, not Expanding: a QLabel otherwise refuses to shrink below the
        # pixmap it was last given, and the frame grows over the widgets under it
        self.view.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        col.addWidget(self.view, 1)

        # instrument readouts, under the frame
        rail = QHBoxLayout()
        rail.setContentsMargins(4, 0, 4, 0)
        self.stats = _label("", "readout")
        rail.addWidget(self.stats)
        rail.addStretch(1)
        self.pan_readout = _label("", "readout")
        rail.addWidget(self.pan_readout)
        col.addLayout(rail)

        det_card, det_lay = _card("just detected")
        self.detected_box = QVBoxLayout()
        self.detected_box.setSpacing(8)
        det_lay.addLayout(self.detected_box)
        col.addWidget(det_card)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.scan_btn = QPushButton("SCAN PRODUCTS")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self.on_scan_clicked)
        actions.addWidget(self.scan_btn, 2)

        self.add_btn = QPushButton("Add to cart")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(self.on_add_to_cart)
        self.add_btn.setEnabled(False)
        actions.addWidget(self.add_btn, 1)
        col.addLayout(actions)

        wrap = QWidget()
        wrap.setLayout(col)
        return wrap

    def _cart_column(self):
        col = QVBoxLayout()
        col.setSpacing(14)
        self.receipt = ReceiptStrip(self.db.get_settings(), self.cart.tax_rate)
        self.receipt.quantity_changed.connect(self.on_quantity_changed)
        col.addWidget(self.receipt, 1)

        self.pay_btn = QPushButton("PAY")
        self.pay_btn.setObjectName("pay")
        self.pay_btn.setCursor(Qt.PointingHandCursor)
        self.pay_btn.clicked.connect(self.on_checkout)
        col.addWidget(self.pay_btn)

        self.clear_btn = QPushButton("Clear cart")
        self.clear_btn.setObjectName("ghostDanger")
        self.clear_btn.clicked.connect(self.on_clear_cart)
        col.addWidget(self.clear_btn)

        wrap = QWidget()
        wrap.setLayout(col)
        wrap.setMinimumWidth(440)
        return wrap

    def _status_bar(self):
        bar = QFrame()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(38)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        self.status = _label("Ready")
        lay.addWidget(self.status)
        lay.addStretch(1)
        self._refresh_stats()
        return bar

    def _refresh_stats(self) -> None:
        gallery = self.pipeline.gallery
        calibrated = self.pipeline.proposer.calibrated
        self.stats.setText(f"GALLERY {len(gallery.skus)} products · {len(gallery)} views     "
                           f"MAT {'calibrated' if calibrated else 'NOT CALIBRATED'}")
        self.stats.setProperty("state", "ok" if calibrated else "bad")
        _repolish(self.stats)

    def _set_view_state(self, state: str) -> None:
        """The viewfinder's border is the till's state: scanning, unknown, ready."""
        self.view.setProperty("state", state)
        _repolish(self.view)

    # ----------------------------------------------------------------- render

    def _tick(self):
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))
        if self.scale is None:
            self.pan_readout.setText("SCALE none")
        else:
            grams = self.scale.read_stable_grams()
            self.pan_readout.setText(f"PAN {grams:.0f} g" if grams is not None else "PAN settling")

    def _draw_frame(self):
        ok, frame = self.video.read()
        if not ok or frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if self._overlay:
            self._paint_overlay(pix, pix.width() / w)
        self.view.setPixmap(pix)

    def _paint_overlay(self, pix: QPixmap, scale: float) -> None:
        """Boxes and labels drawn on the frame itself, so the customer sees which
        object was priced as what."""
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont("IBM Plex Mono")
        font.setPixelSize(13)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        fm = p.fontMetrics()
        for box, colour_key, text in self._overlay:
            x1, y1, x2, y2 = (int(round(v * scale)) for v in box)
            colour = QColor(theme.TOKENS[colour_key])
            p.setPen(QPen(colour, 3))
            p.setBrush(Qt.NoBrush)
            p.drawRect(x1, y1, x2 - x1, y2 - y1)
            tw, th = fm.horizontalAdvance(text) + 16, fm.height() + 8
            ty = y1 - th if y1 >= th else y2
            p.fillRect(x1 - 1, ty, tw, th, colour)
            p.setPen(QColor(theme.TOKENS["on_accent"]))
            p.drawText(x1 + 7, ty + 4 + fm.ascent(), text)
        p.end()

    def _product_for(self, item: RecognisedItem) -> Product | None:
        """The priced product behind a recognised sku, if the database has one."""
        if not item.sku_id:
            return None
        row = self.db.get_product(item.sku_id)
        if not row:
            return None
        return Product(id=row["id"], name=row["name"], price=row["price"],
                       category=row["category"], barcode=row.get("barcode"),
                       stock=row.get("stock", 0), description=row.get("description"),
                       weight=row.get("size"), restricted=row.get("restricted", "none"))

    def _sellable(self) -> list[tuple[RecognisedItem, Product]]:
        """Only items that are recognised, priced and legal to sell right now.

        Alcohol outside 11:00-24:00 is dropped here with a reason; alcohol and
        tobacco inside hours stay, and `on_add_to_cart` asks staff to confirm
        the ID check before they go anywhere (docs/research/01, section 2).
        """
        out = []
        for item in self.detected:
            if item.status is Status.UNKNOWN:
                continue
            product = self._product_for(item)
            if product is None:
                continue
            gate = sale_gate(product.restricted, staff_confirmed=True)
            if not gate:                       # outside legal hours: not for sale
                self._set_status(f"{product.name}: {gate.reason}")
                continue
            out.append((item, product))
        return out

    def _restricted(self, sellable) -> list[Product]:
        return [p for _, p in sellable if getattr(p, "restricted", "none") != "none"]

    def _staff_confirms_restricted(self, products: list[Product]) -> bool:
        """The ID check the law puts on the seller, made explicit on screen."""
        names = ", ".join(p.name for p in products)
        box = QMessageBox(self)
        box.setStyleSheet(theme.QSS)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Age-restricted item")
        box.setText(f"{names}: restricted sale")
        box.setInformativeText("A member of staff must check the buyer's ID (20 or over) "
                               "and that they are not intoxicated before this can be sold.\n\n"
                               "Confirm only if you have checked.")
        confirm = box.addButton("ID checked - confirm", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        ok = box.clickedButton() is confirm
        self.db.log_event("override", {"kind": "restricted_confirm", "confirmed": ok,
                                       "products": [p.id for p in products]})
        return ok

    def _refresh_detected(self):
        _clear_layout(self.detected_box)
        self._overlay = []
        for item in self.detected:
            product = self._product_for(item)
            if item.status is Status.UNKNOWN or product is None:
                self._overlay.append((item.box, "accent", "UNKNOWN · ENROL"))
            elif item.status is Status.AMBIGUOUS:
                self._overlay.append((item.box, "info", f"{product.name} ?"))
            else:
                self._overlay.append((item.box, "ok", f"{product.name}  {BAHT}{product.price:.0f}"))
        if not self.detected:
            self.detected_box.addWidget(
                _label("Place products under the camera, then press SCAN.", "emptyNote"))
        else:
            for i, item in enumerate(self.detected):
                chip = DetectedChip(item, self._product_for(item), i)
                chip.dismissed.connect(self.on_dismiss_detected)
                chip.enrol_requested.connect(self.on_enrol_detected)
                chip.disambiguate.connect(self.on_disambiguate)
                self.detected_box.addWidget(chip)

        n = len(self._sellable())
        unknown = sum(1 for i in self.detected if i.status is Status.UNKNOWN)
        self.add_btn.setEnabled(bool(n))
        self.add_btn.setText("Add to cart" if n <= 1 else f"Add {n} to cart")
        if unknown:
            self._set_status(f"{unknown} item(s) not recognised - enrol them or remove them")
        ambiguous = any(i.status is Status.AMBIGUOUS for i in self.detected)
        self._set_view_state("" if not self.detected else
                             "unknown" if unknown else "ambiguous" if ambiguous else "ready")

    def _refresh_cart(self):
        items = self.cart.get_items()
        s = self.cart.get_summary()
        self.receipt.set_cart(items, s)
        self.pay_btn.setEnabled(bool(items))
        self.pay_btn.setText(f"PAY  {BAHT}{s['total']:,.2f}" if items else "PAY")
        self.clear_btn.setEnabled(bool(items))

    def _set_status(self, text):
        self.status.setText(text)
        logger.info(text)

    # ----------------------------------------------------------------- actions

    def _show_dashboard(self):
        """Where the shopkeeper's pages are.  The till no longer depends on the
        server for anything - it writes the database directly - so this is a
        signpost, not a health check."""
        self.server_pill.setText(self.dashboard_url.replace("http://", ""))
        self.server_pill.setProperty("state", "on")
        self.server_pill.style().unpolish(self.server_pill)
        self.server_pill.style().polish(self.server_pill)

    #: frames to watch before deciding. Voting across a few frames costs a third
    #: of a second and removes most single-frame mistakes - a hand passing over
    #: an item, or one bad glare, loses a vote instead of the whole decision.
    SCAN_FRAMES = 5

    @property
    def scanning(self) -> bool:
        return self._scan_thread is not None

    def on_scan_clicked(self):
        if not self.pipeline.proposer.calibrated:
            self._warn("The mat is not calibrated",
                       "Clear the mat and press “Calibrate mat” once, so the till "
                       "knows what an empty mat looks like.")
            return
        if self.scanning:
            return

        self.scan_btn.setEnabled(False)
        self.add_btn.setEnabled(False)
        self._set_status("Scanning...")
        self._set_view_state("scanning")
        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(self.pipeline, self.video, self.scale,
                                       self._pan_baseline_g, self.SCAN_FRAMES)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.done.connect(self._on_scanned)
        self._scan_thread.start()

    def _on_scanned(self, items, weight, error):
        thread, self._scan_thread, self._scan_worker = self._scan_thread, None, None
        if thread is not None:
            thread.quit()
            thread.wait(2000)
        self.scan_btn.setEnabled(True)
        if error:
            self._set_status(error)
            self._set_view_state("")
            return

        self.detected = items
        self._refresh_detected()
        for item in items:
            if item.status is not Status.ACCEPTED:
                top = item.decision.top
                self.db.log_event("abstention", {
                    "status": item.status.value, "top_sku": top.sku_id if top else None,
                    "score": float(top.appearance) if top else None,
                    "weight_g": weight})

        known = len(self._sellable())
        unknown = sum(1 for i in items if i.status is Status.UNKNOWN)
        if not items:
            self._set_status("Nothing on the mat - place the products and scan again")
        elif unknown:
            self._set_status(f"{known} recognised, {unknown} not in the gallery")
        else:
            self._set_status(f"Recognised {known} product(s)")

    def on_dismiss_detected(self, index):
        if 0 <= index < len(self.detected):
            del self.detected[index]
            self._refresh_detected()

    def on_disambiguate(self, index):
        """Two candidates were too close to call, so let a person decide."""
        if not (0 <= index < len(self.detected)):
            return
        item = self.detected[index]
        box = QMessageBox(self)
        box.setStyleSheet(theme.QSS)
        box.setWindowTitle("Which one is it?")
        box.setText("The camera cannot separate these two.")
        buttons = {}
        for candidate in item.decision.candidates[:3]:
            product = self.db.get_product(candidate.sku_id)
            label = product["name"] if product else candidate.sku_id
            buttons[box.addButton(label, QMessageBox.AcceptRole)] = candidate.sku_id
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()

        chosen = buttons.get(box.clickedButton())
        if chosen:
            decision = replace(item.decision, status=Status.ACCEPTED, sku_id=chosen)
            self.detected[index] = replace(item, decision=decision)
            self._refresh_detected()
            self.db.log_event("override", {"kind": "disambiguate", "chosen": chosen,
                                           "candidates": [c.sku_id for c in item.decision.candidates[:3]]})
            self._set_status("Operator chose the product by hand")

    # -------------------------------------------------------------- enrolment

    def on_calibrate_mat(self):
        """Record what the empty mat looks like. Everything else builds on this."""
        ok, frame = self.video.read()
        if not ok or frame is None:
            self._warn("No camera frame", "Check the camera is connected.")
            return

        rig = self.settings.get("rig", {})
        marker_mm = rig.get("marker_mm")
        self.pipeline.calibrate(frame, marker_mm=marker_mm,
                                marker_layout_mm=rig.get("marker_positions_mm"))
        mat_path = paths.mat_path()
        mat_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(mat_path), frame)

        m = self.pipeline.metrology
        measured = (f"and {m.n_markers} size marker(s) found" if m else
                    ("but no size marker was found" if marker_mm else ""))
        self._refresh_stats()
        self._set_status(f"Mat calibrated {measured}".strip())

    def on_enrol_detected(self, index):
        if 0 <= index < len(self.detected):
            self.on_enrol()

    def on_enrol(self, suggested_name: str = ""):
        """Teach the till a product. No retraining, no restart."""
        if self.scanning:
            return
        if not self.pipeline.proposer.calibrated:
            self._warn("The mat is not calibrated",
                       "Press “Calibrate mat” with the mat empty first.")
            return

        dialog = EnrolDialog(self.pipeline, self.video, self.scale, self,
                             suggested_name=suggested_name)
        if dialog.exec() != QDialog.Accepted or not dialog.result_product:
            return

        product = dialog.result_product
        self.db.upsert_product(product)
        self._save_gallery()
        # the new product needs its fusion prior straight away, not next restart
        self.pipeline.priors.update(priors_from_products(self.db.get_products()))
        self.db.log_event("enrolment", {"sku_id": product["id"], "views": product["views"],
                                        "weight_g": product.get("weight_g"),
                                        "restricted": product.get("restricted", "none")})
        self.detected = []
        self._refresh_detected()
        self._refresh_stats()
        self._set_status(f"{product['name']} enrolled from {product['views']} views "
                         f"- on sale at {BAHT}{product['price']:.2f}")

    def on_add_to_cart(self):
        """Send the recognised items to the server cart, and mirror them locally."""
        sellable = self._sellable()
        if not sellable:
            return
        restricted = self._restricted(sellable)
        if restricted and not self._staff_confirms_restricted(restricted):
            self._set_status("Restricted items not added - ID check not confirmed")
            return
        # one cart, on this screen.  Stock is checked again, in one
        # transaction, when the payment is confirmed.
        added, short = 0, []
        for _, product in sellable:
            if self.cart.add_product(product):
                added += 1
            else:
                short.append(f"{product.name}: only {product.stock} left")
        if short:
            self._warn("Not enough stock", "\n".join(short))
        if self.scale:
            # the next single item's mass is measured from here
            self._pan_baseline_g = self.scale.read_stable_grams() or self._pan_baseline_g
        self.detected = []
        self._refresh_detected()
        self._refresh_cart()
        self._set_status(f"Added {added} item(s) to the cart")

    def on_quantity_changed(self, product_id, quantity):
        if quantity <= 0:
            self.cart.remove_product(product_id)
        else:
            self.cart.update_quantity(product_id, quantity)
        self._refresh_cart()

    def on_clear_cart(self):
        self.cart.clear()
        self._new_basket()
        self._refresh_cart()
        self._set_status("Cart cleared")

    def _new_basket(self) -> None:
        """Between baskets the pan is emptied; the scale stream re-zeroes it on
        its own once it settles near empty (zero tracking), so only the
        per-item baseline resets here."""
        self._pan_baseline_g = 0.0

    def _basket_weight_ok(self) -> bool:
        """Does the mass on the pan match what the till is about to charge for?

        This is what catches an item swapped after it was scanned.  A check that
        could not be performed - no scale, or a product with no reference weight
        - is reported as such and does not block the sale, because pretending it
        passed would be worse than admitting it did not run.
        """
        if self.scale is None or not self.scale.is_settled():
            return True

        cart = {item.product.id: item.quantity for item in self.cart.get_items()}
        measured = self.scale.read_stable_grams()
        if measured is None:
            self._set_status("Weight check skipped - the pan is empty or still settling")
            return True
        check = verify_basket(self.pipeline.priors, cart, measured)
        if check is None:
            self._set_status("Weight check skipped - some products have no reference weight")
            return True
        self.db.log_event("basket_check", {
            "ok": check.ok, "expected_g": check.expected_g, "measured_g": check.measured_g,
            "tolerance_g": check.tolerance_g, "cart": cart})
        if check.ok:
            return True

        box = QMessageBox(self)
        box.setStyleSheet(theme.QSS)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("The weight does not match")
        box.setText(check.reason.capitalize())
        box.setInformativeText(
            f"Basket should weigh {check.expected_g:.0f} g, the pan reads "
            f"{check.measured_g:.0f} g (allowed ±{check.tolerance_g:.0f} g).\n\n"
            "Check the items, or have a member of staff override.")
        override = box.addButton("Staff override", QMessageBox.DestructiveRole)
        box.addButton("Go back", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() is override:
            logger.warning("staff override: basket %.0f g, pan %.0f g",
                           check.expected_g, check.measured_g)
            self.db.log_event("override", {"kind": "weight_mismatch",
                                           "expected_g": check.expected_g,
                                           "measured_g": check.measured_g})
            self._set_status("Weight mismatch overridden by staff")
            return True
        return False

    def on_checkout(self):
        if not self._basket_weight_ok():
            return
        items = [{"product_id": it.product.id, "quantity": it.quantity}
                 for it in self.cart.get_items()]
        # restricted items only reach the cart through the staff dialog, so
        # their confirmation travels with the cart
        restricted = any(getattr(it.product, "restricted", "none") != "none"
                         for it in self.cart.get_items())
        try:
            payment = create_payment(self.db, items, staff_confirmed=restricted)
        except CheckoutError as e:
            self._warn("Payment could not be created", e.payload.get("error", "unknown error"))
            return

        if not payment.get("payable", True):
            self._warn("PromptPay is not configured",
                       "The QR on screen is a placeholder, not a payment. Set "
                       "promptpay_id in the shop settings before taking money.")

        self.pending_payment = payment
        if PaymentDialog(payment, self).exec() != QDialog.Accepted:
            self._set_status("Payment cancelled - nothing was charged")
            return
        try:
            sale = confirm_payment(self.db, payment["payment_id"])
        except CheckoutError as e:
            # e.g. a slip verifier is configured and no slip was checked
            self._warn("Payment not confirmed", e.payload.get("error", "unknown error"))
            return
        self.cart.clear()
        self._new_basket()
        self._refresh_cart()
        self._set_status(f"Paid {BAHT}{payment['total']:,.2f} - stock updated")
        ReceiptDialog(sale["receipt"], self).exec()

    def _warn(self, title, detail):
        box = QMessageBox(self)
        box.setStyleSheet(theme.QSS)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(detail)
        box.exec()

    def closeEvent(self, event):
        if self._scan_thread is not None:
            self._scan_thread.quit()
            self._scan_thread.wait(3000)
        self.video.stop()
        if self.scale:
            self.scale.stop()
        event.accept()
