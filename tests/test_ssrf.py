"""SSRF protection regression tests for the EPL HTTP client (H1).

Covers the three defenses added after the security audit:
  1. URL scheme allowlist (only http/https; blocks file://, ftp://, gopher://).
  2. Private/internal host blocking on the initial request.
  3. Redirect re-validation so a public URL cannot 3xx into a private address.
"""

import io
import os
import sys
import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.networking import HTTPClient, _SSRFRedirectHandler


@pytest.mark.parametrize(
    'url', ['file:///etc/passwd', 'ftp://host/x', 'gopher://a/', 'data:text/plain,x']
)
def test_non_http_schemes_blocked(url):
    with pytest.raises(ConnectionError):
        HTTPClient()._make_request('GET', url)


@pytest.mark.parametrize(
    'url',
    [
        'http://127.0.0.1/',
        'http://localhost/',
        'http://169.254.169.254/latest/meta-data/',  # cloud metadata
        'http://0.0.0.0/',
        'http://[::1]/',
    ],
)
def test_private_hosts_blocked(url):
    with pytest.raises(ConnectionError):
        HTTPClient()._make_request('GET', url)


def test_is_private_ip_fails_closed_on_unresolvable():
    # A name that cannot resolve must be treated as blocked, not allowed.
    assert HTTPClient._is_private_ip('no-such-host.invalid') is True
    assert HTTPClient._is_private_ip('') is True


@pytest.mark.parametrize(
    'target',
    [
        'http://169.254.169.254/',
        'http://127.0.0.1/',
        'http://localhost/admin',
        'file:///etc/passwd',
    ],
)
def test_redirect_to_private_or_bad_scheme_blocked(target):
    handler = _SSRFRedirectHandler()

    class _Req:
        full_url = 'http://public.example/'

        def get_full_url(self):
            return self.full_url

        def __getattr__(self, name):
            return None

    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(_Req(), io.BytesIO(b''), 302, 'Found', {}, target)
