"""Tests for the console Flask app (auth, publish, admin, V6/V7/V11/V19)."""

import os
import tempfile
from pathlib import Path

import pytest

tmp = tempfile.mkdtemp()
os.environ["SQLITE_PATH"] = str(Path(tmp) / "console-test.db")
os.environ["PAYLOAD_KEY"] = "test-key"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_PASSWORD"] = "admin-password"
os.environ["RATE_LIMIT_PER_MINUTE"] = "3"
os.environ.pop("TRUST_PROXY", None)

from console.app import _bootstrap_admin, app, db  # noqa: E402


import secrets as _secrets


@pytest.fixture(autouse=True)
def _reset_db():
    """Each test starts from a clean DB (module-level db is shared)."""
    for table in ("users", "patterns", "audit", "kv"):
        db.conn.execute(f"DELETE FROM {table}")
    db.conn.commit()
    yield
    for table in ("users", "patterns", "audit", "kv"):
        db.conn.execute(f"DELETE FROM {table}")
    db.conn.commit()


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _csrf_token(client) -> str:
    """Put a CSRF token into the session (the before_request validator
    compares it against the form's _csrf field)."""
    with client.session_transaction() as s:
        return s.setdefault("csrf", _secrets.token_hex(16))


_orig_post = None


def _post(client, url, data=None, **kwargs):
    """client.post with the CSRF token merged into the form data."""
    data = dict(data or {})
    data.setdefault("_csrf", _csrf_token(client))
    return client.post(url, data=data, **kwargs)


def _login(client, username="admin", password="admin-password"):
    return _post(client, "/login", data={"username": username, "password": password},
                 follow_redirects=True)


def test_bootstrap_admin_created():
    _bootstrap_admin()
    assert db.get_user("admin") is not None


def test_login_wrong_password(client):
    r = _post(client, "/login", data={"username": "admin", "password": "nope"})
    assert b"Invalid credentials" in r.data


def test_login_ok_redirects_to_change_password(client):
    _bootstrap_admin()
    r = _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    assert r.status_code in (302, 303)
    assert "/change-password" in r.headers["Location"]


def test_requires_login(client):
    r = client.get("/patterns")
    assert r.status_code in (302, 303)


def test_publish_pattern_and_ip_not_in_payload(client, monkeypatch):
    _bootstrap_admin()
    # create a normal user while still logged in as admin
    _login(client)
    _post(client, "/change-password", data={"password": "newpass123",
                                          "password2": "newpass123"})
    _post(client, "/admin/users", data={"action": "create", "username": "bob",
                                      "password": "bobpass123"})
    client.get("/logout")
    # bob logs in and publishes
    _post(client, "/login", data={"username": "bob", "password": "bobpass123"})
    # stub publisher so no real broker needed
    calls = []

    def fake_publish_pattern(msg, retain=True):
        calls.append(msg)
        # V19: the payload must never contain creator or ip
        assert "creator" not in msg and "ip" not in msg
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish_pattern)
    r = _post(client, "/patterns/new", data={
        "title": "Test pattern", "description": "d", "primitive": "rainbow",
        "speed": "1", "brightness": "0.5",
        "colors": "255,0,0;0,255,0",
    }, follow_redirects=True)
    assert b"published" in r.data
    assert calls, "publisher called"


def test_rate_limit(client, monkeypatch):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})

    def fake_publish(msg, retain=True):
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish)
    # RATE_LIMIT_PER_MINUTE = 3 -> 4th publish in a minute is limited
    for _ in range(3):
        _post(client, "/patterns/new", data={
            "title": "p", "primitive": "off", "speed": "1", "brightness": "1",
        })
    r = _post(client, "/patterns/new", data={
        "title": "p4", "primitive": "off", "speed": "1", "brightness": "1",
    }, follow_redirects=True)
    assert b"Rate limit" in r.data


def test_admin_required(client):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    _post(client, "/admin/users", data={"action": "create", "username": "carl",
                                      "password": "carlpass123"})
    client.get("/logout")
    _post(client, "/login", data={"username": "carl", "password": "carlpass123"})
    r = client.get("/admin")
    assert r.status_code == 403


def test_activate_pattern(client, monkeypatch):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    calls = []

    def fake_publish(msg, retain=True):
        calls.append(msg)
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish)
    # create a pattern directly in the DB (with hash) then activate
    _steps = [{"duration_s": 5.0,
               "cubes": {"0": {"primitive": "rainbow", "params": {}},
                         "1": None, "2": None}}]
    db.add_pattern("pid1", "hash1", "Title", "desc", "admin", "127.0.0.1", _steps)
    r = _post(client, "/patterns/pid1/activate", follow_redirects=True)
    assert b"activated" in r.data
    assert calls and calls[0]["pattern_hash"] == "hash1"


def test_activate_old_pattern_without_hash(client, monkeypatch):
    # regression: rows migrated without a hash must still activate (hash fallback)
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    calls = []
    monkeypatch.setattr("console.app.publisher.publish_pattern",
                        lambda msg, retain=True: calls.append(msg) or 1)
    db.conn.execute(
        "INSERT INTO patterns (pattern_id, pattern_hash, title, creator, "
        "created_ts, posting_ip, steps) "
        "VALUES ('old1','','T','a',1,'1.2.3.4','[]')")
    db.conn.commit()
    r = _post(client, "/patterns/old1/activate", follow_redirects=True)
    assert b"activated" in r.data
    assert calls and calls[0]["pattern_hash"]  # fallback hash generated


def test_publish_sequence_steps(client, monkeypatch):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    calls = []

    def fake_publish(msg, retain=True):
        calls.append(msg)
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish)
    import json

    steps = [
        {"duration_s": 3.0,
         "cubes": {"0": {"primitive": "fire", "params": {}},
                   "1": None, "2": None}},
        {"duration_s": 2.0,
         "cubes": {"1": {"primitive": "static", "params": {"colors": [[0, 0, 255]]}}}},
    ]
    r = _post(client, "/patterns/new", data={
        "title": "Seq", "steps": json.dumps(steps),
    }, follow_redirects=True)
    assert b"published" in r.data
    assert calls and calls[0]["steps"] == steps


def test_publish_bad_steps_json(client, monkeypatch):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    r = _post(client, "/patterns/new", data={
        "title": "Bad", "steps": "{not json",
    }, follow_redirects=True)
    assert b"Invalid steps JSON" in r.data


def test_activate_without_broker_no_500(client, monkeypatch):
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin", "password": "admin-password"})
    _post(client, "/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    db.add_pattern("pid2", "hash2", "T2", "", "admin", "127.0.0.1",
                   [{"duration_s": 5.0,
                     "cubes": {"0": {"primitive": "rainbow", "params": {}}}}])

    def boom(msg, retain=True):
        raise ConnectionError("broker down")

    monkeypatch.setattr("console.app.publisher.publish_pattern", boom)
    r = _post(client, "/patterns/pid2/activate", follow_redirects=True)
    assert r.status_code == 200
    assert b"MQTT publish failed" in r.data


def test_alpha2_console_migration_rebuilds_table(tmp_path):
    """The alpha2 console DB had primitive/params NOT NULL columns; the old
    ADD-COLUMN migration left them in place and broke every new insert
    (review finding). The rebuild must convert rows and allow inserts."""
    import sqlite3

    from console.db import ConsoleDB

    p = tmp_path / "legacy-console.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(
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
            primitive TEXT NOT NULL,
            params TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO patterns (pattern_id, title, creator, created_ts,
                              posting_ip, primitive, params, active)
        VALUES ('old1', 'Legacy', 'admin', 1000.0, '1.2.3.4', 'pulse', '{}', 0);
        """
    )
    conn.commit()
    conn.close()

    db = ConsoleDB(str(p))
    # legacy row converted to steps
    old = db.get_pattern("old1")
    assert old is not None and old["steps"], "legacy row converted to steps"
    # inserting a NEW pattern works (used to fail: primitive NOT NULL)
    db.add_pattern("new1", "h1", "Fresh", "", "admin", "127.0.0.1",
                   [{"duration_s": 5.0, "cubes": {}}])
    assert db.get_pattern("new1") is not None
    tables = {r[0] for r in db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "patterns_legacy" not in tables
    db.close()


def test_csrf_required_on_post(client):
    """Every POST must carry the session CSRF token (review finding)."""
    _bootstrap_admin()
    r = client.post("/login", data={"username": "admin",
                                    "password": "admin-password"})
    assert r.status_code == 400, "POST without CSRF token must be rejected"
    # with the token it works
    r = _post(client, "/login", data={"username": "admin",
                                      "password": "admin-password"})
    assert r.status_code == 302


def test_csrf_token_reuse_of_foreign_token_rejected(client):
    _bootstrap_admin()
    # token from a DIFFERENT session must not pass
    with app.test_client() as other:
        foreign = _csrf_token(other)
    r = client.post("/login", data={"username": "admin",
                                    "password": "admin-password",
                                    "_csrf": foreign})
    assert r.status_code == 400


def test_lang_toggle_sets_cookie_and_stays_local(client):
    r = _post(client, "/lang", data={"lang": "nl"})
    assert r.status_code == 302
    cookie = client.get_cookie("lf_lang")
    assert cookie is not None and cookie.value == "nl"
    # open-redirect guard: an external referrer falls back to /patterns
    r = client.post("/lang", data={"lang": "nl", "_csrf": _csrf_token(client)},
                    headers={"Referer": "https://evil.example/steal"},
                    follow_redirects=False)
    assert (r.headers.get("Location") or "").startswith("/"), \
        "external referrer must not be followed"


def test_dutch_ui_strings(client):
    """With lf_lang=nl the UI renders Dutch (alpha4 i18n)."""
    client.set_cookie("lf_lang", "nl")
    r = client.get("/login")
    assert "Inloggen" in r.get_data(as_text=True)
    # default (no cookie) stays English
    client.delete_cookie("lf_lang")
    r = client.get("/login")
    assert "Log in" in r.get_data(as_text=True)


def test_must_change_password_is_a_guard(client):
    """The forced first-login change must block /patterns too, not just be a
    redirect suggestion (review finding)."""
    _bootstrap_admin()
    _post(client, "/login", data={"username": "admin",
                                  "password": "admin-password"})
    # do NOT change the password -> /patterns must bounce to change-password
    r = client.get("/patterns", follow_redirects=False)
    assert r.status_code == 302
    assert "/change-password" in (r.headers.get("Location") or "")
    # after changing it, /patterns is reachable
    _post(client, "/change-password", data={"password": "newpass123",
                                            "password2": "newpass123"})
    r = client.get("/patterns", follow_redirects=False)
    assert r.status_code == 200
