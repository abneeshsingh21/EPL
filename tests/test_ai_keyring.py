"""Tests for epl/ai.py keyring + JSON-fallback secret storage (v9.2.0)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Ensure we import the in-tree package, not an installed copy.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ai  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Redirect ai._CONFIG_PATH to a temp file and reset module globals.

    The fixture runs for every test so state never leaks across cases.
    """
    cfg_path = tmp_path / 'ai_config.json'
    monkeypatch.setattr(ai, '_CONFIG_PATH', str(cfg_path))
    monkeypatch.setattr(ai, '_CONFIG_LOADED', False)
    monkeypatch.setattr(ai, 'CLOUD_PROVIDER', None)
    monkeypatch.setattr(ai, 'CLOUD_API_KEY', None)
    monkeypatch.setattr(ai, 'CLOUD_MODEL', None)
    yield cfg_path


class _FakeKeyring:
    """Minimal in-memory keyring substitute the tests can drive."""

    def __init__(self, working=True):
        self.store: dict[tuple[str, str], str] = {}
        self.working = working

    # Public API matching the `keyring` module surface we use.
    def get_keyring(self):
        backend = mock.Mock()
        backend.__class__.__name__ = 'TestBackend' if self.working else 'FailBackend'
        return backend

    def get_password(self, service, user):
        return self.store.get((service, user))

    def set_password(self, service, user, value):
        self.store[(service, user)] = value

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


def test_keyring_unavailable_falls_back_to_json(monkeypatch):
    """When the keyring import fails, the key persists in JSON."""
    monkeypatch.setattr(ai, '_try_keyring', lambda: None)

    ai.configure_cloud('groq', 'sk-test-12345', model='llama-3.1-8b-instant')

    saved = json.loads(Path(ai._CONFIG_PATH).read_text())
    assert saved['provider'] == 'groq'
    assert saved['model'] == 'llama-3.1-8b-instant'
    assert saved['api_key'] == 'sk-test-12345'  # fallback path is documented


def test_keyring_available_keeps_key_out_of_json(monkeypatch):
    fake = _FakeKeyring(working=True)
    monkeypatch.setattr(ai, '_try_keyring', lambda: fake)

    ai.configure_cloud('gemini', 'gem-secret-xyz', model='gemini-2.0-flash')

    saved = json.loads(Path(ai._CONFIG_PATH).read_text())
    assert saved == {'provider': 'gemini', 'model': 'gemini-2.0-flash'}
    assert 'api_key' not in saved
    assert fake.store[('epl-lang', 'cloud_api_key')] == 'gem-secret-xyz'


def test_legacy_plaintext_key_migrates_to_keyring(monkeypatch):
    """A pre-9.2.0 config with api_key in JSON must be migrated, not re-read."""
    Path(ai._CONFIG_PATH).write_text(
        json.dumps(
            {
                'provider': 'groq',
                'api_key': 'legacy-plaintext-key',
                'model': None,
            }
        )
    )
    fake = _FakeKeyring(working=True)
    monkeypatch.setattr(ai, '_try_keyring', lambda: fake)

    ai._load_config(force=True)

    assert ai.CLOUD_API_KEY == 'legacy-plaintext-key'
    # Keyring now holds the secret.
    assert fake.store[('epl-lang', 'cloud_api_key')] == 'legacy-plaintext-key'
    # JSON has been rewritten with the key removed.
    on_disk = json.loads(Path(ai._CONFIG_PATH).read_text())
    assert 'api_key' not in on_disk
    assert on_disk['provider'] == 'groq'


def test_clear_cloud_wipes_keyring_entry(monkeypatch):
    fake = _FakeKeyring(working=True)
    monkeypatch.setattr(ai, '_try_keyring', lambda: fake)

    ai.configure_cloud('groq', 'to-be-cleared')
    assert ('epl-lang', 'cloud_api_key') in fake.store

    ai.clear_cloud()

    assert ai.CLOUD_API_KEY is None
    assert ('epl-lang', 'cloud_api_key') not in fake.store
    assert not Path(ai._CONFIG_PATH).exists()


def test_keyring_read_failure_falls_back_to_legacy(monkeypatch):
    """If the keyring lookup raises mid-call, we shouldn't crash."""
    fake = _FakeKeyring(working=True)

    def boom(service, user):
        raise RuntimeError('keyring backend locked')

    monkeypatch.setattr(fake, 'get_password', boom)
    monkeypatch.setattr(ai, '_try_keyring', lambda: fake)

    Path(ai._CONFIG_PATH).write_text(
        json.dumps(
            {
                'provider': 'groq',
                'api_key': 'fallback-key',
            }
        )
    )

    ai._load_config(force=True)
    # Lookup failed, so we fall back to the legacy plaintext value.
    assert ai.CLOUD_API_KEY == 'fallback-key'


def test_mask_key_redacts_short_keys():
    assert ai._mask_key('abc') == '***'
    assert ai._mask_key('abcdefghij12') == '*' * 12
    assert ai._mask_key('abcdefghijklmnop') == 'abcd...mnop'
    assert ai._mask_key('') == ''
    assert ai._mask_key(None) == ''
