"""console MQTT publisher.

Publishes AEAD-sealed messages to kubusd topics (V9, V13, V15). The counter is
persisted in the console DB so restarts don't reset it (V13). sign/schedule
messages are admin-only (V18), enforced in the routes.
"""

from __future__ import annotations

import threading
import time

from shared import crypto, schema


class Publisher:
    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self._client = None
        self._counter = 0
        self._lock = threading.Lock()
        self._load_counter()

    def _load_counter(self) -> None:
        row = self.db.get_counter()
        self._counter = row if row is not None else 0

    def _save_counter(self) -> None:
        self.db.set_counter(self._counter)

    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        c = mqtt.Client(client_id="lichtfabriek-console")
        if self.cfg.mqtt_username:
            c.username_pw_set(self.cfg.mqtt_username, self.cfg.mqtt_password)
        self._client = c
        # connect_async + network loop (review 2026-11-26): if the broker is
        # down at startup, the loop keeps retrying instead of leaving every
        # publish dead until a console restart
        self._client.connect_async(self.cfg.mqtt_broker, self.cfg.mqtt_port)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.loop_start()

    def publish(self, topic: str, message: dict, retain: bool = False) -> int:
        """Seal + publish. Returns the counter used."""
        if self._client is None:
            raise ConnectionError("publisher not connected")
        with self._lock:
            self._counter += 1
            counter = self._counter
            self._save_counter()
        env = crypto.seal(
            topic, message, self.cfg.payload_key, self.cfg.key_id, counter)
        # V14: reject at the source — kubusd would silently drop an oversized
        # message while the console reported it published (review 2026-11-26)
        if len(env) > schema.MAX_MESSAGE_BYTES:
            self._counter -= 1  # unused counter: don't burn replay slots
            self._save_counter()
            raise ValueError(
                f"message too large for the Pi ({len(env)} > "
                f"{schema.MAX_MESSAGE_BYTES} bytes) — simplify the pattern")
        info = self._client.publish(topic, env, qos=1, retain=retain)
        info.wait_for_publish(timeout=5)
        return counter

    def publish_pattern(self, pattern: dict, retain: bool = True) -> int:
        return self.publish(schema.TOPIC_PATTERN_SET, pattern, retain=retain)

    def publish_sign_set(self, on: bool, retain: bool = True) -> int:
        return self.publish(schema.TOPIC_SIGN_SET, {"on": on}, retain=retain)

    def publish_sign_schedule(self, schedule: dict, retain: bool = True) -> int:
        return self.publish(
            schema.TOPIC_SIGN_SCHEDULE, {"schedule": schedule}, retain=retain)

    def close(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
