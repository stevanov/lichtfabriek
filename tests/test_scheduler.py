"""Tests for the fixed sign (hammer) animation (SPEC §C, V5, V18)."""

from kubusd.scheduler import CYCLE, SPARK_DURATION, STEP_DURATION, sign_sequence


def test_anvil_always_on():
    for t in range(0, int(CYCLE) * 4):
        seq = sign_sequence(now=float(t) + 0.5)
        assert seq[0] is True, "anvil must always be on"


def test_hammer_falls_in_steps():
    # step1 on in [0,1), step2 in [1,2), step3 in [2,3)
    s1 = sign_sequence(now=0.5)
    s2 = sign_sequence(now=1.5)
    s3 = sign_sequence(now=2.5)
    assert s1[1] and not s1[2] and not s1[3]
    assert s2[2] and not s2[1] and not s2[3]
    assert s3[3] and not s3[1] and not s3[2]


def test_sparks_after_hammer():
    # sparks during [3, 3+SPARK_DURATION)
    s = sign_sequence(now=3.5)
    assert s[4] is True
    assert s[3] is True  # hammer still down while sparks fly


def test_reset_phase():
    # after sparks: nothing on except anvil
    t = 3 * STEP_DURATION + SPARK_DURATION + 0.5
    s = sign_sequence(now=t)
    assert s == [True, False, False, False, False]


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
