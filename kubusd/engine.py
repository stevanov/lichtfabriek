"""kubusd animation engine.

Built-in primitives (SPEC §C): rainbow, pulse, fade, chase, holiday, sign, off.
Each primitive is a pure function of time t (seconds) + params -> a Frame:
  3 strip colors (each [r,g,b] 0..1) + 5 sign outputs (bools).
Safety caps enforced here too (V14): strobe < 3 Hz, brightness cap.
"""

from __future__ import annotations

import colorsys
import math
import random
import time

from shared.schema import MAX_BRIGHTNESS, MAX_STROBE_HZ, PRIMITIVES

NUM_STRIPS = 3
NUM_SIGN = 5


class Frame:
    __slots__ = ("strips", "sign")

    def __init__(self, strips=None, sign=None):
        # strips: list of 3 colors, each [r,g,b] floats 0..1
        self.strips = strips if strips is not None else [[0.0, 0.0, 0.0]] * NUM_STRIPS
        # sign: list of 5 bools
        self.sign = sign if sign is not None else [False] * NUM_SIGN

    def as_ints(self):
        return [
            [min(255, max(0, round(c * 255))) for c in strip]
            for strip in self.strips
        ]


def _apply_brightness(strips, brightness: float):
    b = max(0.0, min(MAX_BRIGHTNESS, brightness))
    return [[c * b for c in strip] for strip in strips]


def _t_strobed(t: float, speed: float) -> float:
    """Limit strobe: period = speed, but clamp effective frequency < 3 Hz (V14)."""
    period = max(1.0 / MAX_STROBE_HZ, speed)
    return (t % period) / period


# ---- primitives: all (t, params) -> Frame ----

def rainbow(t: float, params: dict) -> Frame:
    speed = params.get("speed", 0.5)
    brightness = params.get("brightness", 1.0)
    n = params.get("n_strips", NUM_STRIPS)
    frame = Frame()
    for i in range(NUM_STRIPS):
        hue = ((t * speed) + i / max(1, NUM_STRIPS)) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        if i >= n:
            r = g = b = 0.0
        frame.strips[i] = [r, g, b]
    frame.strips = _apply_brightness(frame.strips, brightness)
    frame.sign = [True] * NUM_SIGN
    return frame


def pulse(t: float, params: dict) -> Frame:
    speed = params.get("speed", 1.0)
    brightness = params.get("brightness", 1.0)
    colors = params.get("colors") or [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    color = colors[int(t / max(speed, 0.01)) % len(colors)]
    # smooth sine pulse between 0.1 and 1.0, strobe-capped
    phase = _t_strobed(t, speed)
    amp = 0.5 + 0.5 * math.sin(phase * 2 * math.pi)
    base = [c / 255.0 for c in color]
    frame = Frame()
    for i in range(NUM_STRIPS):
        frame.strips[i] = [c * amp * brightness for c in base]
    frame.sign = [True] * NUM_SIGN
    return frame


def fade(t: float, params: dict) -> Frame:
    speed = params.get("speed", 0.5)
    brightness = params.get("brightness", 1.0)
    colors = params.get("colors") or [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    # crossfade between colors by index over time
    n = len(colors)
    phase = _t_strobed(t, speed)
    idx = int(phase * n)
    nxt = (idx + 1) % n
    frac = (phase * n) - idx
    c1 = [c / 255.0 for c in colors[idx]]
    c2 = [c / 255.0 for c in colors[nxt]]
    frame = Frame()
    for i in range(NUM_STRIPS):
        frame.strips[i] = [
            (c1[j] * (1 - frac) + c2[j] * frac) * brightness for j in range(3)
        ]
    frame.sign = [bool(int(phase * 2))] * NUM_SIGN
    return frame


def chase(t: float, params: dict) -> Frame:
    speed = params.get("speed", 0.8)
    brightness = params.get("brightness", 1.0)
    color = params.get("colors") or [[255, 255, 255]]
    base = [c / 255.0 for c in color[0]]
    step = _t_strobed(t, speed)
    frame = Frame()
    for i in range(NUM_STRIPS):
        on = bool(round(step * 2 + (i / NUM_STRIPS)) % 2)
        frame.strips[i] = [c * brightness if on else 0.0 for c in base]
    frame.sign = [bool(i % 2 == int(step * 4) % 2) for i in range(NUM_SIGN)]
    return frame


def holiday(t: float, params: dict) -> Frame:
    """Holiday themes: golden/white sparkle + slow warm pulse on cubes, sign on."""
    speed = params.get("speed", 1.0)
    brightness = params.get("brightness", 1.0)
    seed = params.get("seed", 0)
    rnd = random.Random(seed)
    frame = Frame()
    for i in range(NUM_STRIPS):
        # warm golden/white with gentle sparkle
        sparkle = 0.7 + 0.3 * rnd.random()
        phase = _t_strobed(t * 0.5, speed)
        warm = 0.5 + 0.5 * math.sin(phase * 2 * math.pi + i)
        frame.strips[i] = [
            (1.0 * warm * sparkle) * brightness,       # R warm
            (0.9 * warm * sparkle) * brightness,       # G
            (0.4 * warm * sparkle) * brightness,       # B low = warm white
        ]
    frame.sign = [True] * NUM_SIGN
    return frame


def off(t: float, params: dict) -> Frame:
    return Frame()


PRIMITIVE_FUNCS = {
    "rainbow": rainbow,
    "pulse": pulse,
    "fade": fade,
    "chase": chase,
    "holiday": holiday,
    "off": off,
}


class Engine:
    """Runs a pattern at a fixed frame rate, producing Frames (V17)."""

    def __init__(self, frame_rate: int = 30):
        self.frame_rate = frame_rate
        self.primitive = "off"
        self.params: dict = {}
        self._t0 = 0.0
        self._running = False

    def set_pattern(self, primitive: str, params: dict) -> None:
        if primitive not in PRIMITIVE_FUNCS:
            raise ValueError(f"unknown primitive {primitive!r}")
        self.primitive = primitive
        self.params = dict(params)
        self._t0 = time.monotonic()

    def start(self) -> None:
        self._running = True
        self._t0 = time.monotonic()

    def stop(self) -> None:
        self._running = False

    def step(self, dt: float | None = None) -> Frame:
        """Advance one frame. dt in seconds; default = 1/frame_rate."""
        if dt is None:
            dt = 1.0 / self.frame_rate
        t = (time.monotonic() - self._t0) if self._running else 0.0
        fn = PRIMITIVE_FUNCS[self.primitive]
        return fn(t, self.params)
