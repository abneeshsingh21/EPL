"""Phase 2 native CSS tests: pseudo-states, descendant selectors, media
queries, and the first-class `Stylesheet` raw-CSS block.

Mirrors the parse -> generate_html -> assert pattern of test_raw_html.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser


def _render(src):
    """Parse a program, render its PageDef with collected styles/stylesheets."""
    program = Parser(Lexer(src).tokenize()).parse()
    page = next(s for s in program.statements if isinstance(s, ast.PageDef))
    styles = [s for s in program.statements if isinstance(s, ast.StyleDef)]
    sheets = [s for s in program.statements if isinstance(s, ast.RawStylesheet)]
    return generate_html(page, styles=styles, stylesheets=sheets)


_PAGE = 'Page "D"\n    Div class "card"\n        Text "x"\n    End\nEnd\n'


def _style(body):
    return _PAGE + 'Style "card"\n' + body + 'End\n'


# ── Pseudo-states ────────────────────────────────────────────────────────────


def test_on_hover_emits_pseudo_class():
    html = _render(_style('    On hover\n        Background "#eee"\n    End\n'))
    assert '.card:hover {' in html
    assert 'background: #eee;' in html


def test_on_focus_visible_hyphenated_pseudo():
    html = _render(_style('    On focus-visible\n        Outline "2px solid"\n    End\n'))
    assert '.card:focus-visible {' in html


def test_on_before_emits_pseudo_element():
    html = _render(_style('    On before\n        Content "x"\n    End\n'))
    assert '.card::before {' in html


def test_on_after_emits_pseudo_element():
    html = _render(_style('    On after\n        Content "y"\n    End\n'))
    assert '.card::after {' in html


# ── Media queries ────────────────────────────────────────────────────────────


def test_named_breakpoints():
    html = _render(
        _style(
            '    On mobile\n        Padding "12px"\n    End\n'
            '    On tablet\n        Padding "16px"\n    End\n'
            '    On desktop\n        Padding "24px"\n    End\n'
        )
    )
    assert '@media (max-width: 640px) {' in html
    assert '@media (max-width: 1024px) {' in html
    assert '@media (min-width: 1025px) {' in html


def test_explicit_breakpoints_below_above():
    html = _render(
        _style(
            '    On screen below "900px"\n        Gap "8px"\n    End\n'
            '    On screen above "1200px"\n        Gap "24px"\n    End\n'
        )
    )
    assert '@media (max-width: 900px) {' in html
    assert '@media (min-width: 1200px) {' in html


def test_invalid_media_width_rejected():
    with pytest.raises(Exception, match='[Ww]idth'):
        _render(_style('    On screen below "wide"\n        Gap "8px"\n    End\n'))


# ── Descendant selectors ─────────────────────────────────────────────────────


def test_select_descendant():
    html = _render(_style('    Select "a"\n        Color "#007DF3"\n    End\n'))
    assert '.card a {' in html
    assert 'color: #007DF3;' in html


def test_select_strips_braces():
    # A malicious selector cannot break out of its rule block: `{` and `}` are
    # stripped from the selector fragment before it is emitted.
    html = _render(_style('    Select "a} body {color:red"\n        Color "red"\n    End\n'))
    # The selector keeps letters/spaces but loses the braces.
    assert '.card a body color:red {' in html
    # And the only declaration block braces come from our generated rule.
    selector_line = next(line for line in html.splitlines() if line.startswith('.card a'))
    assert '}' not in selector_line


# ── Raw Stylesheet block ─────────────────────────────────────────────────────


def test_stylesheet_emits_verbatim_css():
    src = _PAGE + 'Stylesheet\n.hero::after { content: ""; inset: 0 }\nEnd\n'
    html = _render(src)
    assert '.hero::after { content: ""; inset: 0 }' in html


def test_stylesheet_supports_at_rules():
    src = _PAGE + 'Stylesheet\n@supports (gap: 1px) { .nav { gap: 8px } }\nEnd\n'
    html = _render(src)
    assert '@supports (gap: 1px)' in html


def test_stylesheet_breakout_rejected():
    src = _PAGE + 'Stylesheet\n.x{} </style><script>alert(1)</script>\nEnd\n'
    with pytest.raises(ValueError, match='style'):
        _render(src)


# ── Regression: existing flat Style still works ─────────────────────────────


def test_flat_style_still_emits_base_rule():
    html = _render(_style('    Background "#fff"\n    Padding "20px"\n'))
    assert '.card {' in html
    assert 'background: #fff;' in html
    assert 'padding: 20px;' in html


def test_base_and_nested_coexist():
    html = _render(
        _style('    Background "#fff"\n    On hover\n        Background "#eee"\n    End\n')
    )
    assert '.card {' in html
    assert '.card:hover {' in html
