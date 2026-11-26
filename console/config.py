"""console configuration.

Static config via .env (SPEC §I). PAYLOAD_KEY must match kubusd (V9).
Key injected via env_file/secrets, never in compose.yaml (V9).
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Config:
    def __init__(self, dotenv: Path | None = None):
        _load_dotenv(dotenv)
        self.mqtt_broker = os.environ.get("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
        self.mqtt_username = os.environ.get("MQTT_USERNAME") or None
        self.mqtt_password = os.environ.get("MQTT_PASSWORD") or None
        self.payload_key = os.environ.get("PAYLOAD_KEY", "")
        self.key_id = os.environ.get("KEY_ID", "k1")
        self.secret_key = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
        self.sqlite_path = os.environ.get("SQLITE_PATH", "./data/console.db")
        self.admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
        self.tz = os.environ.get("TZ", "Europe/Amsterdam")
        self.rate_limit_per_minute = int(
            os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
        self.trust_proxy = os.environ.get("TRUST_PROXY", "0") in (
            "1", "true", "yes")

    def validate(self) -> None:
        if not self.payload_key:
            raise ValueError("PAYLOAD_KEY is required")
        # Never run with placeholder secrets (privacy review 2026-11-26): a
        # public repo ships usable defaults, so a careless deploy would have a
        # forgeable session key / known admin password.
        if self.secret_key in ("", "dev-insecure-change-me", "change-me"):
            raise ValueError(
                "SECRET_KEY must be set to a real random value (not a placeholder)")
        if self.admin_password in ("", "admin", "change-me",
                                   "change-me-on-first-deploy"):
            raise ValueError(
                "ADMIN_PASSWORD must be set to a real value (not a placeholder)")
