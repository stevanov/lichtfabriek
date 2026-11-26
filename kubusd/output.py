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
    """ANSI terminal render (V4) that mirrors the physical layout
    (`docs/sign-layout.svg`): the 5 sign LED outputs (hammer + sparks) run
    across the top, and the 3 cube strips are stacked vertically on the
    right of the screen. No hardware needed."""

    # per-output LED colours (matches docs/sign-layout.svg): hammer = light
    # blue, sparks = warm amber, anvil = cool white
    SIGN_LEDS = ("anvil", "raised", "swing", "impact", "sparks")
    SIGN_COLORS = ((230, 230, 230), (207, 232, 245), (207, 232, 245),
                   (207, 232, 245), (255, 217, 138))

    def __init__(self, cols: int = 60, width: int = 12):
        self.cols = cols
        self.width = width
        self._lines = 0

    @staticmethod
    def _esc(c: tuple) -> str:
        return f"\x1b[48;2;{int(c[0])};{int(c[1])};{int(c[2])}m"

    def _render(self, frame) -> list[str]:
        ints = frame.as_ints()
        rows: list[str] = []

        # ---- top: the 5 sign LED outputs (hammer loop, SPEC §C) ----
        leds = []
        for name, on, color in zip(self.SIGN_LEDS, frame.sign, self.SIGN_COLORS):
            if on:
                cell = self._esc(color) + "  " + "\x1b[0m"
            else:
                cell = "\x1b[90m··\x1b[0m"
            leds.append(f"{name} {cell}")
        rows.append("  sign: " + "   ".join(leds))
        rows.append("")

        # ---- right side: 3 cubes stacked (cube 1 on top, 3 on the bottom) ----
        pad = max(self.cols - (self.width + 2), 2)
        left = " " * pad
        for i in (0, 1, 2):
            color = ints[i]
            inner = f"  cube {i} ".ljust(self.width)
            rows.append(f"{left}┌{'─' * self.width}┐")
            rows.append(f"{left}│{self._esc(color)}{inner}\x1b[0m│")
            rows.append(f"{left}└{'─' * self.width}┘")
        return rows

    def set_frame(self, frame) -> None:
        rows = self._render(frame)
        if self._lines:
            # move cursor back to the start of our block and rewrite in place
            print(f"\x1b[{self._lines}A", end="")
        for row in rows:
            print("\x1b[K" + row)
        self._lines = len(rows)
        time.sleep(0.05)  # keep the loop human-readable

    def close(self) -> None:
        pass


def make_output(cfg, simulator: bool = False) -> BaseOutput:
    if simulator:
        return SimulatorOutput(cols=cfg.sim_cols)
    return PigpioOutput(cfg.pwm_pins, cfg.sign_pins, cfg.pigpiod_host, cfg.pigpiod_port)
