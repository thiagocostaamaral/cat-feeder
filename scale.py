import json
import os
import threading
import time
from collections import deque

try:
    import lgpio as gpio
    GPIO_AVAILABLE = True
    GPIO_ERROR = None
except Exception as exc:
    gpio = None
    GPIO_AVAILABLE = False
    GPIO_ERROR = str(exc)

SCALE_FILE = os.path.join(os.path.dirname(__file__), "scale.json")
READY_TIMEOUT = 0.5
MAX_PULSE_US = 60
GAIN_PULSES = {"A128": 1, "B32": 2, "A64": 3}
INVALID_FRAMES = (0x000000, 0xFFFFFF, 0x7FFFFF, 0x800000)
MAX_RETRIES = 5


class HX711:
    def __init__(self, dt_pin=24, sck_pin=25, gain="A128", history=120):
        self.dt_pin = dt_pin
        self.sck_pin = sck_pin
        self.gain = gain
        self.samples = deque(maxlen=history)
        self.raw = 0
        self.weight = 0.0
        self.scale = 0.0
        self.offset = 0
        self.pulse_us = 0.0
        self.available = False
        self.error = None
        self._last_fault = None
        self._handle = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._load()

        if not GPIO_AVAILABLE:
            self.error = "lgpio not available: %s" % GPIO_ERROR
            return

        try:
            self._handle = gpio.gpiochip_open(0)
            gpio.gpio_claim_output(self._handle, self.sck_pin, 0)
            gpio.gpio_claim_input(self._handle, self.dt_pin, getattr(gpio, "SET_PULL_UP", 0))
            self.available = True
            self.reset()
            self._start()
        except Exception as exc:
            self.error = str(exc)

    def _load(self):
        try:
            with open(SCALE_FILE) as f:
                data = json.load(f)
            self.offset = int(data.get("offset", 0))
            self.scale = float(data.get("scale", 0.0))
        except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
            pass

    def _save(self):
        with open(SCALE_FILE, "w") as f:
            json.dump({"offset": self.offset, "scale": self.scale}, f, indent=2)

    def _start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def reset(self):
        with self._lock:
            if not self.available:
                return False
            gpio.gpio_write(self._handle, self.sck_pin, 0)
            gpio.gpio_write(self._handle, self.sck_pin, 1)
            time.sleep(0.00012)
            gpio.gpio_write(self._handle, self.sck_pin, 0)
            time.sleep(0.00012)
            return True

    def _read_frame(self):
        with self._lock:
            if not self.available:
                return None

            deadline = time.time() + READY_TIMEOUT
            while gpio.gpio_read(self._handle, self.dt_pin):
                if time.time() > deadline:
                    self._last_fault = "timeout"
                    self.error = "no data from HX711 (DOUT stayed high)"
                    return None
                time.sleep(0.0005)

            value = 0
            slowest = 0.0
            for _ in range(24):
                start = time.perf_counter()
                gpio.gpio_write(self._handle, self.sck_pin, 1)
                gpio.gpio_write(self._handle, self.sck_pin, 0)
                elapsed = time.perf_counter() - start
                if elapsed > slowest:
                    slowest = elapsed
                value = (value << 1) | gpio.gpio_read(self._handle, self.dt_pin)

            for _ in range(GAIN_PULSES.get(self.gain, 1)):
                gpio.gpio_write(self._handle, self.sck_pin, 1)
                gpio.gpio_write(self._handle, self.sck_pin, 0)

            self.pulse_us = round(slowest * 1e6, 1)

            if self.pulse_us >= MAX_PULSE_US:
                self._last_fault = "slow"
                self.error = "clock pulse too slow (%.0f us)" % self.pulse_us
                return None

            if value & 0x800000:
                value -= 1 << 24
            self._last_fault = None
            self.error = None
            return value

    def _read_valid(self, retries=MAX_RETRIES):
        for _ in range(retries):
            raw = self._read_frame()
            if raw is None:
                if self._last_fault == "slow":
                    continue
                return None
            if (raw & 0xFFFFFF) not in INVALID_FRAMES:
                self.error = None
                return raw
            self.error = "invalid readings, check load cell wiring"
        return None

    def _weight_for(self, raw):
        if not self.scale:
            return 0.0
        return (raw - self.offset) / self.scale

    def _loop(self):
        while self._running:
            raw = self._read_valid()
            if raw is None:
                time.sleep(0.5)
                continue
            self.raw = raw
            self.weight = self._weight_for(raw)
            self.samples.append(round(self.weight, 1))
            time.sleep(0.05)

    def _sample(self, count):
        values = []
        for _ in range(count):
            raw = self._read_valid()
            if raw is not None:
                values.append(raw)
        if not values:
            return None
        values.sort()
        return values[len(values) // 2]

    def tare(self, count=16):
        median = self._sample(count)
        if median is None:
            return None
        self.offset = median
        self._save()
        return self.offset

    def calibrate(self, known_grams, count=16):
        if known_grams <= 0:
            raise ValueError("known weight must be positive")
        median = self._sample(count)
        if median is None:
            return None
        delta = median - self.offset
        if abs(delta) < 1:
            raise ValueError("no load detected, place the weight and try again")
        self.scale = delta / float(known_grams)
        self._save()
        return self.scale

    def reset_calibration(self):
        self.scale = 0.0
        self.offset = 0
        self._save()

    def get_state(self):
        recent = list(self.samples)[-8:]
        stable = len(recent) >= 4 and (max(recent) - min(recent)) <= 2.0
        return {
            "available": self.available,
            "error": self.error,
            "calibrated": bool(self.scale),
            "grams": round(self.weight, 1),
            "stable": stable,
            "raw": self.raw,
            "raw_hex": "0x%06X" % (self.raw & 0xFFFFFF),
            "pulse_us": self.pulse_us,
            "offset": self.offset,
            "scale": round(self.scale, 3) if self.scale else None,
            "samples": list(self.samples)
        }

    def close(self):
        self._running = False
        if self._handle is not None:
            try:
                gpio.gpio_write(self._handle, self.sck_pin, 0)
                gpio.gpiochip_close(self._handle)
            except Exception:
                pass
