"""The camera settings in config actually reach the driver (docs/research/09, D9)."""
import cv2
import numpy as np

from scanner.detection.camera import V4L2_EXPOSURE_MANUAL, VideoStream


class FakeCapture:
    def __init__(self, src):
        self.src, self.props, self.released = src, {}, False

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def read(self):
        return True, np.zeros((4, 4, 3), np.uint8)

    def release(self):
        self.released = True


def test_fourcc_size_and_exposure_lock_are_applied(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(0, fourcc="MJPG", size=(1280, 720), lock_exposure=True)
    v.stop()
    p = v.cap.props
    assert p[cv2.CAP_PROP_FOURCC] == cv2.VideoWriter_fourcc(*"MJPG")
    assert p[cv2.CAP_PROP_FRAME_WIDTH] == 1280 and p[cv2.CAP_PROP_FRAME_HEIGHT] == 720
    assert p[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_MANUAL and p[cv2.CAP_PROP_AUTO_WB] == 0
    assert v.cap.released


def test_nothing_is_set_when_nothing_is_asked(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(1)
    v.stop()
    assert v.cap.props == {} and v.cap.src == 1
