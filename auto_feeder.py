import json
import os
import threading
import time
from collections import deque

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "feeding.json")
EVENT_FILE = os.path.join(os.path.dirname(__file__), "feed_log.jsonl")

DEFAULTS = {
    "enabled": True,
    "low_g": 10.0,
    "target_g": 40.0,
    "tolerance_g": 2.0,
    "fine_gap_g": 8.0,
    "coarse_factor": 0.85,
    "fine_factor": 0.5,
    "min_steps": 5,
    "max_cycle_steps": 400,
    "max_total_steps": 2500,
    "max_cycles": 12,
    "settle_s": 2.0,
    "low_dwell_s": 300.0,
    "cooldown_s": 300.0,
    "plausible_max_g": 300.0,
    "bowl_min_g": -20.0,
    "grams_per_step": 0.08,
}

CHUNK_STEPS = 25


class AutoFeeder:
    def __init__(self, scale, motor, config_path=None, event_path=None, poll=1.0):
        self.scale = scale
        self.motor = motor
        self._config_path = config_path or CONFIG_FILE
        self._event_path = event_path or EVENT_FILE
        self._poll = poll
        self._lock = threading.Lock()
        self.config = dict(DEFAULTS)
        self._load()

        self.state = "idle"
        self.message = "starting"
        self._low_since = None
        self._recent = deque(maxlen=5)
        self._bad_ticks = 0
        self._last_reset = None
        self._last_attempt_end = 0.0
        self._stop_requested = False
        self._dose_requested = False
        self._no_output = 0
        self._last_refill = None
        self._events = []
        self._running = False
        self._thread = None
        self._load_events()

    def _load(self):
        try:
            with open(self._config_path) as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                for key, value in stored.items():
                    if key in DEFAULTS:
                        self.config[key] = value
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            pass

    def _save(self):
        with open(self._config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def _load_events(self):
        try:
            with open(self._event_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except FileNotFoundError:
            return
        self._events = self._events[-50:]

    def _log_event(self, event):
        self._events.append(event)
        self._events = self._events[-50:]
        with open(self._event_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def set_config(self, patch):
        if not isinstance(patch, dict):
            raise ValueError("config must be an object")
        candidate = dict(self.config)
        for key, value in patch.items():
            if key not in DEFAULTS:
                continue
            default = DEFAULTS[key]
            try:
                if isinstance(default, bool):
                    candidate[key] = bool(value)
                elif isinstance(default, int):
                    candidate[key] = int(value)
                else:
                    candidate[key] = float(value)
            except (TypeError, ValueError):
                raise ValueError("invalid value for %s" % key)

        if candidate["target_g"] <= candidate["low_g"]:
            raise ValueError("target must be greater than low")
        if candidate["grams_per_step"] <= 0:
            raise ValueError("grams_per_step must be positive")
        if candidate["tolerance_g"] < 0:
            raise ValueError("tolerance must be zero or positive")

        with self._lock:
            self.config = candidate
            self._save()
        return dict(candidate)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_requested = True

    def dose_once(self):
        self._dose_requested = True

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as exc:
                self.state = "fault"
                self.message = str(exc)
            time.sleep(self._poll)

    def _read_weight(self):
        reading = self.scale.capture()
        if not reading:
            return None
        return reading.get("grams")

    def _burst_steps(self, gap):
        cfg = self.config
        grams_per_step = max(cfg["grams_per_step"], 0.001)
        factor = cfg["coarse_factor"] if gap > cfg["fine_gap_g"] else cfg["fine_factor"]
        steps = int(gap * factor / grams_per_step)
        steps = max(steps, cfg["min_steps"])
        return min(steps, cfg["max_cycle_steps"])

    def _dose(self, steps):
        done = 0
        while done < steps:
            if self._stop_requested:
                break
            chunk = min(CHUNK_STEPS, steps - done)
            self.motor.rotate(chunk)
            done += chunk
        return done

    def _learn(self, delta, steps):
        if steps <= 0 or delta <= 0:
            return
        with self._lock:
            grams_per_step = self.config["grams_per_step"]
            ratio = delta / steps
            if not (0.2 * grams_per_step <= ratio <= 5.0 * grams_per_step):
                return
            learned = 0.5 * grams_per_step + 0.5 * ratio
            learned = min(max(learned, 0.005), 0.5)
            self.config["grams_per_step"] = round(learned, 4)
            self._save()

    def _filtered_weight(self):
        if not self._recent:
            return self.scale.weight
        values = sorted(self._recent)
        return values[len(values) // 2]

    def _reset_dwell(self, reason):
        if self._low_since is not None:
            self._last_reset = {"t": time.time(), "reason": reason}
        self._low_since = None

    def _tick(self):
        cfg = self.config

        if not cfg["enabled"]:
            self.state = "off"
            self.message = "auto feeding disabled"
            self._reset_dwell("auto disabled")
            return

        if not self.scale.available:
            self.state = "fault"
            self.message = self.scale.error or "scale not available"
            return

        if self.scale.error:
            self.state = "fault"
            self.message = self.scale.error
            return

        if not self.scale.is_calibrated():
            self.state = "fault"
            self.message = "scale not calibrated"
            return

        weight = self.scale.weight
        if cfg["bowl_min_g"] <= weight <= cfg["plausible_max_g"]:
            self._recent.append(weight)
            self._bad_ticks = 0
        else:
            self._bad_ticks += 1
            if self._bad_ticks >= 3:
                self._recent.clear()
                self._reset_dwell("implausible weight (%.0f g)" % weight)
                self.state = "fault"
                self.message = "implausible weight (%.0f g)" % weight
            else:
                self.state = "fault"
                self.message = "implausible reading ignored (%.0f g)" % weight
            return

        if self._dose_requested:
            self._dose_requested = False
            self._run_refill()
            return

        filtered = self._filtered_weight()
        if len(self._recent) < 3:
            self.state = "idle"
            self.message = "%.1f g" % filtered
            return
        if min(self._recent) >= cfg["low_g"]:
            self._reset_dwell("weight back to %.1f g" % filtered)
            self.state = "idle"
            self.message = "%.1f g" % filtered
            return

        now = time.time()
        if self._low_since is None:
            self._low_since = now

        dwell_left = cfg["low_dwell_s"] - (now - self._low_since)
        cooldown_left = cfg["cooldown_s"] - (now - self._last_attempt_end)
        if dwell_left > 0 or cooldown_left > 0:
            self.state = "waiting"
            if cooldown_left > 0:
                self.message = "cooldown %.0fs" % cooldown_left
            else:
                self.message = "low for %.0fs" % (now - self._low_since)
            return

        if not self.scale.stable:
            self.state = "waiting"
            self.message = "waiting for a stable reading"
            return

        self._run_refill()

    def _run_refill(self):
        cfg = self.config
        self._stop_requested = False
        self._no_output = 0

        before = self._read_weight()
        if before is None or before < cfg["bowl_min_g"] or before > cfg["plausible_max_g"]:
            self.state = "fault"
            self.message = "no usable weight reading"
            self._last_attempt_end = time.time()
            return

        total_steps = 0
        cycles = 0
        current = before
        result = "max cycles"

        while cycles < cfg["max_cycles"]:
            if self._stop_requested:
                result = "stopped"
                break

            gap = cfg["target_g"] - current
            if gap <= cfg["tolerance_g"]:
                result = "ok"
                break

            steps = self._burst_steps(gap)
            if total_steps + steps > cfg["max_total_steps"]:
                result = "max total steps"
                break

            cycles += 1
            self.state = "dosing"
            self.message = "dosing %d steps" % steps
            done = self._dose(steps)
            total_steps += done

            if done == 0:
                result = "stopped"
                break

            self.state = "settling"
            self.message = "settling"
            time.sleep(cfg["settle_s"])

            after = self._read_weight()
            if after is None:
                result = "no reading"
                break

            delta = after - current
            if delta <= 0.5:
                self._no_output += 1
            else:
                self._no_output = 0
                self._learn(delta, done)

            if self._no_output >= 2:
                result = "nothing dispensed (hopper empty?)"
                break

            current = after

        self._finish_refill(before, current, total_steps, cycles, result)

    def _finish_refill(self, before, after, steps, cycles, result):
        now = time.time()
        self._last_attempt_end = now
        self._reset_dwell("refill finished")
        self._last_refill = {
            "t": now,
            "before": round(before, 1),
            "after": None if after is None else round(after, 1),
            "steps": steps,
            "cycles": cycles,
            "result": result
        }
        self._log_event(self._last_refill)

        if result == "ok":
            self.state = "idle"
            self.message = "refilled to %.1f g" % after
        else:
            self.state = "fault"
            self.message = result

    def get_state(self):
        cfg = dict(self.config)
        now = time.time()
        dwell_left = 0.0
        if self._low_since is not None:
            dwell_left = max(cfg["low_dwell_s"] - (now - self._low_since), 0.0)
        cooldown_left = max(cfg["cooldown_s"] - (now - self._last_attempt_end), 0.0)
        return {
            "enabled": cfg["enabled"],
            "state": self.state,
            "message": self.message,
            "weight": round(self.scale.weight, 1),
            "filtered_g": round(self._filtered_weight(), 1),
            "low_g": cfg["low_g"],
            "target_g": cfg["target_g"],
            "tolerance_g": cfg["tolerance_g"],
            "grams_per_step": cfg["grams_per_step"],
            "low_for_s": round(now - self._low_since, 0) if self._low_since is not None else 0.0,
            "dwell_left_s": round(dwell_left, 0),
            "cooldown_left_s": round(cooldown_left, 0),
            "last_reset": self._last_reset,
            "last_refill": self._last_refill,
            "events": self._events[-10:],
            "config": cfg
        }
