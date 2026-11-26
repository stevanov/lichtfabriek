"""Tests for the fixed sign (hammer) animation (SPEC §C, V5, V18).

Confirmed sign loop (Steven, 2026-11-26): raised upright → ~45° mid-swing →
nearly horizontal impact → impact + sparks (split second) → impact, no sparks
→ loop back to raised. The board never goes dark; only hammer pose + sparks
change. Outputs: [anvil, pose1_raised, pose2_midswing, pose3_impact, sparks].
"""

from kubusd.scheduler import (
    CYCLE,
    IMPACT_DURATION,
    RAISE_DURATION,
    SPARK_DURATION,
    SWING_DURATION,
    sign_sequence,
)

IMPACT_START = RAISE_DURATION + SWING_DURATION
SPARK_START = IMPACT_START + IMPACT_DURATION
SPARK_END = SPARK_START + SPARK_DURATION


def test_anvil_always_on():
    for t in range(0, int(CYCLE) * 4):
        seq = sign_sequence(now=float(t) + 0.5)
        assert seq[0] is True, "anvil must always be on"


def test_board_never_goes_dark():
    # at every instant at least one hammer pose is lit (only pose + sparks change)
    for t in [0.1, RAISE_DURATION + 0.1, IMPACT_START + 0.1, SPARK_START + 0.1,
              SPARK_END + 0.1, CYCLE - 0.1]:
        seq = sign_sequence(now=t)
        assert seq[1] or seq[2] or seq[3], f"board dark at t={t}: {seq}"


def test_loop_sequence():
    # 1) raised upright
    s = sign_sequence(now=0.5)
    assert s == [True, True, False, False, False]
    # 2) mid-swing ~45°
    s = sign_sequence(now=RAISE_DURATION + 0.25)
    assert s == [True, False, True, False, False]
    # 3) impact pose (head on anvil), no sparks yet
    s = sign_sequence(now=IMPACT_START + 0.1)
    assert s == [True, False, False, True, False]
    # 4) impact pose + sparks
    s = sign_sequence(now=SPARK_START + 0.1)
    assert s == [True, False, False, True, True]
    # 5) impact pose, sparks off (same frame as step 3)
    s = sign_sequence(now=SPARK_END + 0.1)
    assert s == [True, False, False, True, False]


def test_loop_restarts_at_raised():
    # after the sparks go off the hammer stays in impact pose, then the loop
    # restarts straight at the raised pose — no dead/dark gap
    last = sign_sequence(now=CYCLE - 0.1)
    assert last == [True, False, False, True, False]
    first = sign_sequence(now=0.05)
    assert first == [True, True, False, False, False]


def test_cycle_wraps():
    a = sign_sequence(now=0.1)
    b = sign_sequence(now=CYCLE + 0.1)
    assert a == b


def test_disabled_sign_blanked():
    # sign_frame() returns all off when disabled — covered via a stub scheduler
    from kubusd.scheduler import SignScheduler


    class FakeDB:
        def __init__(self, override):
            self._o = override

        def get_sign_state(self):
            return {"sign_override": self._o, "sign_override_ts": "9999999999"}


    class FakeOutput:
        pass


    sched = SignScheduler(cfg=None, db=FakeDB("0"), output=FakeOutput())
    assert sched.sign_frame() == [False] * 5
    sched_on = SignScheduler(cfg=None, db=FakeDB("1"), output=FakeOutput())
    f = sched_on.sign_frame()
    assert f[0] is True and len(f) == 5
