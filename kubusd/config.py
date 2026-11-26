"""kubusd config loader.

Static config lives in .env (SPEC §C, §I). GPIO pin map, MQTT broker, key.
Never hard-code config; .env.example is the contract.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _bool(v: str, default: bool = False) -> bool:
    return {"1": True, "true": True, "yes": True, "on": True}.get(
        v.lower(), default
    )


@dataclass
class Config:
    # MQTT
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    # crypto (V9)
    payload_key: str = ""
    key_id: str = "k1"
    # pigpio
    pigpiod_host: str = "localhost"
    pigpiod_port: int = 8888
    # GPIO pin map: 9 PWM (3 strips x R/G/B) + 5 sign outputs (SPEC §I)
    pwm_pins: list[int] = field(default_factory=lambda: list(range(0, 9)))
    sign_pins: list[int] = field(default_factory=lambda: list(range(10, 15)))
    # runtime (relative, no host paths in repo — V20)
    sqlite_path: str = "./data/kubusd.db"
    sign_schedule: dict = field(default_factory=dict)
    sign_schedule_env: dict = field(default_factory=dict)
    tz: str = "Europe/Amsterdam"
    frame_rate: int = 30  # V17
    log_level: str = "INFO"
    # simulator (dev)
    sim_cols: int = 60

    @classmethod
    def from_env(cls, dotenv: Path | None = None) -> "Config":
        _load_dotenv(dotenv)
        c = cls()

        def get(key, default=None):
            return os.environ.get(key, default)

        c.mqtt_broker = get("MQTT_BROKER", c.mqtt_broker)
        c.mqtt_port = int(get("MQTT_PORT", str(c.mqtt_port)))
        c.mqtt_username = get("MQTT_USERNAME") or None
        c.mqtt_password = get("MQTT_PASSWORD") or None
        c.payload_key = get("PAYLOAD_KEY", "")
        c.key_id = get("KEY_ID", c.key_id)
        c.pigpiod_host = get("PIGPIOD_HOST", c.pigpiod_host)
        c.pigpiod_port = int(get("PIGPIOD_PORT", str(c.pigpiod_port)))
        pwm = get("PWM_PINS")
        if pwm:
            c.pwm_pins = [int(x) for x in pwm.split(",") if x.strip()]
        sign = get("SIGN_PINS")
        if sign:
            c.sign_pins = [int(x) for x in sign.split(",") if x.strip()]
        c.sqlite_path = get("SQLITE_PATH", c.sqlite_path)
        sched = get("SIGN_SCHEDULE")
        if sched:
            try:
                c.sign_schedule_env = json.loads(sched)
            except json.JSONDecodeError:
                # non-fatal (review 2026-11-26): a mangled value must not
                # crash-loop a stock install — fall back to the default
                logging.getLogger("kubusd.config").warning(
                    "SIGN_SCHEDULE is not valid JSON; using the built-in default")
                c.sign_schedule_env = {}
        c.tz = get("TZ", c.tz)
        c.frame_rate = int(get("FRAME_RATE", str(c.frame_rate)))
        c.log_level = get("LOG_LEVEL", c.log_level)
        c.sim_cols = int(get("SIM_COLS", str(c.sim_cols)))
        return c

    @property
    def sign_schedule_effective(self) -> dict:
        return self.sign_schedule_env or self.sign_schedule

    def validate(self) -> None:
        if not self.payload_key:
            raise ValueError("PAYLOAD_KEY is required (see .env.example)")
        if len(self.pwm_pins) != 9:
            raise ValueError(f"need exactly 9 PWM pins, got {len(self.pwm_pins)}")
        if len(self.sign_pins) != 5:
            raise ValueError(f"need exactly 5 sign pins, got {len(self.sign_pins)}")
        overlap = set(self.pwm_pins) & set(self.sign_pins)
        if overlap:
            raise ValueError(f"pins overlap: {overlap}")
        if self.frame_rate <= 0 or self.frame_rate > 60:
            raise ValueError("FRAME_RATE must be 1..60")
