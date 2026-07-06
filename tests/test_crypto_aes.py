"""Regression tests for the builtin aes_encrypt/aes_decrypt (H3).

The builtin now uses authenticated AES-GCM with a PBKDF2-salted key. These
tests lock in the security properties: round-trip works, tampering and wrong
keys are rejected (no padding oracle), ciphertexts are randomized per call, and
the insecure legacy AES-CBC format is refused.
"""

import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.stdlib import call_stdlib


def _enc(pt, key):
    return call_stdlib('aes_encrypt', [pt, key], 0)


def _dec(ct, key):
    return call_stdlib('aes_decrypt', [ct, key], 0)


def test_roundtrip():
    ct = _enc('secret message', 'passphrase-1')
    assert _dec(ct, 'passphrase-1') == 'secret message'


def test_wrong_key_rejected():
    ct = _enc('data', 'right-key')
    with pytest.raises(Exception) as e:
        _dec(ct, 'wrong-key')
    assert 'authentication failed' in str(e.value)


def test_tamper_detected():
    ct = _enc('important', 'k')
    raw = bytearray(base64.b64decode(ct))
    raw[35] ^= 0x01  # flip a bit in the ciphertext body
    tampered = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(Exception) as e:
        _dec(tampered, 'k')
    assert 'authentication failed' in str(e.value)


def test_ciphertext_is_randomized():
    # Fresh salt + nonce each call -> identical plaintext/key yields distinct ct.
    assert _enc('same', 'same-key') != _enc('same', 'same-key')


def test_legacy_cbc_format_rejected():
    # No magic prefix == old insecure format; must be refused, not decrypted.
    legacy = base64.b64encode(b'\x00' * 48).decode()
    with pytest.raises(Exception) as e:
        _dec(legacy, 'k')
    assert 'unsupported' in str(e.value).lower()
