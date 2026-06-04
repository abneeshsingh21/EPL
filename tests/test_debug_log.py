"""Tests for epl/_debug_log.py (v9.2.0)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import _debug_log


def test_suppressed_is_silent_without_env_var(capsys, monkeypatch):
    monkeypatch.delenv('EPL_DEBUG', raising=False)
    try:
        raise ValueError('hidden')
    except Exception:
        _debug_log.suppressed('test:1')
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out == ''


@pytest.mark.parametrize('truthy', ['1', 'true', 'TRUE', 'yes', 'on'])
def test_suppressed_logs_when_env_var_truthy(capsys, monkeypatch, truthy):
    monkeypatch.setenv('EPL_DEBUG', truthy)
    try:
        raise RuntimeError('boom')
    except Exception:
        _debug_log.suppressed('mysite:42')
    captured = capsys.readouterr()
    assert 'mysite:42' in captured.err
    assert 'RuntimeError' in captured.err
    assert 'boom' in captured.err


@pytest.mark.parametrize('falsy', ['0', 'false', 'no', 'off', ''])
def test_suppressed_silent_for_falsy_values(capsys, monkeypatch, falsy):
    monkeypatch.setenv('EPL_DEBUG', falsy)
    try:
        raise ValueError('hidden')
    except Exception:
        _debug_log.suppressed('test:1')
    captured = capsys.readouterr()
    assert captured.err == ''


def test_suppressed_outside_except_is_safe(capsys, monkeypatch):
    monkeypatch.setenv('EPL_DEBUG', '1')
    # Calling with no active exception should not raise.
    _debug_log.suppressed('no-context:1')
    captured = capsys.readouterr()
    # Either silent or a single "no active exception" note — must not raise.
    assert 'Traceback' not in captured.err
