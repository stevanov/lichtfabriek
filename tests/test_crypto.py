"""Tests for shared payload crypto (V9, V12, V13)."""

import time

import pytest

from shared import crypto


def test_seal_open_roundtrip():
    secret = crypto.new_key()
    env = crypto.seal("lichtfabriek/pattern/set", {"a": 1}, secret, "k1", counter=1)
    auth = crypto.open_envelope(
        "lichtfabriek/pattern/set", env, secret, last_counter=0
    )
    assert auth.message == {"a": 1}
    assert auth.counter == 1


def test_wrong_topic_rejected():
    secret = crypto.new_key()
    env = crypto.seal("lichtfabriek/pattern/set", {"a": 1}, secret, "k1", counter=1)
    with pytest.raises(crypto.Reject):
        crypto.open_envelope(
            "lichtfabriek/sign/set", env, secret, last_counter=0
        )


def test_wrong_key_rejected():
    secret = crypto.new_key()
    other = crypto.new_key()
    env = crypto.seal("lichtfabriek/pattern/set", {"a": 1}, secret, "k1", counter=1)
    with pytest.raises(crypto.Reject):
        crypto.open_envelope(
            "lichtfabriek/pattern/set", env, other, last_counter=0
        )


def test_replay_rejected():
    secret = crypto.new_key()
    env = crypto.seal("lichtfabriek/pattern/set", {"a": 1}, secret, "k1", counter=5)
    # first accept
    crypto.open_envelope("lichtfabriek/pattern/set", env, secret, last_counter=4)
    # replay: same envelope, last_counter now 5 -> rejected (V13)
    with pytest.raises(crypto.Reject, match="replay"):
        crypto.open_envelope("lichtfabriek/pattern/set", env, secret, last_counter=5)


def test_clock_window_rejected():
    secret = crypto.new_key()
    env = crypto.seal(
        "lichtfabriek/pattern/set", {"a": 1}, secret, "k1",
        counter=1, now=time.time() - 10000,
    )
    with pytest.raises(crypto.Reject, match="window"):
        crypto.open_envelope("lichtfabriek/pattern/set", env, secret, last_counter=0)


def test_key_rotation():
    key1 = crypto.new_key()
    key2 = crypto.new_key()
    env = crypto.seal("lichtfabriek/pattern/set", {"a": 1}, key2, "k2", counter=1)
    auth = crypto.open_envelope(
        "lichtfabriek/pattern/set", env, key1,
        keys={"k1": key1, "k2": key2}, last_counter=0,
    )
    assert auth.message == {"a": 1}
    # old key removed from rotation -> rejected
    with pytest.raises(crypto.Reject, match="unknown key_id"):
        crypto.open_envelope(
            "lichtfabriek/pattern/set", env, key1,
            keys={"k1": key1}, last_counter=0,
        )


def test_tampered_ciphertext_rejected():
    secret = crypto.new_key()
    env = bytearray(crypto.seal(
        "lichtfabriek/pattern/set", {"a": 1}, secret, "k1", counter=1))
    env[-1] ^= 0xFF  # flip a ciphertext bit
    with pytest.raises(crypto.Reject):
        crypto.open_envelope(
            "lichtfabriek/pattern/set", bytes(env), secret, last_counter=0
        )
