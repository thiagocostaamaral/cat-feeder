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
STABILITY_GRAMS = 2.0


class HX711:
    def __init__(self, dt_pin=24, sck_pin=25, gain="A128", history=120):
        self.dt_pin = dt_pin
        self.sck_pin = sck_pin
        self.gain = gain
        self.samples = deque(maxlen=history)
        self.points = []
        self.raw = 0
        self.weight = 0.0
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
            points = data.get("points")
            if isinstance(points, list):
                self.points = [{"grams": float(p["grams"]), "raw": int(p["raw"])} for p in points]
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            self.points = []

    def _save(self):
        with open(SCALE_FILE, "w") as f:
            json.dump({"points": self.points}, f, indent=2)

    def _start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _sorted_points(self):
        return sorted(self.points, key=lambda p: p["raw"])

    def is_calibrated(self):
        raw_values = [p["raw"] for p in self.points]
        return len(raw_values) >= 2 and len(set(raw_values)) >= 2

    def grams_for(self, raw):
        points = self._sorted_points()
        if len(points) < 2:
            return None

        segments = [(a, b) for a, b in zip(points, points[1:]) if b["raw"] > a["raw"]]
        if not segments:
            return None

        if raw <= points[0]["raw"]:
            low, high = segments[0]
        elif raw >= points[-1]["raw"]:
            low, high = segments[-1]
        else:
            low, high = segments[0]
            for a, b in segments:
                if a["raw"] <= raw <= b["raw"]:
                    low, high = a, b
                    break

        span = high["raw"] - low["raw"]
        return low["grams"] + (raw - low["raw"]) * (high["grams"] - low["grams"]) / span

    def _warning(self):
        points = self._sorted_points()
        if len(points) < 3:
            return None
        steps = [b["grams"] - a["grams"] for a, b in zip(points, points[1:])]
        if any(step > 0 for step in steps) and any(step < 0 for step in steps):
            return "calibration points are not monotonic, check the table"
        return None

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

    def _loop(self):
        while self._running:
            raw = self._read_valid()
            if raw is None:
                time.sleep(0.5)
                continue
            self.raw = raw
            grams = self.grams_for(raw)
            self.weight = grams if grams is not None else 0.0
            if grams is not None:
                self.samples.append(round(grams, 1))
            time.sleep(0.05)

    def _sample(self, count=16):
        values = []
        for _ in range(count):
            raw = self._read_valid()
            if raw is not None:
                values.append(raw)
        if not values:
            return None
        values.sort()
        return values[len(values) // 2]

    def capture(self, count=16):
        raw = self._sample(count)
        if raw is None:
            return None
        return {"raw": raw, "grams": self.grams_for(raw)}

    def tare(self, count=16):
        raw = self._sample(count)
        if raw is None:
            return None
        zeros = [p for p in self.points if abs(p["grams"]) < 1e-9]
        if zeros:
            zeros[0]["raw"] = raw
        else:
            self.points.append({"grams": 0.0, "raw": raw})
        self._save()
        return raw

    def set_points(self, points):
        cleaned = []
        for point in points:
            grams = float(point["grams"])
            raw = int(point["raw"])
            if grams < 0:
                raise ValueError("weights must be zero or positive")
            cleaned.append({"grams": grams, "raw": raw})
        raws = [p["raw"] for p in cleaned]
        if len(raws) != len(set(raws)):
            raise ValueError("two points share the same raw signal")
        self.points = cleaned
        self._save()
        return self.points

    def get_state(self):
        recent = list(self.samples)[-8:]
        stable = len(recent) >= 4 and (max(recent) - min(recent)) <= STABILITY_GRAMS
        calibrated = self.is_calibrated()
        grams = self.grams_for(self.raw) if calibrated else None
        return {
            "available": self.available,
            "error": self.error,
            "calibrated": calibrated,
            "grams": round(grams, 1) if grams is not None else None,
            "stable": stable,
            "raw": self.raw,
            "raw_hex": "0x%06X" % (self.raw & 0xFFFFFF),
            "pulse_us": self.pulse_us,
            "points": self._sorted_points(),
            "warning": self._warning()
        }

    def close(self):
        self._running = False
        if self._handle is not None:
            try:
                gpio.gpio_write(self._handle, self.sck_pin, 0)
                gpio.gpiochip_close(self._handle)
            except Exception:
                pass
