"""Tests for the animation engine (V1, V4, V14)."""

from kubusd.engine import Engine, Frame, PRIMITIVE_FUNCS


def test_all_primitives_run():
    engine = Engine(frame_rate=30)
    for name in PRIMITIVE_FUNCS:
        engine.set_pattern(name, {"speed": 1.0, "brightness": 1.0})
        engine.start()
        frame = engine.step()
        assert isinstance(frame, Frame)
        assert len(frame.strips) == 3
        assert len(frame.sign) == 5
        engine.stop()


def test_brightness_cap():
    engine = Engine(frame_rate=30)
    engine.set_pattern("rainbow", {"speed": 0.5, "brightness": 0.5})
    engine.start()
    frame = engine.step()
    ints = frame.as_ints()
    for strip in ints:
        for c in strip:
            assert 0 <= c <= 255


def test_off_is_blank():
    engine = Engine(frame_rate=30)
    engine.set_pattern("off", {})
    engine.start()
    frame = engine.step()
    assert all(all(c == 0 for c in strip) for strip in frame.as_ints())
    assert all(not s for s in frame.sign)


def test_unknown_primitive():
    engine = Engine(frame_rate=30)
    try:
        engine.set_pattern("bogus", {})
        assert False, "should raise"
    except ValueError:
        pass


def test_simulator_renders():
    from kubusd.output import SimulatorOutput

    engine = Engine(frame_rate=30)
    engine.set_pattern("rainbow", {"speed": 0.5, "brightness": 0.5})
    engine.start()
    out = SimulatorOutput(cols=40)
    out.set_frame(engine.step())
    out.close()


# ---- alpha2: sequence + per-cube (V21, V22) ----

STEPS = [
    {"duration_s": 3.0, "cubes": {"0": {"primitive": "static", "params": {"colors": [[255, 0, 0]]}}}},
    {"duration_s": 3.0, "cubes": {"1": {"primitive": "static", "params": {"colors": [[0, 255, 0]]}}}},
    {"duration_s": 3.0, "cubes": {"2": {"primitive": "static", "params": {"colors": [[0, 0, 255]]}}}},
]


def _step_at(engine, seq_t: float):
    """Move the engine's internal clock to seq_t and return a frame."""
    import time as _time

    engine._seq_t0 = _time.monotonic() - seq_t
    return engine.step(dt=0.0)


def test_sequence_steps_advance():
    engine = Engine(frame_rate=30)
    engine.set_pattern(STEPS)
    engine.start()
    f0 = _step_at(engine, 0.5)   # step 0: cube0 red
    assert f0.strips[0][0] > 0.4 and f0.strips[0][1] < 0.1  # red (dim 0.5)
    f1 = _step_at(engine, 4.0)   # step 1: cube1 green
    assert f1.strips[1][1] > 0.4 and f1.strips[1][0] < 0.1
    f2 = _step_at(engine, 7.0)   # step 2: cube2 blue
    assert f2.strips[2][2] > 0.4 and f2.strips[2][0] < 0.1


def test_sequence_loops():
    engine = Engine(frame_rate=30)
    engine.set_pattern(STEPS)
    engine.start()
    # total = 9s; at t=10s we're back in step 0
    f = _step_at(engine, 10.0)
    assert f.strips[0][0] > 0.4  # cube0 red again


def test_unspecified_cubes_persist():
    engine = Engine(frame_rate=30)
    steps = [
        {"duration_s": 2.0, "cubes": {"0": {"primitive": "static", "params": {"colors": [[255, 255, 255]]}}}},
        {"duration_s": 2.0, "cubes": {"1": {"primitive": "static", "params": {"colors": [[0, 0, 255]]}}}},
    ]
    engine.set_pattern(steps)
    engine.start()
    # step 0: cube0 white, cube1/2 default off
    f0 = _step_at(engine, 0.5)
    assert f0.strips[0][0] > 0.4
    assert f0.strips[1] == [0.0, 0.0, 0.0]
    # step 1: cube1 blue, cube0 persists white (V21)
    f1 = _step_at(engine, 2.5)
    assert f1.strips[1][2] > 0.4
    assert f1.strips[0][0] > 0.4, "cube0 persists from step 0"


def test_new_primitives_render():
    engine = Engine(frame_rate=30)
    for name in ("random", "fire", "sparkle", "huesweep", "sine",
                 "strobe", "police", "knight", "static"):
        engine.set_pattern(name, {"speed": 1.0, "brightness": 0.5})
        engine.start()
        frame = engine.step()
        for strip in frame.as_ints():
            for c in strip:
                assert 0 <= c <= 255
        engine.stop()


def test_static_dim():
    engine = Engine(frame_rate=30)
    engine.set_pattern("static", {"brightness": 0.5, "colors": [[255, 255, 255]]})
    engine.start()
    f = engine.step()
    assert abs(f.strips[0][0] - 0.5) < 0.05
