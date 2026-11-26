"""kubusd sign scheduler.

The sign runs a FIXED always-on animation of the 5 outputs (SPEC §C) — a
hammer falling in 3 steps onto an always-on anvil, then sparks:

  output 0 = anvil    (always on)
  outputs 1-3 = hammer steps (fall in sequence)
  output 4 = sparks   (after the hammer hits)

The cycle repeats (default period ~8 s). A time-based schedule + manual
override gate whether the whole sign runs at all (V5, V18). Manual MQTT
override wins over the schedule and expires after OVERRIDE_TTL. Without a
synced clock the sign falls back to a defined default state (V18).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime

log = logging.getLogger("kubusd.scheduler")

OVERRIDE_TTL = 3600  # manual override expires after 1 h (V18)

# sign animation timings (seconds within one cycle) — SPEC §C constants
CYCLE = 8.0
STEP_DURATION = 1.0   # each hammer step (output 1, 2, 3)
SPARK_DURATION = 1.5  # sparks after the hammer hits
RESET_DURATION = 3.5  # dwell before the next fall


def sign_sequence(now: float | None = None) -> list[bool]:
    """The fixed 5-output sign animation at wall-clock time `now`.

    Returns [anvil, hammer_step1, hammer_step2, hammer_step3, sparks].
    Hammer falls step1→step2→step3, stays down while sparks fly, then resets.
    """
    t = (now if now is not None else time.time()) % CYCLE
    anvil = True  # always on
    step1 = 0.0 <= t < STEP_DURATION
    step2 = STEP_DURATION <= t < 2 * STEP_DURATION
    step3 = 2 * STEP_DURATION <= t < 3 * STEP_DURATION + SPARK_DURATION
    sparks = 3 * STEP_DURATION <= t < 3 * STEP_DURATION + SPARK_DURATION
    return [anvil, step1, step2, step3, sparks]


class SignScheduler:
    def __init__(self, cfg, db, output):
        self.cfg = cfg
        self.db = db
        self.output = output
        self._running = False
        self._thread = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while self._running:
            self.tick()
            time.sleep(1.0)

    def tick(self) -> None:
        self._last_state = self._state()

    def sign_enabled(self) -> bool:
        """Is the sign allowed to run right now? (schedule + override, V5/V18)."""
        state = self._state()
        return self._sign_on(state)

    def sign_frame(self) -> list[bool]:
        """The current sign outputs (all off when the sign is disabled)."""
        if not self.sign_enabled():
            return [False] * 5
        return sign_sequence()

    def _state(self) -> dict:
        return self.db.get_sign_state()

    def _sign_on(self, state: dict) -> bool:
        # manual override, with expiry (V18)
        override = state.get("sign_override")
        if override == "1":
            set_ts = float(state.get("sign_override_ts", 0) or 0)
            if time.time() - set_ts < OVERRIDE_TTL:
                return True
            # expired -> fall through to schedule
        elif override == "0":
            set_ts = float(state.get("sign_override_ts", 0) or 0)
            if time.time() - set_ts < OVERRIDE_TTL:
                return False
        # schedule (V18): no synced clock -> defined default (on)
        try:
            sched = json.loads(state.get("sign_schedule", "{}"))
        except (ValueError, TypeError):
            sched = {}
        if sched.get("enabled", True):
            start, stop = sched.get("start", "18:00"), sched.get("stop", "23:00")
            now = datetime.now().strftime("%H:%M")
            # handle overnight ranges (stop < start)
            if stop < start:
                return now >= start or now < stop
            return start <= now < stop
        return True
