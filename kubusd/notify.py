"""Minimal sd_notify client — no python3-systemd dependency.

systemd sets $NOTIFY_SOCKET for services that use Type=notify (with or without
WatchdogSec). We send a WATCHDOG=1 datagram from the render loop so the
watchdog supervises REAL render health (V17): a wedged render loop stops
pinging and systemd restarts us, while a healthy loop is never killed.

Outside systemd (manual run/sim) there is no NOTIFY_SOCKET: every call is a
cheap no-op.
"""

from __future__ import annotations

import os
import socket

_sock: socket.socket | None = None
_checked = False


def _connect():
    s = os.environ.get("NOTIFY_SOCKET")
    if not s:
        return None
    if s.startswith("@"):  # abstract namespace socket
        s = "\0" + s[1:]
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(s)
        return sock
    except OSError:
        return None


def watchdog_ping() -> bool:
    """Send WATCHDOG=1 to systemd. Returns False when not supervised."""
    global _sock, _checked
    if not _checked:
        _sock = _connect()
        _checked = True
    if _sock is None:
        return False
    try:
        _sock.sendall(b"WATCHDOG=1")
        return True
    except OSError:
        # socket died (systemd restarted under us) — reconnect on next ping
        _sock = None
        _checked = False
        return False
