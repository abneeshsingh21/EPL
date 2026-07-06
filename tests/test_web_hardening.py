"""Web/server hardening regression tests (M7).

Covers the href/src scheme sanitizer allowlist and the default CSP policy.
Additional server-behavior items (rate-limit key, error-text leakage, session
cookie flags) are exercised where they can be unit-tested without a live socket.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.html_gen import _safe_href, build_csp_header


ALLOWED_URLS = [
    "https://example.com/x",
    "http://x",
    "mailto:a@b.com",
    "tel:+15550001111",
    "/relative/path",
    "#anchor",
    "?q=1",
    "example.com/page",
]

BLOCKED_URLS = [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "java\tscript:alert(1)",
    "java\nscript:alert(1)",
    "\x00javascript:alert(1)",
    "  javascript:alert(1)",
    "vbscript:msgbox(1)",
    "data:text/html,<script>alert(1)</script>",
    "data:image/svg+xml;base64,PHN2Zz4=",
    "file:///etc/passwd",
]


@pytest.mark.parametrize("url", ALLOWED_URLS)
def test_safe_href_allows_benign_urls(url):
    assert _safe_href(url) != "#"


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_safe_href_blocks_dangerous_schemes(url):
    assert _safe_href(url) == "#"


def test_csp_off_mode_permits_inline_scripts():
    header = build_csp_header(None)
    assert "script-src 'self' 'unsafe-inline'" in header
    assert "object-src 'none'" in header


def test_csp_on_mode_is_strict_nonce():
    header = build_csp_header("NONCE1")
    script_src = header.split("script-src ")[1].split(";")[0]
    assert "'nonce-NONCE1'" in script_src
    assert "'unsafe-inline'" not in script_src


# ── Rate-limit client key (playground XFF spoof) ─────────────────────────────


def test_rate_limit_key_ignores_spoofed_xff_by_default(monkeypatch):
    import epl.playground as pg

    monkeypatch.delenv("EPL_TRUST_PROXY", raising=False)
    # Two different spoofed XFF values from the same socket peer must map to the
    # same bucket -> XFF cannot be used to evade the limiter.
    assert pg._resolve_client_key("1.2.3.4", "10.0.0.9") == "10.0.0.9"
    assert pg._resolve_client_key("9.9.9.9", "10.0.0.9") == "10.0.0.9"
    assert pg._resolve_client_key(None, "10.0.0.9") == "10.0.0.9"


def test_rate_limit_key_uses_rightmost_hop_when_proxy_trusted(monkeypatch):
    import epl.playground as pg

    monkeypatch.setenv("EPL_TRUST_PROXY", "1")
    # Proxy appends the real client on the right; a client-forged left hop is
    # ignored.
    assert pg._resolve_client_key("1.2.3.4, 172.16.0.1", "172.16.0.1") == "172.16.0.1"


# ── Error-text leakage ───────────────────────────────────────────────────────


def test_client_error_detail_hidden_by_default(monkeypatch):
    import epl.web as web

    monkeypatch.delenv("EPL_WEB_DEBUG", raising=False)
    detail = web._client_error_detail(ValueError("secret /etc/db.sqlite line 42"))
    assert "secret" not in detail
    assert detail == "Internal server error"


def test_client_error_detail_shown_in_debug(monkeypatch):
    import epl.web as web

    monkeypatch.setenv("EPL_WEB_DEBUG", "1")
    detail = web._client_error_detail(ValueError("boom-detail"))
    assert "boom-detail" in detail


# ── Cookie flags ─────────────────────────────────────────────────────────────


def test_samesite_none_cookie_forced_secure():
    from epl.web import Response

    r = Response()
    r.set_cookie("sid", "abc", samesite="None")
    cookie = r._cookies[-1]
    assert "SameSite=None" in cookie
    assert "; Secure" in cookie


def test_default_cookie_has_httponly_and_samesite():
    from epl.web import Response

    r = Response()
    r.set_cookie("sid", "abc")
    cookie = r._cookies[-1]
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie
