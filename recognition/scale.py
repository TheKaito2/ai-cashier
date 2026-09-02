"""The weighing platform.

Vision alone cannot separate Lay's Original from Lay's Ridged Original - the
packets differ mainly in a word.  Grams can.  The scale is also what catches an
item being swapped after it was scanned, which was the security hole named in
the version 2 plan.

Three parts:

  * `_FilteredScale`  - the moving-average filter and the settling test that
                        every cell shares;
  * `SimulatedScale` / `HX711Scale` - a cell in software, and the real one,
                        bit-banged over lgpio (the GPIO library that works on
                        the Raspberry Pi 5);
  * `ScaleStream`     - reads the cell continuously on its own thread.  Until
                        the architecture review (docs/research/09, D5) nothing
                        in the till polled the scale at all, so the filter
                        window never filled and every weight question was
                        answered "unknown".
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import deque
from typing import Protocol

logger = logging.getLogger(__name__)


class Scale(Protocol):
    def read_grams(self) -> float: ...
    def read_stable_grams(self, min_g: float = ...) -> float | None: ...
    def tare(self) -> None: ...
    def is_settled(self) -> bool: ...


class _FilteredScale:
    """Shared filtering: a load cell is noisy and takes time to settle.

    Readings go through a moving average, and `is_settled` reports whether the
    window has stopped moving - the till must not price an item while the pan is
    still bouncing.  A lock guards the window because `ScaleStream` pushes from
    its own thread while the till reads.
    """

    #: a 5 kg bar cell through an HX711 at 10 SPS is quiet to well under a gram
    SETTLE_STDEV_G = 1.5
    WINDOW = 8
    #: below this, treat the pan as empty rather than as a very light product
    MIN_MEANINGFUL_G = 5.0

    def __init__(self, window: int = WINDOW):
        self._window: deque[float] = deque(maxlen=window)
        self._offset_g = 0.0
        self._lock = threading.Lock()

    def _push(self, grams: float) -> float:
        with self._lock:
            self._window.append(grams)
            return statistics.fmean(self._window) - self._offset_g

    def value(self) -> float | None:
        """The latest filtered reading, without touching the hardware."""
        with self._lock:
            if not self._window:
                return None
            return statistics.fmean(self._window) - self._offset_g

    def tare(self) -> None:
        """Call with the pan empty (or with the current basket as the new zero)."""
        with self._lock:
            self._offset_g = statistics.fmean(self._window) if self._window else 0.0

    def is_settled(self) -> bool:
        with self._lock:
            if len(self._window) < self._window.maxlen:
                return False
            return statistics.pstdev(self._window) < self.SETTLE_STDEV_G

    def read_stable_grams(self, min_g: float | None = None) -> float | None:
        """A reading fusion is allowed to use, or None.

        Never return a number the caller might mistake for a measurement.  An
        unsettled pan, or an empty one, reads near zero - and feeding that into
        the fusion makes every product look far too heavy, which drags the
        decision towards whichever enrolled product is lightest.  That is a
        wrong answer produced confidently, which is worse than no answer.
        """
        if not self.is_settled():
            return None
        grams = self.value()
        if grams is None:
            return None
        return grams if grams >= (min_g if min_g is not None else self.MIN_MEANINGFUL_G) else None


class SimulatedScale(_FilteredScale):
    """A load cell that only exists in software.

    Reproduces what makes a real one awkward - gaussian noise and slow thermal
    drift - so code written against it does not fall over on real hardware.
    """

    def __init__(self, noise_g: float = 0.8, drift_g_per_min: float = 0.5, seed: int = 0):
        super().__init__()
        import random
        self._rng = random.Random(seed)
        self._noise_g = noise_g
        self._drift = drift_g_per_min
        self._t0 = time.monotonic()
        self._on_pan_g = 0.0

    def place(self, grams: float) -> None:
        """Put something on the pan."""
        self._on_pan_g += grams

    def clear(self) -> None:
        self._on_pan_g = 0.0

    def read_grams(self) -> float:
        drift = self._drift * (time.monotonic() - self._t0) / 60.0
        raw = self._on_pan_g + drift + self._rng.gauss(0.0, self._noise_g)
        return self._push(raw)

    def settle(self) -> float:
        """Fill the window, as if the operator waited. Returns the settled reading."""
        value = 0.0
        for _ in range(self._window.maxlen):
            value = self.read_grams()
        return value


def decode_hx711(word: int) -> int:
    """The HX711 sends 24-bit two's complement, MSB first."""
    word &= 0xFFFFFF
    return word - (1 << 24) if word & 0x800000 else word


class HX711Scale(_FilteredScale):
    """A 5 kg bar load cell read through an HX711, bit-banged over lgpio.

    lgpio is the library the Raspberry Pi engineers put underneath gpiozero and
    the one that drives the Pi 5's RP1 GPIO controller.  The PyPI `hx711`
    package this project used to pin imports RPi.GPIO, which does not work on a
    Pi 5, and does not have the method the old code called (docs/research/09, D5).

    Protocol, from the datasheet: DOUT falls when a conversion is ready; each
    rising edge on PD_SCK shifts one bit out, MSB first, 24 bits; the total
    pulse count - 25, 26 or 27 - selects channel A gain 128, channel B gain 32
    or channel A gain 64 for the *next* conversion.  PD_SCK held high for more
    than 60 us powers the chip down, so the clock is toggled as tightly as
    Python allows and the reading is discarded if it comes back all ones.

        grams = (raw - offset_counts) / counts_per_gram

    Two-point calibration (`calibrate` below) gives both constants; they live
    in config/settings.json so calibration survives a restart.
    """

    GAIN_PULSES = {128: 1, 32: 2, 64: 3}

    def __init__(self, dout_pin: int, sck_pin: int,
                 counts_per_gram: float, offset_counts: float,
                 gain: int = 128, chip: int = 0, gpio=None):
        super().__init__()
        self.counts_per_gram = counts_per_gram
        self.offset_counts = offset_counts
        self._extra_pulses = self.GAIN_PULSES[gain]
        if gpio is None:
            try:
                import lgpio as gpio               # pragma: no cover - needs the Pi
            except ImportError as e:               # pragma: no cover
                raise RuntimeError(
                    "HX711Scale needs the lgpio package (pip install lgpio) and a "
                    "Raspberry Pi. Use SimulatedScale on a development machine."
                ) from e
        self._g = gpio
        self._h = gpio.gpiochip_open(chip)
        self._dout, self._sck = dout_pin, sck_pin
        gpio.gpio_claim_input(self._h, dout_pin)
        gpio.gpio_claim_output(self._h, sck_pin, 0)
        self._read_word()                          # the first read sets the gain

    def _ready(self, timeout_s: float = 1.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while self._g.gpio_read(self._h, self._dout):
            if time.monotonic() > deadline:
                return False
            time.sleep(0.001)
        return True

    def _read_word(self) -> int:
        if not self._ready():
            raise RuntimeError("HX711 not ready - check the DT/SCK wiring and the 3.3 V supply")
        word = 0
        for _ in range(24):
            self._g.gpio_write(self._h, self._sck, 1)
            word = (word << 1) | (1 if self._g.gpio_read(self._h, self._dout) else 0)
            self._g.gpio_write(self._h, self._sck, 0)
        for _ in range(self._extra_pulses):
            self._g.gpio_write(self._h, self._sck, 1)
            self._g.gpio_write(self._h, self._sck, 0)
        return decode_hx711(word)

    def read_raw(self, readings: int = 1) -> float:
        return statistics.fmean(self._read_word() for _ in range(max(1, readings)))

    def read_grams(self) -> float:
        return self._push((self.read_raw() - self.offset_counts) / self.counts_per_gram)

    def close(self) -> None:
        self._g.gpiochip_close(self._h)


#: a settled pan within this much of zero is re-zeroed, so slow drift never
#: accumulates between baskets (a scale's "zero tracking")
ZERO_TRACK_G = 5.0


class ScaleStream:
    """Reads the cell continuously on its own thread, as VideoStream does the camera.

    The filter window is therefore always full, `read_stable_grams()` can
    actually answer, and the pan is re-zeroed whenever it sits settled and
    near-empty - which is what "tare between baskets" means in practice.
    Everything the till asks the scale goes through here; the wrapped cell is
    never read from the UI thread.
    """

    def __init__(self, scale: _FilteredScale, hz: float = 10.0,
                 zero_track_g: float = ZERO_TRACK_G):
        self.scale = scale
        self._period = 1.0 / hz
        self._zero_track_g = zero_track_g
        self.stopped = False
        self.thread = threading.Thread(target=self._run, name="scale", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stopped:
            try:
                self.scale.read_grams()
                v = self.scale.value()
                if v is not None and v != 0.0 and abs(v) < self._zero_track_g \
                        and self.scale.is_settled():
                    self.scale.tare()
            except Exception as e:                 # a wiring fault must not kill the till
                logger.warning("scale read failed: %s", e)
                time.sleep(1.0)
            time.sleep(self._period)

    # ------------------------------------------------- the Scale protocol

    def read_grams(self) -> float:
        return self.scale.value() or 0.0

    def value(self) -> float | None:
        return self.scale.value()

    def read_stable_grams(self, min_g: float | None = None) -> float | None:
        return self.scale.read_stable_grams(min_g)

    def is_settled(self) -> bool:
        return self.scale.is_settled()

    def tare(self) -> None:
        self.scale.tare()

    def stop(self) -> None:
        self.stopped = True
        self.thread.join(timeout=2.0)

    def __getattr__(self, name):
        # place()/clear() on the simulated cell, close() on the real one
        return getattr(self.scale, name)


def calibrate(read_raw, known_mass_g: float, samples: int = 20) -> tuple[float, float]:
    """Two-point calibration. Returns (counts_per_gram, offset_counts).

    Caller prompts: empty the pan -> first phase; place the known mass -> second.
    `read_raw` is called for both, so this is testable without hardware.
    """
    if known_mass_g <= 0:
        raise ValueError("known_mass_g must be positive")

    empty = statistics.fmean(read_raw() for _ in range(samples))
    input(f"  place the {known_mass_g:g} g reference mass, then press Enter... ")
    loaded = statistics.fmean(read_raw() for _ in range(samples))

    counts_per_gram = (loaded - empty) / known_mass_g
    if abs(counts_per_gram) < 1e-9:
        raise RuntimeError("no change between empty and loaded - check the wiring")
    return counts_per_gram, empty
