"""XSS regression tests for the wasm/web widget HTML generator (M6).

Widget content (text, placeholders, dropdown options) comes from the EPL
source and was interpolated into HTML without escaping. These tests lock in
that every interpolated value is HTML-escaped so injected markup stays inert.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.wasm_web import WebCodeGenerator


def _render(widgets):
    g = WebCodeGenerator('X')
    g.widgets = widgets
    return g._widgets_to_html()


def test_label_text_script_is_escaped():
    html = _render([{'type': 'label', 'id': 'l1', 'text': '<script>alert(1)</script>'}])
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_button_tag_breakout_is_escaped():
    html = _render(
        [{'type': 'button', 'id': 'b1', 'text': '</button><img src=x onerror=alert(2)>'}]
    )
    # The closing tag and injected element must not appear as live markup.
    assert '</button><img' not in html
    assert '&lt;/button&gt;&lt;img' in html


def test_input_placeholder_attribute_breakout_is_escaped():
    html = _render(
        [{'type': 'input', 'id': 'i1', 'properties': {'placeholder': '"><script>evil()</script>'}}]
    )
    assert '"><script>' not in html
    assert '&quot;&gt;&lt;script&gt;' in html


def test_dropdown_option_is_escaped_in_value_and_text():
    html = _render(
        [{'type': 'dropdown', 'id': 'd1', 'properties': {'options': ['"><svg onload=alert(3)>']}}]
    )
    assert '"><svg' not in html
    assert '&quot;&gt;&lt;svg' in html


def test_default_widget_text_is_escaped():
    html = _render([{'type': 'unknownkind', 'id': 'x1', 'text': '<img src=x onerror=alert(9)>'}])
    assert '<img src=x' not in html
    assert '&lt;img' in html
