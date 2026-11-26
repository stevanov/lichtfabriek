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
