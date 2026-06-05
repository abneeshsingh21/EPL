"""
EPL Auth Package - Python Backend
Authentication & security: JWT, password hashing, sessions, API keys.
"""

import base64 as _b64
import hashlib as _hashlib
import hmac as _hmac
import json as _json
import os as _os
import re as _re
import secrets as _secrets
import time as _time
import uuid as _uuid

# ═══════════════════════════════════════════════════════════
#  Password Hashing (PBKDF2-SHA256)
# ═══════════════════════════════════════════════════════════

_DEFAULT_ITERATIONS = 260000


def hash_password(password):
    salt = _os.urandom(16)
    dk = _hashlib.pbkdf2_hmac('sha256', password.encode(), salt, _DEFAULT_ITERATIONS)
    return _b64.b64encode(salt + dk).decode()


def verify_password(password, hashed):
    raw = _b64.b64decode(hashed.encode())
    salt = raw[:16]
    stored_dk = raw[16:]
    dk = _hashlib.pbkdf2_hmac('sha256', password.encode(), salt, _DEFAULT_ITERATIONS)
    return _hmac.compare_digest(dk, stored_dk)


def generate_salt(rounds=16):
    return _b64.b64encode(_os.urandom(int(rounds))).decode()


# ═══════════════════════════════════════════════════════════
#  JWT (HMAC-SHA256)
# ═══════════════════════════════════════════════════════════


def _b64url_encode(data):
    return _b64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s):
    padding = 4 - len(s) % 4
    s += '=' * padding
    return _b64.urlsafe_b64decode(s.encode())


def create_jwt(payload, secret, expires_in_hours):
    header = {'alg': 'HS256', 'typ': 'JWT'}
    now = _time.time()
    claims = dict(payload) if isinstance(payload, dict) else {}
    claims['iat'] = now
    claims['exp'] = now + float(expires_in_hours) * 3600
    h = _b64url_encode(_json.dumps(header).encode())
    p = _b64url_encode(_json.dumps(claims).encode())
    sig_input = f'{h}.{p}'.encode()
    sig = _hmac.new(secret.encode(), sig_input, _hashlib.sha256).digest()
    return f'{h}.{p}.{_b64url_encode(sig)}'


def verify_jwt(token, secret):
    parts = token.split('.')
    if len(parts) != 3:
        return None
    sig_input = f'{parts[0]}.{parts[1]}'.encode()
    expected_sig = _hmac.new(secret.encode(), sig_input, _hashlib.sha256).digest()
    actual_sig = _b64url_decode(parts[2])
    if not _hmac.compare_digest(expected_sig, actual_sig):
        return None
    payload = _json.loads(_b64url_decode(parts[1]))
    if payload.get('exp', 0) < _time.time():
        return None
    return payload


def decode_jwt_unverified(token):
    parts = token.split('.')
    if len(parts) != 3:
        return None
    return _json.loads(_b64url_decode(parts[1]))


def is_jwt_expired(token, secret):
    payload = decode_jwt_unverified(token)
    if payload is None:
        return True
    return payload.get('exp', 0) < _time.time()


def refresh_jwt(token, secret, new_expires_in_hours):
    payload = verify_jwt(token, secret)
    if payload is None:
        return None
    payload.pop('iat', None)
    payload.pop('exp', None)
    return create_jwt(payload, secret, new_expires_in_hours)


# ═══════════════════════════════════════════════════════════
#  API Keys & Secrets
# ═══════════════════════════════════════════════════════════


def generate_api_key(prefix='epl'):
    key = _secrets.token_urlsafe(32)
    return f'{prefix}_{key}'


def generate_secret(length=32):
    return _secrets.token_hex(int(length) // 2)


def generate_uuid():
    return str(_uuid.uuid4())


# ═══════════════════════════════════════════════════════════
#  Sessions
# ═══════════════════════════════════════════════════════════

import threading as _threading

_sessions: dict = {}
_sessions_lock = _threading.Lock()
_rate_limits_lock = _threading.Lock()

# ── Background eviction ────────────────────────────────────

_EVICTION_INTERVAL_SECONDS = 300  # sweep every 5 minutes
_eviction_timer = None


def _evict_expired() -> None:
    """Remove expired sessions and stale rate-limit buckets.

    Runs in a background daemon thread on a self-rescheduling timer so
    the in-process dicts don't grow without bound even when specific
    tokens / identifiers are never referenced again.
    """
    global _eviction_timer
    now = _time.time()

    with _sessions_lock:
        expired_tokens = [t for t, s in _sessions.items() if s['expires_at'] < now]
        for t in expired_tokens:
            del _sessions[t]

    with _rate_limits_lock:
        # Remove buckets whose most-recent timestamp is older than the
        # largest sensible window (1 hour).  Callers that care about
        # shorter windows already prune per-call; this is catch-all.
        stale_keys = [
            k for k, ts in _rate_limits.items()
            if not ts or (now - max(ts)) > 3600
        ]
        for k in stale_keys:
            del _rate_limits[k]

    # Reschedule
    _eviction_timer = _threading.Timer(_EVICTION_INTERVAL_SECONDS, _evict_expired)
    _eviction_timer.daemon = True
    _eviction_timer.start()


def _start_eviction_timer() -> None:
    global _eviction_timer
    if _eviction_timer is None or not _eviction_timer.is_alive():
        _eviction_timer = _threading.Timer(_EVICTION_INTERVAL_SECONDS, _evict_expired)
        _eviction_timer.daemon = True
        _eviction_timer.start()


# Start on first import
_start_eviction_timer()


def create_session(user_id, data, expires_in_minutes):
    token = _secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = {
            'user_id': user_id,
            'data': data,
            'expires_at': _time.time() + float(expires_in_minutes) * 60,
        }
    return token


def validate_session(session_token, secret=None):
    with _sessions_lock:
        session = _sessions.get(session_token)
        if session is None:
            return None
        if session['expires_at'] < _time.time():
            del _sessions[session_token]
            return None
        return session


def invalidate_session(session_token):
    with _sessions_lock:
        _sessions.pop(session_token, None)
    return True


# ═══════════════════════════════════════════════════════════
#  OAuth2 Helpers
# ═══════════════════════════════════════════════════════════

_OAUTH_URLS = {
    'google': 'https://accounts.google.com/o/oauth2/v2/auth',
    'github': 'https://github.com/login/oauth/authorize',
    'facebook': 'https://www.facebook.com/v18.0/dialog/oauth',
}

_OAUTH_TOKEN_URLS = {
    'google': 'https://oauth2.googleapis.com/token',
    'github': 'https://github.com/login/oauth/access_token',
    'facebook': 'https://graph.facebook.com/v18.0/oauth/access_token',
}


def build_oauth_url(provider, client_id, redirect_uri, scopes):
    base = _OAUTH_URLS.get(provider.lower(), provider)
    import urllib.parse

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scopes if isinstance(scopes, str) else ' '.join(scopes),
        'response_type': 'code',
    }
    return base + '?' + urllib.parse.urlencode(params)


def exchange_oauth_code(provider, code, client_id, client_secret, redirect_uri):
    try:
        import requests

        token_url = _OAUTH_TOKEN_URLS.get(provider.lower(), provider)
        resp = requests.post(
            token_url,
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            headers={'Accept': 'application/json'},
            timeout=30,
        )
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


# ═══════════════════════════════════════════════════════════
#  Hashing & HMAC
# ═══════════════════════════════════════════════════════════


def sha256(data):
    return _hashlib.sha256(str(data).encode()).hexdigest()


def sha512(data):
    return _hashlib.sha512(str(data).encode()).hexdigest()


def md5(data):
    """Return the MD5 hex digest of data.

    .. deprecated::
        MD5 is cryptographically broken and must not be used for security
        purposes (passwords, tokens, signatures).  Use sha256() or
        hash_password() instead.  This function is retained only for
        non-security checksums and legacy interoperability.
    """
    import warnings
    warnings.warn(
        "epl-auth md5() is not safe for security purposes. "
        "Use sha256() for checksums or hash_password() for passwords.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _hashlib.md5(str(data).encode()).hexdigest()


def hmac_sign(message, key):
    return _hmac.new(key.encode(), str(message).encode(), _hashlib.sha256).hexdigest()


def hmac_verify(message, signature, key):
    expected = _hmac.new(key.encode(), str(message).encode(), _hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature)


# ═══════════════════════════════════════════════════════════
#  Rate Limiting
# ═══════════════════════════════════════════════════════════

_rate_limits: dict = {}


def check_rate_limit(identifier, max_requests, window_seconds):
    """Sliding-window rate limiter.

    Returns True if the request is allowed, False if the limit is exceeded.
    Thread-safe: uses _rate_limits_lock for all dict mutations.
    Stale entries are periodically removed by the background eviction timer.
    """
    now = _time.time()
    key = str(identifier)
    win = float(window_seconds)
    with _rate_limits_lock:
        bucket = [t for t in _rate_limits.get(key, []) if now - t < win]
        if len(bucket) >= int(max_requests):
            _rate_limits[key] = bucket
            return False
        bucket.append(now)
        _rate_limits[key] = bucket
    return True


def reset_rate_limit(identifier):
    with _rate_limits_lock:
        _rate_limits.pop(str(identifier), None)
    return True


# ═══════════════════════════════════════════════════════════
#  Validation & Sanitization
# ═══════════════════════════════════════════════════════════

_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def is_valid_email(email):
    return bool(_EMAIL_RE.match(str(email)))


def is_strong_password(password):
    p = str(password)
    if len(p) < 8:
        return False
    if not _re.search(r'[A-Z]', p):
        return False
    if not _re.search(r'[a-z]', p):
        return False
    if not _re.search(r'\d', p):
        return False
    if not _re.search(r'[!@#$%^&*(),.?":{}|<>]', p):
        return False
    return True


def sanitize_input(raw_input):
    import html

    return html.escape(str(raw_input))
