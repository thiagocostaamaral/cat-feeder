import json
import os
import threading
import time

LOG_FILE = os.path.join(os.path.dirname(__file__), "weight_log.jsonl")
IDLE_INTERVAL = 600
PRESENCE_INTERVAL = 10
MAX_SAMPLES = 5000
MAX_RUNTIME_SAMPLES = 6000


class WeightLog:
    def __init__(self, scale, presence, path=None, idle_interval=IDLE_INTERVAL,
                 presence_interval=PRESENCE_INTERVAL, poll=1.0):
        self._scale = scale
        self._presence = presence
        self._path = path or LOG_FILE
        self._idle_interval = idle_interval
        self._presence_interval = presence_interval
        self._poll = poll
        self.samples = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._load()

    def _load(self):
        self.samples = []
        try:
            with open(self._path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        self.samples.append({"t": float(item["t"]), "g": float(item["g"])})
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        continue
        except FileNotFoundError:
            return

        if len(self.samples) > MAX_SAMPLES:
            self.samples = self.samples[-MAX_SAMPLES:]
            self._rewrite()

    def _rewrite(self):
        temp = self._path + ".tmp"
        with open(temp, "w") as f:
            for sample in self.samples:
                f.write(json.dumps(sample) + "\n")
        os.replace(temp, self._path)

    def interval(self):
        return self._presence_interval if self._presence.current else self._idle_interval

    def idle_interval(self):
        return self._idle_interval

    @property
    def presence_interval(self):
        return self._presence_interval

    def add(self, grams, timestamp=None):
        item = {
            "t": time.time() if timestamp is None else timestamp,
            "g": round(float(grams), 1)
        }
        with self._lock:
            self.samples.append(item)
            with open(self._path, "a") as f:
                f.write(json.dumps(item) + "\n")
            if len(self.samples) > MAX_RUNTIME_SAMPLES:
                self.samples = self.samples[-MAX_SAMPLES:]
                self._rewrite()

    def get_all(self, limit=1000):
        with self._lock:
            return list(self.samples[-limit:])

    def count(self):
        with self._lock:
            return len(self.samples)

    def clear(self):
        with self._lock:
            self.samples = []
            open(self._path, "w").close()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        last = 0.0
        while self._running:
            now = time.time()
            if now - last >= self.interval() and self._scale.is_calibrated() and not self._scale.error:
                self.add(self._scale.weight, now)
                last = now
            time.sleep(self._poll)

    def stop(self):
        self._running = False
