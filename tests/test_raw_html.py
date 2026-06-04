"""Tests for the v9.3.0 `Raw HTML` escape-hatch keyword."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl.html_gen import generate_html
from epl.lexer import Lexer
from epl.parser import Parser


def _compile(src):
    program = Parser(Lexer(src).tokenize()).parse()
    return program


def _render_page(src):
    program = _compile(src)
    page = program.statements[0]
    return generate_html(page)


def test_raw_html_emits_verbatim_table():
    html = _render_page('Page "Demo"\nRaw HTML "<table><tr><td>Hello</td></tr></table>".\nEnd')
    assert '<table><tr><td>Hello</td></tr></table>' in html


def test_raw_html_does_not_escape_angle_brackets():
    html = _render_page('Page "Demo"\nRaw HTML "<video controls src=\\"v.mp4\\"></video>".\nEnd')
    assert '<video controls' in html
    assert '&lt;video' not in html


def test_raw_html_preserves_attributes_and_quotes():
    html = _render_page(
        'Page "Demo"\nRaw HTML "<details><summary>Click</summary><p>hidden</p></details>".\nEnd'
    )
    assert '<details>' in html
    assert '<summary>Click</summary>' in html


def test_raw_html_can_coexist_with_other_elements():
    html = _render_page(
        'Page "Demo"\nHeading "Title".\nRaw HTML "<hr class=\\"sep\\">".\nText "After".\nEnd'
    )
    assert '<h1' in html  # heading rendered
    assert '<hr class="sep">' in html  # raw block rendered
    assert 'After' in html


def test_html_identifier_still_usable_as_variable():
    # Regression: making `html` a keyword must not break code that uses it as
    # an identifier (common pattern: `html = ""` builder loop).
    program = _compile('Function build takes items\n    html = ""\n    Return html\nEnd')
    assert program.statements[0].name == 'build'


def test_raw_identifier_still_usable_as_parameter_name():
    program = _compile('Function pass_through takes raw\n    Return raw\nEnd')
    assert program.statements[0].name == 'pass_through'


def test_raw_html_in_page_ast_node():
    program = _compile('Page "Demo"\nRaw HTML "<x></x>".\nEnd')
    page = program.statements[0]
    assert page.elements[0].tag == 'raw_html'
    assert page.elements[0].content == '<x></x>'
