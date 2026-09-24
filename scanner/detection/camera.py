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

import logging
import sys
import threading
import time

import cv2

logger = logging.getLogger(__name__)

#: V4L2: 1 = manual exposure, 3 = aperture-priority auto
V4L2_EXPOSURE_MANUAL = 1
V4L2_EXPOSURE_AUTO = 3

#: True once --demo has swapped the webcam for a still image.  The till has to
#: know, because a mat calibrated from the demo frame is written to the real
#: data directory and then silently ruins every scan from the real camera -
#: every pixel differs from the still, so the whole frame reads as one object.
DEMO_SOURCE = False


class VideoStream:
    """Reads frames continuously so the UI never blocks on the camera."""

    #: below this share of the pre-lock brightness, the lock is judged to have
    #: blinded the camera and is undone
    LOCK_MIN_BRIGHTNESS_RATIO = 0.6

    def __init__(self, src, fourcc: str | None = None,
                 size: tuple[int, int] | None = None, lock_exposure: bool = False,
                 exposure: float | None = None):
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
            self._lock_exposure(exposure)
        else:
            # V4L2 keeps these on the device, not in the process.  Leaving them
            # alone means a run with lock_exposure on strands the camera in
            # manual for every later run - including one whose config says
            # false.  Turning the setting off has to actually turn it off.
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, V4L2_EXPOSURE_AUTO)
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def _brightness(self, frames: int = 8) -> float:
        for _ in range(frames):
            ok, frame = self.cap.read()
            time.sleep(0.02)
        return float(frame.mean()) if ok and frame is not None else 0.0

    def _lock_exposure(self, exposure: float | None) -> None:
        """Pin exposure and white balance, and refuse to pin them to darkness.

        A retrieval system enrols a product under one exposure and looks it up
        under another, so the rig wants them fixed (docs/research/09, D9).  But
        V4L2 does not carry the automatic value over when you switch to manual,
        and on the rig's webcam `CAP_PROP_EXPOSURE` reports 166 whether auto is
        producing a bright picture or not - 166 in manual is nearly black.  Read
        back, therefore, is not trustworthy on every camera.

        So the lock checks itself: measure the picture, lock, measure again, and
        if the picture collapsed, give auto-mode back.  A camera that drifts is
        a measurement problem.  A till that cannot see is not a till.

        `camera.exposure` in the settings pins a value measured on the rig once,
        which is the only way to get a lock this camera will honour.
        """
        before = self._brightness()

        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, V4L2_EXPOSURE_MANUAL)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        if exposure is not None:
            self.cap.set(cv2.CAP_PROP_EXPOSURE, float(exposure))

        after = self._brightness()
        if before > 0 and after < before * self.LOCK_MIN_BRIGHTNESS_RATIO:
            logger.warning(
                "exposure lock made the picture %.0f%% darker (%.0f -> %.0f); "
                "staying on auto.  Measure a working value on this rig and put "
                "it in camera.exposure.", 100 * (1 - after / before), before, after)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, V4L2_EXPOSURE_AUTO)
            self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)

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
