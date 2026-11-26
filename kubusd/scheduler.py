"""kubusd sign scheduler.

The sign runs a FIXED always-on animation of the 5 outputs (SPEC §C) — a
hammer falling onto an always-on anvil, then sparks:

  output 0 = anvil    (always on)
  output 1 = hammer pose 1: upright/vertical, raised high (head at top)
  output 2 = hammer pose 2: tilted ~45° to the left, mid-swing
  output 3 = hammer pose 3: nearly horizontal, pointing left, head resting
             on the anvil top (impact pose)
  output 4 = sparks: a few thin diagonal lines flashing up and to the left
             of the head

Geometry: the hammer pivots around the BOTTOM END of its handle, which sits
at the right side of the anvil's top face; the head is the far (upper) end
and swings counterclockwise from straight up to pointing left.

The loop (board never goes dark — only hammer pose + sparks change), total
cycle ~3 s:

  1. hammer upright/vertical, head at the top, handle down to the pivot
  2. hammer tilted ~45° to the left, head upper-left (mid-swing)
  3. hammer horizontal, pointing left, head resting on the anvil top
     (impact pose), handle extending right
  4. impact pose + sparks flash up-left of the head for a split second
  5. sparks off, same frame as step 3 (impact pose, no sparks)
  6. hammer JUMPS straight back to upright (step 1) — no gradual lift,
     no in-between frames — and the loop repeats

A time-based schedule + manual override gate whether the whole sign runs at
all (V5, V18). Manual MQTT override wins over the schedule and expires after
OVERRIDE_TTL. Without a synced clock the sign falls back to a defined
default state (V18).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime

log = logging.getLogger("kubusd.scheduler")

OVERRIDE_TTL = 3600  # manual override expires after 1 h (V18)

# sign animation timings (seconds within one cycle) — SPEC §C constants.
# The 6-step loop (raised → mid-swing → impact → impact+sparks → impact-rest
# → JUMP back to raised) maps onto the 5 outputs; the board never goes dark
# because the raised pose (or impact pose) is always lit between the swing
# poses. Total cycle ≈ 3 s (Steven, 2026-11-26).
CYCLE = 3.0
RAISE_DURATION = 1.2   # pose 1: hammer upright, head at the top
SWING_DURATION = 0.5   # pose 2: tilted ~45° to the left, mid-swing
IMPACT_DURATION = 0.4  # pose 3: horizontal, pointing left, head on the anvil
SPARK_DURATION = 0.5   # sparks flash up-left of the head, hammer stays in impact
REST_DURATION = CYCLE - RAISE_DURATION - SWING_DURATION - IMPACT_DURATION - SPARK_DURATION


def sign_sequence(now: float | None = None) -> list[bool]:
    """The fixed 5-output sign animation at wall-clock time `now`.

    Returns [anvil, pose1_raised, pose2_midswing, pose3_impact, sparks].
    Loop: raised → mid-swing → impact → impact+sparks → impact (sparks off)
    → JUMP back to raised. Anvil is always on; one of the three poses is
    always lit — the board never goes dark.
    """
    t = (now if now is not None else time.time()) % CYCLE
    anvil = True
    pose1 = 0.0 <= t < RAISE_DURATION
    pose2 = RAISE_DURATION <= t < RAISE_DURATION + SWING_DURATION
    impact_start = RAISE_DURATION + SWING_DURATION
    pose3 = impact_start <= t  # stays lit through sparks + rest until the loop
    sparks = impact_start + IMPACT_DURATION <= t < impact_start + IMPACT_DURATION + SPARK_DURATION
    return [anvil, pose1, pose2, pose3, sparks]


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
