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


def _login(client, username="admin", password="admin-password"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


def test_bootstrap_admin_created():
    _bootstrap_admin()
    assert db.get_user("admin") is not None


def test_login_wrong_password(client):
    r = client.post("/login", data={"username": "admin", "password": "nope"})
    assert b"Invalid credentials" in r.data


def test_login_ok_redirects_to_change_password(client):
    _bootstrap_admin()
    r = client.post("/login", data={"username": "admin", "password": "admin-password"})
    assert r.status_code in (302, 303)
    assert "/change-password" in r.headers["Location"]


def test_requires_login(client):
    r = client.get("/patterns")
    assert r.status_code in (302, 303)


def test_publish_pattern_and_ip_not_in_payload(client, monkeypatch):
    _bootstrap_admin()
    # create a normal user while still logged in as admin
    _login(client)
    client.post("/change-password", data={"password": "newpass123",
                                          "password2": "newpass123"})
    client.post("/admin/users", data={"action": "create", "username": "bob",
                                      "password": "bobpass123"})
    client.get("/logout")
    # bob logs in and publishes
    client.post("/login", data={"username": "bob", "password": "bobpass123"})
    # stub publisher so no real broker needed
    calls = []

    def fake_publish_pattern(msg, retain=True):
        calls.append(msg)
        # V19: the payload must never contain creator or ip
        assert "creator" not in msg and "ip" not in msg
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish_pattern)
    r = client.post("/patterns/new", data={
        "title": "Test pattern", "description": "d", "primitive": "rainbow",
        "speed": "1", "brightness": "0.5",
        "colors": "255,0,0;0,255,0",
    }, follow_redirects=True)
    assert b"published" in r.data
    assert calls, "publisher called"


def test_rate_limit(client, monkeypatch):
    _bootstrap_admin()
    client.post("/login", data={"username": "admin", "password": "admin-password"})
    client.post("/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})

    def fake_publish(msg, retain=True):
        return 1

    monkeypatch.setattr("console.app.publisher.publish_pattern", fake_publish)
    # RATE_LIMIT_PER_MINUTE = 3 -> 4th publish in a minute is limited
    for _ in range(3):
        client.post("/patterns/new", data={
            "title": "p", "primitive": "off", "speed": "1", "brightness": "1",
        })
    r = client.post("/patterns/new", data={
        "title": "p4", "primitive": "off", "speed": "1", "brightness": "1",
    }, follow_redirects=True)
    assert b"Rate limit" in r.data


def test_admin_required(client):
    _bootstrap_admin()
    client.post("/login", data={"username": "admin", "password": "admin-password"})
    client.post("/change-password", data={"password": "adminpass123",
                                          "password2": "adminpass123"})
    client.post("/admin/users", data={"action": "create", "username": "carl",
                                      "password": "carlpass123"})
    client.get("/logout")
    client.post("/login", data={"username": "carl", "password": "carlpass123"})
    r = client.get("/admin")
    assert r.status_code == 403
