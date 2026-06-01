"""Tests for the v9.3.0 Phase 4 theme system."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.html_gen import configure_page, generate_html, reset_config


@pytest.fixture(autouse=True)
def _reset():
    reset_config()
    yield
    reset_config()


def _page():
    return ast.PageDef('T', [ast.HtmlElement('heading', 'Hi', line=1)], line=1)


def test_default_theme_is_auto():
    html = generate_html(_page())
    assert 'content="light dark"' in html
    assert 'prefers-color-scheme: dark' in html
    assert '--bg:' in html
    assert '--fg:' in html


def test_dark_theme_emits_single_palette():
    configure_page(theme='dark')
    html = generate_html(_page())
    assert 'content="dark"' in html
    assert 'prefers-color-scheme' not in html
    assert '#0f172a' in html  # dark --bg


def test_light_theme_emits_single_palette():
    configure_page(theme='light')
    html = generate_html(_page())
    assert 'content="light"' in html
    assert 'prefers-color-scheme' not in html
    assert '#ffffff' in html  # light --bg


def test_auto_emits_both_palettes():
    configure_page(theme='auto')
    html = generate_html(_page())
    assert '#ffffff' in html  # light default
    assert '#0f172a' in html  # dark override inside media query


def test_invalid_theme_raises():
    with pytest.raises(ValueError, match='theme must be'):
        configure_page(theme='neon')


def test_all_palette_tokens_present():
    configure_page(theme='dark')
    html = generate_html(_page())
    for token in ('--bg', '--fg', '--muted', '--accent', '--surface', '--border', '--danger'):
        assert f'{token}:' in html, f'{token} missing from emitted CSS'


def test_reset_returns_to_auto():
    configure_page(theme='dark')
    reset_config()
    html = generate_html(_page())
    assert 'content="light dark"' in html
