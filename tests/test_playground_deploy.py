"""Regression coverage for public-hosting concerns of the playground server.

These guard the behaviour that lets the playground run headless behind a cloud
host (Azure App Service): environment-driven bind address, a sliding-window rate
limiter, and a concurrency cap — without changing the local `epl playground`
defaults.
"""

import os
import socket
import threading
import time
import urllib.request

import pytest
from epl import playground as pg


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture
def live_server():
    """Start the real playground server headless on an ephemeral port."""
    port = _free_port()
    thread = threading.Thread(
        target=pg.start_playground,
        kwargs={'port': port, 'host': '127.0.0.1', 'open_browser': False},
        daemon=True,
    )
    thread.start()
    base = f'http://127.0.0.1:{port}'
    for _ in range(50):  # wait up to ~5s for the socket to accept
        try:
            urllib.request.urlopen(base + '/api/examples', timeout=1).read()
            break
        except Exception:
            time.sleep(0.1)
    yield base


@pytest.fixture(autouse=True)
def _clean_bind_env():
    """Isolate each test from PORT/host environment leakage."""
    saved = {k: os.environ.get(k) for k in ('PORT', 'WEBSITES_PORT', 'EPL_PLAYGROUND_HOST')}
    for k in saved:
        os.environ.pop(k, None)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_resolve_bind_defaults_to_local():
    # Local `epl playground` must keep binding loopback on 8080 — no change.
    assert pg._resolve_bind() == ('127.0.0.1', 8080)


def test_resolve_bind_honours_explicit_args():
    assert pg._resolve_bind('0.0.0.0', 9000) == ('0.0.0.0', 9000)


def test_resolve_bind_reads_port_from_env():
    os.environ['PORT'] = '8000'
    assert pg._resolve_bind('0.0.0.0') == ('0.0.0.0', 8000)


def test_resolve_bind_reads_websites_port_fallback():
    os.environ['WEBSITES_PORT'] = '7777'
    assert pg._resolve_bind()[1] == 7777


def test_resolve_bind_reads_host_from_env():
    os.environ['EPL_PLAYGROUND_HOST'] = '0.0.0.0'
    assert pg._resolve_bind() == ('0.0.0.0', 8080)


def test_rate_limiter_blocks_after_quota():
    limiter = pg._RateLimiter(max_requests=3, window_seconds=60)
    assert [limiter.allow('1.2.3.4') for _ in range(4)] == [True, True, True, False]


def test_rate_limiter_is_per_client():
    limiter = pg._RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow('a') is True
    assert limiter.allow('a') is False
    assert limiter.allow('b') is True  # a different client is unaffected


def test_concurrency_cap_is_bounded():
    # The execution semaphore must be a hard ceiling on simultaneous runs.
    assert pg._EXEC_SEMAPHORE._value == pg.PLAYGROUND_MAX_CONCURRENT_EXECUTIONS


def test_run_response_sends_cors_header(live_server):
    # The embedded site playground calls this cross-origin; the allow-origin
    # header must be present on the actual API response.
    req = urllib.request.Request(
        live_server + '/api/run',
        data=b'{"code": "Print \\"hi\\""}',
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    resp = urllib.request.urlopen(req, timeout=30)
    assert resp.headers.get('Access-Control-Allow-Origin') == '*'


def test_options_preflight_allows_cross_origin(live_server):
    req = urllib.request.Request(live_server + '/api/run', method='OPTIONS')
    resp = urllib.request.urlopen(req, timeout=10)
    assert resp.status == 204
    assert resp.headers.get('Access-Control-Allow-Origin') == '*'
    assert 'POST' in resp.headers.get('Access-Control-Allow-Methods', '')
