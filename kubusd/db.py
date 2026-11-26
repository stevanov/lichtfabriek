"""kubusd SQLite persistence.

Tables (SPEC §I): patterns (last-good + history), sign_state (schedule +
override), audit (ring buffer). WAL + synchronous=FULL (V16). On corruption:
rename the db, recreate, run default show (V3).
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

AUDIT_RING_SIZE = 2000  # V16 cap


class DB:
    def __init__(self, path: str):
        self.path = Path(path)
        self.conn = None
        self.open()

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connect()
            if not self._integrity_ok():
                raise sqlite3.DatabaseError("integrity check failed")
        except sqlite3.DatabaseError:
            # V3/V16: rename corrupt db, recreate, start fresh with default show
            corrupt = self.path.with_suffix(self.path.suffix + ".corrupt")
            n = 0
            while corrupt.exists():
                n += 1
                corrupt = self.path.with_suffix(self.path.suffix + f".corrupt{n}")
            try:
                self.path.rename(corrupt)
            except FileNotFoundError:
                pass
            self._connect()
        self._create_tables()

    def _connect(self) -> None:
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=FULL")
        self.conn.execute("PRAGMA busy_timeout=5000")

    def _integrity_ok(self) -> bool:
        row = self.conn.execute("PRAGMA integrity_check").fetchone()
        return bool(row) and row[0] == "ok"

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT NOT NULL,
                pattern_hash TEXT NOT NULL,
                steps TEXT NOT NULL,
                created_ts REAL NOT NULL,
                ttl REAL,
                active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sign_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS counters (
                topic TEXT PRIMARY KEY,
                counter INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                topic TEXT NOT NULL,
                kind TEXT NOT NULL,
                detail TEXT NOT NULL
            );
            """
        )
        self.conn.commit()
        self._migrate_legacy_patterns()

    def _migrate_legacy_patterns(self) -> None:
        """alpha1 stored primitive/params in `patterns`; alpha2 uses `steps`.

        Rebuild the table when the old schema is found, converting each legacy
        row to canonical steps (review 2026-11-26: a pre-alpha2 DB used to
        crash kubusd at startup with 'no such column: steps')."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(patterns)")}
        if not cols or "steps" in cols:
            return
        import json

        from shared.schema import normalize_pattern

        rows = self.conn.execute(
            "SELECT pattern_id, pattern_hash, primitive, params, "
            "created_ts, ttl, active FROM patterns").fetchall()
        self.conn.execute("ALTER TABLE patterns RENAME TO patterns_legacy")
        self.conn.executescript(
            """
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT NOT NULL,
                pattern_hash TEXT NOT NULL,
                steps TEXT NOT NULL,
                created_ts REAL NOT NULL,
                ttl REAL,
                active INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        for pid, phash, primitive, params, created, ttl, active in rows:
            try:
                msg = {"pattern_id": pid, "pattern_hash": phash,
                       "primitive": primitive,
                       "params": json.loads(params or "{}")}
                steps = json.dumps(normalize_pattern(msg)["steps"])
            except (ValueError, TypeError):
                continue  # unmigratable row: drop it, default show applies
            # old ttl was relative to creation -> absolute expiry
            expires = created + ttl if (ttl is not None and ttl < 1e6) else ttl
            self.conn.execute(
                "INSERT INTO patterns (pattern_id, pattern_hash, steps, "
                "created_ts, ttl, active) VALUES (?,?,?,?,?,?)",
                (pid, phash, steps, created, expires, active),
            )
        self.conn.execute("DROP TABLE patterns_legacy")
        self.conn.commit()

    # ---- patterns (V3, V15) ----

    def get_active_pattern(self) -> dict | None:
        row = self.conn.execute(
            "SELECT pattern_id, pattern_hash, steps, created_ts, ttl "
            "FROM patterns WHERE active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        import json

        return {
            "pattern_id": row[0],
            "pattern_hash": row[1],
            "steps": json.loads(row[2]),
            "created_ts": row[3],
            "ttl": row[4],
        }

    def set_active_pattern(self, msg: dict, ttl: float | None = None) -> None:
        import json

        from shared.schema import normalize_pattern

        normalized = normalize_pattern(msg)
        # ttl arrives as RELATIVE seconds from the message; store an ABSOLUTE
        # expiry so prune_expired compares like with like (review 2026-11-26)
        expires = (time.time() + ttl) if ttl is not None else None
        self.conn.execute(
            "UPDATE patterns SET active=0 WHERE active=1"
        )
        self.conn.execute(
            "INSERT INTO patterns (pattern_id, pattern_hash, steps, "
            "created_ts, ttl, active) VALUES (?,?,?,?,?,1)",
            (
                normalized["pattern_id"], normalized["pattern_hash"],
                json.dumps(normalized["steps"]), time.time(), expires,
            ),
        )
        self.conn.commit()

    def prune_expired(self, now: float | None = None) -> int:
        """Deactivate patterns whose TTL has passed (V15). Returns the count."""
        now = time.time() if now is None else now
        cur = self.conn.execute(
            "UPDATE patterns SET active=0 WHERE active=1 AND ttl IS NOT NULL AND ttl < ?",
            (now,),
        )
        self.conn.commit()
        return cur.rowcount

    # ---- per-topic replay counters (V13, review 2026-11-26) ----

    def get_counter(self, topic: str) -> int | None:
        row = self.conn.execute(
            "SELECT counter FROM counters WHERE topic=?", (topic,)).fetchone()
        return row[0] if row else None

    def set_counter(self, topic: str, counter: int) -> None:
        self.conn.execute(
            "INSERT INTO counters (topic, counter) VALUES (?,?) "
            "ON CONFLICT(topic) DO UPDATE SET counter=excluded.counter",
            (topic, counter),
        )
        self.conn.commit()

    # ---- sign state (V5, V18) ----

    def get_sign_state(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM sign_state").fetchall()
        return {k: v for k, v in rows}

    def set_sign_state(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO sign_state (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---- audit (V16 ring buffer) ----

    def audit(self, topic: str, kind: str, detail: str) -> None:
        self.conn.execute(
            "INSERT INTO audit (ts, topic, kind, detail) VALUES (?,?,?,?)",
            (time.time(), topic, kind, detail),
        )
        # ring buffer: trim oldest rows beyond cap (V16)
        self.conn.execute(
            "DELETE FROM audit WHERE id NOT IN "
            "(SELECT id FROM audit ORDER BY id DESC LIMIT ?)",
            (AUDIT_RING_SIZE,),
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
