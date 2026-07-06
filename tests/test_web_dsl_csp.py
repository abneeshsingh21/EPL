"""Phase 5 CSP tests: opt-in strict Content-Security-Policy with a per-response
script nonce. Every generated <script> is authorized via `script-src 'self'
'nonce-…'`; off by default so output stays byte-identical.

Mirrors the parse -> generate_html -> assert pattern of test_web_dsl_css.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import epl.html_gen as hg
from epl import ast_nodes as ast
from epl.html_gen import build_csp_header, configure_page, generate_html, new_nonce, reset_config
from epl.lexer import Lexer
from epl.parser import Parser


@pytest.fixture(autouse=True)
def _reset():
    """Keep CSP config from leaking between tests."""
    reset_config()
    yield
    reset_config()


_SRC = (
    'Page "D"\n'
    '    Div class "card"\n'
    '        On click\n'
    '            Add class "x"\n'
    '        End\n'
    '        Text "hi"\n'
    '    End\n'
    'End\n'
)


def _page():
    program = Parser(Lexer(_SRC).tokenize()).parse()
    return next(s for s in program.statements if isinstance(s, ast.PageDef))


# ── new_nonce / config ───────────────────────────────────────────────────────


def test_new_nonce_none_when_off():
    assert new_nonce() is None


def test_new_nonce_unique_when_on():
    configure_page(csp=True)
    a, b = new_nonce(), new_nonce()
    assert a and b and a != b


def test_reset_disables_csp():
    configure_page(csp=True)
    reset_config()
    assert new_nonce() is None


# ── build_csp_header ─────────────────────────────────────────────────────────


def test_csp_header_without_nonce_allows_inline_scripts():
    # CSP mode off (default): script-src must include 'unsafe-inline' so the
    # generator's own inline scripts (which are only nonced when CSP is on) are
    # not blocked, while the other protective directives stay in place.
    header = build_csp_header(None)
    assert header == (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'"
    )


def test_csp_header_with_nonce_is_strict():
    header = build_csp_header('ABC123')
    assert "script-src 'self' 'nonce-ABC123'" in header
    # On-mode script-src must NOT fall back to 'unsafe-inline'.
    script_src = header.split('script-src ')[1].split(';')[0]
    assert "'unsafe-inline'" not in script_src
    assert "object-src 'none'" in header
    assert "base-uri 'self'" in header


# ── generate_html nonce tagging ──────────────────────────────────────────────


def test_nonce_tags_every_script():
    html = generate_html(_page(), nonce='FIXED123')
    tags = re.findall(r'<script[^>]*>', html)
    assert tags, 'expected at least the native-animation + event scripts'
    assert all('nonce="FIXED123"' in t for t in tags)


def test_nonce_not_double_added():
    html = generate_html(_page(), nonce='FIXED123')
    # No tag should carry two nonce attributes.
    assert '<script nonce="FIXED123" nonce=' not in html


def test_no_nonce_no_attr():
    html = generate_html(_page())
    assert 'nonce=' not in html


def test_off_is_byte_identical_to_no_nonce():
    # CSP-off output must equal explicit nonce=None output (no behavior change).
    assert generate_html(_page()) == generate_html(_page(), nonce=None)


def test_nonce_value_is_attribute_safe():
    # A real nonce contains only URL-safe base64 chars (no quotes/spaces/<>).
    configure_page(csp=True)
    nonce = new_nonce()
    assert re.fullmatch(r'[A-Za-z0-9_-]+', nonce)


# ── canvas/CDN scripts also get the nonce ────────────────────────────────────


def test_external_script_also_nonced():
    # A <script src="..."> tag (e.g. a CDN) is authorized by the nonce too.
    html = '<html><head><script src="https://cdn.example/x.js"></script></head></html>'
    out = hg._add_nonce_to_scripts(html, 'N1')
    assert '<script nonce="N1" src="https://cdn.example/x.js">' in out
