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


def test_control():
    schema.validate_control({"cmd": "status"})
    with pytest.raises(ValueError):
        schema.validate_control({"cmd": "explode"})


def test_dispatch_unknown_topic():
    with pytest.raises(ValueError):
        schema.validate_for_topic("lichtfabriek/bogus", {})
