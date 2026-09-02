"""Teaching the till a product it has never seen.

This is the whole point of the rebuild.  On version 3, adding a product meant
photographing it hundreds of times, labelling every image, retraining a detector
and reinstalling the model - days of work for one new line of crisps.  Here the
operator puts the product on the mat, turns it a few times, types a price, and
the till can sell it on the next frame.

No training happens.  Each view becomes one vector in the gallery.
"""

from __future__ import annotations

import re

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

import cv2

from scanner.ui import theme

BAHT = "฿"
DEFAULT_VIEWS = 5


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "product"


class EnrolDialog(QDialog):
    """Capture k views of a product, then price it.

    The operator is asked to turn the product between shots on purpose: a
    gallery of five near-identical photographs is worth about as much as one,
    and the whole method depends on the views actually differing.
    """

    def __init__(self, pipeline, video, scale=None, parent=None,
                 suggested_name: str = "", n_views: int = DEFAULT_VIEWS):
        super().__init__(parent)
        self.pipeline = pipeline
        self.video = video
        self.scale = scale
        self.n_views = n_views
        self.frames: list[np.ndarray] = []
        self.result_product: dict | None = None

        self.setWindowTitle("Add a product")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(760)
        self._build(suggested_name)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._draw)
        self.timer.start(40)

    # ------------------------------------------------------------------ build

    def _build(self, suggested_name: str) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 22)
        lay.setSpacing(16)

        head = QLabel("ADD A PRODUCT")
        head.setObjectName("cardTitle")
        lay.addWidget(head)

        self.hint = QLabel(f"Put the product on the mat, then capture {self.n_views} views. "
                           "Turn it a little between each one.")
        self.hint.setObjectName("emptyNote")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        body = QHBoxLayout()
        body.setSpacing(18)

        self.view = QLabel()
        self.view.setObjectName("viewfinder")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(420, 300)
        body.addWidget(self.view, 3)

        form = QVBoxLayout()
        form.setSpacing(10)

        form.addWidget(self._label("Name"))
        self.name = QLineEdit(suggested_name)
        self.name.setPlaceholderText("Lay's Nori Seaweed Flavor")
        self.name.setMinimumHeight(46)
        form.addWidget(self.name)

        form.addWidget(self._label("Price"))
        self.price = QDoubleSpinBox()
        self.price.setRange(0.5, 9999.0)
        self.price.setDecimals(2)
        self.price.setValue(20.0)
        self.price.setPrefix(BAHT + " ")
        self.price.setMinimumHeight(46)
        form.addWidget(self.price)

        row = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(self._label("Category"))
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(["chips", "drinks", "sweets", "other"])
        self.category.setMinimumHeight(46)
        col.addWidget(self.category)
        row.addLayout(col)

        col2 = QVBoxLayout()
        col2.addWidget(self._label("Opening stock"))
        self.stock = QSpinBox()
        self.stock.setRange(0, 9999)
        self.stock.setValue(10)
        self.stock.setMinimumHeight(46)
        col2.addWidget(self.stock)
        row.addLayout(col2)
        form.addLayout(row)

        form.addWidget(self._label("Restricted sale"))
        self.restricted = QComboBox()
        # alcohol: 11:00-24:00, staff ID check; tobacco: staff-only, never displayed
        self.restricted.addItems(["none", "alcohol", "tobacco"])
        self.restricted.setMinimumHeight(46)
        form.addWidget(self.restricted)

        self.weight_note = QLabel()
        self.weight_note.setObjectName("rowMeta")
        self.weight_note.setWordWrap(True)
        form.addWidget(self.weight_note)
        self._refresh_weight_note()

        form.addStretch(1)
        body.addLayout(form, 2)
        lay.addLayout(body)

        self.progress = QLabel()
        self.progress.setObjectName("rowMeta")
        lay.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.capture_btn = QPushButton(f"CAPTURE VIEW 1 OF {self.n_views}")
        self.capture_btn.setObjectName("primary")
        self.capture_btn.setCursor(Qt.PointingHandCursor)
        self.capture_btn.clicked.connect(self.capture)
        actions.addWidget(self.capture_btn, 2)

        self.save_btn = QPushButton("Save product")
        self.save_btn.setObjectName("pay")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save)
        actions.addWidget(self.save_btn, 1)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel, 1)
        lay.addLayout(actions)

        self._refresh_progress()

    @staticmethod
    def _label(text: str) -> QLabel:
        lab = QLabel(text.upper())
        lab.setObjectName("cardTitle")
        return lab

    # ----------------------------------------------------------------- camera

    def _draw(self) -> None:
        ok, frame = self.video.read()
        if not ok or frame is None:
            return
        self._latest = frame
        preview = frame.copy()
        # show what the till would actually cut out, so a bad placement is
        # obvious before it is committed to the gallery
        try:
            proposals = self.pipeline.proposer.propose(frame)
        except RuntimeError:
            proposals = []
            self.hint.setText("The mat is not calibrated. Close this and press "
                              "“Calibrate mat” with the mat empty first.")
        for p in proposals[:1]:
            x1, y1, x2, y2 = p.box
            cv2.rectangle(preview, (x1, y1), (x2, y2), (24, 122, 255), 3)

        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        self.view.setPixmap(QPixmap.fromImage(img).scaled(
            self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # -------------------------------------------------------------- enrolment

    def capture(self) -> None:
        frame = getattr(self, "_latest", None)
        if frame is None:
            # the preview timer may not have fired yet - read the camera rather
            # than swallowing the operator's button press
            ok, frame = self.video.read()
            if not ok or frame is None:
                self.progress.setText("No camera frame - check the camera is connected.")
                return
        if not self.pipeline.proposer.propose(frame):
            self.progress.setText("Nothing on the mat - place the product and try again.")
            return
        self.frames.append(frame.copy())
        self._refresh_progress()
        self._refresh_weight_note()

    def _refresh_progress(self) -> None:
        n = len(self.frames)
        self.progress.setText(f"{n} of {self.n_views} views captured"
                              + ("  -  turn the product and capture again" if n < self.n_views
                                 else "  -  ready to save"))
        self.capture_btn.setText(f"CAPTURE VIEW {min(n + 1, self.n_views)} OF {self.n_views}")
        self.capture_btn.setEnabled(n < self.n_views)
        self.save_btn.setEnabled(n >= 1)          # one view works; more is better

    def _read_weight(self) -> float | None:
        return self.scale.read_stable_grams() if self.scale else None

    def _refresh_weight_note(self) -> None:
        if self.scale is None:
            self.weight_note.setText("No scale connected - this product will have no "
                                     "reference weight, so the basket check will skip it.")
            return
        grams = self._read_weight()
        self.weight_note.setText(
            f"Scale reads {grams:.0f} g - stored as this product's reference weight."
            if grams else "Scale reads empty. Leave the product on the mat to record its weight.")

    def save(self) -> None:
        name = self.name.text().strip()
        if not name:
            self.progress.setText("Give the product a name first.")
            return

        weight = self._read_weight()
        sku_id = _slug(name)
        try:
            views = self.pipeline.enrol(sku_id, self.frames, weight_g=weight)
        except ValueError as e:
            self.progress.setText(str(e))
            return

        prior = self.pipeline.priors.get(sku_id)
        self.result_product = {
            "id": sku_id,
            "name": name,
            "price": float(self.price.value()),
            "category": self.category.currentText().strip() or "other",
            "stock": int(self.stock.value()),
            "min_stock": 5,
            "weight_g": weight,
            "size_mm": list(prior.size_mm) if prior and prior.size_mm else None,
            "restricted": self.restricted.currentText(),
            "views": views,
        }
        self.accept()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
