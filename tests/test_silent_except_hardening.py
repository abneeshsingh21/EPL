"""Regression tests for the Phase-1 silent-except hardening batch.

Previously-silent ``except …: pass`` sites now either route through
``epl._debug_log.suppressed`` (diagnosable under EPL_DEBUG) or, for operator
misconfigurations, emit a visible warning. These tests pin the observable
behavior and guard against the broad-except pattern creeping back.
"""

import pathlib
import re

import pytest

EPL_DIR = pathlib.Path(__file__).resolve().parent.parent / 'epl'


def test_bad_env_port_warns_and_falls_back(monkeypatch, caplog):
    from epl import deploy

    monkeypatch.setenv('EPL_WEB_PORT', 'not-a-number')
    monkeypatch.delenv('PORT', raising=False)
    with caplog.at_level('WARNING', logger='epl.deploy'):
        host, port, workers = deploy._resolve_env_bind('0.0.0.0', 8000, 4)
    assert port == 8000  # fell back to the default
    assert any('EPL_WEB_PORT' in r.message for r in caplog.records)


def test_bad_env_workers_warns_and_falls_back(monkeypatch, caplog):
    from epl import deploy

    monkeypatch.delenv('EPL_WEB_PORT', raising=False)
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.setenv('EPL_WEB_WORKERS', 'lots')
    with caplog.at_level('WARNING', logger='epl.deploy'):
        _, _, workers = deploy._resolve_env_bind('0.0.0.0', 8000, 4)
    assert workers == 4
    assert any('EPL_WEB_WORKERS' in r.message for r in caplog.records)


def test_valid_env_port_is_applied(monkeypatch):
    from epl import deploy

    monkeypatch.setenv('EPL_WEB_PORT', '9090')
    monkeypatch.setenv('EPL_WEB_WORKERS', '2')
    _, port, workers = deploy._resolve_env_bind('0.0.0.0', 8000, 4)
    assert port == 9090
    assert workers == 2


def test_corrupt_ai_config_warns_not_silent(monkeypatch, tmp_path, capsys):
    from epl import ai

    bad = tmp_path / 'ai_config.json'
    bad.write_text('{ this is not valid json', encoding='utf-8')
    monkeypatch.setattr(ai, '_get_config_path', lambda: str(bad))
    monkeypatch.setattr(ai, '_CONFIG_LOADED', False, raising=False)
    monkeypatch.setattr(ai, '_try_keyring', lambda: None, raising=False)

    ai._load_config(force=True)  # must not raise
    err = capsys.readouterr().err
    assert 'corrupt AI config' in err


def test_missing_ai_config_is_silent(monkeypatch, tmp_path, capsys):
    from epl import ai

    missing = tmp_path / 'does_not_exist.json'
    monkeypatch.setattr(ai, '_get_config_path', lambda: str(missing))
    monkeypatch.setattr(ai, '_CONFIG_LOADED', False, raising=False)
    monkeypatch.setattr(ai, '_try_keyring', lambda: None, raising=False)

    ai._load_config(force=True)
    assert 'corrupt' not in capsys.readouterr().err


def test_suppressed_routes_to_stderr_under_debug(monkeypatch, tmp_path, capsys):
    from epl import update_checker

    corrupt = tmp_path / 'cache.json'
    corrupt.write_text('not json', encoding='utf-8')
    monkeypatch.setattr(update_checker, '_get_cache_path', lambda: str(corrupt))
    monkeypatch.setenv('EPL_DEBUG', '1')

    assert update_checker._read_cache() is None  # behavior preserved
    assert 'update_checker:57' in capsys.readouterr().err


def test_suppressed_silent_without_debug(monkeypatch, tmp_path, capsys):
    from epl import update_checker

    corrupt = tmp_path / 'cache.json'
    corrupt.write_text('not json', encoding='utf-8')
    monkeypatch.setattr(update_checker, '_get_cache_path', lambda: str(corrupt))
    monkeypatch.delenv('EPL_DEBUG', raising=False)

    assert update_checker._read_cache() is None
    assert capsys.readouterr().err == ''


def test_corrupt_registry_falls_back_and_is_diagnosable(monkeypatch, tmp_path, capsys):
    from epl import registry

    corrupt = tmp_path / 'reg.json'
    corrupt.write_text('{bad', encoding='utf-8')
    monkeypatch.setenv('EPL_DEBUG', '1')
    store = registry.RegistryCache(str(corrupt)) if hasattr(registry, 'RegistryCache') else None
    if store is None:
        pytest.skip('RegistryCache not exposed')
    assert isinstance(store._data, dict)
    assert 'registry:68' in capsys.readouterr().err


BROAD = re.compile(r'except\s+Exception\s*:\s*\n\s*pass\b')


def test_no_new_broad_except_pass():
    """Guard: broad ``except Exception: pass`` count must not grow past baseline."""
    count = 0
    for f in EPL_DIR.rglob('*.py'):
        count += len(BROAD.findall(f.read_text(encoding='utf-8', errors='replace')))
    assert count == 0, f'{count} broad `except Exception: pass` block(s) reintroduced'
