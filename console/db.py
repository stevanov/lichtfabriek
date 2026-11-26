"""console database: users, patterns (with IP audit), live state (V6, V7, V19)."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from pathlib import Path


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """pbkdf2 password hash. Returns (salt, hash)."""
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 100_000
    ).hex()
    return salt, h


class ConsoleDB:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Flask serves requests from worker threads; sqlite3 needs either
        # per-thread connections or check_same_thread=False + a lock.
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _execute(self, sql, params=()):
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                banned INTEGER NOT NULL DEFAULT 0,
                created_ts REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT UNIQUE NOT NULL,
                pattern_hash TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                creator TEXT NOT NULL,
                created_ts REAL NOT NULL,
                posting_ip TEXT NOT NULL,
                steps TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                ip TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        # migrations (review 2026-11-26): older DBs lack pattern_hash; the
        # alpha2 migration used to just ADD a steps column — but the leftover
        # primitive/params NOT NULL columns then broke every new insert. Rebuild
        # the table properly, converting legacy rows to canonical steps.
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(patterns)")}
        if cols and "steps" not in cols:
            self._rebuild_patterns_table(cols)
        elif cols and "pattern_hash" not in cols:
            self.conn.execute(
                "ALTER TABLE patterns ADD COLUMN pattern_hash TEXT NOT NULL DEFAULT ''")
        self.conn.commit()

    def _rebuild_patterns_table(self, cols: set) -> None:
        """Recreate `patterns` with the current schema, converting legacy
        primitive/params rows into canonical steps. Transactional."""
        import json

        legacy = "primitive" in cols
        select_cols = ["pattern_id", "title", "description", "creator",
                       "created_ts", "posting_ip", "active"]
        if "pattern_hash" in cols:
            select_cols.insert(1, "pattern_hash")
        if legacy:
            select_cols[6:6] = ["primitive", "params"]
        rows = self.conn.execute(
            f"SELECT {', '.join(select_cols)} FROM patterns").fetchall()
        self.conn.execute("ALTER TABLE patterns RENAME TO patterns_legacy")
        self.conn.executescript(
            """
            CREATE TABLE patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT UNIQUE NOT NULL,
                pattern_hash TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                creator TEXT NOT NULL,
                created_ts REAL NOT NULL,
                posting_ip TEXT NOT NULL,
                steps TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        for row in rows:
            d = dict(zip(select_cols, row))
            if legacy:
                # legacy single-primitive -> one all-cubes step (V22)
                cube = {"primitive": d["primitive"],
                        "params": json.loads(d.get("params") or "{}")}
                steps = json.dumps([{"duration_s": 60.0,
                                     "cubes": {"0": cube, "1": cube, "2": cube}}])
            else:
                steps = "[]"
            self.conn.execute(
                "INSERT INTO patterns (pattern_id, pattern_hash, title, "
                "description, creator, created_ts, posting_ip, steps, active) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (d["pattern_id"], d.get("pattern_hash", ""), d["title"],
                 d["description"], d["creator"], d["created_ts"],
                 d["posting_ip"], steps, d["active"]),
            )
        self.conn.execute("DROP TABLE patterns_legacy")
        self.conn.commit()

    # ---- users (V11: admin-created only) ----

    def create_user(self, username: str, password: str, is_admin: bool = False,
                    must_change_password: bool = False) -> None:
        salt, h = hash_password(password)
        self._execute(
            "INSERT INTO users (username, salt, hash, is_admin, "
            "must_change_password, created_ts) VALUES (?,?,?,?,?,?)",
            (username, salt, h, 1 if is_admin else 0,
             1 if must_change_password else 0, time.time()),
        )

    def get_user(self, username: str):
        with self._lock:
            return self.conn.execute(
                "SELECT * FROM users WHERE username=?", (username,)
            ).fetchone()

    def verify_password(self, username: str, password: str) -> bool:
        u = self.get_user(username)
        if not u:
            return False
        salt, h = hash_password(password, u["salt"])
        return secrets.compare_digest(h, u["hash"])

    def set_password(self, username: str, password: str) -> None:
        salt, h = hash_password(password)
        self._execute(
            "UPDATE users SET salt=?, hash=?, must_change_password=0 WHERE username=?",
            (salt, h, username),
        )

    def list_users(self):
        with self._lock:
            return self.conn.execute(
                "SELECT id, username, is_admin, banned, created_ts FROM users "
                "ORDER BY created_ts"
            ).fetchall()

    def set_banned(self, username: str, banned: bool) -> None:
        self._execute(
            "UPDATE users SET banned=? WHERE username=?", (1 if banned else 0, username))

    # ---- patterns (V6) ----

    def add_pattern(self, pattern_id: str, pattern_hash: str, title: str,
                    description: str, creator: str, posting_ip: str,
                    steps: list) -> None:
        import json

        self._execute(
            "INSERT INTO patterns (pattern_id, pattern_hash, title, description, creator, "
            "created_ts, posting_ip, steps) VALUES (?,?,?,?,?,?,?,?)",
            (pattern_id, pattern_hash, title, description, creator, time.time(),
             posting_ip, json.dumps(steps)),
        )

    def _pattern_row(self, r) -> dict:
        import json

        d = dict(r)
        try:
            d["steps"] = json.loads(d.get("steps") or "[]")
        except (ValueError, TypeError):
            d["steps"] = []
        # legacy rows: no steps -> derive from old primitive/params if present
        if not d["steps"] and d.get("primitive"):
            cube = {"primitive": d["primitive"], "params": json.loads(d.get("params") or "{}")}
            d["steps"] = [{"duration_s": 60.0,
                           "cubes": {"0": cube, "1": cube, "2": cube}}]
        return d

    def list_patterns(self):
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM patterns ORDER BY created_ts DESC").fetchall()
        return [self._pattern_row(r) for r in rows]

    def get_pattern(self, pattern_id: str):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM patterns WHERE pattern_id=?", (pattern_id,)).fetchone()
        if not r:
            return None
        return self._pattern_row(r)

    def set_active(self, pattern_id: str) -> None:
        self._execute("UPDATE patterns SET active=0")
        self._execute(
            "UPDATE patterns SET active=1 WHERE pattern_id=?", (pattern_id,))

    def get_active(self):
        with self._lock:
            return self.conn.execute(
                "SELECT * FROM patterns WHERE active=1").fetchone()

    def clear_active(self) -> None:
        self._execute("UPDATE patterns SET active=0")

    # ---- audit (V7) ----

    def audit(self, actor: str, action: str, detail: str, ip: str = "") -> None:
        self._execute(
            "INSERT INTO audit (ts, actor, action, detail, ip) VALUES (?,?,?,?,?)",
            (time.time(), actor, action, detail, ip),
        )

    def list_audit(self, limit: int = 100):
        with self._lock:
            return self.conn.execute(
                "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    # ---- rate limiting (V7) ----

    def rate_limit_hits(self, ip: str, minute: int) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM audit WHERE ip=? AND action IN "
                "('publish','activate','revoke','login') AND ts > ?",
                (ip, minute),
            ).fetchone()
        return row["c"]

    # ---- publish counter (V13: monotonic across restarts) ----

    def get_counter(self) -> int | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT value FROM kv WHERE key='publish_counter'").fetchone()
        return int(row["value"]) if row else None

    def set_counter(self, n: int) -> None:
        self._execute(
            "INSERT INTO kv (key, value) VALUES ('publish_counter', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(n),),
        )

    def close(self) -> None:
        self.conn.close()
