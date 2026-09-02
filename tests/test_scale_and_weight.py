"""The scale is actually read, the HX711 protocol is right, and one item's
mass is only ever the difference the pan saw (docs/research/09, D5 and D6)."""
import time

import pytest

from recognition.fusion import item_weight_for_scan
from recognition.scale import HX711Scale, ScaleStream, SimulatedScale, decode_hx711


# --------------------------------------------------------------- the protocol

class FakeLgpio:
    """Just enough of lgpio to run the HX711 bit protocol against known words.

    DOUT is low when a conversion is ready.  Each rising edge on SCK shifts the
    next bit out, MSB first; after the 24th the chip reports busy until the
    reader comes back for the next conversion, at which point the fake records
    how many pulses the previous read used (24 + gain pulses).
    """

    def __init__(self, words):
        self.words = list(words)
        self.pulses = []
        self.sck = 0
        self.closed = False
        self._load()

    def _load(self):
        self.word = self.words.pop(0) if self.words else 0
        self.count = 0
        self.bit = 0

    def gpiochip_open(self, chip):
        return 42

    def gpiochip_close(self, h):
        self.closed = True

    def gpio_claim_input(self, h, pin):
        self.dout_pin = pin

    def gpio_claim_output(self, h, pin, level=0):
        self.sck_pin = pin

    def gpio_read(self, h, pin):
        assert pin == self.dout_pin
        if self.sck == 0 and self.count == 0:
            return 0                                  # ready: DOUT low
        if self.sck == 0 and self.count >= 24:
            # the reader is back for the next conversion
            self.pulses.append(self.count)
            self._load()
            return 0
        return self.bit

    def gpio_write(self, h, pin, level):
        assert pin == self.sck_pin
        if level == 1 and self.sck == 0:              # rising edge
            self.count += 1
            self.bit = (self.word >> (24 - self.count)) & 1 if self.count <= 24 else 1
        self.sck = level


def test_twos_complement_decoding():
    assert decode_hx711(0x7FFFFF) == 8388607
    assert decode_hx711(0x800000) == -8388608
    assert decode_hx711(0xFFFFFF) == -1
    assert decode_hx711(0x000010) == 16


def test_hx711_reads_words_with_25_pulses_at_gain_128():
    fake = FakeLgpio([0x7FFFFF, 0x800000, 0xFFFFFF, 0x000010])
    cell = HX711Scale(5, 6, counts_per_gram=1.0, offset_counts=0.0, gpio=fake)
    # the constructor consumed the first word to set the gain
    assert [cell.read_raw() for _ in range(3)] == [-8388608.0, -1.0, 16.0]
    assert fake.pulses == [25, 25, 25]
    assert fake.dout_pin == 5 and fake.sck_pin == 6


def test_gain_64_clocks_27_pulses_and_grams_follow_the_calibration():
    fake = FakeLgpio([0, 120000 + 412 * 500, 120000 + 412 * 500])
    cell = HX711Scale(5, 6, counts_per_gram=412.0, offset_counts=120000.0, gain=64, gpio=fake)
    cell.read_raw()
    assert fake.pulses == [27]
    assert cell.read_grams() == pytest.approx(500.0)
    cell.close()
    assert fake.closed


# ---------------------------------------------------------------- the stream

def _wait(predicate, seconds=3.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        v = predicate()
        if v is not None and v is not False:
            return v
        time.sleep(0.02)
    return None


def test_the_stream_fills_the_window_so_a_reading_can_be_trusted():
    cell = SimulatedScale(seed=3)
    stream = ScaleStream(cell, hz=200)
    try:
        assert stream.read_stable_grams() is None          # nothing on the pan
        cell.place(200.0)
        grams = _wait(stream.read_stable_grams)
        assert grams == pytest.approx(200.0, abs=3.0)
        cell.clear()
        assert _wait(lambda: stream.read_stable_grams() is None)
    finally:
        stream.stop()


def test_zero_tracking_removes_slow_drift_between_baskets():
    """Two grams a second of drift, the pan empty: without re-zeroing the
    reading walks off; with it the pan stays at zero."""
    cell = SimulatedScale(noise_g=0.2, drift_g_per_min=120.0, seed=4)
    stream = ScaleStream(cell, hz=100)
    try:
        time.sleep(2.0)
        assert abs(stream.value()) < 1.5
    finally:
        stream.stop()


def test_the_stream_forwards_the_cells_extras():
    cell = SimulatedScale()
    stream = ScaleStream(cell, hz=50)
    try:
        stream.place(75.0)                                 # a SimulatedScale method
        assert cell._on_pan_g == 75.0
    finally:
        stream.stop()


# ------------------------------------------------------------ one item's mass

def test_one_new_item_weighs_the_difference_the_pan_saw():
    assert item_weight_for_scan(80.0, 0.0, 1) == 80.0
    assert item_weight_for_scan(155.0, 75.0, 1) == 80.0


def test_two_items_on_the_mat_give_the_fusion_nothing():
    assert item_weight_for_scan(155.0, 0.0, 2) is None
    assert item_weight_for_scan(155.0, 0.0, 0) is None


def test_a_pan_that_went_down_or_was_unread_gives_nothing():
    assert item_weight_for_scan(70.0, 75.0, 1) is None    # something was bagged
    assert item_weight_for_scan(None, 0.0, 1) is None     # unsettled
    assert item_weight_for_scan(3.0, 0.0, 1) is None      # below the noise floor
