"""Lichtfabriek shared payload crypto.

AEAD-only (V9, V12): ChaCha20-Poly1305 via PyNaCl, fallback AES-GCM via
cryptography. Random nonce per message, topic bound as associated data,
key_id in every message, monotonic counter + timestamp window (V13).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

try:  # preferred: ChaCha20-Poly1305 via PyNaCl
    from nacl.bindings import (
        crypto_aead_chacha20poly1305_ietf_decrypt,
        crypto_aead_chacha20poly1305_ietf_encrypt,
    )

    _PRIMITIVE = "chacha20-poly1305"
except ImportError:  # fallback: AES-GCM via cryptography (V9)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _PRIMITIVE = "aes-256-gcm"

_NONCEBYTES = 12
_ABYTES = 16
_VERSION = 1
MAX_CLOCK_SKEW = 300  # seconds, timestamp window (V13)

AAD_TOPIC_KEY = b"lichtfabriek-topic"


def derive_key(secret: str, key_id: str) -> bytes:
    """Derive a 32-byte key from the shared secret + key_id (HKDF-ish, hmac-sha256)."""
    return hmac.new(secret.encode(), key_id.encode(), hashlib.sha256).digest()


def new_key() -> str:
    """Generate a new random shared key, base64 (for .env)."""
    return base64.b64encode(os.urandom(32)).decode()


def _encrypt_impl(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    if _PRIMITIVE == "chacha20-poly1305":
        return crypto_aead_chacha20poly1305_ietf_encrypt(plaintext, aad, nonce, key)
    aes = AESGCM(key)
    return aes.encrypt(nonce, plaintext, aad)


def _decrypt_impl(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    if _PRIMITIVE == "chacha20-poly1305":
        return crypto_aead_chacha20poly1305_ietf_decrypt(
            ciphertext, aad, nonce, key
        )
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, aad)


def seal(topic: str, message: dict, secret: str, key_id: str,
         counter: int, now: float | None = None) -> bytes:
    """Seal a message dict for a topic: AEAD + topic AAD + nonce + counter.

    Returns a bytes envelope: version|key_id|counter|ts|nonce|ciphertext.
    """
    now = time.time() if now is None else now
    key = derive_key(secret, key_id)
    payload = json.dumps(message, separators=(",", ":")).encode()
    aad = AAD_TOPIC_KEY + topic.encode() + counter.to_bytes(8, "big")
    nonce = os.urandom(_NONCEBYTES)
    ct = _encrypt_impl(key, nonce, payload, aad)
    env = (
        bytes([_VERSION])
        + len(key_id).to_bytes(1, "big")
        + key_id.encode()
        + counter.to_bytes(8, "big")
        + int(now).to_bytes(8, "big")
        + nonce
        + ct
    )
    return env


class Reject(Exception):
    """Message rejected (bad auth, stale, replay, malformed). Reason in str()."""


def open_envelope(topic: str, envelope: bytes, secret: str,
                  keys: dict[str, str] | None = None,
                  last_counter: int = -1, now: float | None = None,
                  max_clock_skew: float = MAX_CLOCK_SKEW,
                  check_timestamp: bool = True) -> PayloadAuth:
    """Authenticate + decrypt an envelope for a topic.

    Returns PayloadAuth(message, counter). keys: key_id -> secret, for
    rotation (V9). last_counter: reject counters <= this (V13).
    Raises Reject on any failure.
    """
    now = time.time() if now is None else now
    if len(envelope) < 1 + 1 + 8 + 8 + _NONCEBYTES + _ABYTES:
        raise Reject("envelope too short")
    ver = envelope[0]
    if ver != _VERSION:
        raise Reject(f"unsupported envelope version {ver}")
    kid_len = envelope[1]
    if not (0 < kid_len <= 32):
        raise Reject("bad key_id length")
    off = 2
    try:
        key_id = envelope[off:off + kid_len].decode()
    except UnicodeDecodeError:
        # review 2026-11-26: a hostile non-UTF-8 key_id must not escape the
        # Reject path (it used to raise out of open_envelope entirely)
        raise Reject("key_id not valid UTF-8")
    off += kid_len
    counter = int.from_bytes(envelope[off:off + 8], "big")
    off += 8
    ts = int.from_bytes(envelope[off:off + 8], "big")
    off += 8
    nonce = envelope[off:off + _NONCEBYTES]
    ct = envelope[off + _NONCEBYTES:]
    if keys is None:
        key = derive_key(secret, key_id)
    else:
        try:
            key = derive_key(keys[key_id], key_id)
        except KeyError:
            raise Reject(f"unknown key_id {key_id!r}")
    # replay + clock window (V13). The timestamp check can be skipped for
    # RETAINED messages (queued while the Pi was offline — review 2026-11-26)
    # and when the local clock looks unsynced (no RTC on the Pi, V18):
    # the per-topic replay counter still orders those.
    if counter <= last_counter:
        raise Reject(f"replay: counter {counter} <= {last_counter}")
    if check_timestamp and abs(now - ts) > max_clock_skew:
        raise Reject(f"timestamp outside window: {ts} vs now {int(now)}")
    aad = AAD_TOPIC_KEY + topic.encode() + counter.to_bytes(8, "big")
    try:
        plaintext = _decrypt_impl(key, nonce, ct, aad)
    except Exception:
        raise Reject("AEAD auth failed")
    try:
        msg = json.loads(plaintext.decode())
    except (ValueError, UnicodeDecodeError):
        raise Reject("payload not valid JSON")
    if not isinstance(msg, dict):
        raise Reject("payload not an object")
    return PayloadAuth(message=msg, counter=counter)


def newest_counter(envs: list[tuple[str, bytes]]) -> int:
    """For a set of candidate envelopes on one topic, return the max counter."""
    best = -1
    for _, env in envs:
        if len(env) < 2 + 8:
            continue
        kid_len = env[1]
        off = 2 + kid_len
        if len(env) < off + 8:
            continue
        best = max(best, int.from_bytes(env[off:off + 8], "big"))
    return best


@dataclass
class PayloadAuth:
    """Result of authenticating a message: plaintext + counter used."""

    message: dict
    counter: int
