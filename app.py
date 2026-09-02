#!/usr/bin/env python3
"""AI Cashier - single entry point.

Version 2 shipped as two processes that had to be started in the right order by
a launcher script.  Version 3 collapsed them into one.  Version 4 replaced the
closed-set classifier with retrieval, so the till can be taught a new product in
seconds and can say it does not recognise something instead of guessing.  The
architecture review (docs/research/09) then made the till the only thing that
touches the camera, the scale and the cart; the web server is the shopkeeper's
dashboard on the same database.

    python app.py                 till + dashboard (normal use)
    python app.py --lan           dashboard reachable from the shop wifi (needs a PIN)
    python app.py --server-only   dashboard only, no camera (spare screen, Pi headless)
    python app.py --demo          replay a still image instead of the camera
    python app.py --scale hx711   use the real load cell instead of a simulated one
    python app.py --fullscreen    kiosk: the till fills the screen
    python app.py --self-test     no camera, no window: scan the demo frame and exit
"""

import argparse
import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

# OpenCV's Windows backend (MSMF) can take many seconds to open a webcam when
# hardware transforms are on; the documented workaround is this variable, set
# before cv2 is imported anywhere (Phase 6 plan, B3).
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import paths  # noqa: E402

PORT = 8000


def _redirect_output_when_windowed() -> None:
    """A windowed (no-console) build has no stdout or stderr at all - they are
    None - and the first print or log line would raise.  Send both to a log
    file in the data folder instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    paths.log_dir().mkdir(parents=True, exist_ok=True)
    log = open(paths.log_dir() / "app.log", "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def start_server(host: str, lan: bool) -> str:
    """Run uvicorn on a daemon thread and return the dashboard URL once it answers."""
    import uvicorn
    import server.main as main

    main.app.state.lan = lan
    config = uvicorn.Config(main.app, host=host, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, name="uvicorn", daemon=True).start()

    local = f"http://127.0.0.1:{PORT}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{local}/api/system-status", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.25)
    else:
        raise RuntimeError(f"server did not come up on {local} within 30s")

    if not lan:
        return local
    if not main.db.get_settings().get("dashboard_pin"):
        print("  WARNING: --lan with no dashboard_pin in the shop settings - "
              "every write from the network will be refused until one is set")
    return f"http://{_lan_ip()}:{PORT}"


def _lan_ip() -> str:
    """The address the shopkeeper's phone can reach; no packets are sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def use_demo_camera() -> None:
    """Swap the webcam for a still image (dev laptops, and offline demos)."""
    import cv2
    frame = cv2.imread(str(paths.DEMO_FRAME))
    if frame is None:
        raise SystemExit(f"--demo needs {paths.DEMO_FRAME}")

    class StillCapture:
        def __init__(self, *a, **k): pass
        def read(self): return True, frame.copy()
        def set(self, *a): return True
        def get(self, *a): return 0
        def isOpened(self): return True
        def release(self): pass

    cv2.VideoCapture = StillCapture


def build_scale(kind: str):
    """The weighing platform, or nothing.

    `simulated` is the default so the till runs, and the basket check exercises,
    on a machine with no load cell attached.  Swapping in the real cell is this
    one function - nothing else in the till knows the difference.
    """
    if kind == "none":
        return None
    if kind == "hx711":
        from recognition.scale import HX711Scale
        cfg = json.loads(paths.settings_path().read_text(encoding="utf-8"))["scale"]
        return HX711Scale(cfg["dout_pin"], cfg["sck_pin"],
                          cfg["counts_per_gram"], cfg["offset_counts"])
    from recognition.scale import SimulatedScale
    return SimulatedScale()


def self_test() -> int:
    """Prove the frozen build can see: calibrate on the bundled empty mat, scan
    the bundled demo frame, report how many items the pipeline found.  What
    CI runs on the installer's exe, where there is no camera and no display."""
    import cv2
    from recognition.embedder import OnnxEmbedder
    from recognition.gallery import SkuGallery
    from recognition.pipeline import RecognitionPipeline
    from recognition.proposer import BackgroundSubtractionProposer

    mat, frame = cv2.imread(str(paths.DEMO_MAT)), cv2.imread(str(paths.DEMO_FRAME))
    if mat is None or frame is None:
        print(f"self-test FAILED: missing {paths.DEMO_MAT} or {paths.DEMO_FRAME}")
        return 1
    embedder = OnnxEmbedder(paths.EMBEDDER)
    proposer = BackgroundSubtractionProposer()
    proposer.calibrate(mat)
    pipeline = RecognitionPipeline(proposer, embedder, SkuGallery(embedder.dim))
    items = []
    for _ in range(5):
        items = pipeline.process(frame)
    unknown = sum(1 for i in items if i.sku_id is None)
    print(f"self-test ok: version {paths.version()}, embedder {embedder.dim}-d, "
          f"{len(items)} item(s) on the demo mat, {unknown} unknown (nothing enrolled)")
    return 0 if len(items) >= 2 else 1


def main() -> int:
    _redirect_output_when_windowed()
    ap = argparse.ArgumentParser(description="AI Cashier System")
    ap.add_argument("--server-only", action="store_true", help="dashboard only, no scanner window")
    ap.add_argument("--lan", action="store_true",
                    help="serve the dashboard on every interface, PIN-protected writes")
    ap.add_argument("--demo", action="store_true", help="still image instead of a camera")
    ap.add_argument("--fullscreen", action="store_true", help="the till fills the screen")
    ap.add_argument("--self-test", action="store_true",
                    help="scan the bundled demo frame headless and exit")
    ap.add_argument("--scale", choices=("simulated", "hx711", "none"), default="simulated",
                    help="weighing platform; 'none' disables the basket weight check")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    print(f"AI CASHIER {paths.version()}  -  Group 3, Assumption College Sriracha")
    for copied in paths.first_run_seed():
        print(f"  seeded    {copied}")
    from recognition.gallery import SkuGallery

    gallery_path = paths.gallery_path()
    if gallery_path.exists():
        gallery = SkuGallery.load(gallery_path)
        taught = f"{len(gallery.skus)} products, {len(gallery)} reference views"
    else:
        taught = "empty - use 'Add product' on the till to teach it something"
    print(f"  data      {paths.data_dir()}")
    print(f"  gallery   {taught}")
    print(f"  embedder  {paths.EMBEDDER}")
    dashboard = start_server("0.0.0.0" if args.lan else "127.0.0.1", args.lan)
    print(f"  dashboard {dashboard}/   inventory {dashboard}/inventory   analytics {dashboard}/admin")

    if args.server_only:
        print("\n  server-only mode - Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return 0

    if args.demo:
        use_demo_camera()

    from PySide6.QtWidgets import QApplication

    # Qt 6 scales for high-DPI screens on its own; the Qt 5 attributes are gone
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setApplicationName("AI Cashier")

    from scanner.ui.main_window import MainWindow
    window = MainWindow(scale=build_scale(args.scale), dashboard_url=dashboard)
    display = json.loads(paths.settings_path().read_text(encoding="utf-8")).get("display", {})
    if args.fullscreen or display.get("fullscreen"):
        window.showFullScreen()
    else:
        window.show()
    print("  scanner window open\n")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
