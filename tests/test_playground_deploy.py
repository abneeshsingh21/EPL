"""Regression coverage for public-hosting concerns of the playground server.

These guard the behaviour that lets the playground run headless behind a cloud
host (Azure App Service): environment-driven bind address, a sliding-window rate
limiter, and a concurrency cap — without changing the local `epl playground`
defaults.
"""

import os

import pytest

from epl import playground as pg


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
