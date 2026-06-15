"""Phase 1 native web-DSL tests: nested elements, inline styles, safe
attributes, and Link/Button attribute suffixes.

These cover the foundation slice that lets EPL pages express structure and
styling natively instead of falling back to the `Script`/`Raw HTML` escape
hatch. See the parser changes in `_parse_element_or_statement`,
`_parse_styled_element`, and `_collect_inline_attrs`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl.errors import ParserError
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser


def _render_page(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return generate_html(program.statements[0])


# ── Bug fix A: nested elements inside Div/Section/etc. ───────────────────────


def test_list_nests_inside_div():
    html = _render_page('Page "D"\n    Div class "wrap"\n        List ["one", "two"]\n    End\nEnd')
    assert '<ul>' in html
    assert '<li>one</li>' in html
    assert '<li>two</li>' in html


def test_raw_html_nests_inside_div():
    html = _render_page(
        'Page "D"\n    Div class "w"\n        Raw HTML "<table><tr><td>c</td></tr></table>".\n'
        '    End\nEnd'
    )
    assert '<table><tr><td>c</td></tr></table>' in html


def test_structural_elements_nest_deeply():
    html = _render_page(
        'Page "D"\n    Section class "s"\n        Div class "inner"\n'
        '            Span class "leaf"\n                Text "deep"\n'
        '            End\n        End\n    End\nEnd'
    )
    assert '<section class="s">' in html
    assert '<div class="inner">' in html
    assert '<span class="leaf">' in html
    assert 'deep' in html


def test_script_nests_inside_div():
    html = _render_page(
        'Page "D"\n    Div class "w"\n        Script\n        console.log("hi");\n'
        '        End\n    End\nEnd'
    )
    # Script content is hoisted into the page <script> section, not inline.
    assert 'console.log("hi");' in html


# ── Feature B: inline style attribute ────────────────────────────────────────


def test_inline_style_renders():
    html = _render_page(
        'Page "D"\n    Div style "color: red; padding: 10px"\n        Text "x"\n    End\nEnd'
    )
    assert 'style="color: red; padding: 10px"' in html


def test_with_style_is_still_a_class_reference():
    # `with style "card"` must remain a class reference, not an inline style.
    html = _render_page('Page "D"\n    Div with style "card"\n        Text "x"\n    End\nEnd')
    assert 'class="card"' in html
    assert 'style="card"' not in html


def test_inline_style_and_class_coexist():
    html = _render_page(
        'Page "D"\n    Div class "box" style "gap: 4px"\n        Text "x"\n    End\nEnd'
    )
    assert 'class="box"' in html
    assert 'style="gap: 4px"' in html


# ── Feature C: arbitrary safe attributes ─────────────────────────────────────


def test_safe_attributes_render():
    html = _render_page(
        'Page "D"\n    Div role "region" aria-label "Hero" data-index "3" title "t"\n'
        '        Text "x"\n    End\nEnd'
    )
    assert 'role="region"' in html
    assert 'aria-label="Hero"' in html
    assert 'data-index="3"' in html
    assert 'title="t"' in html


def test_attribute_values_are_escaped():
    html = _render_page(
        'Page "D"\n    Div data-x "<script>alert(1)</script>"\n        Text "x"\n    End\nEnd'
    )
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_event_handler_attribute_is_rejected():
    with pytest.raises(ParserError, match='event handler'):
        _render_page('Page "D"\n    Div onclick "alert(1)"\n        Text "x"\n    End\nEnd')


def test_unknown_attribute_is_rejected():
    with pytest.raises(ParserError, match='Unsupported attribute'):
        _render_page('Page "D"\n    Div bogusattr "v"\n        Text "x"\n    End\nEnd')


# ── Feature D: Link / Button attribute suffixes ──────────────────────────────


def test_link_accepts_class_and_id():
    html = _render_page('Page "D"\n    Link "Docs" to "/docs" class "btn primary" id "dl"\nEnd')
    assert '<a href="/docs"' in html
    assert 'class="btn primary"' in html
    assert 'id="dl"' in html


def test_link_accepts_target_rel_aria():
    html = _render_page(
        'Page "D"\n    Link "X" to "/x" target "_blank" rel "noopener" aria-label "ext"\nEnd'
    )
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert 'aria-label="ext"' in html


def test_link_inline_style():
    html = _render_page('Page "D"\n    Link "X" to "/x" style "color: blue"\nEnd')
    assert 'style="color: blue"' in html


def test_link_href_still_sanitized():
    html = _render_page('Page "D"\n    Link "bad" to "javascript:alert(1)" class "c"\nEnd')
    assert 'javascript:alert(1)' not in html
    assert 'class="c"' in html


def test_button_accepts_class():
    html = _render_page('Page "D"\n    Button "Save" class "btn"\nEnd')
    assert '<button class="btn">' in html


def test_link_event_handler_rejected():
    with pytest.raises(ParserError, match='event handler'):
        _render_page('Page "D"\n    Link "x" to "/x" onmouseover "steal()"\nEnd')
