"""Runtime hardening tests for the EPL playground."""

from __future__ import annotations

import subprocess
from unittest import mock

from epl import playground


def test_execute_epl_worker_payload_runs_simple_program() -> None:
    result = playground._execute_epl_worker_payload('Say "hello"')

    assert result['error'] is None
    assert result['output'].strip() == 'hello'


def test_execute_epl_reports_timeout_when_worker_hangs() -> None:
    with mock.patch(
        'epl.playground.subprocess.run',
        side_effect=subprocess.TimeoutExpired(
            cmd='python -m epl.playground --worker-run', timeout=10
        ),
    ):
        result = playground._execute_epl('While True\n    Set x to 1\nEnd')

    assert result['output'] == ''
    assert 'timed out' in str(result['error']).lower()


def test_start_playground_uses_threading_http_server() -> None:
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, address, handler):
            captured['address'] = address
            captured['handler'] = handler

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            captured['closed'] = True

    with mock.patch('http.server.ThreadingHTTPServer', FakeServer):
        playground.start_playground(port=8765, open_browser=False)

    assert captured['address'] == ('127.0.0.1', 8765)
    assert captured['closed'] is True
