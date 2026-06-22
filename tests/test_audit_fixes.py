"""Regression tests for the post-v9.7.0 enterprise-hardening audit.

Each test pins a confirmed bug found during the review so it cannot silently
regress:

  1. HEAD requests 404'd (or wrote a body) in the WSGI/deploy adapters.
  2. The standalone WSGI 500 page echoed the raw exception text.
  3. The deploy adapter trusted spoofable ``X-Forwarded-For`` for rate limiting.
  4. The Redis store backend crashed on out-of-range / racy removals.
  6. The static build scripts crashed with ``IndexError`` on a missing ``--out``.
"""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _environ(method='GET', path='/', headers=None, body=b''):
    """Build a minimal WSGI environ for the adapters under test."""
    env = {
        'REQUEST_METHOD': method,
        'PATH_INFO': path,
        'QUERY_STRING': '',
        'REMOTE_ADDR': '127.0.0.1',
        'wsgi.input': io.BytesIO(body),
    }
    if body:
        env['CONTENT_LENGTH'] = str(len(body))
    for key, value in (headers or {}).items():
        env['HTTP_' + key.upper().replace('-', '_')] = value
    return env


def _drive(app, environ):
    """Call a WSGI app and return (captured_status_headers, body_bytes)."""
    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured['status'] = status
        captured['headers'] = dict(headers)

    body = b''.join(app(environ, start_response))
    return captured, body


# ═══════════════════════════════════════════════════════════
# Bug 1 + Bug 2 — epl.wsgi.EPLWSGIApp
# ═══════════════════════════════════════════════════════════


class TestWSGIHeadAndErrors(unittest.TestCase):
    def _app(self):
        from epl.wsgi import EPLWSGIApp

        app = EPLWSGIApp()

        @app.route('/', methods=['GET'])
        def index(req, resp):  # noqa: ANN001
            return 'hello world'

        return app

    def test_head_routes_as_get_with_no_body(self):
        """Bug 1: HEAD on a GET route returns 200, no body, real Content-Length."""
        cap, body = _drive(self._app(), _environ('HEAD', '/'))
        self.assertIn('200', cap['status'])
        self.assertEqual(body, b'')
        self.assertEqual(cap['headers']['Content-Length'], str(len(b'hello world')))

    def test_get_still_returns_body(self):
        """Control: GET is unchanged."""
        cap, body = _drive(self._app(), _environ('GET', '/'))
        self.assertIn('200', cap['status'])
        self.assertEqual(body, b'hello world')

    def test_500_does_not_leak_exception_text(self):
        """Bug 2: a handler crash must not surface the exception to the client."""
        from epl.wsgi import EPLWSGIApp

        secret = 'SECRET_DB_PASSWORD_abc123'
        app = EPLWSGIApp()

        @app.route('/boom', methods=['GET'])
        def boom(req, resp):  # noqa: ANN001
            raise RuntimeError(secret)

        cap, body = _drive(app, _environ('GET', '/boom'))
        self.assertIn('500', cap['status'])
        self.assertNotIn(secret.encode(), body)

    def test_500_debug_mode_escapes_exception_text(self):
        """Bug 2: opt-in debug mode shows the error but HTML-escaped (no XSS)."""
        from epl.wsgi import EPLWSGIApp

        app = EPLWSGIApp()
        app.debug = True

        @app.route('/boom', methods=['GET'])
        def boom(req, resp):  # noqa: ANN001
            raise RuntimeError('<script>alert(1)</script>')

        cap, body = _drive(app, _environ('GET', '/boom'))
        self.assertIn('500', cap['status'])
        self.assertNotIn(b'<script>', body)
        self.assertIn(b'&lt;script&gt;', body)


# ═══════════════════════════════════════════════════════════
# Bug 1 + Bug 3 — epl.deploy.WSGIAdapter
# ═══════════════════════════════════════════════════════════


class TestDeployAdapterHeadAndProxy(unittest.TestCase):
    def _app(self, rate_limit=0):
        from epl.web import EPLWebApp

        app = EPLWebApp('AuditTest')
        app.rate_limit = rate_limit
        return app

    def test_head_on_health_has_headers_but_no_body(self):
        """Bug 1: HEAD keeps GET's headers (Content-Length) but drops the body."""
        from epl.deploy import WSGIAdapter

        adapter = WSGIAdapter(self._app())
        cap, body = _drive(adapter, _environ('HEAD', '/_health'))
        self.assertIn('200', cap['status'])
        self.assertEqual(body, b'')
        self.assertIn('Content-Length', cap['headers'])
        self.assertNotEqual(cap['headers']['Content-Length'], '0')

    def test_xforwarded_for_ignored_by_default(self):
        """Bug 3: spoofed XFF must not split the rate-limit bucket by default."""
        from epl.deploy import WSGIAdapter
        from epl.web import _rate_tracker

        _rate_tracker.clear()
        adapter = WSGIAdapter(self._app(rate_limit=1))  # trust_proxy defaults False

        statuses = []
        for spoof in ('1.1.1.1', '2.2.2.2'):
            cap, _ = _drive(adapter, _environ('GET', '/p', headers={'X-Forwarded-For': spoof}))
            statuses.append(cap['status'])
        # Same real REMOTE_ADDR -> same bucket -> the second request is limited.
        self.assertTrue(any('429' in s for s in statuses))

    def test_xforwarded_for_used_when_trusted(self):
        """Bug 3: with trust_proxy=True the proxied client IP is honored."""
        from epl.deploy import WSGIAdapter
        from epl.web import _rate_tracker

        _rate_tracker.clear()
        adapter = WSGIAdapter(self._app(rate_limit=1), trust_proxy=True)

        statuses = []
        for spoof in ('1.1.1.1', '2.2.2.2'):
            cap, _ = _drive(adapter, _environ('GET', '/p', headers={'X-Forwarded-For': spoof}))
            statuses.append(cap['status'])
        # Distinct proxied client IPs -> distinct buckets -> neither is limited.
        self.assertFalse(any('429' in s for s in statuses))


# ═══════════════════════════════════════════════════════════
# Bug 4 — epl.store_backends.RedisStoreBackend remove semantics
# ═══════════════════════════════════════════════════════════


class _FakeRedis:
    """Minimal Redis list emulation; lset raises on a bad index like real Redis."""

    def __init__(self):
        self._lists: dict = {}

    def rpush(self, key, value):
        self._lists.setdefault(key, []).append(value)

    def lrange(self, key, start, end):
        items = self._lists.get(key, [])
        return items[start:] if end == -1 else items[start : end + 1]

    def llen(self, key):
        return len(self._lists.get(key, []))

    def lset(self, key, index, value):
        items = self._lists.get(key, [])
        if index < 0 or index >= len(items):
            raise Exception('ERR index out of range')
        items[index] = value

    def lrem(self, key, count, value):
        items = self._lists.get(key, [])
        kept, removed = [], 0
        for item in items:
            if item == value and (count == 0 or removed < count):
                removed += 1
                continue
            kept.append(item)
        self._lists[key] = kept
        return removed


def _redis_backend():
    """A RedisStoreBackend wired to a fake client, bypassing the live connection."""
    from epl.store_backends import RedisStoreBackend

    backend = object.__new__(RedisStoreBackend)
    backend._redis = _FakeRedis()
    backend._prefix = 'epl:store:'
    return backend


class TestRedisStoreRemoveContract(unittest.TestCase):
    def test_remove_valid_index(self):
        backend = _redis_backend()
        for item in ('a', 'b', 'c'):
            backend.store_add('items', item)
        backend.store_remove('items', 1)
        self.assertEqual(backend.store_get('items'), ['a', 'c'])

    def test_remove_out_of_range_is_ignored(self):
        """Bug 4: matches Memory/SQLite — a bad index is a no-op, not a crash."""
        backend = _redis_backend()
        backend.store_add('items', 'a')
        backend.store_remove('items', 5)  # must not raise
        self.assertEqual(backend.store_get('items'), ['a'])

    def test_remove_negative_index_is_ignored(self):
        backend = _redis_backend()
        backend.store_add('items', 'a')
        backend.store_remove('items', -1)
        self.assertEqual(backend.store_get('items'), ['a'])


# ═══════════════════════════════════════════════════════════
# Bug 6 — static build script rejects a missing --out value
# ═══════════════════════════════════════════════════════════


class TestBuildScriptArgs(unittest.TestCase):
    def test_build_static_out_without_value_exits_cleanly(self):
        """Bug 6: `--out` with no argument fails with exit 2, not an IndexError."""
        script = ROOT / 'landing_page' / 'build_static.py'
        proc = subprocess.run(
            [sys.executable, str(script), '--out'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn('--out requires', proc.stderr)
        self.assertNotIn('IndexError', proc.stderr)


if __name__ == '__main__':
    unittest.main()
