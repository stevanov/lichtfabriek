"""console Flask app: auth, patterns, admin, publish (V6, V7, V11, V18, V19)."""

from __future__ import annotations

import functools
import secrets
import time
from pathlib import Path

from flask import (
    Flask, abort, flash, g, redirect, render_template, request, session, url_for,
)

from console.config import Config
from console.db import ConsoleDB
from console.publisher import Publisher
from shared import schema
from shared.crypto import new_key

app = Flask(__name__)
cfg = Config(dotenv=Path(__file__).parent / ".env")
cfg.validate()
app.secret_key = cfg.secret_key

db = ConsoleDB(cfg.sqlite_path)
publisher = Publisher(cfg, db)


@app.template_filter("ctime")
def ctime_filter(ts: float) -> str:
    import time as _time

    return _time.strftime("%Y-%m-%d %H:%M", _time.localtime(ts))


try:
    publisher.connect()
except ConnectionError as e:
    app.logger.warning("MQTT not connected at startup: %s", e)

# ---- helpers ----

def _bootstrap_admin() -> None:
    """First admin account from ADMIN_PASSWORD, forced change on login (V11)."""
    if db.get_user("admin") is None:
        db.create_user("admin", cfg.admin_password, is_admin=True,
                       must_change_password=True)
        db.audit("system", "bootstrap", "created initial admin")


def _client_ip() -> str:
    # V7: only trust X-Forwarded-For when explicitly configured behind a proxy
    if cfg.trust_proxy:
        return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0]
    return request.remote_addr or ""


def login_required(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrap


def admin_required(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        u = db.get_user(session["user"])
        if not u or not u["is_admin"] or u["banned"]:
            abort(403)
        return f(*args, **kwargs)
    return wrap


def _banned_or_deleted(f):
    @functools.wraps(f)
    def wrap(*args, **kwargs):
        u = db.get_user(session.get("user", ""))
        if u and u["banned"]:
            session.clear()
            flash("Account suspended.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrap


# ---- auth ----

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        u = db.get_user(username)
        if u and not u["banned"] and db.verify_password(username, password):
            session["user"] = username
            session["is_admin"] = bool(u["is_admin"])
            db.audit(username, "login", "ok", _client_ip())
            nxt = request.args.get("next") or url_for("patterns")
            if u["must_change_password"]:
                return redirect(url_for("change_password"))
            return redirect(nxt)
        db.audit(username or "?", "login", "failed", _client_ip())
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    db.audit(session.get("user", "?"), "logout", "", _client_ip())
    session.clear()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        p1 = request.form.get("password", "")
        p2 = request.form.get("password2", "")
        if len(p1) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif p1 != p2:
            flash("Passwords do not match.", "error")
        else:
            db.set_password(session["user"], p1)
            db.audit(session["user"], "change_password", "ok", _client_ip())
            flash("Password updated.", "ok")
            return redirect(url_for("patterns"))
    return render_template("change_password.html")


# ---- patterns ----

@app.route("/")
@login_required
def index():
    return redirect(url_for("patterns"))


@app.route("/patterns")
@login_required
@_banned_or_deleted
def patterns():
    return render_template("patterns.html", patterns=db.list_patterns())


@app.route("/patterns/new", methods=["GET", "POST"])
@login_required
@_banned_or_deleted
def new_pattern():
    if request.method == "POST":
        return _publish(request)
    return render_template("new_pattern.html", primitives=sorted(schema.PRIMITIVES))


def _publish(request) -> redirect:
    ip = _client_ip()
    # rate limit publish endpoint (V7)
    minute_start = time.time() - 60
    if db.rate_limit_hits(ip, minute_start) >= cfg.rate_limit_per_minute:
        flash("Rate limit reached — try again in a minute.", "error")
        return redirect(url_for("patterns"))
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    primitive = request.form.get("primitive", "").strip()
    speed = _float(request.form.get("speed", "1"))
    brightness = _float(request.form.get("brightness", "1"))
    colors = _colors(request.form.get("colors", ""))
    pattern_id = secrets.token_hex(8)
    params = {"speed": speed, "brightness": brightness}
    if colors:
        params["colors"] = colors
    msg = {
        "pattern_id": pattern_id,
        "pattern_hash": secrets.token_hex(8),
        "primitive": primitive,
        "params": params,
    }
    try:
        schema.validate_pattern(msg)
    except ValueError as e:
        flash(f"Invalid pattern: {e}", "error")
        return redirect(url_for("new_pattern"))
    # V19: IP + creator stay in console DB, never in the payload
    db.add_pattern(pattern_id, msg["pattern_hash"], title or pattern_id,
                   description, session["user"], ip, primitive, params)
    try:
        counter = publisher.publish_pattern(msg)
    except (ConnectionError, Exception) as e:  # noqa: BLE001
        db.audit(session["user"], "publish", f"failed: {e}", ip)
        flash(f"MQTT publish failed: {e}", "error")
        return redirect(url_for("patterns"))
    db.set_active(pattern_id)
    db.audit(session["user"], "publish", f"{pattern_id} -> {primitive}", ip)
    flash(f"Pattern {title or pattern_id} published (counter {counter}).", "ok")
    return redirect(url_for("patterns"))


@app.route("/patterns/<pattern_id>/activate", methods=["POST"])
@login_required
@_banned_or_deleted
def activate(pattern_id: str):
    p = db.get_pattern(pattern_id)
    if not p:
        abort(404)
    ip = _client_ip()
    msg = {
        "pattern_id": p["pattern_id"],
        "pattern_hash": p["pattern_hash"] or secrets.token_hex(8),
        "primitive": p["primitive"],
        "params": p["params"],
    }
    try:
        publisher.publish_pattern(msg)
    except Exception as e:  # noqa: BLE001
        db.audit(session["user"], "activate_failed", f"{pattern_id}: {e}", ip)
        flash(f"MQTT publish failed: {e}", "error")
        return redirect(url_for("patterns"))
    db.set_active(pattern_id)
    db.audit(session["user"], "activate", pattern_id, ip)
    flash(f"Pattern {p['title']} activated.", "ok")
    return redirect(url_for("patterns"))


@app.route("/patterns/revoke", methods=["POST"])
@login_required
@_banned_or_deleted
def revoke():
    # V15: revoke = publish default/previous pattern (off), retained
    ip = _client_ip()
    msg = {"pattern_id": "default", "pattern_hash": "default",
           "primitive": "off", "params": {}}
    try:
        publisher.publish_pattern(msg, retain=True)
    except Exception as e:  # noqa: BLE001
        db.audit(session["user"], "revoke_failed", str(e), ip)
        flash(f"MQTT publish failed: {e}", "error")
        return redirect(url_for("patterns"))
    db.clear_active()
    db.audit(session["user"], "revoke", "all patterns off", ip)
    flash("All patterns revoked (default show).", "ok")
    return redirect(url_for("patterns"))


# ---- admin ----

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", users=db.list_users(),
                           audit=db.list_audit(), active=db.get_active())


@app.route("/admin/users", methods=["POST"])
@admin_required
def admin_users():
    action = request.form.get("action")
    username = request.form.get("username", "").strip()
    ip = _client_ip()
    if action == "create":
        password = request.form.get("password", "")
        if not username or len(password) < 8:
            flash("Username + password (>= 8 chars) required.", "error")
        elif db.get_user(username):
            flash("User already exists.", "error")
        else:
            is_admin = "is_admin" in request.form
            db.create_user(username, password, is_admin=is_admin)
            db.audit(session["user"], "user_create", username, ip)
            flash(f"User {username} created.", "ok")
    elif action == "ban":
        db.set_banned(username, True)
        db.audit(session["user"], "user_ban", username, ip)
        flash(f"User {username} banned.", "ok")
    elif action == "unban":
        db.set_banned(username, False)
        db.audit(session["user"], "user_unban", username, ip)
        flash(f"User {username} unbanned.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/sign", methods=["POST"])
@admin_required
def admin_sign():
    # V18: sign/schedule messages are console-admin only
    ip = _client_ip()
    action = request.form.get("action")
    try:
        if action == "sign_on":
            publisher.publish_sign_set(True)
            db.audit(session["user"], "sign_set", "on", ip)
            flash("Sign manually on (override, expires in 1 h).", "ok")
        elif action == "sign_off":
            publisher.publish_sign_set(False)
            db.audit(session["user"], "sign_set", "off", ip)
            flash("Sign manually off (override, expires in 1 h).", "ok")
        elif action == "schedule":
            start = request.form.get("start", "18:00")
            stop = request.form.get("stop", "23:00")
            enabled = "enabled" in request.form
            schedule = {"enabled": enabled, "start": start, "stop": stop}
            try:
                schema.validate_sign_schedule({"schedule": schedule})
            except ValueError as e:
                flash(f"Invalid schedule: {e}", "error")
                return redirect(url_for("admin"))
            publisher.publish_sign_schedule(schedule)
            db.audit(session["user"], "sign_schedule", str(schedule), ip)
            flash("Schedule published.", "ok")
    except Exception as e:  # noqa: BLE001
        db.audit(session["user"], "sign_publish_failed", str(e), ip)
        flash(f"MQTT publish failed: {e}", "error")
    return redirect(url_for("admin"))


def _float(v: str, default: float = 1.0) -> float:
    try:
        return float(v)
    except ValueError:
        return default


def _colors(raw: str) -> list | None:
    """Parse 'r,g,b;r,g,b;...' into [[r,g,b],...]."""
    if not raw.strip():
        return None
    out = []
    for part in raw.split(";"):
        vals = [int(x) for x in part.split(",") if x.strip()]
        if len(vals) != 3:
            return None
        out.append(vals)
    return out


if __name__ == "__main__":
    _bootstrap_admin()
    app.run(host="0.0.0.0", port=5001)
