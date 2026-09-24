"""The camera settings in config actually reach the driver (docs/research/09, D9).

The exposure lock has its own section: it stranded the rig's webcam in a nearly
black picture, and `lock_exposure: false` did not undo it, because V4L2 keeps
these controls on the device rather than in the process.
"""
import cv2
import numpy as np

from scanner.detection.camera import (V4L2_EXPOSURE_AUTO, V4L2_EXPOSURE_MANUAL,
                                      VideoStream)


class FakeCapture:
    """A camera whose picture goes dark the moment exposure is set to manual -
    which is exactly what the rig's Sunplus webcam does."""

    goes_dark_when_locked = True

    def __init__(self, src):
        self.src, self.props, self.released = src, {}, False
        self.manual = False

    def set(self, prop, value):
        self.props[prop] = value
        if prop == cv2.CAP_PROP_AUTO_EXPOSURE:
            self.manual = value == V4L2_EXPOSURE_MANUAL
        return True

    def get(self, prop):
        return 0.0

    def read(self):
        dark = self.manual and self.goes_dark_when_locked
        level = 12 if dark else 150
        return True, np.full((4, 4, 3), level, np.uint8)

    def release(self):
        self.released = True


class WellBehaved(FakeCapture):
    """A camera that honours a manual exposure without going dark."""
    goes_dark_when_locked = False


def test_fourcc_and_size_are_applied(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", WellBehaved)
    v = VideoStream(0, fourcc="MJPG", size=(1280, 720))
    v.stop()
    p = v.cap.props
    assert p[cv2.CAP_PROP_FOURCC] == cv2.VideoWriter_fourcc(*"MJPG")
    assert p[cv2.CAP_PROP_FRAME_WIDTH] == 1280 and p[cv2.CAP_PROP_FRAME_HEIGHT] == 720
    assert v.cap.released


def test_a_lock_that_honours_the_exposure_is_kept(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", WellBehaved)
    v = VideoStream(0, lock_exposure=True, exposure=156)
    v.stop()
    assert v.cap.props[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_MANUAL
    assert v.cap.props[cv2.CAP_PROP_AUTO_WB] == 0
    assert v.cap.props[cv2.CAP_PROP_EXPOSURE] == 156


def test_the_lock_measures_against_auto_even_if_the_device_was_left_in_manual(monkeypatch):
    """V4L2 keeps the control on the device.  A camera left dark by a previous
    run reads dark before the lock too, so a naive before/after comparison sees
    no collapse and preserves the blindness."""
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    stranded = FakeCapture(0)
    stranded.manual = True                       # as a previous process left it
    monkeypatch.setattr(cv2, "VideoCapture", lambda src: stranded)

    v = VideoStream(0, lock_exposure=True)
    v.stop()
    assert stranded.props[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_AUTO


def test_a_lock_that_blinds_the_camera_is_undone(monkeypatch):
    """The rig's camera reports an exposure it will not reproduce in manual, so
    locking it produced a nearly black frame and every scan saw nothing.  A till
    that drifts is a measurement problem; a till that cannot see is not a till."""
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(0, lock_exposure=True)
    v.stop()
    assert v.cap.props[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_AUTO
    assert v.cap.props[cv2.CAP_PROP_AUTO_WB] == 1


def test_not_locking_actively_restores_auto(monkeypatch):
    """V4L2 keeps these on the device.  A previous run with the lock on would
    otherwise leave every later run dark, including one configured not to lock."""
    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    v = VideoStream(0, lock_exposure=False)
    v.stop()
    assert v.cap.props[cv2.CAP_PROP_AUTO_EXPOSURE] == V4L2_EXPOSURE_AUTO
    assert v.cap.props[cv2.CAP_PROP_AUTO_WB] == 1


def test_nothing_else_is_set_when_nothing_is_asked(monkeypatch):
    monkeypatch.setattr(cv2, "VideoCapture", WellBehaved)
    v = VideoStream(1)
    v.stop()
    assert v.cap.src == 1
    assert cv2.CAP_PROP_FOURCC not in v.cap.props
    assert cv2.CAP_PROP_EXPOSURE not in v.cap.props
