"""Tests for kubusd SQLite persistence (V3, V15, V16)."""

import json

from kubusd.db import DB


def test_roundtrip_pattern(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    msg = {
        "pattern_id": "p1", "pattern_hash": "h1",
        "primitive": "rainbow", "params": {"speed": 1.0},
    }
    db.set_active_pattern(msg)
    active = db.get_active_pattern()
    assert active["pattern_id"] == "p1"
    assert active["steps"], "normalized to steps"
    assert active["steps"][0]["cubes"]["0"]["primitive"] == "rainbow"
    db.close()


def test_roundtrip_steps_pattern(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    msg = {
        "pattern_id": "p2", "pattern_hash": "h2",
        "steps": [
            {"duration_s": 3.0, "cubes": {"0": {"primitive": "rainbow", "params": {}}}},
            {"duration_s": 2.0, "cubes": {"1": {"primitive": "static", "params": {}}}},
        ],
    }
    db.set_active_pattern(msg)
    active = db.get_active_pattern()
    assert len(active["steps"]) == 2
    db.close()


def test_revoke_clears_active(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    db.set_active_pattern({
        "pattern_id": "p1", "pattern_hash": "h1",
        "primitive": "pulse", "params": {},
    })
    db.revoke_active()
    assert db.get_active_pattern() is None
    db.close()


def test_ttl_expiry(tmp_path):
    import time

    db = DB(str(tmp_path / "test.db"))
    db.set_active_pattern({
        "pattern_id": "p1", "pattern_hash": "h1",
        "primitive": "pulse", "params": {},
    }, ttl=time.time() - 10)
    db.prune_expired()
    assert db.get_active_pattern() is None
    db.close()


def test_audit_ring_buffer(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    from kubusd.db import AUDIT_RING_SIZE

    for i in range(AUDIT_RING_SIZE + 50):
        db.audit("topic", "drop", str(i))
    rows = db.conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    assert rows <= AUDIT_RING_SIZE
    db.close()


def test_corruption_recovery(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    db.set_sign_state("k", "v")
    db.close()
    # corrupt the file
    p = tmp_path / "test.db"
    p.write_bytes(b"this is not a sqlite file at all" * 100)
    # reopen: should rename corrupt db and recreate (V3/V16)
    db2 = DB(str(p))
    assert db2.get_active_pattern() is None
    db2.set_sign_state("k2", "v2")
    db2.close()
    assert list(tmp_path.glob("test.db.corrupt*")), "corrupt copy kept"


def test_wal_enabled(tmp_path):
    db = DB(str(tmp_path / "test.db"))
    mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    db.close()
