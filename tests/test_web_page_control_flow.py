"""Tests for control flow inside the Page DSL (v9.9.2).

Covers omniapp stress-test finding B1: `For Each` (and `If`) were silently
dropped inside a `Page`, so native dynamic lists were impossible. They are now
parsed as element bodies and expanded into markup at request time.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.cli import _load_epl_web_app
from epl.deploy import WSGIAdapter
from epl.lexer import Lexer
from epl.parser import Parser


class TestPageControlFlowParsing(unittest.TestCase):
    """Parser-level: For Each / If inside a Page are kept, not skipped."""

    def _parse_page(self, source: str):
        program = Parser(Lexer(source).tokenize()).parse()
        return program.statements[0]

    def test_for_each_inside_page_is_parsed(self):
        page = self._parse_page(
            'Page "List"\n    For each item in things\n        Text "$item"\n    End\nEnd\n'
        )
        kinds = [type(e).__name__ for e in page.elements]
        self.assertIn('ForEachLoop', kinds)

    def test_if_inside_page_is_parsed(self):
        page = self._parse_page(
            'Page "Cond"\n'
            '    If ready Then\n'
            '        Text "yes"\n'
            '    Otherwise\n'
            '        Text "no"\n'
            '    End\n'
            'End\n'
        )
        kinds = [type(e).__name__ for e in page.elements]
        self.assertIn('IfStatement', kinds)

    def test_for_each_inside_div_is_parsed(self):
        page = self._parse_page(
            'Page "Nested"\n'
            '    Div class "wrap"\n'
            '        For each item in things\n'
            '            Text "$item"\n'
            '        End\n'
            '    End\n'
            'End\n'
        )
        div = page.elements[0]
        child_kinds = [type(c).__name__ for c in div.children]
        self.assertIn('ForEachLoop', child_kinds)


class TestPageControlFlowRendering(unittest.TestCase):
    """End-to-end: a served Page expands loops/branches into real markup."""

    def _load_adapter(self, source: str):
        tmpdir = tempfile.TemporaryDirectory(prefix='epl_page_ctrl_')
        source_path = Path(tmpdir.name, 'app.epl')
        source_path.write_text(source, encoding='utf-8')
        app, interpreter = _load_epl_web_app(str(source_path))
        adapter = WSGIAdapter(app, interpreter=interpreter)
        self.addCleanup(tmpdir.cleanup)
        return adapter

    def _get(self, adapter, path='/'):
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': path,
            'QUERY_STRING': '',
            'REMOTE_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'wsgi.input': BytesIO(b''),
            'wsgi.errors': BytesIO(),
            'wsgi.url_scheme': 'http',
        }
        captured = {}

        def start_response(status_text, headers, exc_info=None):
            captured['status'] = status_text

        chunks = adapter(environ, start_response)
        captured['payload'] = b''.join(chunks).decode('utf-8')
        return captured

    def test_for_each_renders_one_element_per_item(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/list" shows\n'
            '    Create things equal to ["alpha", "beta", "gamma"]\n'
            '    Page "List"\n'
            '        For each item in things\n'
            '            Text "row:$item"\n'
            '        End\n'
            '    End\n'
            'End\n'
        )
        result = self._get(adapter, '/list')
        self.assertIn('200', result['status'])
        payload = result['payload']
        self.assertIn('row:alpha', payload)
        self.assertIn('row:beta', payload)
        self.assertIn('row:gamma', payload)
        self.assertEqual(payload.count('row:'), 3)

    def test_if_renders_only_the_true_branch(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/cond" shows\n'
            '    Create ready equal to true\n'
            '    Page "Cond"\n'
            '        If ready Then\n'
            '            Text "branch-yes"\n'
            '        Otherwise\n'
            '            Text "branch-no"\n'
            '        End\n'
            '    End\n'
            'End\n'
        )
        result = self._get(adapter, '/cond')
        self.assertIn('200', result['status'])
        payload = result['payload']
        self.assertIn('branch-yes', payload)
        self.assertNotIn('branch-no', payload)

    def test_empty_list_renders_no_rows(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/empty" shows\n'
            '    Create things equal to []\n'
            '    Page "Empty"\n'
            '        Heading "Items"\n'
            '        For each item in things\n'
            '            Text "row:$item"\n'
            '        End\n'
            '    End\n'
            'End\n'
        )
        result = self._get(adapter, '/empty')
        self.assertIn('200', result['status'])
        self.assertNotIn('row:', result['payload'])
        self.assertIn('Items', result['payload'])


if __name__ == '__main__':
    unittest.main()
