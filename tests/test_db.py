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


def test_ttl_absolute_and_expiry(tmp_path):
    """ttl arrives as RELATIVE seconds; stored as ABSOLUTE expiry (argon-era
    review: a relative ttl used to be compared against epoch time)."""
    import time

    db = DB(str(tmp_path / "test.db"))
    db.set_active_pattern({
        "pattern_id": "p1", "pattern_hash": "h1",
        "primitive": "pulse", "params": {},
    }, ttl=10.0)
    active = db.get_active_pattern()
    assert active["ttl"] is not None
    assert active["ttl"] > time.time()  # absolute, in the future
    # not expired yet
    assert db.prune_expired() == 0
    assert db.get_active_pattern() is not None
    # force expiry -> prune deactivates exactly the expired pattern
    db.conn.execute("UPDATE patterns SET ttl = ? WHERE active=1",
                    (time.time() - 10,))
    db.conn.commit()
    assert db.prune_expired() == 1
    assert db.get_active_pattern() is None
    db.close()


def test_per_topic_counters(tmp_path):
    """Replay counters are per topic (review: one global counter rejected
    valid patterns when retained messages crossed topics out of order)."""
    db = DB(str(tmp_path / "test.db"))
    db.set_counter("lichtfabriek/pattern/set", 11)
    db.set_counter("lichtfabriek/sign/set", 5)
    assert db.get_counter("lichtfabriek/pattern/set") == 11
    assert db.get_counter("lichtfabriek/sign/set") == 5
    assert db.get_counter("lichtfabriek/sign/schedule") is None
    # advancing one topic does not disturb the other
    db.set_counter("lichtfabriek/pattern/set", 12)
    assert db.get_counter("lichtfabriek/sign/set") == 5
    db.close()


def test_alpha1_pattern_migration(tmp_path):
    """An alpha1 DB (primitive/params columns) must migrate to steps at open,
    not crash kubusd at startup (review finding)."""
    import sqlite3

    p = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(
        """
        CREATE TABLE patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id TEXT NOT NULL,
            pattern_hash TEXT NOT NULL,
            primitive TEXT NOT NULL,
            params TEXT NOT NULL,
            created_ts REAL NOT NULL,
            ttl REAL,
            active INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO patterns (pattern_id, pattern_hash, primitive, params,
                              created_ts, ttl, active)
        VALUES ('old1', 'h1', 'rainbow', '{"speed": 1.0}', 1000.0, 3600.0, 1);
        """
    )
    conn.commit()
    conn.close()

    db = DB(str(p))
    active = db.get_active_pattern()
    assert active is not None, "legacy row migrated to an active steps pattern"
    assert active["pattern_id"] == "old1"
    assert active["steps"], "converted to canonical steps"
    assert active["ttl"] > 0, "relative ttl converted to absolute expiry"
    # legacy table is gone
    tables = {r[0] for r in db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "patterns_legacy" not in tables
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
