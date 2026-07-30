import time
import lgpio
HALF_STEP_SEQUENCE = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1],
]

class StepperMotor:
    def __init__(self, pins = [17,18,27,22]):
        self.pins = pins
        self.handle = lgpio.gpiochip_open(0)
        for pin in self.pins:
            lgpio.gpio_claim_output(
                self.handle,
                pin
            )

    def rotate(self, steps, delay=0.001):
        direction = 1
        if steps < 0:
            direction = -1
            steps = abs(steps)
        sequence = HALF_STEP_SEQUENCE
        if direction < 0:
            sequence = list(reversed(sequence))
        for _ in range(steps):
            for state in sequence:
                for pin, value in zip(self.pins, state):
                    lgpio.gpio_write(
                        self.handle,
                        pin,
                        value
                    )
                time.sleep(delay)
        self.stop()

    def stop(self):
        for pin in self.pins:
            lgpio.gpio_write(
                self.handle,
                pin,
                0
            )

    def close(self):
        self.stop()
        lgpio.gpiochip_close(self.handle)