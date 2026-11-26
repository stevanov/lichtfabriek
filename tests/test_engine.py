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


def test_sparkle_is_multicolor():
    """Sparkle flashes in RANDOM colors from the palette, not one fixed color."""
    from kubusd.engine import prim_sparkle

    seen = set()
    for i in range(2000):
        c = prim_sparkle(i / 100.0, {"speed": 2.0})
        if c[0] > 0 or c[1] > 0 or c[2] > 0:  # a lit flash
            seen.add((round(c[0], 2), round(c[1], 2), round(c[2], 2)))
    assert len(seen) >= 3, f"sparkle should show multiple colors, saw {len(seen)}"
    # and at least one non-white color appears (default palette is colorful)
    non_white = [c for c in seen if c != (1.0, 1.0, 1.0)]
    assert non_white, "sparkle should include non-white colors"


def test_speed_uniform_multiplier():
    """`speed` means the same for every primitive: 1 = normal, 2 = faster,
    0.5 = slower (SPEC §C). Rate-based primitives advance hue faster with
    higher speed; period-based primitives (strobe) flash more often."""
    from kubusd.engine import prim_rainbow, prim_strobe, _period, _rate

    # helper level: rate grows with speed; period shrinks with speed
    assert _rate(2.0, 0.5) > _rate(1.0, 0.5) > _rate(0.5, 0.5)
    assert _period(1.0, 2.0) < _period(1.0, 1.0) < _period(1.0, 0.5)

    # period-based: count on/off transitions over a 4 s window
    def transitions(speed):
        prev = None
        n = 0
        for i in range(400):
            c = prim_strobe(i / 100.0, {"speed": speed})
            on = c[0] > 0.0
            if prev is not None and on != prev:
                n += 1
            prev = on
        return n

    slow = transitions(0.5)
    norm = transitions(1.0)
    fast = transitions(2.0)
    assert slow < norm < fast, f"strobe transitions {slow} < {norm} < {fast}"

    # rate-based: count full hue wraps (returns to red) in a 4 s window
    def red_events(speed):
        prev = False
        n = 0
        for i in range(400):
            c = prim_rainbow(i / 100.0, {"speed": speed})
            red = c[0] > 0.9 and c[1] < 0.2 and c[2] < 0.2
            if red and not prev:
                n += 1
            prev = red
        return n

    sr, nr, fr = red_events(0.5), red_events(1.0), red_events(2.0)
    assert sr < nr < fr, f"rainbow hue wraps {sr} < {nr} < {fr}"


def test_offset_shifts_phase():
    """params.offset is a FRACTION of one animation cycle (0..1): offset=1.0
    must reproduce the base frame; offset=0.5 must shift to the opposite phase
    (e.g. knight flash moved by half a cycle)."""
    from kubusd.engine import prim_rainbow, prim_knight

    # rainbow: offset=1.0 (full cycle) lands on the same hue as offset=0
    a = prim_rainbow(1.0, {"speed": 1.0, "offset": 0.0})
    b = prim_rainbow(1.0, {"speed": 1.0, "offset": 1.0})
    assert abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6

    # knight: at half-cycle offset the flash is on the opposite side, so at
    # wall times where one cube is lit the other is off (and vice versa)
    on_times = [t / 20.0 for t in range(20)]
    lit0 = [prim_knight(t, {"speed": 1.0, "offset": 0.0})[0] > 0 for t in on_times]
    lit1 = [prim_knight(t, {"speed": 1.0, "offset": 0.5})[0] > 0 for t in on_times]
    assert lit0 != lit1, "half-cycle offset should flip the knight flash"
    assert any(a_ and not b_ for a_, b_ in zip(lit0, lit1)), "cubes must be out of phase"
