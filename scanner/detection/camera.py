"""The camera, on its own thread.

Extracted from the old yolo_detector module so the till no longer has to import
a training framework to read a webcam.  Recognition lives in recognition/ now;
this is only the capture loop.

The two bugs it carried are fixed and covered by tests: the source argument used
to be accepted and then ignored (so every camera setting in the config did
nothing), and a dropped frame returned a tuple nested inside a tuple.

Exposure and white balance can be locked (docs/HARDWARE.md prescribed it; the
code never did it before docs/research/09, D9).  A retrieval system enrols a
product under one exposure and looks it up under another; auto-exposure makes
the same packet embed differently frame to frame.  The property values are the
V4L2 ones the Raspberry Pi uses - other backends ignore what they do not know.
"""

from __future__ import annotations

import sys
import threading
import time

import cv2

#: V4L2: 1 = manual exposure, 3 = aperture-priority auto
V4L2_EXPOSURE_MANUAL = 1


class VideoStream:
    """Reads frames continuously so the UI never blocks on the camera."""

    def __init__(self, src, fourcc: str | None = None,
                 size: tuple[int, int] | None = None, lock_exposure: bool = False):
        # Windows: DirectShow opens a webcam in well under a second; the
        # default MSMF backend can take many seconds (Phase 6 plan, B3)
        self.cap = (cv2.VideoCapture(src, cv2.CAP_DSHOW)
                    if sys.platform == "win32" and isinstance(src, int) else cv2.VideoCapture(src))
        if fourcc:
            # MJPG is what lets a USB2 webcam deliver 720p at full rate
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        if size and size[0] and size[1]:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(size[0]))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(size[1]))
        if lock_exposure:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, V4L2_EXPOSURE_MANUAL)
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self) -> None:
        while not self.stopped:
            ret, frame = self.cap.read()
            with self.lock:
                self.ret, self.frame = ret, frame
            time.sleep(0.01)

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return self.ret, self.frame.copy()

    def stop(self) -> None:
        self.stopped = True
        self.thread.join(timeout=2.0)
        self.cap.release()
