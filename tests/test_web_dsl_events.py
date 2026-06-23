"""Phase 4 native interactivity tests: element-level event handlers compiled to
CSP-safe generated JS (addEventListener / IntersectionObserver), never inline
on* attributes.

Mirrors the parse -> generate_html -> assert pattern of test_web_dsl_css.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl import ast_nodes as ast
from epl.errors import ParserError
from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser


def _render(body):
    """Render a Page whose body is `body` (lines already indented)."""
    src = 'Page "D"\n' + body + 'End\n'
    program = Parser(Lexer(src).tokenize()).parse()
    page = next(s for s in program.statements if isinstance(s, ast.PageDef))
    return generate_html(page)


def _div(inner):
    return '    Div class "card"\n' + inner + '    End\n'


# ── Nested On blocks ─────────────────────────────────────────────────────────


def test_on_click_toggle_class():
    html = _render(
        _div('        On click\n            Toggle class "open" on "#nav"\n        End\n')
    )
    assert 'data-evt="1"' in html
    assert "addEventListener('click'" in html
    assert "document.querySelector('#nav')||el" in html
    assert ".classList.toggle('open')" in html


def test_on_click_add_and_remove():
    html = _render(
        _div(
            '        On click\n            Add class "a"\n            Remove class "b"\n        End\n'
        )
    )
    assert ".classList.add('a')" in html
    assert ".classList.remove('b')" in html


def test_on_hover_uses_mouseenter():
    html = _render(_div('        On hover\n            Add class "lifted"\n        End\n'))
    assert "addEventListener('mouseenter'" in html
    assert ".classList.add('lifted')" in html


def test_on_reveal_uses_intersection_observer():
    html = _render(_div('        On reveal\n            Add class "visible"\n        End\n'))
    assert 'IntersectionObserver' in html
    assert '__ro.observe(el)' in html
    assert "el.classList.add('visible')" in html


def test_navigate_action():
    html = _render(_div('        On click\n            Navigate to "/docs"\n        End\n'))
    assert "window.location.href='/docs'" in html


def test_scroll_action():
    html = _render(_div('        On click\n            Scroll to "#top"\n        End\n'))
    assert "document.querySelector('#top')" in html
    assert "scrollIntoView({behavior:'smooth'})" in html


def test_run_bridge_guarded():
    html = _render(_div('        On click\n            Run "trackClick"\n        End\n'))
    assert "typeof window.trackClick==='function'" in html
    assert 'window.trackClick(el)' in html


def test_multi_action_block():
    html = _render(
        _div(
            '        On click\n'
            '            Toggle class "open" on "#nav"\n'
            '            Run "track"\n'
            '            Navigate to "/x"\n'
            '        End\n'
        )
    )
    assert ".classList.toggle('open')" in html
    assert 'window.track(el)' in html
    assert "window.location.href='/x'" in html


def test_reveal_observer_defined_once():
    html = _render(
        _div('        On reveal\n            Add class "a"\n        End\n')
        + _div('        On reveal\n            Add class "b"\n        End\n')
    )
    # A single shared events observer, even with multiple `On reveal` handlers.
    # (Core no longer ships a separate always-on pull-up observer.)
    assert html.count('new IntersectionObserver') == 1


# ── Inline sugar ─────────────────────────────────────────────────────────────


def test_inline_button_toggle():
    html = _render('    Button "Menu" on click toggles "open" on "#nav"\n')
    assert 'data-evt="1"' in html
    assert "addEventListener('click'" in html
    assert ".classList.toggle('open')" in html


def test_inline_link_scroll():
    html = _render('    Link "Top" to "#top" on click scrolls to "#top"\n')
    assert '<a href="#top"' in html
    assert "scrollIntoView({behavior:'smooth'})" in html


def test_inline_div_hover_add():
    html = _render('    Div class "card" on hover adds "lifted"\n        Text "x"\n    End\n')
    assert "addEventListener('mouseenter'" in html
    assert ".classList.add('lifted')" in html


def test_inline_and_nested_parity():
    # Inline sugar and the nested block produce the same classList call.
    inline = _render('    Button "X" on click toggles "open" on "#nav"\n')
    nested = _render(
        _div('        On click\n            Toggle class "open" on "#nav"\n        End\n')
    )
    assert ".classList.toggle('open')" in inline
    assert ".classList.toggle('open')" in nested


# ── data-evt wiring ──────────────────────────────────────────────────────────


def test_data_evt_id_matches_selector():
    html = _render(_div('        On click\n            Add class "x"\n        End\n'))
    assert 'data-evt="1"' in html
    assert 'querySelectorAll(\'[data-evt="1"]\')' in html


def test_unique_ids_across_elements():
    html = _render('    Button "A" on click toggles "x"\n    Button "B" on click toggles "y"\n')
    assert 'data-evt="1"' in html
    assert 'data-evt="2"' in html


# ── Security ─────────────────────────────────────────────────────────────────


def test_javascript_navigate_neutralized():
    html = _render(
        _div('        On click\n            Navigate to "javascript:alert(1)"\n        End\n')
    )
    assert 'javascript:alert' not in html


def test_no_inline_on_attribute_emitted():
    html = _render(_div('        On click\n            Add class "x"\n        End\n'))
    # Behavior lives in a generated <script>, not an inline onclick= attribute.
    assert 'onclick=' not in html


def test_bad_class_rejected():
    with pytest.raises(ParserError):
        _render(_div('        On click\n            Add class "a b"\n        End\n'))


def test_bad_selector_rejected():
    with pytest.raises(ParserError):
        _render(_div('        On click\n            Toggle class "x" on "a{}b"\n        End\n'))


def test_bad_fn_rejected():
    with pytest.raises(ParserError):
        _render(_div('        On click\n            Run "a;b()"\n        End\n'))


def test_unknown_event_rejected():
    with pytest.raises(ParserError):
        _render(_div('        On wheel\n            Add class "x"\n        End\n'))


# ── Regression ───────────────────────────────────────────────────────────────


def test_no_events_no_script_or_attr():
    html = _render(_div('        Text "hello"\n'))
    assert 'data-evt' not in html
    # No event IIFE injected when there are no handlers.
    assert '__ro' not in html
