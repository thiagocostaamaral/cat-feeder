import json
import os
import threading
import time
import uuid

SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "schedules.json")


class Scheduler:
    def __init__(self):
        self._schedules = []
        self._motor = None
        self._running = False
        self._thread = None
        self._fired = set()
        self._lock = threading.Lock()
        self._load()

    def set_motor(self, motor):
        self._motor = motor

    def _load(self):
        try:
            with open(SCHEDULE_FILE) as f:
                self._schedules = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._schedules = []

    def _save(self):
        with open(SCHEDULE_FILE, "w") as f:
            json.dump(self._schedules, f, indent=2)

    def get_all(self):
        with self._lock:
            return list(self._schedules)

    def add(self, time_str, rotation):
        entry = {
            "id": uuid.uuid4().hex[:8],
            "time": time_str,
            "rotation": int(rotation)
        }
        with self._lock:
            self._schedules.append(entry)
            self._schedules.sort(key=lambda s: s["time"])
            self._save()
        return entry

    def remove(self, schedule_id):
        with self._lock:
            self._schedules = [s for s in self._schedules if s["id"] != schedule_id]
            self._save()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            now = time.strftime("%H:%M")
            current_minute = time.strftime("%H:%M")

            with self._lock:
                pending = [s for s in self._schedules if s["time"] == now]

            for entry in pending:
                key = entry["id"] + current_minute
                if key not in self._fired and self._motor:
                    self._fired.add(key)
                    try:
                        self._motor.rotate(entry["rotation"])
                    except Exception:
                        pass

            self._fired = {k for k in self._fired if k.endswith(current_minute)}
            time.sleep(5)

    def stop(self):
        self._running = False
