import json
import os
import sys
import tempfile
import time
import types

DT = 24
SCK = 25


class FakeGPIO(types.ModuleType):
    def __init__(self):
        super().__init__("lgpio")
        self.SET_PULL_UP = 32
        self.raw = 650          # 6.5 g at 100 counts/g
        self._bits = []

    def gpiochip_open(self, chip):
        return 1

    def gpio_claim_output(self, handle, pin, level=0):
        return 0

    def gpio_claim_input(self, handle, pin, flags=0):
        return 0

    def gpio_read(self, handle, pin):
        if pin != DT:
            return 0
        if not self._bits:
            self._bits = [(self.raw & 0xFFFFFF) >> i & 1 for i in range(23, -1, -1)]
            return 0
        return self._bits.pop(0)

    def gpio_write(self, handle, pin, level):
        pass

    def gpiochip_close(self, handle):
        pass


gpio = FakeGPIO()
sys.modules["lgpio"] = gpio

import auto_feeder
import scale as scale_mod

scale_mod.SCALE_FILE = os.path.join(tempfile.gettempdir(), "int_scale.json")
auto_feeder.CONFIG_FILE = os.path.join(tempfile.gettempdir(), "int_feeding.json")
auto_feeder.EVENT_FILE = os.path.join(tempfile.gettempdir(), "int_feed_log.jsonl")
for path in (scale_mod.SCALE_FILE, auto_feeder.CONFIG_FILE, auto_feeder.EVENT_FILE):
    if os.path.exists(path):
        os.remove(path)


class FakeMotor:
    def __init__(self):
        self.total = 0

    def rotate(self, steps):
        gpio.raw += steps * 8      # 8 counts per step = 0.08 g/step
        self.total += steps

    def stop(self):
        pass


scale = scale_mod.HX711(dt_pin=DT, sck_pin=SCK)
scale.set_points([{"grams": 0, "raw": 0}, {"grams": 50, "raw": 5000}])
time.sleep(0.3)
assert scale.available and scale.is_calibrated()
assert scale.error is None, scale.error

# the attribute the controller relies on must exist on the real class
assert hasattr(scale, "stable"), "HX711.stable is missing (this was the crash)"
assert scale.stable is True
assert scale.get_state()["stable"] is scale.stable
assert abs(scale.weight - 6.5) < 0.2, scale.weight

motor = FakeMotor()
with open(auto_feeder.CONFIG_FILE, "w") as f:
    json.dump({
        "low_g": 10.0, "target_g": 40.0, "tolerance_g": 2.0,
        "low_dwell_s": 0.05, "cooldown_s": 0.05, "settle_s": 0.02,
        "max_cycles": 10, "max_total_steps": 2500, "max_cycle_steps": 400,
        "grams_per_step": 0.08
    }, f)

feeder = auto_feeder.AutoFeeder(scale, motor, poll=0.02)
feeder.start()
time.sleep(2.5)
feeder._running = False
feeder.stop()
feeder._thread.join(2)

state = feeder.get_state()
assert state["state"] != "fault", "controller faulted: %s" % state["message"]
assert state["last_refill"] is not None, state
assert state["last_refill"]["result"] == "ok", state["last_refill"]
grams = float(state["weight"])
assert 38.0 <= grams <= 44.0, grams
print("real-scale integration ok: 6.5 g -> %.1f g in %d steps (logged %s)"
      % (grams, motor.total, state["last_refill"]["result"]))

# stability still reported while idle
time.sleep(0.4)
assert scale.stable is True

scale.close()
for path in (scale_mod.SCALE_FILE, auto_feeder.CONFIG_FILE, auto_feeder.EVENT_FILE):
    if os.path.exists(path):
        os.remove(path)

print("integration verification passed")
