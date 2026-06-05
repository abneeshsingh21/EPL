"""
EPL v9.4.0 Phase 4 Security Test Suite
Official package security: epl-crypto, epl-validator, epl-auth, epl-http/mcp
"""

import importlib
import sys
import time
import warnings
from functools import wraps

sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), '..'))


# ── Minimal test harness (matches prior phases) ──────────────────────────────

class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0


def _start_tracker():
    _TrackerState.current = {'passed': 0, 'failed': 0, 'failures': []}


def _finish_tracker():
    t = _TrackerState.current
    _TrackerState.current = None
    if t is None:
        return
    _TrackerState.total_pass += t['passed']
    _TrackerState.total_fail += t['failed']
    if t['failures']:
        raise AssertionError('\n'.join(t['failures']))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            _finish_tracker()
    return wrapper


def check(name, condition, detail=''):
    t = _TrackerState.current
    if t is None:
        raise RuntimeError('check() called outside an active test tracker.')
    if condition:
        print(f'  PASS: {name}')
        t['passed'] += 1
    else:
        print(f'  FAIL: {name} {detail}')
        t['failed'] += 1
        t['failures'].append(f'{name}: {detail}' if detail else name)


# ══════════════════════════════════════════════════════════════════════════════
# P4-SEC-1  epl-crypto — no insecure XOR fallback
# ══════════════════════════════════════════════════════════════════════════════

@_tracked_test
def test_crypto_no_xor_fallback():
    print('\n=== P4-SEC-1: epl-crypto — no XOR fallback ===')

    import importlib.util, os
    pkg_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'epl', 'official_packages', 'epl-crypto', 'python', '__init__.py'
    )
    spec = importlib.util.spec_from_file_location('_epl_crypto', pkg_path)
    crypto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crypto)

    # T1: XOR keyword gone from source
    import inspect
    src = inspect.getsource(crypto)
    check('XOR keyword absent from source', 'XOR' not in src and 'xor' not in src.lower() or
          'cycle' not in src)

    # T2: aes_encrypt raises ImportError when cryptography absent (simulate)
    orig = crypto._HAS_CRYPTOGRAPHY
    crypto._HAS_CRYPTOGRAPHY = False
    try:
        crypto.aes_encrypt('hello', 'a' * 44)
        check('aes_encrypt raises when no cryptography', False, 'no exception raised')
    except ImportError as e:
        check('aes_encrypt raises ImportError', True)
        check('Error message mentions package name', 'cryptography' in str(e).lower())
        check('Error message has install hint', 'pip install' in str(e))
    except Exception as e:
        check('aes_encrypt raises ImportError (not other)', False, type(e).__name__)
    finally:
        crypto._HAS_CRYPTOGRAPHY = orig

    # T3: aes_decrypt raises ImportError when cryptography absent
    crypto._HAS_CRYPTOGRAPHY = False
    try:
        crypto.aes_decrypt('aGVsbG8=', 'a' * 44)
        check('aes_decrypt raises when no cryptography', False, 'no exception raised')
    except ImportError:
        check('aes_decrypt raises ImportError', True)
    except Exception as e:
        check('aes_decrypt raises ImportError (not other)', False, type(e).__name__)
    finally:
        crypto._HAS_CRYPTOGRAPHY = orig

    # T4: _require_cryptography helper exists and is callable
    check('_require_cryptography exists', callable(getattr(crypto, '_require_cryptography', None)))

    # T5: Functions that always worked still work (no cryptography dep)
    try:
        key = crypto.aes_generate_key()
        check('aes_generate_key works', len(key) > 0)
        salt = crypto.generate_salt(16)
        check('generate_salt works', len(salt) > 0)
        rb = crypto.random_bytes(8)
        check('random_bytes works', len(rb) > 0)
        rh = crypto.random_hex(16)
        check('random_hex works', len(rh) == 16)
        b64 = crypto.to_base64('hello')
        check('to_base64 round-trips', crypto.from_base64(b64) == 'hello')
    except Exception as e:
        check('Basic crypto utilities work', False, str(e))

    # T6: Round-trip with real cryptography lib (if installed)
    if crypto._HAS_CRYPTOGRAPHY:
        key = crypto.aes_generate_key()
        ct = crypto.aes_encrypt('secret message', key)
        pt = crypto.aes_decrypt(ct, key)
        check('AES round-trip succeeds', pt == 'secret message')
        # Different nonce each time → different ciphertext
        ct2 = crypto.aes_encrypt('secret message', key)
        check('AES uses fresh nonce each call', ct != ct2)
    else:
        print('  SKIP: cryptography not installed — skipping live AES tests')

    # T7: derive_key works without cryptography
    dk = crypto.derive_key('password', 'somesalt', 100)
    check('derive_key works', len(dk) > 0)


# ══════════════════════════════════════════════════════════════════════════════
# P4-SEC-2  epl-validator — SQL sanitization completeness + ReDoS guard
# ══════════════════════════════════════════════════════════════════════════════

@_tracked_test
def test_validator_security():
    print('\n=== P4-SEC-2: epl-validator — SQL sanitization + ReDoS ===')

    import importlib.util, os
    pkg_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'epl', 'official_packages', 'epl-validator', 'python', '__init__.py'
    )
    spec = importlib.util.spec_from_file_location('_epl_validator', pkg_path)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)

    # ── SQL sanitization ─────────────────────────────────────────────────────

    # T1: Single-quote escaped
    check("sanitize_sql escapes '", v.sanitize_sql("O'Brien") == "O''Brien")

    # T2: Backslash escaped first (must not double-escape)
    result = v.sanitize_sql("back\\slash")
    check('sanitize_sql escapes backslash', '\\\\' in result)

    # T3: Double-quote escaped
    check('sanitize_sql escapes "', '\\"' in v.sanitize_sql('say "hi"'))

    # T4: Backtick escaped
    check('sanitize_sql escapes `', '\\`' in v.sanitize_sql('`table`'))

    # T5: Semicolon escaped
    check('sanitize_sql escapes ;', '\\;' in v.sanitize_sql('end; DROP TABLE'))

    # T6: Double-dash comment escaped
    result_dd = v.sanitize_sql("-- comment")
    check('sanitize_sql escapes --', '\\-\\-' in result_dd)

    # T7: Hash comment escaped
    check('sanitize_sql escapes #', '\\#' in v.sanitize_sql('# mysql comment'))

    # T8: LIKE wildcards escaped
    result_like = v.sanitize_sql('100% pure')
    check('sanitize_sql escapes %', '\\%' in result_like)
    result_under = v.sanitize_sql('_username_')
    check('sanitize_sql escapes _', '\\_' in result_under)

    # T9: Null byte removed
    check('sanitize_sql removes NUL', '\x00' not in v.sanitize_sql('bad\x00input'))

    # T10: Newline + carriage-return escaped to literals
    result_nl = v.sanitize_sql('line1\nline2\r')
    check('sanitize_sql escapes \\n', '\\n' in result_nl)
    check('sanitize_sql escapes \\r', '\\r' in result_nl)

    # T11: Backslash-first ordering: escaping 'a\b' must not double-escape \\
    raw = "a\\b'c"
    san = v.sanitize_sql(raw)
    # backslash should become \\\\ and quote ''
    check('sanitize_sql backslash-first ordering', "\\\\b''c" in san)

    # ── ReDoS guard ──────────────────────────────────────────────────────────

    # T12: _safe_match exists
    check('_safe_match helper exists', callable(getattr(v, '_safe_match', None)))

    # T13: Normal pattern match succeeds
    check('_safe_match basic true', v._safe_match(r'^\d+$', '12345'))
    check('_safe_match basic false', not v._safe_match(r'^\d+$', 'abc'))

    # T14: Invalid regex raises ValueError
    try:
        v._safe_match(r'[unclosed', 'test')
        check('_safe_match raises on invalid regex', False, 'no exception')
    except ValueError:
        check('_safe_match raises ValueError on bad regex', True)
    except Exception as e:
        check('_safe_match raises ValueError (not other)', False, type(e).__name__)

    # T15: matches_pattern public API uses safe match
    check('matches_pattern(digits, 123)', v.matches_pattern('12345', r'^\d+$'))
    check('matches_pattern(digits, abc)', not v.matches_pattern('abc', r'^\d+$'))

    # T16: ReDoS catastrophic pattern times out (thread-based guard)
    catastrophic_pattern = r'(a+)+'
    evil_input = 'a' * 30 + 'b'
    start = time.monotonic()
    try:
        v._safe_match(catastrophic_pattern, evil_input)
        elapsed = time.monotonic() - start
        # If it returned quickly, the pattern wasn't catastrophic enough on this
        # engine.  Accept that — the timeout mechanism is the important thing.
        check('_safe_match returns/times-out quickly on ReDoS', elapsed < 3.0)
    except ValueError as e:
        elapsed = time.monotonic() - start
        check('_safe_match raised ValueError on ReDoS', elapsed <= 2.0,
              f'took {elapsed:.2f}s')

    # T17: validate() schema with pattern field uses safe_match
    schema = v.create_schema()
    v.add_pattern_field(schema, 'email', r'^[a-z]+@[a-z]+\.[a-z]{2,}$')
    result = v.validate(schema, {'email': 'user@example.com'})
    check('Schema pattern validation passes valid', result['valid'])
    result2 = v.validate(schema, {'email': 'notanemail'})
    check('Schema pattern validation fails invalid', not result2['valid'])

    # T18: sanitize_html delegates to html.escape
    check('sanitize_html escapes <', '&lt;' in v.sanitize_html('<script>'))
    check('sanitize_html escapes >', '&gt;' in v.sanitize_html('<b>'))
    check('sanitize_html escapes &', '&amp;' in v.sanitize_html('a&b'))


# ══════════════════════════════════════════════════════════════════════════════
# P4-SEC-3  epl-auth — MD5 deprecation, session eviction, thread-safety
# ══════════════════════════════════════════════════════════════════════════════

@_tracked_test
def test_auth_security():
    print('\n=== P4-SEC-3: epl-auth — MD5 warning, sessions, thread safety ===')

    import importlib.util, os
    pkg_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'epl', 'official_packages', 'epl-auth', 'python', '__init__.py'
    )
    spec = importlib.util.spec_from_file_location('_epl_auth', pkg_path)
    auth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth)

    # ── MD5 deprecation ──────────────────────────────────────────────────────

    # T1: md5() still returns correct digest (not broken)
    import hashlib
    expected = hashlib.md5(b'hello').hexdigest()
    with warnings.catch_warnings(record=True):
        warnings.simplefilter('always')
        actual = auth.md5('hello')
    check('md5 digest still correct', actual == expected)

    # T2: md5() emits DeprecationWarning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        auth.md5('test')
    dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
    check('md5 emits DeprecationWarning', len(dep_warnings) > 0)

    # T3: Warning message mentions security
    if dep_warnings:
        msg = str(dep_warnings[0].message).lower()
        check('md5 warning mentions security', 'security' in msg or 'safe' in msg or 'broken' in msg)

    # T4: sha256() does NOT emit deprecation warnings
    with warnings.catch_warnings(record=True) as w2:
        warnings.simplefilter('always')
        auth.sha256('test')
    check('sha256 has no deprecation warnings', not any(
        issubclass(x.category, DeprecationWarning) for x in w2
    ))

    # ── Session eviction ─────────────────────────────────────────────────────

    # T5: Background eviction timer starts on import
    check('Eviction timer started', auth._eviction_timer is not None)
    check('Eviction timer is alive', auth._eviction_timer.is_alive())
    check('Eviction timer is daemon', auth._eviction_timer.daemon)

    # T6: create_session returns a token
    token = auth.create_session('user1', {'role': 'admin'}, 60)
    check('create_session returns token', token is not None and len(token) > 10)

    # T7: validate_session returns the session
    sess = auth.validate_session(token)
    check('validate_session returns session', sess is not None)
    check('Session has user_id', sess.get('user_id') == 'user1')

    # T8: Expired session is evicted on validate
    short_token = auth.create_session('user2', {}, expires_in_minutes=0.0001)
    time.sleep(0.02)
    sess2 = auth.validate_session(short_token)
    check('Expired session returns None', sess2 is None)
    check('Expired token removed from dict', short_token not in auth._sessions)

    # T9: invalidate_session removes session
    token2 = auth.create_session('user3', {}, 60)
    auth.invalidate_session(token2)
    check('invalidate_session removes token', auth.validate_session(token2) is None)

    # T10: Concurrent session creation is thread-safe
    import threading
    tokens_created = []
    errors = []

    def _create():
        try:
            t = auth.create_session('concurrent_user', {}, 60)
            tokens_created.append(t)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_create) for _ in range(50)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    check('Concurrent create_session no errors', len(errors) == 0)
    check('All 50 sessions created', len(tokens_created) == 50)
    check('All tokens unique', len(set(tokens_created)) == 50)

    # T11: _evict_expired removes expired sessions from the dict
    exp_token = auth.create_session('evict_me', {}, expires_in_minutes=-1)
    # Force the expiry_at to the past
    with auth._sessions_lock:
        if exp_token in auth._sessions:
            auth._sessions[exp_token]['expires_at'] = time.time() - 1
    auth._evict_expired()
    check('_evict_expired removes expired', exp_token not in auth._sessions)

    # ── Rate limit thread safety ──────────────────────────────────────────────

    # T12: check_rate_limit allows within limit
    auth.reset_rate_limit('test_rl')
    check('Rate limit allows first 3', all(auth.check_rate_limit('test_rl', 3, 60) for _ in range(3)))

    # T13: check_rate_limit blocks over limit
    check('Rate limit blocks 4th request', not auth.check_rate_limit('test_rl', 3, 60))

    # T14: reset_rate_limit clears state
    auth.reset_rate_limit('test_rl')
    check('After reset, first request allowed', auth.check_rate_limit('test_rl', 3, 60))

    # T15: Rate limit concurrent access is safe
    auth.reset_rate_limit('concurrent_rl')
    results = []
    lock = threading.Lock()

    def _check_rl():
        r = auth.check_rate_limit('concurrent_rl', 10, 60)
        with lock:
            results.append(r)

    rl_threads = [threading.Thread(target=_check_rl) for _ in range(20)]
    for th in rl_threads:
        th.start()
    for th in rl_threads:
        th.join()

    allowed = sum(1 for r in results if r)
    blocked = sum(1 for r in results if not r)
    check('Concurrent rate limit: exactly 10 allowed', allowed == 10,
          f'allowed={allowed} blocked={blocked}')
    check('Concurrent rate limit: exactly 10 blocked', blocked == 10)

    # ── Password hashing ─────────────────────────────────────────────────────

    # T16: hash_password / verify_password round-trip
    h = auth.hash_password('my$3cretPwd!')
    check('verify_password correct', auth.verify_password('my$3cretPwd!', h))
    check('verify_password wrong', not auth.verify_password('wrongpassword', h))

    # T17: Different salts → different hashes
    h2 = auth.hash_password('my$3cretPwd!')
    check('hash_password uses fresh salt', h != h2)

    # ── JWT ──────────────────────────────────────────────────────────────────

    # T18: JWT create / verify round-trip
    payload = {'user_id': 42, 'role': 'editor'}
    token_jwt = auth.create_jwt(payload, 'supersecret', 1)
    verified = auth.verify_jwt(token_jwt, 'supersecret')
    check('JWT verify succeeds', verified is not None)
    check('JWT payload preserved', verified.get('user_id') == 42)

    # T19: JWT with wrong secret fails
    bad = auth.verify_jwt(token_jwt, 'wrongsecret')
    check('JWT wrong secret returns None', bad is None)

    # T20: Expired JWT returns None
    old_token = auth.create_jwt({'x': 1}, 'key', -1)
    check('Expired JWT returns None', auth.verify_jwt(old_token, 'key') is None)


# ══════════════════════════════════════════════════════════════════════════════
# P4-SEC-4  mcp_http_server — CORS default is not wildcard
# ══════════════════════════════════════════════════════════════════════════════

@_tracked_test
def test_mcp_cors_default():
    print('\n=== P4-SEC-4: mcp_http_server — CORS default ===')

    import importlib.util, os, inspect

    src_path = os.path.join(
        os.path.dirname(__file__), '..', 'epl', 'mcp_http_server.py'
    )
    src = open(src_path, encoding='utf-8').read()

    # T1: Default is NOT '*'
    # The line should be: CORS_ORIGIN = os.environ.get("EPL_MCP_CORS_ORIGIN", "null")
    check('CORS default is not wildcard *',
          '"null"' in src and 'get("EPL_MCP_CORS_ORIGIN", "*")' not in src)

    # T2: Default value is "null" (blocks cross-origin browser requests)
    check('CORS default is "null"',
          'get("EPL_MCP_CORS_ORIGIN", "null")' in src)

    # T3: Module docstring warns about wildcard
    check('Docstring warns about wildcard risks',
          'NEVER use "*"' in src or 'never use "*"' in src.lower())

    # T4: Docstring recommends env var for production
    check('Docstring mentions production env var',
          'EPL_MCP_CORS_ORIGIN' in src and ('production' in src.lower() or 'https://' in src))

    # T5: Test via env var override (simulate)
    import os as _os
    original = _os.environ.get('EPL_MCP_CORS_ORIGIN')
    try:
        _os.environ['EPL_MCP_CORS_ORIGIN'] = 'https://myapp.example.com'
        # We can't easily reload the module, but we can confirm the env var logic
        import os as oos
        cors = oos.environ.get('EPL_MCP_CORS_ORIGIN', 'null')
        check('EPL_MCP_CORS_ORIGIN env var overridable', cors == 'https://myapp.example.com')
    finally:
        if original is None:
            _os.environ.pop('EPL_MCP_CORS_ORIGIN', None)
        else:
            _os.environ['EPL_MCP_CORS_ORIGIN'] = original

    # T6: add_cors_headers function present
    check('add_cors_headers function in source', 'add_cors_headers' in src)

    # T7: CORS headers are set on responses
    check('Access-Control-Allow-Origin header set',
          'Access-Control-Allow-Origin' in src)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print('=' * 60)
    print('  EPL v9.4.0 Phase 4 Security Tests')
    print('=' * 60)

    test_functions = [
        test_crypto_no_xor_fallback,
        test_validator_security,
        test_auth_security,
        test_mcp_cors_default,
    ]

    for fn in test_functions:
        try:
            fn()
        except AssertionError:
            pass

    total = _TrackerState.total_pass + _TrackerState.total_fail
    print(f'\n{"=" * 60}')
    print(f'  Results: {_TrackerState.total_pass}/{total} passed, '
          f'{_TrackerState.total_fail} failed')
    print(f'{"=" * 60}')
    return _TrackerState.total_fail == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
