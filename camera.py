import os
import subprocess
import time
import threading
from datetime import datetime

PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "Photos")


def _find_camera_cmd():
    for cmd in ["rpicam-still", "libcamera-still"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=3)
            return cmd
        except Exception:
            continue
    return None


def capture():
    cmd = _find_camera_cmd()
    if not cmd:
        return None

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M%S.jpg")
    path = os.path.join(PHOTOS_DIR, filename)

    try:
        subprocess.run(
            [cmd, "-o", path, "-t", "1", "--width", "640", "--height", "480"],
            capture_output=True,
            timeout=10
        )
        if os.path.exists(path):
            return filename
    except Exception:
        pass
    return None


def list_photos():
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    files = sorted(
        [f for f in os.listdir(PHOTOS_DIR) if f.endswith(".jpg")],
        reverse=True
    )[:100]
    return [{"name": f, "url": f"/photos/{f}"} for f in files]


def delete_photo(name):
    path = os.path.join(PHOTOS_DIR, name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


class CameraTrigger:
    def __init__(self, cooldown=10):
        self._cooldown = cooldown
        self._last_capture = 0
        self._lock = threading.Lock()

    def on_detect(self):
        now = time.time()
        with self._lock:
            if now - self._last_capture < self._cooldown:
                return
            self._last_capture = now
        threading.Thread(target=capture, daemon=True).start()
