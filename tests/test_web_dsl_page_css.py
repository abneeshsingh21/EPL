"""Phase 6 per-page CSS tests: a `Stylesheet`/`Style` block nested inside a
`Page` renders ONLY on that route (after any site-wide CSS), so per-route CSS
no longer needs a Script escape hatch.

Mirrors the parse -> generate_html -> assert pattern of test_web_dsl_css.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser


def _pages(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return [s for s in program.statements if isinstance(s, ast.PageDef)]


_TWO = """Page "A"
    Stylesheet
        .a-only { color: red }
    End
    Style "acard"
        Background "#aaa"
    End
    Div class "acard"
        Text "A"
    End
End
Page "B"
    Div class "bcard"
        Text "B"
    End
End
"""


# ── Parsing ──────────────────────────────────────────────────────────────────


def test_page_collects_scoped_stylesheet_and_style():
    a, b = _pages(_TWO)
    assert len(a.stylesheets) == 1
    assert len(a.styles) == 1
    assert b.stylesheets == [] and b.styles == []
    # The Div is a real element, not swallowed by the CSS blocks.
    assert any(isinstance(e, ast.StyledElement) for e in a.elements)


# ── Rendering / isolation ────────────────────────────────────────────────────


def test_scoped_stylesheet_renders_on_its_page():
    a, _ = _pages(_TWO)
    html = generate_html(a)
    assert '.a-only { color: red }' in html
    assert '.acard {' in html  # page-scoped Style block too


def test_scoped_css_absent_from_other_page():
    _, b = _pages(_TWO)
    html = generate_html(b)
    assert '.a-only' not in html
    assert '.acard {' not in html


def test_sitewide_stylesheet_still_applies():
    _, b = _pages(_TWO)
    site = ast.RawStylesheet('.site { color: blue }')
    html = generate_html(b, stylesheets=[site])
    assert '.site { color: blue }' in html


def test_cascade_order_sitewide_before_page():
    a, _ = _pages(_TWO)
    site = ast.RawStylesheet('.site { color: blue }')
    html = generate_html(a, stylesheets=[site])
    # Site-wide CSS must precede page-scoped CSS so the page wins the cascade.
    assert html.index('.site') < html.index('.a-only')


def test_sitewide_and_page_both_present():
    a, _ = _pages(_TWO)
    site_style = ast.StyleDef('sitecard', [ast.StyleProperty('color', 'green', 0)])
    html = generate_html(a, styles=[site_style])
    assert '.sitecard {' in html  # site-wide Style
    assert '.acard {' in html  # page-scoped Style


# ── Regression ───────────────────────────────────────────────────────────────


def test_page_without_scoped_css_unchanged():
    (b,) = _pages('Page "B"\n    Div class "x"\n        Text "y"\n    End\nEnd\n')
    html = generate_html(b)
    assert b.stylesheets == [] and b.styles == []
    assert '<div class="x">' in html
