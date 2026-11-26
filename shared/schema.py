"""Lichtfabriek shared MQTT message schema + validation.

Topics and message shapes (SPEC §I). Validation is strict on both kubusd and
console (V2). Safety caps (V14) enforced here so both sides share the rules.

alpha2: a pattern is a SEQUENCE of steps (SPEC §C, V21/V22):

    {pattern_id, pattern_hash,
     steps: [
       {duration_s: float, cubes: {0: {primitive, params} | null,
                                   1: {primitive, params} | null,
                                   2: {primitive, params} | null}},
       ...
     ]}

Legacy single-primitive messages (pre-alpha2) are still accepted and
normalized to a one-step sequence (V22).
"""

from __future__ import annotations

import re

# MQTT topics (SPEC §I)
TOPIC_PATTERN_SET = "lichtfabriek/pattern/set"
TOPIC_SIGN_SET = "lichtfabriek/sign/set"
TOPIC_SIGN_SCHEDULE = "lichtfabriek/sign/schedule"
TOPIC_CONTROL = "lichtfabriek/control"
ALL_TOPICS = {
    TOPIC_PATTERN_SET,
    TOPIC_SIGN_SET,
    TOPIC_SIGN_SCHEDULE,
    TOPIC_CONTROL,
}

# Safety caps (V14)
MAX_STROBE_HZ = 3.0
MAX_BRIGHTNESS = 1.0
MAX_MESSAGE_BYTES = 8192  # sequences grow the payload (alpha2)
MAX_COLORS = 64
MAX_COLOR_CHANNELS = 3
MIN_SPEED = 0.01
MAX_SPEED = 20.0
MIN_OFFSET = 0.0
MAX_OFFSET = 60.0  # seconds of time-shift for a phase offset (knight sweep etc.)

# Sequence bounds (alpha2, V14)
MAX_STEPS = 20
MIN_STEP_DURATION = 0.5
MAX_TOTAL_DURATION = 600.0  # seconds = 10 min
LEGACY_STEP_DURATION = 60.0  # legacy single-primitive -> one step loops

# Pattern primitives (SPEC §C animation model). 'sign' is NOT user-selectable:
# the sign runs its own fixed hammer animation (SPEC §C, scheduler.py).
PRIMITIVES = {
    "rainbow",
    "pulse",
    "fade",
    "chase",
    "holiday",
    "off",
    # alpha2 additions
    "random",
    "fire",
    "sparkle",
    "huesweep",
    "sine",
    "strobe",
    "police",
    "knight",
    "static",
}

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

MAX_META_LEN = 128

NUM_CUBES = 3


def _check_meta(meta: dict) -> None:
    for key in ("title", "creator", "description"):
        if key in meta and not isinstance(meta[key], str):
            raise ValueError(f"meta.{key} must be a string")
        if isinstance(meta.get(key), str) and len(meta[key]) > MAX_META_LEN:
            raise ValueError(f"meta.{key} too long")


def validate_params(params: dict) -> None:
    """Validate primitive params + safety caps (V14). Raises ValueError."""
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    speed = params.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or isinstance(speed, bool):
        raise ValueError("params.speed must be a number")
    if not (MIN_SPEED <= speed <= MAX_SPEED):
        raise ValueError(f"params.speed out of range [{MIN_SPEED},{MAX_SPEED}]")
    colors = params.get("colors")
    if colors is not None:
        if not isinstance(colors, list) or not colors:
            raise ValueError("params.colors must be a non-empty list")
        if len(colors) > MAX_COLORS:
            raise ValueError(f"params.colors too long ({len(colors)} > {MAX_COLORS})")
        for c in colors:
            if (not isinstance(c, list) or len(c) != MAX_COLOR_CHANNELS
                    or not all(isinstance(x, (int, float))
                               and not isinstance(x, bool) and 0 <= x <= 255
                               for x in c)):
                raise ValueError("each color must be [r,g,b] 0..255")
    brightness = params.get("brightness", 1.0)
    if not isinstance(brightness, (int, float)) or isinstance(brightness, bool):
        raise ValueError("params.brightness must be a number")
    if not (0 <= brightness <= MAX_BRIGHTNESS):
        raise ValueError("params.brightness out of range")
    offset = params.get("offset", 0.0)
    if not isinstance(offset, (int, float)) or isinstance(offset, bool):
        raise ValueError("params.offset must be a number")
    if not (MIN_OFFSET <= offset <= MAX_OFFSET):
        raise ValueError(f"params.offset out of range [{MIN_OFFSET},{MAX_OFFSET}]")


def _validate_cube_spec(cube_spec, cube_idx: int) -> None:
    """Validate one cube entry: null (persist) or {primitive, params}."""
    if cube_spec is None:
        return  # persist previous step (V21)
    if not isinstance(cube_spec, dict):
        raise ValueError(f"cubes.{cube_idx} must be an object or null")
    primitive = cube_spec.get("primitive")
    if primitive not in PRIMITIVES:
        raise ValueError(f"cubes.{cube_idx}.primitive unknown {primitive!r}")
    validate_params(cube_spec.get("params", {}))


def _validate_step(step: dict, idx: int) -> None:
    if not isinstance(step, dict):
        raise ValueError(f"steps[{idx}] must be an object")
    duration = step.get("duration_s")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        raise ValueError(f"steps[{idx}].duration_s must be a number")
    if not (MIN_STEP_DURATION <= duration):
        raise ValueError(
            f"steps[{idx}].duration_s too short (min {MIN_STEP_DURATION}s)")
    cubes = step.get("cubes")
    if not isinstance(cubes, dict):
        raise ValueError(f"steps[{idx}].cubes must be an object")
    keys = set(cubes.keys())
    if not keys:
        raise ValueError(f"steps[{idx}].cubes is empty")
    for k in keys:
        if k not in ("0", "1", "2"):
            raise ValueError(f"steps[{idx}].cubes key {k!r} invalid (0-2)")
    for ci in range(NUM_CUBES):
        if str(ci) in cubes:
            _validate_cube_spec(cubes[str(ci)], ci)


def normalize_pattern(msg: dict) -> dict:
    """Return the canonical steps form of a pattern message (V22).

    Accepts both legacy `{primitive, params}` and alpha2 `{steps: [...]}`.
    Raises ValueError on invalid input.
    """
    pattern_id = msg.get("pattern_id")
    if not isinstance(pattern_id, str) or not _ID_RE.match(pattern_id):
        raise ValueError("pattern_id invalid")
    pattern_hash = msg.get("pattern_hash")
    if not isinstance(pattern_hash, str) or not _ID_RE.match(pattern_hash):
        raise ValueError("pattern_hash invalid")

    if "steps" in msg:
        steps = msg["steps"]
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps must be a non-empty list")
        if len(steps) > MAX_STEPS:
            raise ValueError(f"steps too many ({len(steps)} > {MAX_STEPS})")
        total = 0.0
        for i, step in enumerate(steps):
            _validate_step(step, i)
            total += step["duration_s"]
        if total > MAX_TOTAL_DURATION:
            raise ValueError(
                f"total sequence too long ({total:.1f}s > {MAX_TOTAL_DURATION}s)")
        return {
            "pattern_id": pattern_id,
            "pattern_hash": pattern_hash,
            "steps": steps,
        }

    # legacy single-primitive form (V22)
    primitive = msg.get("primitive")
    if primitive not in PRIMITIVES:
        raise ValueError(f"unknown primitive {primitive!r}")
    params = msg.get("params", {})
    validate_params(params)
    cube_spec = {"primitive": primitive, "params": params}
    return {
        "pattern_id": pattern_id,
        "pattern_hash": pattern_hash,
        "steps": [{
            "duration_s": LEGACY_STEP_DURATION,
            "cubes": {"0": cube_spec, "1": cube_spec, "2": cube_spec},
        }],
    }


def validate_pattern(msg: dict) -> None:
    """Validate a pattern/set message (either form). Raises ValueError."""
    normalize_pattern(msg)  # raises on any problem
    _check_meta(msg.get("meta") or {})


def validate_sign_set(msg: dict) -> None:
    on = msg.get("on")
    if not isinstance(on, bool):
        raise ValueError("sign/set requires boolean 'on'")


def validate_sign_schedule(msg: dict) -> None:
    sched = msg.get("schedule")
    if not isinstance(sched, dict):
        raise ValueError("sign/schedule requires object 'schedule'")
    for k in ("start", "stop"):
        v = sched.get(k)
        if not isinstance(v, str) or not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError(f"schedule.{k} must be HH:MM")
    if "enabled" in sched and not isinstance(sched["enabled"], bool):
        raise ValueError("schedule.enabled must be bool")


def validate_control(msg: dict) -> None:
    cmd = msg.get("cmd")
    if cmd not in ("status", "reset", "reboot"):
        raise ValueError(f"unknown control cmd {cmd!r}")


def validate_for_topic(topic: str, msg: dict) -> None:
    """Dispatch validation by topic. Raises ValueError."""
    if topic == TOPIC_PATTERN_SET:
        validate_pattern(msg)
    elif topic == TOPIC_SIGN_SET:
        validate_sign_set(msg)
    elif topic == TOPIC_SIGN_SCHEDULE:
        validate_sign_schedule(msg)
    elif topic == TOPIC_CONTROL:
        validate_control(msg)
    else:
        raise ValueError(f"unknown topic {topic!r}")
