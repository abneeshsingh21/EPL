"""Regression tests for native WebApp route execution context."""

from __future__ import annotations

from io import BytesIO
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.cli import _load_epl_web_app
from epl.deploy import WSGIAdapter


class TestWebRouteContext(unittest.TestCase):
    def _load_adapter(self, source: str):
        tmpdir = tempfile.TemporaryDirectory(prefix="epl_web_route_ctx_")
        source_path = Path(tmpdir.name, "app.epl")
        source_path.write_text(source, encoding="utf-8")
        app, interpreter = _load_epl_web_app(str(source_path))
        adapter = WSGIAdapter(app, interpreter=interpreter)
        self.addCleanup(tmpdir.cleanup)
        return adapter

    def _request(self, adapter, *, method="GET", path="/", query="", body=b"", content_type="application/json"):
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "REMOTE_ADDR": "127.0.0.1",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
            "wsgi.input": BytesIO(body),
            "wsgi.errors": BytesIO(),
            "wsgi.url_scheme": "http",
        }
        if body:
            environ["CONTENT_LENGTH"] = str(len(body))
        if content_type:
            environ["CONTENT_TYPE"] = content_type

        status = {}

        def start_response(status_text, headers, exc_info=None):
            status["status"] = status_text
            status["headers"] = dict(headers)

        chunks = adapter(environ, start_response)
        payload = b"".join(chunks).decode("utf-8")
        return status, payload

    def test_json_route_can_branch_on_request_data_inside_if_blocks(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/api/chat" responds with\n'
            '    If request_data.message == "hello" Then\n'
            '        Send json Map with ok = True and reply = "hi"\n'
            '    Otherwise\n'
            '        Send json Map with ok = False and reply = "fallback"\n'
            '    End\n'
            'End\n'
        )

        status, payload = self._request(
            adapter,
            method="POST",
            path="/api/chat",
            body=b'{"message":"hello"}',
        )

        self.assertIn("200", status["status"])
        self.assertIn('"ok": true', payload.lower())
        self.assertIn('"reply": "hi"', payload)

    def test_page_routes_resolve_template_strings_from_route_context(self):
        adapter = self._load_adapter(
            'Create WebApp called app\n\n'
            'Route "/hello/:name" shows\n'
            '    Create title equal to "Welcome, " + request_params.name\n'
            '    Page "$title"\n'
            '        Heading "$title"\n'
            '        Text "Method: $request_method"\n'
            '    End\n'
            'End\n'
        )

        status, payload = self._request(adapter, path="/hello/Ada")

        self.assertIn("200", status["status"])
        self.assertIn("Welcome, Ada", payload)
        self.assertIn("Method: GET", payload)


if __name__ == "__main__":
    unittest.main()
