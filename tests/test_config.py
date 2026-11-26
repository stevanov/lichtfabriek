"""Tests for kubusd config (env loading, pin map, validation)."""

import os

from kubusd.config import Config


def test_defaults_relative():
    os.environ.pop("SQLITE_PATH", None)
    cfg = Config.from_env(None)
    assert cfg.sqlite_path.startswith("./"), "no absolute path default (V20)"
    assert len(cfg.pwm_pins) == 9
    assert len(cfg.sign_pins) == 5


def test_validate_rejects_missing_key():
    os.environ["PAYLOAD_KEY"] = ""
    cfg = Config.from_env(None)
    try:
        cfg.validate()
        assert False, "should raise"
    except ValueError:
        pass


def test_validate_rejects_overlap():
    os.environ["PAYLOAD_KEY"] = "x"
    cfg = Config.from_env(None)
    cfg.pwm_pins = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    cfg.sign_pins = [9, 10, 11, 12, 13]
    try:
        cfg.validate()
        assert False, "should raise"
    except ValueError:
        pass
