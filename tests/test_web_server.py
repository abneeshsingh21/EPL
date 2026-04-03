"""Comprehensive tests for EPL Web Server v4.0 production features."""
import os
import sys
import json
import time
import tempfile
import threading
import hashlib
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASSED = 0
FAILED = 0


def register_case(name):
    """Decorator to run/track a test."""
    def decorator(fn):
        global PASSED, FAILED
        try:
            fn()
            print(f"  PASS: {name}")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: {name} -> {e}")
            FAILED += 1
        return fn
    return decorator


# ═══════════════════════════════════════════════════════════
# 1. Connection Pool
# ═══════════════════════════════════════════════════════════

def main():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n--- Connection Pool ---")
    
    @register_case("pool_create_and_get")
    def _():
        from epl.web import ConnectionPool
        tmp = os.path.join(tempfile.gettempdir(), 'test_pool_1.db')
        pool = ConnectionPool(tmp)
        conn = pool.get()
        assert conn is not None
        # Same thread → same connection
        conn2 = pool.get()
        assert conn is conn2
        pool.close_all()
    
    @register_case("pool_thread_isolation")
    def _():
        from epl.web import ConnectionPool
        tmp = os.path.join(tempfile.gettempdir(), 'test_pool_2.db')
        pool = ConnectionPool(tmp)
        main_conn = pool.get()
        other_conn = [None]
        def worker():
            other_conn[0] = pool.get()
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        # Different threads get different connections
        assert other_conn[0] is not main_conn
        pool.close_all()
    
    @register_case("pool_wal_mode")
    def _():
        from epl.web import ConnectionPool
        tmp = os.path.join(tempfile.gettempdir(), 'test_pool_wal.db')
        pool = ConnectionPool(tmp)
        conn = pool.get()
        mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
        assert mode == 'wal', f"Expected WAL, got {mode}"
        pool.close_all()
    
    @register_case("pool_concurrent_writes")
    def _():
        from epl.web import ConnectionPool
        tmp = os.path.join(tempfile.gettempdir(), 'test_pool_concurrent.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        pool = ConnectionPool(tmp)
        conn = pool.get()
        conn.execute('CREATE TABLE IF NOT EXISTS test_concurrent (id INTEGER PRIMARY KEY, val TEXT)')
        conn.commit()
        errors = []
        def writer(n):
            try:
                c = pool.get()
                for i in range(10):
                    c.execute('INSERT INTO test_concurrent (val) VALUES (?)', (f'thread_{n}_{i}',))
                    c.commit()
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert not errors, f"Concurrent write errors: {errors}"
        count = conn.execute('SELECT COUNT(*) FROM test_concurrent').fetchone()[0]
        assert count == 40, f"Expected 40 rows, got {count}"
        pool.close_all()
    
    @register_case("init_db_uses_pool")
    def _():
        import epl.web as web_mod
        tmp = os.path.join(tempfile.gettempdir(), 'test_init_pool.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        web_mod.init_db(tmp)
        assert web_mod._db_pool is not None
        conn = web_mod._get_db()
        assert conn is not None
        # Verify tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert 'epl_store' in table_names
        assert 'epl_sessions' in table_names
    
    
    # ═══════════════════════════════════════════════════════════
    # 2. Request / Response Objects
    # ═══════════════════════════════════════════════════════════
    print("\n--- Request / Response ---")
    
    @register_case("request_basic")
    def _():
        from epl.web import Request
        req = Request(method='POST', path='/api/users?page=2&limit=10',
                      headers={'Content-Type': 'application/json', 'Cookie': 'epl_session=abc123'})
        assert req.method == 'POST'
        assert req.path == '/api/users'
        assert req.query == {'page': '2', 'limit': '10'}
        assert req.cookies == {'epl_session': 'abc123'}
        assert req.client_ip == '127.0.0.1'
    
    @register_case("request_json_body")
    def _():
        from epl.web import Request
        body = json.dumps({'name': 'Alice', 'age': 30}).encode()
        req = Request(method='POST', path='/api', headers={'Content-Type': 'application/json'},
                      body_raw=body)
        data = req.json()
        assert data == {'name': 'Alice', 'age': 30}
        # Calling again returns cached
        assert req.json() is data
    
    @register_case("request_cookie_parsing")
    def _():
        from epl.web import Request
        req = Request(headers={'Cookie': 'a=1; b=two; session=xyz123'})
        assert req.cookies == {'a': '1', 'b': 'two', 'session': 'xyz123'}
    
    @register_case("response_json")
    def _():
        from epl.web import Response
        resp = Response()
        resp.json_body({'users': [1, 2, 3]})
        assert resp.status == 200
        assert 'json' in resp.content_type
        body = resp.encode()
        parsed = json.loads(body.decode())
        assert parsed['users'] == [1, 2, 3]
    
    @register_case("response_html")
    def _():
        from epl.web import Response
        resp = Response()
        resp.html_body('<h1>Hello</h1>')
        assert 'html' in resp.content_type
        assert b'<h1>Hello</h1>' in resp.encode()
    
    @register_case("response_redirect")
    def _():
        from epl.web import Response
        resp = Response()
        resp.redirect('/dashboard', status=302)
        assert resp.status == 302
        assert resp.headers['Location'] == '/dashboard'
    
    @register_case("response_cookies")
    def _():
        from epl.web import Response
        resp = Response()
        resp.set_cookie('token', 'abc', max_age=7200, httponly=True, secure=True, samesite='Lax')
        assert len(resp._cookies) == 1
        c = resp._cookies[0]
        assert 'token=abc' in c
        assert 'Max-Age=7200' in c
        assert 'HttpOnly' in c
        assert 'Secure' in c
        assert 'SameSite=Lax' in c
    
    @register_case("response_chain")
    def _():
        from epl.web import Response
        resp = Response()
        r = resp.set_header('X-Custom', 'value').set_cookie('a', 'b')
        assert r is resp  # method chaining
        assert resp.headers['X-Custom'] == 'value'
    
    
    # ═══════════════════════════════════════════════════════════
    # 3. Blueprint System
    # ═══════════════════════════════════════════════════════════
    print("\n--- Blueprint ---")
    
    @register_case("blueprint_register")
    def _():
        from epl.web import EPLWebApp, Blueprint
        app = EPLWebApp("bp_test")
        api = Blueprint('/api/v1')
        api.route('/health', 'json', [], method='GET')
        api.route('/users', 'json', [], method='POST')
        app.register_blueprint(api)
        assert app.get_route('/api/v1/health', 'GET') is not None
        assert app.get_route('/api/v1/users', 'POST') is not None
    
    @register_case("blueprint_middleware")
    def _():
        from epl.web import EPLWebApp, Blueprint
        app = EPLWebApp("bp_mw")
        bp = Blueprint('/admin')
        log = []
        bp.add_middleware('auth', before_fn=lambda r: log.append('auth'))
        app.register_blueprint(bp)
        assert len(app.middleware) == 1
    
    @register_case("blueprint_error_handler")
    def _():
        from epl.web import EPLWebApp, Blueprint
        app = EPLWebApp("bp_err")
        bp = Blueprint('/api')
        bp.on_error(404, lambda: 'not found')
        app.register_blueprint(bp)
        assert 404 in app.error_handlers
    
    @register_case("multiple_blueprints")
    def _():
        from epl.web import EPLWebApp, Blueprint
        app = EPLWebApp("multi_bp")
        api_v1 = Blueprint('/api/v1')
        api_v1.route('/data', 'json', [], method='GET')
        api_v2 = Blueprint('/api/v2')
        api_v2.route('/data', 'json', [], method='GET')
        app.register_blueprint(api_v1)
        app.register_blueprint(api_v2)
        assert app.get_route('/api/v1/data', 'GET') is not None
        assert app.get_route('/api/v2/data', 'GET') is not None
    
    
    # ═══════════════════════════════════════════════════════════
    # 4. Template Engine
    # ═══════════════════════════════════════════════════════════
    print("\n--- Template Engine ---")
    
    @register_case("template_variable")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        assert t.render_string('Hello {{ name }}!', {'name': 'World'}) == 'Hello World!'
    
    @register_case("template_auto_escape")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string('{{ text }}', {'text': '<script>xss</script>'})
        assert '&lt;script&gt;' in result
        assert '<script>' not in result
    
    @register_case("template_safe_filter")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string('{{ html|safe }}', {'html': '<b>bold</b>'})
        assert result == '<b>bold</b>'
    
    @register_case("template_for_loop")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string(
            '{% for item in items %}[{{ item }}]{% endfor %}',
            {'items': ['a', 'b', 'c']}
        )
        assert result == '[a][b][c]'
    
    @register_case("template_for_loop_index")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string(
            '{% for x in nums %}{{ loop.index1 }}:{{ x }} {% endfor %}',
            {'nums': [10, 20, 30]}
        )
        assert '1:10' in result
        assert '2:20' in result
        assert '3:30' in result
    
    @register_case("template_if_true")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        assert t.render_string('{% if show %}visible{% endif %}', {'show': True}) == 'visible'
    
    @register_case("template_if_false")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        assert t.render_string('{% if show %}visible{% endif %}', {'show': False}) == ''
    
    @register_case("template_if_else")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string(
            '{% if admin %}admin{% else %}user{% endif %}',
            {'admin': False}
        )
        assert result == 'user'
    
    @register_case("template_if_comparison")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string(
            '{% if role == "admin" %}yes{% else %}no{% endif %}',
            {'role': 'admin'}
        )
        assert result == 'yes'
    
    @register_case("template_not_condition")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string(
            '{% if not logged_in %}login{% else %}dashboard{% endif %}',
            {'logged_in': False}
        )
        assert result == 'login'
    
    @register_case("template_dot_notation")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string('{{ user.name }}', {'user': {'name': 'Alice'}})
        assert result == 'Alice'
    
    @register_case("template_raw_block")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string('{% raw %}{{ not_a_variable }}{% endraw %}', {})
        assert '{{ not_a_variable }}' in result
    
    @register_case("template_missing_variable")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine()
        result = t.render_string('Hello {{ missing }}!', {})
        assert result == 'Hello !'
    
    @register_case("template_extends_and_blocks")
    def _():
        from epl.web import TemplateEngine
        tmp_dir = tempfile.mkdtemp()
        # Create base template
        with open(os.path.join(tmp_dir, 'base.html'), 'w') as f:
            f.write('<html>{% block title %}Default{% endblock %} {% block body %}{% endblock %}</html>')
        # Create child template
        with open(os.path.join(tmp_dir, 'page.html'), 'w') as f:
            f.write('{% extends "base.html" %}{% block title %}My Page{% endblock %}{% block body %}Content{% endblock %}')
        t = TemplateEngine(template_dir=tmp_dir)
        result = t.render('page.html', {})
        assert 'My Page' in result
        assert 'Content' in result
        assert '<html>' in result
    
    @register_case("template_include")
    def _():
        from epl.web import TemplateEngine
        tmp_dir = tempfile.mkdtemp()
        with open(os.path.join(tmp_dir, 'header.html'), 'w') as f:
            f.write('<nav>{{ site_name }}</nav>')
        with open(os.path.join(tmp_dir, 'page.html'), 'w') as f:
            f.write('{% include "header.html" %}<main>Hello</main>')
        t = TemplateEngine(template_dir=tmp_dir)
        result = t.render('page.html', {'site_name': 'MySite'})
        assert '<nav>MySite</nav>' in result
        assert '<main>Hello</main>' in result
    
    @register_case("template_path_traversal_blocked")
    def _():
        from epl.web import TemplateEngine
        t = TemplateEngine(template_dir='templates')
        result = t.render('../../../etc/passwd', {})
        assert 'access denied' in result.lower() or 'not found' in result.lower()
    
    @register_case("template_nesting_depth_limit")
    def _():
        from epl.web import TemplateEngine
        tmp_dir = tempfile.mkdtemp()
        # Create self-including template
        with open(os.path.join(tmp_dir, 'infinite.html'), 'w') as f:
            f.write('{% include "infinite.html" %}')
        t = TemplateEngine(template_dir=tmp_dir)
        result = t.render('infinite.html', {})
        assert 'depth exceeded' in result.lower()
    
    @register_case("template_file_caching")
    def _():
        from epl.web import TemplateEngine
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, 'cached.html')
        with open(path, 'w') as f:
            f.write('v1')
        t = TemplateEngine(template_dir=tmp_dir)
        assert t.render('cached.html') == 'v1'
        # Modify (same mtime sometimes on fast systems, so force different content check)
        time.sleep(0.1)
        with open(path, 'w') as f:
            f.write('v2')
        result = t.render('cached.html')
        # Should detect change via mtime
        assert result == 'v2'
    
    
    # ═══════════════════════════════════════════════════════════
    # 5. Health Check & Metrics
    # ═══════════════════════════════════════════════════════════
    print("\n--- Health Check ---")
    
    @register_case("health_check_response")
    def _():
        from epl import __version__
        from epl.web import EPLWebApp
        app = EPLWebApp("health_test")
        h = app.health_check()
        assert h['status'] == 'healthy'
        assert h['version'] == __version__
        assert 'uptime_seconds' in h
        assert 'total_requests' in h
        assert 'total_errors' in h
    
    @register_case("health_check_metrics_track")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("metrics_test")
        app._metrics['requests'] = 100
        app._metrics['errors'] = 5
        h = app.health_check()
        assert h['total_requests'] == 100
        assert h['total_errors'] == 5
    
    
    # ═══════════════════════════════════════════════════════════
    # 6. EPLWebApp Enhanced Features
    # ═══════════════════════════════════════════════════════════
    print("\n--- EPLWebApp Enhanced ---")
    
    @register_case("app_before_request_hook")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("hooks")
        calls = []
        @app.before_request
        def log_request(req):
            calls.append('before')
        assert len(app.before_request_hooks) == 1
    
    @register_case("app_after_request_hook")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("hooks2")
        @app.after_request
        def add_header(req, resp):
            return resp
        assert len(app.after_request_hooks) == 1
    
    @register_case("app_teardown_hook")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("teardown")
        @app.teardown
        def cleanup(exc):
            pass
        assert len(app.teardown_hooks) == 1
    
    @register_case("app_render_template")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("tmpl_test")
        tmp_dir = tempfile.mkdtemp()
        app.template_engine.template_dir = tmp_dir
        with open(os.path.join(tmp_dir, 'hello.html'), 'w') as f:
            f.write('Hello {{ user_name }}!')
        result = app.render_template('hello.html', user_name='EPL')
        assert result == 'Hello EPL!'
    
    @register_case("app_custom_health_path")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("custom_health")
        app._health_path = '/healthz'
        assert app._health_path == '/healthz'
    
    
    # ═══════════════════════════════════════════════════════════
    # 7. Security Features
    # ═══════════════════════════════════════════════════════════
    print("\n--- Security ---")
    
    @register_case("password_pbkdf2")
    def _():
        from epl.web import hash_password, verify_password
        h = hash_password("test_pass_123")
        assert '$' in h  # salt$hash format
        assert verify_password("test_pass_123", h)
        assert not verify_password("wrong", h)
        assert not verify_password("", h)
    
    @register_case("password_unique_salts")
    def _():
        from epl.web import hash_password
        h1 = hash_password("same_pass")
        h2 = hash_password("same_pass")
        # Different salts → different hashes
        assert h1 != h2
    
    @register_case("csrf_token_generation")
    def _():
        from epl.web import csrf_token, session_create, session_get
        sid = session_create()
        token = csrf_token(sid)
        stored = session_get(sid, '_csrf_token')
        assert stored == token
        assert len(token) == 64
    
    @register_case("sanitize_html_xss")
    def _():
        from epl.web import sanitize_html
        # Script tag
        assert '<script>' not in sanitize_html('<script>alert(1)</script>')
        # Event handlers
        assert 'onerror' not in sanitize_html('<img onerror="alert(1)">')
        # Safe tags preserved
        result = sanitize_html('<b>bold</b> <em>italic</em>')
        assert '<b>' in result
        assert '<em>' in result
    
    @register_case("sanitize_html_safe_links")
    def _():
        from epl.web import sanitize_html
        result = sanitize_html('<a href="https://example.com">link</a>')
        assert 'https://example.com' in result
        # JavaScript protocol blocked
        result2 = sanitize_html('<a href="javascript:alert(1)">bad</a>')
        assert 'javascript:' not in result2
    
    @register_case("validate_email_patterns")
    def _():
        from epl.web import validate_email
        assert validate_email("user@example.com")
        assert validate_email("user.name+tag@domain.co.uk")
        assert not validate_email("invalid")
        assert not validate_email("@domain.com")
        assert not validate_email("user@")
        assert not validate_email("")
    
    
    # ═══════════════════════════════════════════════════════════
    # 8. Session Management
    # ═══════════════════════════════════════════════════════════
    print("\n--- Sessions ---")
    
    @register_case("session_create_secure")
    def _():
        from epl.web import session_create
        sid = session_create()
        assert len(sid) == 64  # 32 bytes hex
    
    @register_case("session_get_set")
    def _():
        from epl.web import session_create, session_get, session_set
        sid = session_create()
        session_set(sid, 'username', 'alice')
        assert session_get(sid, 'username') == 'alice'
        assert session_get(sid, 'missing') is None
        assert session_get(sid, 'missing', 'default') == 'default'
    
    @register_case("session_expiry")
    def _():
        from epl.web import session_get, session_set, session_create
        from epl.store_backends import get_session_backend
        backend = get_session_backend()
        # Create a session and manually expire it
        fake_sid = 'expired_session_test'
        if hasattr(backend, '_sessions'):
            # Memory backend — inject expired session directly
            backend._sessions[fake_sid] = {'_expires': time.time() - 10, 'key': 'val'}
            result = session_get(fake_sid, 'key')
            assert result is None  # expired
        else:
            # Other backends — just verify non-existent session returns None
            result = session_get(fake_sid, 'key')
            assert result is None
    
    
    # ═══════════════════════════════════════════════════════════
    # 9. WebSocket
    # ═══════════════════════════════════════════════════════════
    print("\n--- WebSocket ---")
    
    @register_case("websocket_room_create")
    def _():
        from epl.web import get_ws_room
        room = get_ws_room('test_room')
        assert room.name == 'test_room'
        assert room.count == 0
    
    @register_case("websocket_room_singleton")
    def _():
        from epl.web import get_ws_room
        room1 = get_ws_room('shared')
        room2 = get_ws_room('shared')
        assert room1 is room2
    
    @register_case("websocket_app_handler")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("ws_test")
        handler = {'on_open': lambda ws: None, 'on_close': lambda ws: None}
        app.on_websocket('/ws', handler)
        assert '/ws' in app.websocket_handlers
    
    
    # ═══════════════════════════════════════════════════════════
    # 10. Rate Limiter
    # ═══════════════════════════════════════════════════════════
    print("\n--- Rate Limiter ---")
    
    @register_case("rate_limit_allow")
    def _():
        from epl.web import _check_rate_limit, _rate_tracker
        _rate_tracker.clear()
        assert _check_rate_limit('1.2.3.4', 100)
    
    @register_case("rate_limit_block")
    def _():
        from epl.web import _check_rate_limit, _rate_tracker
        _rate_tracker.clear()
        ip = '10.0.0.99'
        for _ in range(5):
            _check_rate_limit(ip, 5)
        assert not _check_rate_limit(ip, 5)
    
    @register_case("rate_limit_disabled")
    def _():
        from epl.web import _check_rate_limit
        assert _check_rate_limit('any', 0)
    
    
    # ═══════════════════════════════════════════════════════════
    # 11. Store Operations
    # ═══════════════════════════════════════════════════════════
    print("\n--- Store ---")
    
    @register_case("store_crud")
    def _():
        from epl.web import store_add, store_get, store_remove, store_count, store_clear, _data_store
        _data_store.pop('test_coll', None)
        store_add('test_coll', 'item1')
        store_add('test_coll', 'item2')
        assert store_count('test_coll') == 2
        assert store_get('test_coll') == ['item1', 'item2']
        store_remove('test_coll', 0)
        assert store_get('test_coll') == ['item2']
        store_clear('test_coll')
        assert store_count('test_coll') == 0
    
    @register_case("db_store_crud")
    def _():
        from epl.web import init_db, db_store_add, db_store_get, db_store_count, db_store_clear
        tmp = os.path.join(tempfile.gettempdir(), 'test_db_crud.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        init_db(tmp)
        db_store_clear('test_db')
        db_store_add('test_db', {'name': 'alice'})
        db_store_add('test_db', {'name': 'bob'})
        items = db_store_get('test_db')
        assert len(items) == 2
        assert items[0]['name'] == 'alice'
        count = db_store_count('test_db')
        assert count == 2
        db_store_clear('test_db')
        assert db_store_count('test_db') == 0
    
    
    # ═══════════════════════════════════════════════════════════
    # 12. Async Server Structure
    # ═══════════════════════════════════════════════════════════
    print("\n--- Async Server ---")
    
    @register_case("async_server_create")
    def _():
        from epl.web import AsyncEPLServer, EPLWebApp
        app = EPLWebApp("async_test")
        server = AsyncEPLServer(app, port=9999)
        assert server.port == 9999
        assert server.app is app
        assert server._executor is not None
        assert server._active_connections == 0
    
    @register_case("async_server_workers")
    def _():
        from epl.web import AsyncEPLServer, EPLWebApp
        app = EPLWebApp("async_workers")
        server = AsyncEPLServer(app, workers=16)
        assert server.workers == 16
    
    @register_case("async_server_error_html")
    def _():
        from epl.web import AsyncEPLServer, EPLWebApp
        app = EPLWebApp("async_err")
        server = AsyncEPLServer(app)
        html = server._error_html(404, 'Not Found')
        assert '404' in html
        assert 'Not Found' in html
        assert '<script>' not in html  # XSS safe
    
    @register_case("async_server_xss_safe_error")
    def _():
        from epl.web import AsyncEPLServer, EPLWebApp
        app = EPLWebApp("xss_test")
        server = AsyncEPLServer(app)
        html = server._error_html(400, '<script>alert(1)</script>')
        assert '<script>' not in html
        assert '&lt;script&gt;' in html
    
    
    # ═══════════════════════════════════════════════════════════
    # 13. Threaded Server Structure  
    # ═══════════════════════════════════════════════════════════
    print("\n--- Threaded Server ---")
    
    @register_case("threaded_server_class")
    def _():
        from epl.web import ThreadedHTTPServer
        assert ThreadedHTTPServer.daemon_threads is True
        assert ThreadedHTTPServer.allow_reuse_address is True
    
    
    # ═══════════════════════════════════════════════════════════
    # 14. Auth System
    # ═══════════════════════════════════════════════════════════
    print("\n--- Auth System ---")
    
    @register_case("auth_register_login")
    def _():
        from epl.web import init_db, register_user, authenticate_user
        tmp = os.path.join(tempfile.gettempdir(), 'test_auth.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        init_db(tmp)
        uid = register_user('testuser', 'pass123', 'test@example.com')
        assert uid is not None
        # Duplicate
        uid2 = register_user('testuser', 'pass', 'other@example.com')
        assert uid2 is None
        # Login
        user = authenticate_user('testuser', 'pass123')
        assert user is not None
        assert user['username'] == 'testuser'
        # Wrong password
        assert authenticate_user('testuser', 'wrong') is None
        # Non-existent user
        assert authenticate_user('nouser', 'pass') is None
    
    @register_case("auth_login_session")
    def _():
        import epl.web as web_mod
        from epl.web import register_user, login_user, get_current_user, session_create
        tmp = os.path.join(tempfile.gettempdir(), 'test_auth_session.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        web_mod._users_table_created = False
        web_mod.init_db(tmp)
        register_user('alice', 'secret', 'alice@test.com')
        old_sid = session_create()
        new_sid, user = login_user(old_sid, 'alice', 'secret')
        assert user is not None
        assert new_sid != old_sid  # session regenerated
        current = get_current_user(new_sid)
        assert current['username'] == 'alice'
    
    @register_case("auth_logout")
    def _():
        import epl.web as web_mod
        from epl.web import register_user, login_user, logout_user, get_current_user, session_create
        tmp = os.path.join(tempfile.gettempdir(), 'test_auth_logout.db')
        if os.path.exists(tmp):
            os.remove(tmp)
        web_mod._users_table_created = False
        web_mod.init_db(tmp)
        register_user('bob', 'pass456')
        sid = session_create()
        new_sid, _ = login_user(sid, 'bob', 'pass456')
        assert get_current_user(new_sid) is not None
        logout_user(new_sid)
        assert get_current_user(new_sid) is None
    
    
    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"  Web Server v4.0 Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    if FAILED == 0:
        print(f"  All tests passed!")
    else:
        print(f"  SOME TESTS FAILED")
    print(f"{'='*60}")
    return FAILED == 0


def test_web_server_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Web server suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
    
