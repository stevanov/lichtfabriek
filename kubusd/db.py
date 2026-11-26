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
                primitive TEXT NOT NULL,
                params TEXT NOT NULL,
                created_ts REAL NOT NULL,
                ttl REAL,
                active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sign_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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

    # ---- patterns (V3, V15) ----

    def get_active_pattern(self) -> dict | None:
        row = self.conn.execute(
            "SELECT pattern_id, pattern_hash, primitive, params, created_ts, ttl "
            "FROM patterns WHERE active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        import json

        return {
            "pattern_id": row[0],
            "pattern_hash": row[1],
            "primitive": row[2],
            "params": json.loads(row[3]),
            "created_ts": row[4],
            "ttl": row[5],
        }

    def set_active_pattern(self, msg: dict, ttl: float | None = None) -> None:
        import json

        self.conn.execute(
            "UPDATE patterns SET active=0 WHERE active=1"
        )
        self.conn.execute(
            "INSERT INTO patterns (pattern_id, pattern_hash, primitive, params, "
            "created_ts, ttl, active) VALUES (?,?,?,?,?,?,1)",
            (
                msg["pattern_id"], msg["pattern_hash"], msg["primitive"],
                json.dumps(msg["params"]), time.time(), ttl,
            ),
        )
        self.conn.commit()

    def revoke_active(self) -> None:
        """Revoke = clear active pattern; caller starts default show (V15)."""
        self.conn.execute("UPDATE patterns SET active=0 WHERE active=1")
        self.conn.commit()

    def prune_expired(self, now: float | None = None) -> None:
        """Drop patterns whose TTL has passed (V15)."""
        now = time.time() if now is None else now
        self.conn.execute(
            "UPDATE patterns SET active=0 WHERE active=1 AND ttl IS NOT NULL AND ttl < ?",
            (now,),
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
