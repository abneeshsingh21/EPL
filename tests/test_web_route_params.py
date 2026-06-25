"""Regression tests for path-parameter routing and the `Send redirect` alias.

Covers the omniapp stress-test findings:
  B7 — `{id}` brace-style routes silently 404'd (regression).
  B8 — captured params were not exposed as bare variables (only via
       web_request_param / request_params).
  B5 — `Send redirect "/path"` was unsupported (only the standalone
       `Redirect to` statement worked).
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


class TestWebRouteParams(unittest.TestCase):
    def _load_adapter(self, source: str):
        tmpdir = tempfile.TemporaryDirectory(prefix='epl_web_route_params_')
        source_path = Path(tmpdir.name, 'app.epl')
        source_path.write_text(source, encoding='utf-8')
        app, interpreter = _load_epl_web_app(str(source_path))
        adapter = WSGIAdapter(app, interpreter=interpreter)
        self.addCleanup(tmpdir.cleanup)
        return adapter

    def _request(self, adapter, *, method='GET', path='/', query='', body=b''):
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': query,
            'REMOTE_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'wsgi.input': BytesIO(body),
            'wsgi.errors': BytesIO(),
            'wsgi.url_scheme': 'http',
        }
        if body:
            environ['CONTENT_LENGTH'] = str(len(body))
            environ['CONTENT_TYPE'] = 'application/json'

        captured = {}

        def start_response(status_text, headers, exc_info=None):
            captured['status'] = status_text
            captured['headers'] = dict(headers)

        chunks = adapter(environ, start_response)
        captured['payload'] = b''.join(chunks).decode('utf-8')
        return captured

    # ── B7: {id} brace-style routes must match ──────────────────────────
    def test_brace_style_param_route_matches_and_binds(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/toggle/{id}" responds with\n'
            '    Send json Map with got = id\n'
            'End\n'
        )
        res = self._request(adapter, path='/toggle/42')
        self.assertIn('200', res['status'])
        self.assertIn('"got": "42"', res['payload'])

    # ── B7 + B8: :id colon-style also binds the bare variable ───────────
    def test_colon_style_param_route_binds_bare_variable(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/hit/:id" responds with\n'
            '    Send json Map with got = id\n'
            'End\n'
        )
        res = self._request(adapter, path='/hit/7')
        self.assertIn('200', res['status'])
        self.assertIn('"got": "7"', res['payload'])

    # ── B8: param still reachable via request_params / web_request_param ─
    def test_param_still_available_via_request_params(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/item/{slug}" responds with\n'
            '    Send json Map with a = slug and b = request_params.slug\n'
            'End\n'
        )
        res = self._request(adapter, path='/item/widget')
        self.assertIn('200', res['status'])
        self.assertIn('"a": "widget"', res['payload'])
        self.assertIn('"b": "widget"', res['payload'])

    def test_unmatched_param_route_still_404s(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/toggle/{id}" responds with\n'
            '    Send json Map with got = id\n'
            'End\n'
        )
        res = self._request(adapter, path='/nope/here')
        self.assertIn('404', res['status'])

    # ── B5: Send redirect "/path" ───────────────────────────────────────
    def test_send_redirect_issues_http_redirect(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/go" responds with\n'
            '    Send redirect "/done"\n'
            'End\n'
        )
        res = self._request(adapter, path='/go')
        self.assertTrue(
            res['status'].startswith('30'),
            msg=f'expected a 3xx redirect, got {res["status"]}',
        )
        location = res['headers'].get('Location') or res['headers'].get('location')
        self.assertEqual(location, '/done')


if __name__ == '__main__':
    unittest.main()
