"""Lichtfabriek shared MQTT message schema + validation.

Topics and message shapes (SPEC §I). Validation is strict on both kubusd and
console (V2). Safety caps (V14) enforced here so both sides share the rules.
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
MAX_MESSAGE_BYTES = 4096
MAX_COLORS = 64
MAX_COLOR_CHANNELS = 3
MIN_SPEED = 0.01
MAX_SPEED = 20.0

# Pattern primitives (SPEC §C animation model). 'sign' is NOT user-selectable:
# the sign runs its own fixed hammer animation (SPEC §C, scheduler.py).
PRIMITIVES = {
    "rainbow",
    "pulse",
    "fade",
    "chase",
    "holiday",
    "off",
}

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

MAX_META_LEN = 128


def _check_meta(meta: dict) -> None:
    for key in ("title", "creator", "description"):
        if key in meta and not isinstance(meta[key], str):
            raise ValueError(f"meta.{key} must be a string")
        if isinstance(meta.get(key), str) and len(meta[key]) > MAX_META_LEN:
            raise ValueError(f"meta.{key} too long")


def validate_pattern(msg: dict) -> None:
    """Validate a pattern/set message. Raises ValueError with a reason."""
    primitive = msg.get("primitive")
    if primitive not in PRIMITIVES:
        raise ValueError(f"unknown primitive {primitive!r}")
    params = msg.get("params")
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    speed = params.get("speed", 1.0)
    if not isinstance(speed, (int, float)) or isinstance(speed, bool):
        raise ValueError("params.speed must be a number")
    if not (MIN_SPEED <= speed <= MAX_SPEED):
        raise ValueError(f"params.speed out of range [{MIN_SPEED},{MAX_SPEED}]")
    # strobe cap: speed is 1/period in our primitives -> keep < 3 Hz (V14)
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
    pattern_id = msg.get("pattern_id")
    if not isinstance(pattern_id, str) or not _ID_RE.match(pattern_id):
        raise ValueError("pattern_id invalid")
    pattern_hash = msg.get("pattern_hash")
    if not isinstance(pattern_hash, str) or not _ID_RE.match(pattern_hash):
        raise ValueError("pattern_hash invalid")
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
