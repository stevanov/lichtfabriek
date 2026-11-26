"""kubusd output driver.

Real hardware: pigpio daemon over its socket (V1). Simulator: ANSI terminal
render (V4) so the engine runs without a Pi. Same interface, no root GPIO
access in-process (pigpiod owns the pins).
"""

from __future__ import annotations

import time

PWM_FREQ = 400  # Hz for all PWM channels (V17)


class BaseOutput:
    """Interface: set_frame(frame) + close()."""

    def set_frame(self, frame) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - interface
        pass


class PigpioOutput(BaseOutput):
    """Drives 9 PWM channels + 5 sign outputs via pigpiod socket (V1)."""

    def __init__(self, pins_pwm: list[int], pins_sign: list[int],
                 host: str = "localhost", port: int = 8888):
        import pigpio  # imported lazily: not present in dev/simulator

        self.pins_pwm = pins_pwm
        self.pins_sign = pins_sign
        self.pi = pigpio.pi(host, port)
        if not self.pi.connected:
            raise ConnectionError(
                f"pigpiod not reachable at {host}:{port} (sudo systemctl start pigpiod)"
            )
        for p in pins_pwm:
            self.pi.set_mode(p, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(p, PWM_FREQ)
            self.pi.set_PWM_dutycycle(p, 0)
        for p in pins_sign:
            self.pi.set_mode(p, pigpio.OUTPUT)
            self.pi.write(p, 0)

    def set_frame(self, frame) -> None:
        duty = [c * 255.0 for strip in frame.strips for c in strip]
        for pin, d in zip(self.pins_pwm, duty):
            self.pi.set_PWM_dutycycle(pin, max(0, min(255, round(d))))
        for pin, on in zip(self.pins_sign, frame.sign):
            self.pi.write(pin, 1 if on else 0)

    def close(self) -> None:
        for p in self.pins_pwm:
            self.pi.set_PWM_dutycycle(p, 0)
        for p in self.pins_sign:
            self.pi.write(p, 0)
        self.pi.stop()


class SimulatorOutput(BaseOutput):
    """ANSI terminal render of strips + sign (V4). No hardware needed."""

    def __init__(self, cols: int = 60, width: int = 12):
        self.cols = cols
        self.width = width
        self._lines = 0

    @staticmethod
    def _esc(c: tuple) -> str:
        return f"\x1b[48;2;{int(c[0])};{int(c[1])};{int(c[2])}m"

    def set_frame(self, frame) -> None:
        ints = frame.as_ints()
        # three strip rows (reuse space, rewrite in place when possible)
        for i, color in enumerate(ints):
            block = self._esc(color) + " " * self.width + "\x1b[0m"
            row = f"cube{i} {block}  " + "".join(
                "\x1b[42m  \x1b[0m" if on else "  " for on in frame.sign
            ) + "  sign"
            if self._lines < 3:
                print(row)
                self._lines += 1
            else:
                # move cursor up 3 and rewrite
                print(f"\x1b[3A\x1b[K{row}", end="\n")
        time.sleep(0.03)  # keep the loop human-readable

    def close(self) -> None:
        pass


def make_output(cfg, simulator: bool = False) -> BaseOutput:
    if simulator:
        return SimulatorOutput(cols=cfg.sim_cols)
    return PigpioOutput(cfg.pwm_pins, cfg.sign_pins, cfg.pigpiod_host, cfg.pigpiod_port)
