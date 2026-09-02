#!/usr/bin/env python3
"""Render the scanner window offscreen and save it as a PNG.

usage: shoot_qt.py <out.png> [width height]

Needs no server: the till writes the database directly.
The dev laptop has no webcam, so cv2.VideoCapture replays docs/assets/demo_frame.jpg.
"""
import os, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1]).resolve()
W, H = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1440, 900)
out.parent.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import cv2
FRAME = cv2.imread(str(ROOT / "docs" / "assets" / "demo_frame.jpg"))

class StillCapture:
    def __init__(self, *a, **k): pass
    def read(self): return True, FRAME.copy()
    def set(self, *a): return True
    def get(self, *a): return 0
    def isOpened(self): return True
    def release(self): pass

cv2.VideoCapture = StillCapture

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv[:1])
app.setStyle("Fusion")

from recognition.scale import SimulatedScale
from scanner.ui.main_window import MainWindow
win = MainWindow(scale=SimulatedScale())
win.scale.place(float(os.environ.get("SHOT_PAN_G", "75")))   # something on the pan
import time; time.sleep(1.2)                                   # let the stream settle it
win.resize(W, H)
win.show()

# let the camera timer paint a frame and the API health check land
for _ in range(60):
    app.processEvents()

def scan():                              # the scan runs on a worker thread now
    win.on_scan_clicked()
    deadline = time.monotonic() + 15
    while win.scanning and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    for _ in range(30):
        app.processEvents()

if os.environ.get("SHOT_SCAN"):          # populate the panel so the shot is not empty
    scan()

if os.environ.get("SHOT_ADD"):           # ... and push it through to the cart
    win.on_add_to_cart()
    for _ in range(30):
        app.processEvents()
    scan()

win.grab().save(str(out))
print(f"{out}  {out.stat().st_size // 1024} KB")

if os.environ.get("SHOT_PAY"):           # the QR the server hands back
    from scanner.ui.main_window import PaymentDialog
    from server.services.checkout import create_payment
    items = [{"product_id": it.product.id, "quantity": it.quantity} for it in win.cart.get_items()]
    payment = create_payment(win.db, items)
    dlg = PaymentDialog(payment)
    dlg.show()
    for _ in range(30):
        app.processEvents()
    alt = out.with_name(out.stem + "-payment.png")
    dlg.grab().save(str(alt))
    print(f"{alt}  {alt.stat().st_size // 1024} KB")

if os.environ.get("SHOT_ENROL"):         # the "teach it a new product" dialog
    from scanner.ui.enrol_dialog import EnrolDialog
    dlg = EnrolDialog(win.pipeline, win.video, win.scale, None,
                      suggested_name=os.environ.get("SHOT_ENROL_NAME", ""))
    dlg.resize(880, 560)
    dlg.show()
    dlg._draw()                          # timers do not tick under processEvents alone
    for _ in range(30):
        app.processEvents()
    for _ in range(int(os.environ.get("SHOT_ENROL_VIEWS", "3"))):
        dlg._draw()
        dlg.capture()
        for _ in range(10):
            app.processEvents()
    alt = out.with_name(out.stem + "-enrol.png")
    dlg.grab().save(str(alt))
    print(f"{alt}  {alt.stat().st_size // 1024} KB")
