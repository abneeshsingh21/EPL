"""Tests for html_gen footer + font configuration (v9.2.0)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast  # noqa: E402
from epl import html_gen  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_config():
    html_gen.reset_config()
    yield
    html_gen.reset_config()


def _page(title='Test'):
    return ast.PageDef(title, [ast.HtmlElement('heading', 'Hi', {}, line=1)])


def test_default_omits_footer():
    out = html_gen.generate_html(_page())
    assert 'Powered by EPL' not in out
    assert '<footer>' not in out


def test_default_does_not_load_google_fonts():
    """Privacy + offline + perf: no third-party CDN unless opted in."""
    out = html_gen.generate_html(_page())
    assert 'fonts.googleapis.com' not in out
    assert 'fonts.gstatic.com' not in out


def test_custom_footer_renders():
    html_gen.configure_page(footer='© 2026 ACME Corp')
    out = html_gen.generate_html(_page())
    assert '<footer>© 2026 ACME Corp</footer>' in out


def test_footer_is_html_escaped():
    """Footer text is user-controlled; must not allow XSS injection."""
    html_gen.configure_page(footer='<script>alert(1)</script>')
    out = html_gen.generate_html(_page())
    assert '<script>alert' not in out
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in out


def test_empty_string_footer_omits_tag():
    html_gen.configure_page(footer='')
    out = html_gen.generate_html(_page())
    assert '<footer>' not in out


def test_fonts_cdn_loads_google_fonts():
    html_gen.configure_page(fonts='cdn')
    out = html_gen.generate_html(_page())
    assert 'fonts.googleapis.com' in out
    assert 'family=Inter' in out


def test_invalid_fonts_value_raises():
    with pytest.raises(ValueError, match='must be'):
        html_gen.configure_page(fonts='material')


def test_reset_config_restores_defaults():
    html_gen.configure_page(footer='temp', fonts='cdn')
    html_gen.reset_config()
    out = html_gen.generate_html(_page())
    assert '<footer>' not in out
    assert 'fonts.googleapis.com' not in out
