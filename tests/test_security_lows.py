"""Regression tests for the low-severity security findings.

Covers:
  * auth_jwt_verify honors `nbf` (not-before) and `exp` with clock-skew leeway.
  * epl-auth is_jwt_expired verifies the signature with `secret` (not an
    unverified decode that ignored the secret).
  * template _resolve_context blocks dunder/private attribute traversal.
  * FFI _check_allowlist does not admit a path via basename collision.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.stdlib import _resolve_context, call_stdlib

_SECRET = "s3cret"


def _mint(claims):
    def b(d):
        return (
            base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode())
            .rstrip(b"=")
            .decode()
        )

    h = b({"alg": "HS256", "typ": "JWT"})
    p = b(claims)
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return f"{h}.{p}.{sig}"


def _verify(tok):
    return call_stdlib("auth_jwt_verify", [tok, _SECRET], 0)


def test_jwt_valid_token_passes():
    now = int(time.time())
    assert _verify(_mint({"exp": now + 3600})) is not None


def test_jwt_expired_rejected():
    now = int(time.time())
    with pytest.raises(Exception):
        _verify(_mint({"exp": now - 3600}))


def test_jwt_not_before_in_future_rejected():
    now = int(time.time())
    with pytest.raises(Exception):
        _verify(_mint({"exp": now + 3600, "nbf": now + 3600}))


def test_jwt_not_before_in_past_accepted():
    now = int(time.time())
    assert _verify(_mint({"exp": now + 3600, "nbf": now - 30})) is not None


def test_epl_auth_is_jwt_expired_uses_secret():
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "epl", "official_packages", "epl-auth", "python",
    ))
    import importlib

    auth = importlib.import_module("__init__")
    tok = auth.create_jwt({"sub": "u1"}, "rightsecret", 1)
    assert auth.is_jwt_expired(tok, "rightsecret") is False
    # A wrong secret must now matter (previously ignored) -> treated as expired.
    assert auth.is_jwt_expired(tok, "wrongsecret") is True
    # Tampered token -> expired/unusable.
    assert auth.is_jwt_expired(tok[:-2] + "xx", "rightsecret") is True


class _Obj:
    pass


def test_template_resolves_legit_attribute():
    o = _Obj()
    o.name = "alice"
    assert _resolve_context("user.name", {"user": o}) == "alice"
    assert _resolve_context("a.b", {"a": {"b": 42}}) == 42


def test_template_blocks_dunder_traversal():
    o = _Obj()
    assert _resolve_context("user.__class__", {"user": o}) is None
    assert _resolve_context("user.__class__.__init__.__globals__", {"user": o}) is None


def test_ffi_allowlist_rejects_basename_collision():
    import epl.ffi as ffi

    saved = ffi._LIBRARY_ALLOWLIST
    try:
        ffi._LIBRARY_ALLOWLIST = frozenset({"libm.so"})
        # Bare allowlisted name resolves via the system loader.
        ffi._check_allowlist("libm.so")
        # A full path whose basename collides must NOT be admitted.
        with pytest.raises(PermissionError):
            ffi._check_allowlist("/tmp/evil/libm.so")
        with pytest.raises(PermissionError):
            ffi._check_allowlist("..\\evil\\libm.so")
    finally:
        ffi._LIBRARY_ALLOWLIST = saved
