"""kubusd MQTT client.

Subscribes to lichtfabriek topics, authenticates every message (AEAD + replay
counter, V2/V13), validates schema + safety caps (V14), applies patterns and
sign control (V5/V18), audits. Never interrupts the current pattern on bad
input; stays on last-good (V3).
"""

from __future__ import annotations

import json
import logging
import threading
import time

from shared import crypto, schema
from shared.schema import (
    TOPIC_PATTERN_SET,
    TOPIC_SIGN_SCHEDULE,
    TOPIC_SIGN_SET,
)

log = logging.getLogger("kubusd.mqtt")

# rate limit for audit writes on rejected/invalid messages (V16, review
# 2026-11-26): every forged message used to cost an fsync'd SQLite insert —
# a public-broker flood could wear the SD card and stall rendering.
AUDIT_LIMIT_PER_MIN = 30


class _AuditThrottle:
    """Tiny token bucket: allow the first N audit rows per minute, then just
    log (the ring buffer only needs a sample of a flood, not all of it)."""

    def __init__(self, limit: int = AUDIT_LIMIT_PER_MIN):
        self._limit = limit
        self._window_start = 0.0
        self._count = 0

    def allow(self, now: float) -> bool:
        if now - self._window_start >= 60.0:
            self._window_start = now
            self._count = 0
        self._count += 1
        return self._count <= self._limit


# clock sanity floor (V18): before this the Pi clock is obviously unsynced
CLOCK_FLOOR = 1767225600  # 2026-01-01 UTC


class MQTTClient:
    def __init__(self, cfg, db, engine, output, on_status=None):
        self.cfg = cfg
        self.db = db
        self.engine = engine
        self.output = output
        self.on_status = on_status or (lambda msg: None)
        self.client = None
        self._counters: dict[str, int] = {}  # V13, per topic (review 2026-11-26)
        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self._audit = _AuditThrottle()
        self._load_counters()

    def _load_counters(self) -> None:
        for topic in schema.ALL_TOPICS:
            n = self.db.get_counter(topic)
            self._counters[topic] = n if n is not None else -1

    def _save_counter(self, topic: str, n: int) -> None:
        self.db.set_counter(topic, n)

    def connect(self) -> None:
        import paho.mqtt.client as mqtt

        c = mqtt.Client(
            client_id="kubusd",
            clean_session=False,  # persistent session (V15)
        )
        if self.cfg.mqtt_username:
            c.username_pw_set(self.cfg.mqtt_username, self.cfg.mqtt_password)
        c.on_connect = self._on_connect
        c.on_message = self._on_message
        c.on_disconnect = self._on_disconnect
        self.client = c
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """Reconnect loop (V17): keep trying to reach the broker, best-effort."""
        while self._running:
            try:
                self.client.connect(self.cfg.mqtt_broker, self.cfg.mqtt_port,
                                    keepalive=30)
                self.client.loop_forever()
            except Exception as e:  # broker down / offline (V3)
                log.warning("MQTT not reachable (%s); retrying in 10s", e)
            time.sleep(10)

    def _on_connect(self, client, userdata, flags, rc) -> None:
        log.info("MQTT connected rc=%s", rc)
        for topic in schema.ALL_TOPICS:
            client.subscribe(topic, qos=1)  # QoS1 + retained (V15)
        log.info("subscribed to %s", sorted(schema.ALL_TOPICS))

    def _on_disconnect(self, client, userdata, rc) -> None:
        log.warning("MQTT disconnected rc=%s", rc)
        self.on_status({"online": False})

    def _on_message(self, client, userdata, message) -> None:
        topic, payload = message.topic, message.payload
        if len(payload) > schema.MAX_MESSAGE_BYTES:
            self._audit_row(topic, "drop", "message too large")
            return
        last = self._counters.get(topic, -1)
        # retained messages were queued while we were offline: their timestamp
        # is stale by design, so the per-topic counter orders them instead
        # (review 2026-11-26). Same for an obviously unsynced clock (V18).
        check_ts = not message.retain and time.time() > CLOCK_FLOOR
        try:
            auth = crypto.open_envelope(
                topic, payload, self.cfg.payload_key,
                last_counter=last, check_timestamp=check_ts,
            )
            msg, counter = auth.message, auth.counter
        except crypto.Reject as e:
            # drop + rate-limited audit; never interrupt pattern (V2/V16)
            self._audit_row(topic, "reject", str(e))
            log.warning("rejected %s: %s", topic, e)
            return
        try:
            schema.validate_for_topic(topic, msg)
        except ValueError as e:
            self._audit_row(topic, "invalid", str(e))
            log.warning("invalid %s: %s", topic, e)
            return
        with self._lock:
            self._counters[topic] = counter
            self._save_counter(topic, counter)
            self.db.audit(topic, "apply", f"{msg.get('pattern_id', '')}")
            self._apply(topic, msg)
        self.on_status({"online": True, "last_topic": topic})

    def _audit_row(self, topic: str, kind: str, detail: str) -> None:
        """Audit a rejected/dropped message, rate-limited (V16)."""
        if self._audit.allow(time.time()):
            self.db.audit(topic, kind, detail)
        else:
            log.debug("audit throttled: %s %s", kind, detail)

    def _apply(self, topic: str, msg: dict) -> None:
        if topic == TOPIC_PATTERN_SET:
            self._apply_pattern(msg)
        elif topic == TOPIC_SIGN_SET:
            self._apply_sign_set(msg)
        elif topic == TOPIC_SIGN_SCHEDULE:
            self._apply_sign_schedule(msg)

    def _apply_pattern(self, msg: dict) -> None:
        from shared.schema import normalize_pattern

        normalized = normalize_pattern(msg)
        ttl = msg.get("params", {}).get("ttl")
        self.db.set_active_pattern(msg, ttl=ttl)
        self.engine.set_pattern(normalized["steps"])
        log.info("pattern %s -> %d steps",
                 msg["pattern_id"], len(normalized["steps"]))

    def _apply_sign_set(self, msg: dict) -> None:
        self.db.set_sign_state("sign_override", "1" if msg["on"] else "0")
        self.db.set_sign_state("sign_override_ts", str(time.time()))
        log.info("sign override -> %s", "on" if msg["on"] else "off")

    def _apply_sign_schedule(self, msg: dict) -> None:
        self.db.set_sign_state("sign_schedule", json.dumps(msg["schedule"]))
        log.info("sign schedule -> %s", msg["schedule"])

    def stop(self) -> None:
        self._running = False
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)
