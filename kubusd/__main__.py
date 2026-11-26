"""kubusd CLI: run (daemon), sim (simulator), smoke (hardware test)."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _is_off_steps(steps) -> bool:
    """True when every step is just 'off' for every cube (used for resume)."""
    if not steps:
        return True
    for step in steps:
        for ci in ("0", "1", "2"):
            spec = step.get("cubes", {}).get(ci)
            if spec and spec.get("primitive") != "off":
                return False
    return True


def _load_cfg(args) -> "Config":
    from kubusd.config import Config

    dotenv = Path(args.config) if args.config else None
    cfg = Config.from_env(dotenv)
    cfg.validate()
    return cfg


def cmd_run(args) -> int:
    """kubusd run — real daemon on the Pi (headless, systemd)."""
    from kubusd.db import DB
    from kubusd.engine import Engine
    from kubusd.mqtt import MQTTClient
    from kubusd.output import make_output
    from kubusd.scheduler import SignScheduler

    cfg = _load_cfg(args)
    _setup_logging(cfg.log_level)
    db = DB(cfg.sqlite_path)
    engine = Engine(cfg.frame_rate)
    output = make_output(cfg, simulator=False)
    mqtt = MQTTClient(cfg, db, engine, output)
    scheduler = SignScheduler(cfg, db, output)
    try:
        # resume last-good pattern (V3) or default show
        active = db.get_active_pattern()
        db.prune_expired()
        active = db.get_active_pattern()
        if active and not _is_off_steps(active.get("steps")):
            engine.set_pattern(active["steps"])
            logging.getLogger("kubusd").info(
                "resumed last-good pattern %s", active["pattern_id"])
        else:
            engine.set_pattern("rainbow", {"speed": 0.5, "brightness": 0.6})
            logging.getLogger("kubusd").info("first boot: default show (rainbow)")
        engine.start()
        scheduler.start()
        mqtt.connect()
        logging.getLogger("kubusd").info("kubusd running (frame_rate=%s)", cfg.frame_rate)
        while True:
            scheduler.tick()
            frame = engine.step()
            frame.sign = scheduler.sign_frame()  # fixed hammer animation (SPEC §C)
            output.set_frame(frame)
            time.sleep(1.0 / cfg.frame_rate)
    except KeyboardInterrupt:
        pass
    finally:
        mqtt.stop()
        scheduler.stop()
        output.close()
        db.close()
    return 0


def cmd_sim(args) -> int:
    """kubusd sim — headless simulator, ANSI output, no pigpio (V4)."""
    from kubusd.db import DB
    from kubusd.engine import Engine
    from kubusd.mqtt import MQTTClient
    from kubusd.output import SimulatorOutput
    from kubusd.scheduler import SignScheduler

    cfg = _load_cfg(args)
    _setup_logging(cfg.log_level)
    db = DB(cfg.sqlite_path)
    engine = Engine(cfg.frame_rate)
    output = SimulatorOutput(cols=cfg.sim_cols)
    mqtt = MQTTClient(cfg, db, engine, output)
    scheduler = SignScheduler(cfg, db, output)
    active = db.get_active_pattern()
    if active and not _is_off_steps(active.get("steps")):
        engine.set_pattern(active["steps"])
    else:
        engine.set_pattern("rainbow", {"speed": 0.5, "brightness": 0.6})
    engine.start()
    scheduler.start()
    mqtt.connect()
    logging.getLogger("kubusd").info(
        "kubusd simulator — press Ctrl-C to stop (broker=%s)", cfg.mqtt_broker)
    try:
        while True:
            scheduler.tick()
            frame = engine.step()
            frame.sign = scheduler.sign_frame()  # fixed hammer animation (SPEC §C)
            output.set_frame(frame)
            time.sleep(1.0 / cfg.frame_rate)
    except KeyboardInterrupt:
        pass
    finally:
        mqtt.stop()
        scheduler.stop()
        output.close()
        db.close()
    return 0


def cmd_smoke(args) -> int:
    """kubusd smoke — hardware smoke test on the real Pi (V12)."""
    from kubusd.config import Config
    from kubusd.output import PigpioOutput
    from kubusd.engine import Frame

    cfg = _load_cfg(args)
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("kubusd.smoke")
    out = PigpioOutput(cfg.pwm_pins, cfg.sign_pins, cfg.pigpiod_host, cfg.pigpiod_port)
    try:
        # sweep each PWM channel 0 -> max -> 0
        for ch in range(9):
            f = Frame()
            f.strips = [[0.0, 0.0, 0.0]] * 3
            strip, color = divmod(ch, 3)
            col = [0.0, 0.0, 0.0]
            col[color] = 1.0
            f.strips[strip] = col
            out.set_frame(f)
            time.sleep(0.4)
            log.info("PWM channel %d (strip %d color %d) OK", ch, strip, color)
        # toggle each sign output
        for s in range(5):
            f = Frame()
            f.sign = [False] * 5
            f.sign[s] = True
            out.set_frame(f)
            time.sleep(0.4)
            log.info("sign output %d OK", s)
        log.info("smoke test passed: all 9 PWM + 5 sign outputs driven")
        return 0
    finally:
        out.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kubusd", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for name in ("run", "sim", "smoke"):
        p = sub.add_parser(name)
        p.add_argument("--config", "-c", default=None,
                       help="path to .env (default: env vars)")
        p.set_defaults(func={"run": cmd_run, "sim": cmd_sim, "smoke": cmd_smoke}[name])

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
