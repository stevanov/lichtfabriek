"""Tests for shared message schema + safety caps (V2, V14)."""

import pytest

from shared import schema


def test_valid_pattern():
    msg = {
        "pattern_id": "p1",
        "pattern_hash": "h1",
        "primitive": "rainbow",
        "params": {"speed": 0.5, "brightness": 1.0, "colors": [[255, 0, 0]]},
    }
    schema.validate_pattern(msg)


@pytest.mark.parametrize(
    "mutate",
    [
        {"primitive": "nope"},
        {"params": {"speed": 100}},
        {"params": {"speed": -1}},
        {"params": {"brightness": 2.0}},
        {"params": {"colors": [[256, 0, 0]]}},
        {"params": {"colors": [[0, 0, 0]] * 100}},
        {"pattern_id": "has spaces"},
        {"pattern_hash": ""},
    ],
)
def test_invalid_pattern(mutate):
    msg = {
        "pattern_id": "p1",
        "pattern_hash": "h1",
        "primitive": "rainbow",
        "params": {"speed": 0.5, "brightness": 1.0},
    }
    msg.update(mutate)
    with pytest.raises(ValueError):
        schema.validate_pattern(msg)


def test_strobe_cap_value():
    # V14: speed must stay under the strobe limit concept; schema enforces range
    with pytest.raises(ValueError):
        schema.validate_pattern({
            "pattern_id": "p",
            "pattern_hash": "h",
            "primitive": "pulse",
            "params": {"speed": 30.0},
        })


def test_sign_set():
    schema.validate_sign_set({"on": True})
    with pytest.raises(ValueError):
        schema.validate_sign_set({"on": "yes"})


def test_sign_schedule():
    schema.validate_sign_schedule(
        {"schedule": {"enabled": True, "start": "18:00", "stop": "23:00"}}
    )
    with pytest.raises(ValueError):
        schema.validate_sign_schedule({"schedule": {"start": "18-00"}})


def test_control_topic_removed():
    """`lichtfabriek/control` was removed (review: its commands were silent
    no-ops). It must no longer be a valid topic."""
    assert "TOPIC_CONTROL" not in dir(schema)
    with pytest.raises(ValueError):
        schema.validate_for_topic("lichtfabriek/control", {"cmd": "status"})


def test_dispatch_unknown_topic():
    with pytest.raises(ValueError):
        schema.validate_for_topic("lichtfabriek/bogus", {})


# ---- alpha2: sequences + legacy conversion (V21, V22, V14) ----

def _steps_msg(steps):
    return {"pattern_id": "p1", "pattern_hash": "h1", "steps": steps}


def test_legacy_pattern_normalized():
    msg = {"pattern_id": "p", "pattern_hash": "h",
           "primitive": "rainbow", "params": {"speed": 1.0}}
    norm = schema.normalize_pattern(msg)
    assert len(norm["steps"]) == 1
    step = norm["steps"][0]
    assert set(step["cubes"]) == {"0", "1", "2"}
    assert step["cubes"]["0"]["primitive"] == "rainbow"


def test_steps_roundtrip():
    msg = _steps_msg([
        {"duration_s": 2.0, "cubes": {"0": {"primitive": "fire", "params": {}}}},
    ])
    norm = schema.normalize_pattern(msg)
    assert norm["steps"][0]["cubes"]["0"]["primitive"] == "fire"


def test_too_many_steps_rejected():
    steps = [{"duration_s": 1.0, "cubes": {"0": {"primitive": "off", "params": {}}}}] * 21
    with pytest.raises(ValueError, match="too many"):
        schema.normalize_pattern(_steps_msg(steps))


def test_step_too_short_rejected():
    msg = _steps_msg([{"duration_s": 0.1, "cubes": {"0": {"primitive": "off", "params": {}}}}])
    with pytest.raises(ValueError, match="too short"):
        schema.normalize_pattern(msg)


def test_total_duration_rejected():
    steps = [{"duration_s": 300.0, "cubes": {"0": {"primitive": "off", "params": {}}}},
             {"duration_s": 301.0, "cubes": {"0": {"primitive": "off", "params": {}}}}]
    with pytest.raises(ValueError, match="total sequence"):
        schema.normalize_pattern(_steps_msg(steps))


def test_bad_cube_key_rejected():
    msg = _steps_msg([{"duration_s": 2.0, "cubes": {"9": {"primitive": "off", "params": {}}}}])
    with pytest.raises(ValueError, match="cubes key"):
        schema.normalize_pattern(msg)


def test_null_cube_persist_allowed():
    msg = _steps_msg([{"duration_s": 2.0, "cubes": {"0": {"primitive": "static", "params": {}}}}])
    norm = schema.normalize_pattern(msg)
    assert norm["steps"][0]["cubes"].get("1") is None


def test_empty_step_cubes_rejected():
    msg = _steps_msg([{"duration_s": 2.0, "cubes": {}}])
    with pytest.raises(ValueError, match="empty"):
        schema.normalize_pattern(msg)


def test_new_primitives_in_set():
    assert {"random", "fire", "sparkle", "huesweep", "sine",
            "strobe", "police", "knight", "static"} <= schema.PRIMITIVES
