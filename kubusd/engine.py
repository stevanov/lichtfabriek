"""kubusd animation engine.

alpha2 model (SPEC §C, V21/V22): a pattern is a SEQUENCE of steps. Each step
specifies per-cube primitives (cube 0/1/2 independently); a cube not named in a
step PERSISTS its previous step's settings (first step default = off). Steps
advance by duration_s and the sequence loops.

Each primitive is a pure function of time t (seconds) + params -> a color
[0..1]^3. Safety caps enforced (V14): strobe < 3 Hz, brightness cap.
"""

from __future__ import annotations

import colorsys
import math
import random
import time

from shared.schema import (
    LEGACY_STEP_DURATION,
    MAX_BRIGHTNESS,
    MAX_STROBE_HZ,
    PRIMITIVES,
)

NUM_STRIPS = 3
NUM_SIGN = 5


def _apply_brightness(color, brightness: float):
    b = max(0.0, min(MAX_BRIGHTNESS, brightness))
    return [c * b for c in color]


def _rate(speed: float, base: float) -> float:
    """Effective animation rate = base rate × speed multiplier (speed ≥ 0.01).

    `speed` means the SAME thing for every primitive: 1.0 = the primitive's
    normal pace, 2.0 = twice as fast, 0.5 = half speed (SPEC §C)."""
    return base * max(speed, 0.01)


def _period(base: float, speed: float) -> float:
    """Effective period for strobe-like primitives = base ÷ speed multiplier,
    clamped so the effective frequency stays < MAX_STROBE_HZ (V14)."""
    return max(1.0 / MAX_STROBE_HZ, base / max(speed, 0.01))


def _t_strobed(t: float, base: float, speed: float) -> float:
    """Strobe phase in [0,1) for a base period `base` at speed multiplier."""
    period = _period(base, speed)
    return (t % period) / period


def _color01(color) -> list[float]:
    """[r,g,b] 0..255 -> floats 0..1."""
    return [c / 255.0 for c in color]


# ---- primitives: all (t, params) -> color [0..1]^3 ----
# `speed` is a uniform multiplier (1.0 = normal) over a per-primitive base rate
# or base period (SPEC §C). All defaults are speed=1.0.

def prim_rainbow(t: float, params: dict) -> list[float]:
    speed = params.get("speed", 1.0)
    hue = (t * _rate(speed, 0.5)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return _apply_brightness([r, g, b], params.get("brightness", 1.0))


def prim_pulse(t: float, params: dict) -> list[float]:
    speed = params.get("speed", 1.0)
    colors = params.get("colors") or [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    period = _period(1.0, speed)
    color = colors[int(t / max(period, 0.01)) % len(colors)]
    phase = _t_strobed(t, 1.0, speed)
    amp = 0.5 + 0.5 * math.sin(phase * 2 * math.pi)
    return _apply_brightness([c * amp / 255.0 for c in color],
                             params.get("brightness", 1.0))


def prim_fade(t: float, params: dict) -> list[float]:
    speed = params.get("speed", 1.0)
    colors = params.get("colors") or [[255, 0, 0], [0, 255, 0], [0, 0, 255]]
    n = len(colors)
    phase = _t_strobed(t, 0.5, speed)
    idx = int(phase * n)
    nxt = (idx + 1) % n
    frac = (phase * n) - idx
    c1 = _color01(colors[idx])
    c2 = _color01(colors[nxt])
    return _apply_brightness(
        [c1[j] * (1 - frac) + c2[j] * frac for j in range(3)],
        params.get("brightness", 1.0))


def prim_chase(t: float, params: dict) -> list[float]:
    # on a single cube, chase = blinking at the strobe-capped rate
    speed = params.get("speed", 1.0)
    colors = params.get("colors") or [[255, 255, 255]]
    step = _t_strobed(t, 0.8, speed)
    on = bool(int(step * 4) % 2)
    base = _color01(colors[0])
    return _apply_brightness([c if on else 0.0 for c in base],
                             params.get("brightness", 1.0))


def prim_holiday(t: float, params: dict) -> list[float]:
    speed = params.get("speed", 1.0)
    seed = params.get("seed", 0)
    rnd = random.Random(seed)
    sparkle = 0.7 + 0.3 * rnd.random()
    phase = _t_strobed(t * 0.5, 1.0, speed)
    warm = 0.5 + 0.5 * math.sin(phase * 2 * math.pi)
    return _apply_brightness(
        [1.0 * warm * sparkle, 0.9 * warm * sparkle, 0.4 * warm * sparkle],
        params.get("brightness", 1.0))


def prim_off(t: float, params: dict) -> list[float]:
    return [0.0, 0.0, 0.0]


# ---- alpha2 primitives (T16) ----

def prim_random(t: float, params: dict) -> list[float]:
    """Random color that changes at a strobe-capped rate (seeded per instance)."""
    speed = params.get("speed", 1.0)
    seed = params.get("seed", 0)
    rnd = random.Random(seed + int(t / max(_period(0.5, speed), 0.01)))
    return _apply_brightness([rnd.random(), rnd.random(), rnd.random()],
                             params.get("brightness", 1.0))


def prim_fire(t: float, params: dict) -> list[float]:
    """Flickering warm fire: orange-red with fast random intensity variation."""
    speed = params.get("speed", 1.0)
    seed = params.get("seed", 0)
    rnd = random.Random(seed + int(t / max(_period(0.3, speed), 0.01) * 10))
    flicker = 0.6 + 0.4 * rnd.random()
    return _apply_brightness(
        [1.0 * flicker, 0.35 * flicker, 0.05 * flicker],
        params.get("brightness", 1.0))


def prim_sparkle(t: float, params: dict) -> list[float]:
    """Twinkling white/color sparkle: mostly dark, brief bright flashes."""
    speed = params.get("speed", 1.0)
    seed = params.get("seed", 0)
    rnd = random.Random(seed + int(t / max(_period(0.7, speed), 0.01)))
    colors = params.get("colors") or [[255, 255, 255]]
    on = rnd.random() < 0.2
    base = _color01(colors[0])
    return _apply_brightness([c if on else 0.0 for c in base],
                             params.get("brightness", 1.0))


def prim_huesweep(t: float, params: dict) -> list[float]:
    """Smooth continuous hue sweep across the full color wheel."""
    speed = params.get("speed", 1.0)
    hue = (t * _rate(speed, 0.2)) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return _apply_brightness([r, g, b], params.get("brightness", 1.0))


def prim_sine(t: float, params: dict) -> list[float]:
    """Two-color sine blend (smooth oscillation between two colors)."""
    speed = params.get("speed", 1.0)
    colors = params.get("colors") or [[255, 0, 0], [0, 0, 255]]
    c1 = _color01(colors[0])
    c2 = _color01(colors[1])
    mix = 0.5 + 0.5 * math.sin(t * _rate(speed, 0.4) * 2 * math.pi)
    return _apply_brightness(
        [c1[j] * (1 - mix) + c2[j] * mix for j in range(3)],
        params.get("brightness", 1.0))


def prim_strobe(t: float, params: dict) -> list[float]:
    """Hard on/off strobing between a color and black (strobe-capped, V14)."""
    colors = params.get("colors") or [[255, 255, 255]]
    phase = _t_strobed(t, 1.0, params.get("speed", 1.0))
    on = phase < 0.5
    base = _color01(colors[0])
    return _apply_brightness([c if on else 0.0 for c in base],
                             params.get("brightness", 1.0))


def prim_police(t: float, params: dict) -> list[float]:
    """Alternate red/blue (or two colors) at strobe-capped rate."""
    colors = params.get("colors") or [[255, 0, 0], [0, 0, 255]]
    phase = _t_strobed(t, 0.6, params.get("speed", 1.0))
    color = colors[int(phase * 2) % len(colors)]
    return _apply_brightness(_color01(color), params.get("brightness", 1.0))


def prim_knight(t: float, params: dict) -> list[float]:
    """A single lit cube scanning a position; per-cube, so on a lone cube this
    becomes a periodic blink; the sequence engine gives it the sweep feel."""
    colors = params.get("colors") or [[255, 255, 255]]
    phase = _t_strobed(t, 0.8, params.get("speed", 1.0))
    on = phase < 0.25
    base = _color01(colors[0])
    return _apply_brightness([c if on else 0.0 for c in base],
                             params.get("brightness", 1.0))


def prim_static(t: float, params: dict) -> list[float]:
    """Static color (or white) at fixed dim level."""
    colors = params.get("colors") or [[255, 255, 255]]
    return _apply_brightness(_color01(colors[0]), params.get("brightness", 0.5))


PRIMITIVE_FUNCS = {
    "rainbow": prim_rainbow,
    "pulse": prim_pulse,
    "fade": prim_fade,
    "chase": prim_chase,
    "holiday": prim_holiday,
    "off": prim_off,
    # alpha2
    "random": prim_random,
    "fire": prim_fire,
    "sparkle": prim_sparkle,
    "huesweep": prim_huesweep,
    "sine": prim_sine,
    "strobe": prim_strobe,
    "police": prim_police,
    "knight": prim_knight,
    "static": prim_static,
}


class Frame:
    __slots__ = ("strips", "sign")

    def __init__(self, strips=None, sign=None):
        self.strips = strips if strips is not None else [[0.0, 0.0, 0.0]] * NUM_STRIPS
        self.sign = sign if sign is not None else [False] * NUM_SIGN

    def as_ints(self):
        return [
            [min(255, max(0, round(c * 255))) for c in strip]
            for strip in self.strips
        ]


class Engine:
    """Runs a sequence of steps, each with per-cube primitives (V21)."""

    def __init__(self, frame_rate: int = 30):
        self.frame_rate = frame_rate
        self.steps: list[dict] = []  # canonical steps form
        self._running = False
        self._seq_t0 = 0.0
        # per-cube persistent settings: (primitive, params) or None = off
        self._cube_state: list[tuple[str, dict] | None] = [None] * NUM_STRIPS

    def set_pattern(self, primitive_or_steps, params=None) -> None:
        """Accept legacy (primitive, params) or canonical steps list."""
        from shared.schema import normalize_pattern

        if params is not None:
            msg = {"pattern_id": "x", "pattern_hash": "x",
                   "primitive": primitive_or_steps, "params": params}
        else:
            msg = {"pattern_id": "x", "pattern_hash": "x",
                   "steps": primitive_or_steps}
        normalized = normalize_pattern(msg)
        self.steps = normalized["steps"]
        self._cube_state = [None] * NUM_STRIPS
        self._seq_t0 = time.monotonic()

    def start(self) -> None:
        self._running = True
        self._seq_t0 = time.monotonic()

    def stop(self) -> None:
        self._running = False

    def _current_step(self, t: float) -> tuple[int, float]:
        """Return (step_index, t_within_step) for wall sequence time t."""
        total = sum(s["duration_s"] for s in self.steps)
        if total <= 0:
            return 0, 0.0
        tt = t % total
        for i, s in enumerate(self.steps):
            if tt < s["duration_s"]:
                return i, tt
            tt -= s["duration_s"]
        return len(self.steps) - 1, tt

    def step(self, dt: float | None = None) -> Frame:
        """Advance one frame: compute per-cube colors from the current step."""
        if dt is None:
            dt = 1.0 / self.frame_rate
        t = (time.monotonic() - self._seq_t0) if self._running else 0.0
        if not self.steps:
            return Frame()
        idx, t_in = self._current_step(t)
        step = self.steps[idx]
        cubes = step.get("cubes", {})
        frame = Frame()
        for ci in range(NUM_STRIPS):
            spec = cubes.get(str(ci))
            if spec is None:
                # persist previous step's settings (V21); None = off
                prim_name, prim_params = self._cube_state[ci] or ("off", {})
            else:
                prim_name = spec["primitive"]
                prim_params = spec.get("params", {})
                self._cube_state[ci] = (prim_name, prim_params)
            fn = PRIMITIVE_FUNCS.get(prim_name, prim_off)
            frame.strips[ci] = fn(t_in, prim_params)
        return frame
