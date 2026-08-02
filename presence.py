import threading
import time
from collections import deque

try:
    import lgpio as gpio
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class PresenceSensor:
    def __init__(self, pin=23, history_seconds=120, on_detect=None):
        self.pin = pin
        self.samples = deque(maxlen=history_seconds)
        self.current = False
        self._running = False
        self._thread = None
        self.handle = None
        self._on_detect = on_detect

        if GPIO_AVAILABLE:
            self.handle = gpio.gpiochip_open(0)
            gpio.gpio_claim_input(self.handle, self.pin)
            self._start_polling()

    def _start_polling(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        while self._running:
            try:
                value = gpio.gpio_read(self.handle, self.pin)
                new_state = bool(value)
                if new_state and not self.current and self._on_detect:
                    self._on_detect()
                self.current = new_state
                self.samples.append(1 if value else 0)
            except Exception:
                pass
            time.sleep(1)

    def get_state(self):
        return {
            "current": self.current,
            "samples": list(self.samples)
        }

    def close(self):
        self._running = False
        if self.handle is not None:
            gpio.gpiochip_close(self.handle)
