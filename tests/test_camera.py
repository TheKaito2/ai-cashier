"""The camera settings in config actually reach the driver (docs/research/09, D9)."""
import cv2
import numpy as np

from scanner.detection.camera import (V4L2_EXPOSURE_AUTO, V4L2_EXPOSURE_MANUAL,
                                      VideoStream)

#: what the driver reports while auto-exposure is running
SETTLED_EXPOSURE, SETTLED_WB = 156.0, 4600.0


class FakeCapture:
    #: 0 is what a camera that will not report its exposure returns
    reports = {cv2.CAP_PROP_EXPOSURE: SETTLED_EXPOSURE,
               cv2.CAP_PROP_WB_TEMPERATURE: SETTLED_WB}

    def __init__(self, src):
        self.src, self.props, self.released = src, {}, False

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def get(self, prop):
        return self.reports.get(prop, 0.0)

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


def test_locking_the_exposure_keeps_the_value_auto_mode_had_settled_on(monkeypatch):
    """Switching V4L2 to manual does not carry the automatic value over - the
    driver falls back to its own default, and on the rig's webcam that is a
    nearly black picture.  Locking must mean "freeze it here"."""
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(0, lock_exposure=True)
    v.stop()
    assert v.cap.props[cv2.CAP_PROP_EXPOSURE] == SETTLED_EXPOSURE
    assert v.cap.props[cv2.CAP_PROP_WB_TEMPERATURE] == SETTLED_WB


def test_a_camera_that_will_not_report_its_exposure_is_left_on_auto(monkeypatch):
    """Better a picture that drifts than a picture that is black."""
    class Silent(FakeCapture):
        reports = {}

    monkeypatch.setattr(cv2, "VideoCapture", Silent)
    v = VideoStream(0, lock_exposure=True)
    v.stop()
    assert v.cap.props[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_AUTO
    assert cv2.CAP_PROP_EXPOSURE not in v.cap.props


def test_nothing_is_set_when_nothing_is_asked(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(1)
    v.stop()
    assert v.cap.props == {} and v.cap.src == 1
