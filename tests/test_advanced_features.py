"""Tests for EPL v4.1 Advanced Features

Tests all 6 new features:
1. Pluggable store/session backends (Memory, SQLite, Redis stub)
2. Cross-platform server (Waitress/Gunicorn detect)
3. WebSocket in ASGI adapter
4. Hot-reload file watcher
5. Python callable route handlers
6. Advanced template engine (30+ filters, ternary, set)
"""
import sys
import os
import time
import json
import threading
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASSED = 0
FAILED = 0

def test(name):
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
test.__test__ = False


# ═══════════════════════════════════════════════════════════
# 1. Store Backends
# ═══════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n--- Store Backends (Memory) ---")
    
    @test("memory_store_add_get")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        store.store_add("items", "apple")
        store.store_add("items", "banana")
        assert store.store_get("items") == ["apple", "banana"]
    
    @test("memory_store_remove")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        store.store_add("items", "a")
        store.store_add("items", "b")
        store.store_add("items", "c")
        store.store_remove("items", 1)
        assert store.store_get("items") == ["a", "c"]
    
    @test("memory_store_clear")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        store.store_add("items", "x")
        store.store_clear("items")
        assert store.store_count("items") == 0
    
    @test("memory_store_count")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        assert store.store_count("empty") == 0
        store.store_add("items", "x")
        store.store_add("items", "y")
        assert store.store_count("items") == 2
    
    @test("memory_store_empty_get")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        assert store.store_get("nonexistent") == []
    
    @test("memory_store_thread_safe")
    def _():
        from epl.store_backends import MemoryStoreBackend
        store = MemoryStoreBackend()
        errors = []
        def add_items():
            for i in range(100):
                try:
                    store.store_add("concurrent", f"item_{i}")
                except Exception as e:
                    errors.append(e)
        threads = [threading.Thread(target=add_items) for _ in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(errors) == 0
        assert store.store_count("concurrent") == 400
    
    
    print("\n--- Session Backends (Memory) ---")
    
    @test("memory_session_create")
    def _():
        from epl.store_backends import MemorySessionBackend
        sess = MemorySessionBackend()
        sid = sess.create(timeout=3600)
        assert isinstance(sid, str)
        assert len(sid) == 64  # hex(32)
    
    @test("memory_session_get_set")
    def _():
        from epl.store_backends import MemorySessionBackend
        sess = MemorySessionBackend()
        sid = sess.create()
        sess.set(sid, "user", "alice")
        assert sess.get(sid, "user") == "alice"
        assert sess.get(sid, "missing", "default") == "default"
    
    @test("memory_session_exists")
    def _():
        from epl.store_backends import MemorySessionBackend
        sess = MemorySessionBackend()
        sid = sess.create()
        assert sess.exists(sid) is True
        assert sess.exists("fake") is False
    
    @test("memory_session_delete")
    def _():
        from epl.store_backends import MemorySessionBackend
        sess = MemorySessionBackend()
        sid = sess.create()
        sess.set(sid, "key", "val")
        sess.delete(sid)
        assert sess.exists(sid) is False
        assert sess.get(sid, "key") is None
    
    @test("memory_session_expiry")
    def _():
        from epl.store_backends import MemorySessionBackend
        sess = MemorySessionBackend()
        sid = sess.create(timeout=1)
        sess.set(sid, "key", "val")
        # Manually expire
        sess._sessions[sid]['_expires'] = time.time() - 10
        assert sess.get(sid, "key") is None
    
    
    print("\n--- Store Backends (SQLite) ---")
    
    @test("sqlite_store_add_get")
    def _():
        from epl.store_backends import SQLiteStoreBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            store = SQLiteStoreBackend(path)
            store.store_add("items", "apple")
            store.store_add("items", "banana")
            result = store.store_get("items")
            assert result == ["apple", "banana"], f"Got {result}"
            store.close()
        finally:
            os.unlink(path)
    
    @test("sqlite_store_remove")
    def _():
        from epl.store_backends import SQLiteStoreBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            store = SQLiteStoreBackend(path)
            store.store_add("items", "a")
            store.store_add("items", "b")
            store.store_add("items", "c")
            store.store_remove("items", 1)
            assert store.store_get("items") == ["a", "c"]
            store.close()
        finally:
            os.unlink(path)
    
    @test("sqlite_store_clear")
    def _():
        from epl.store_backends import SQLiteStoreBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            store = SQLiteStoreBackend(path)
            store.store_add("items", "x")
            store.store_clear("items")
            assert store.store_count("items") == 0
            store.close()
        finally:
            os.unlink(path)
    
    @test("sqlite_store_persistence")
    def _():
        from epl.store_backends import SQLiteStoreBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            # Write data
            store1 = SQLiteStoreBackend(path)
            store1.store_add("persist", "data1")
            store1.store_add("persist", "data2")
            store1.close()
            # Read from fresh instance
            store2 = SQLiteStoreBackend(path)
            result = store2.store_get("persist")
            assert result == ["data1", "data2"], f"Got {result}"
            store2.close()
        finally:
            os.unlink(path)
    
    
    print("\n--- Session Backends (SQLite) ---")
    
    @test("sqlite_session_create_get_set")
    def _():
        from epl.store_backends import SQLiteSessionBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            sess = SQLiteSessionBackend(path)
            sid = sess.create(timeout=3600)
            sess.set(sid, "name", "alice")
            assert sess.get(sid, "name") == "alice"
            assert sess.get(sid, "missing", "def") == "def"
            sess.close()
        finally:
            os.unlink(path)
    
    @test("sqlite_session_delete")
    def _():
        from epl.store_backends import SQLiteSessionBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            sess = SQLiteSessionBackend(path)
            sid = sess.create()
            sess.set(sid, "key", "val")
            sess.delete(sid)
            assert sess.exists(sid) is False
            sess.close()
        finally:
            os.unlink(path)
    
    @test("sqlite_session_exists")
    def _():
        from epl.store_backends import SQLiteSessionBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            sess = SQLiteSessionBackend(path)
            sid = sess.create()
            assert sess.exists(sid) is True
            assert sess.exists("nonexistent") is False
            sess.close()
        finally:
            os.unlink(path)
    
    
    print("\n--- Configure Backends ---")
    
    @test("configure_backends_memory")
    def _():
        from epl.store_backends import configure_backends, get_store_backend, get_session_backend, MemoryStoreBackend, MemorySessionBackend
        configure_backends(store='memory', session='memory')
        assert isinstance(get_store_backend(), MemoryStoreBackend)
        assert isinstance(get_session_backend(), MemorySessionBackend)
    
    @test("configure_backends_sqlite")
    def _():
        from epl.store_backends import configure_backends, get_store_backend, get_session_backend, SQLiteStoreBackend, SQLiteSessionBackend
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            store_path = f.name
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            session_path = f.name
        try:
            configure_backends(store='sqlite', session='sqlite',
                              sqlite_store_path=store_path,
                              sqlite_session_path=session_path)
            assert isinstance(get_store_backend(), SQLiteStoreBackend)
            assert isinstance(get_session_backend(), SQLiteSessionBackend)
        finally:
            # Close backends before cleanup
            get_store_backend().close()
            get_session_backend().close()
            # Reset to memory
            configure_backends(store='memory', session='memory')
            try:
                os.unlink(store_path)
            except OSError:
                pass
            try:
                os.unlink(session_path)
            except OSError:
                pass
    
    @test("web_store_delegates_to_backend")
    def _():
        from epl.store_backends import configure_backends, get_store_backend
        configure_backends(store='memory', session='memory')
        from epl.web import store_add, store_get, store_count, store_clear
        store_clear("test_delegation")
        store_add("test_delegation", "item1")
        assert store_get("test_delegation") == ["item1"]
        assert store_count("test_delegation") == 1
        store_clear("test_delegation")
    
    @test("web_session_delegates_to_backend")
    def _():
        from epl.store_backends import configure_backends
        configure_backends(store='memory', session='memory')
        from epl.web import session_create, session_get, session_set
        sid = session_create()
        session_set(sid, "user", "bob")
        assert session_get(sid, "user") == "bob"
    
    
    # ═══════════════════════════════════════════════════════════
    # 2. Cross-Platform Server Detection
    # ═══════════════════════════════════════════════════════════
    print("\n--- Cross-Platform Server ---")
    
    @test("serve_function_exists")
    def _():
        from epl.deploy import serve
        assert callable(serve)
    
    @test("serve_wraps_eplwebapp_in_wsgi")
    def _():
        from epl.web import EPLWebApp
        from epl.deploy import WSGIAdapter
        app = EPLWebApp("test")
        wsgi = WSGIAdapter(app)
        assert callable(wsgi)
    
    @test("fallback_serve_exists")
    def _():
        from epl.deploy import _fallback_serve
        assert callable(_fallback_serve)
    
    
    # ═══════════════════════════════════════════════════════════
    # 3. WebSocket in ASGI Adapter
    # ═══════════════════════════════════════════════════════════
    print("\n--- ASGI WebSocket ---")
    
    @test("asgi_adapter_handles_websocket_scope")
    def _():
        import asyncio
        from epl.web import EPLWebApp
        from epl.deploy import ASGIAdapter
        
        app = EPLWebApp("ws_test")
        messages_received = []
    
        def ws_handler(ws):
            pass  # Simple handler
    
        app.on_websocket("/ws/chat", ws_handler)
        adapter = ASGIAdapter(app)
    
        # The adapter should handle websocket scope type
        scope = {'type': 'websocket', 'path': '/ws/chat', 'headers': []}
    
        async def run():
            received = []
            async def receive():
                if not received:
                    received.append(True)
                    return {'type': 'websocket.connect'}
                return {'type': 'websocket.disconnect'}
            
            sent = []
            async def send(msg):
                sent.append(msg)
            
            await adapter(scope, receive, send)
            return sent
    
        sent = asyncio.run(run())
        # Should have sent websocket.accept
        assert any(m.get('type') == 'websocket.accept' for m in sent), f"Expected accept, got {sent}"
    
    @test("asgi_websocket_class_exists")
    def _():
        from epl.deploy import _ASGIWebSocket
        assert _ASGIWebSocket is not None
    
    @test("asgi_websocket_no_handler_closes")
    def _():
        import asyncio
        from epl.web import EPLWebApp
        from epl.deploy import ASGIAdapter
    
        app = EPLWebApp("ws_test2")
        adapter = ASGIAdapter(app)
    
        scope = {'type': 'websocket', 'path': '/ws/nonexistent', 'headers': []}
    
        async def run():
            async def receive():
                return {'type': 'websocket.connect'}
            sent = []
            async def send(msg):
                sent.append(msg)
            await adapter(scope, receive, send)
            return sent
    
        sent = asyncio.run(run())
        assert any(m.get('type') == 'websocket.close' for m in sent)
    
    @test("asgi_websocket_dict_handler")
    def _():
        import asyncio
        from epl.web import EPLWebApp
        from epl.deploy import ASGIAdapter
    
        app = EPLWebApp("ws_dict_test")
        events = []
    
        def on_open(ws):
            events.append('open')
        def on_message(ws, msg):
            events.append(f'msg:{msg}')
        def on_close(ws):
            events.append('close')
    
        app.on_websocket("/ws/dict", {
            'on_open': on_open,
            'on_message': on_message,
            'on_close': on_close,
        })
        adapter = ASGIAdapter(app)
        scope = {'type': 'websocket', 'path': '/ws/dict', 'headers': []}
    
        async def run():
            # In ASGI, receive() returns websocket.receive messages after accept
            msg_queue = [
                {'type': 'websocket.receive', 'text': 'hello'},
                {'type': 'websocket.disconnect'},
            ]
            idx = [0]
            async def receive():
                if idx[0] < len(msg_queue):
                    m = msg_queue[idx[0]]
                    idx[0] += 1
                    return m
                return {'type': 'websocket.disconnect'}
            
            sent = []
            async def send(msg):
                sent.append(msg)
    
            await adapter(scope, receive, send)
            return sent
    
        asyncio.run(run())
        assert 'open' in events
        assert 'msg:hello' in events
        assert 'close' in events
    
    
    # ═══════════════════════════════════════════════════════════
    # 4. Hot Reload
    # ═══════════════════════════════════════════════════════════
    print("\n--- Hot Reload ---")
    
    @test("file_watcher_creates")
    def _():
        from epl.hot_reload import FileWatcher
        watcher = FileWatcher(watch_dirs=['.'], patterns=['*.py'])
        assert watcher is not None
    
    @test("file_watcher_matches_patterns")
    def _():
        from epl.hot_reload import FileWatcher
        watcher = FileWatcher(patterns=['*.py', '*.epl'])
        assert watcher._matches('test.py') is True
        assert watcher._matches('app.epl') is True
        assert watcher._matches('data.txt') is False
        assert watcher._matches('style.css') is False
    
    @test("file_watcher_scans_directory")
    def _():
        from epl.hot_reload import FileWatcher
        watcher = FileWatcher(watch_dirs=['.'], patterns=['*.py'])
        snapshot = watcher._scan()
        assert len(snapshot) > 0  # Should find .py files in workspace
    
    @test("file_watcher_detects_change")
    def _():
        from epl.hot_reload import FileWatcher
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'test.py')
            with open(test_file, 'w') as f:
                f.write('# initial')
            
            watcher = FileWatcher(watch_dirs=[tmpdir], patterns=['*.py'])
            changes = []
            watcher.on_change(lambda files: changes.extend(files))
            
            # Take initial snapshot
            watcher._snapshots = watcher._scan()
            
            # Modify file
            time.sleep(0.1)
            with open(test_file, 'w') as f:
                f.write('# modified')
            # Force different mtime (Windows has 2s resolution sometimes)
            os.utime(test_file, (time.time() + 2, time.time() + 2))
            
            watcher._check()
            assert len(changes) > 0
    
    @test("hot_reloader_creates")
    def _():
        from epl.hot_reload import HotReloader
        reloader = HotReloader(watch_dirs=['.'], patterns=['*.py'])
        assert reloader is not None
    
    @test("file_watcher_start_stop")
    def _():
        from epl.hot_reload import FileWatcher
        watcher = FileWatcher(watch_dirs=['.'], patterns=['*.py'], interval=0.5)
        watcher.start()
        assert watcher._running is True
        watcher.stop()
        assert watcher._running is False
    
    
    # ═══════════════════════════════════════════════════════════
    # 5. Python Callable Route Handlers
    # ═══════════════════════════════════════════════════════════
    print("\n--- Callable Route Handlers ---")
    
    @test("callable_route_registration")
    def _():
        from epl.web import EPLWebApp, Request
        app = EPLWebApp("callable_test")
        def my_handler(req):
            return {"status": "ok"}
        app.add_route("/api/test", "callable", my_handler, method='GET')
        route = app.get_route("/api/test", 'GET')
        assert route is not None
        rtype, body, params = route
        assert rtype == 'callable'
        assert body is my_handler
    
    @test("callable_handler_returns_dict")
    def _():
        from epl.web import EPLWebApp, Request, Response
        app = EPLWebApp("callable_dict")
        def handler(req):
            return {"items": [1, 2, 3]}
        app.add_route("/api/items", "callable", handler)
        route = app.get_route("/api/items", 'GET')
        rtype, body, params = route
        req = Request(method='GET', path='/api/items', app=app)
        result = body(req)
        assert result == {"items": [1, 2, 3]}
    
    @test("callable_handler_returns_string")
    def _():
        from epl.web import EPLWebApp, Request
        app = EPLWebApp("callable_str")
        def handler(req):
            return "<h1>Hello</h1>"
        app.add_route("/page", "callable", handler)
        route = app.get_route("/page", 'GET')
        rtype, body, params = route
        req = Request(method='GET', path='/page', app=app)
        result = body(req)
        assert result == "<h1>Hello</h1>"
    
    @test("callable_handler_returns_response")
    def _():
        from epl.web import EPLWebApp, Request, Response
        app = EPLWebApp("callable_resp")
        def handler(req):
            resp = Response(status=201)
            resp.json_body({"created": True})
            return resp
        app.add_route("/api/create", "callable", handler, method='POST')
        route = app.get_route("/api/create", 'POST')
        rtype, body, params = route
        req = Request(method='POST', path='/api/create', app=app)
        result = body(req)
        assert isinstance(result, Response)
        assert result.status == 201
    
    @test("callable_handler_access_request")
    def _():
        from epl.web import EPLWebApp, Request
        app = EPLWebApp("callable_req")
        def handler(req):
            return {"method": req.method, "path": req.path}
        app.add_route("/api/echo", "callable", handler)
        req = Request(method='GET', path='/api/echo', app=app)
        result = handler(req)
        assert result["method"] == "GET"
        assert result["path"] == "/api/echo"
    
    @test("callable_with_param_route")
    def _():
        from epl.web import EPLWebApp, Request
        app = EPLWebApp("callable_param")
        def handler(req):
            return {"id": req.params.get("id")}
        app.add_route("/api/users/:id", "callable", handler, method='GET')
        route = app.get_route("/api/users/42", 'GET')
        assert route is not None
        rtype, body, params = route
        assert rtype == 'callable'
        assert params.get('id') == '42'
    
    @test("callable_wsgi_adapter")
    def _():
        from epl.web import EPLWebApp, Request, Response
        from epl.deploy import WSGIAdapter
        import io
    
        app = EPLWebApp("wsgi_callable")
        def handler(req):
            return {"hello": "world"}
        app.add_route("/api/hello", "callable", handler)
    
        wsgi = WSGIAdapter(app)
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/api/hello',
            'QUERY_STRING': '',
            'REMOTE_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'wsgi.input': io.BytesIO(b''),
        }
        status_holder = []
        def start_response(status, headers, exc_info=None):
            status_holder.append(status)
        
        result = wsgi(environ, start_response)
        body = b''.join(result).decode('utf-8')
        assert '200' in status_holder[0]
        data = json.loads(body)
        assert data["hello"] == "world"
    
    @test("callable_wsgi_response_obj")
    def _():
        from epl.web import EPLWebApp, Request, Response
        from epl.deploy import WSGIAdapter
        import io
    
        app = EPLWebApp("wsgi_callable_resp")
        def handler(req):
            resp = Response(status=201)
            resp.json_body({"created": True})
            resp.set_header('X-Custom', 'test')
            return resp
        app.add_route("/api/create", "callable", handler, method='POST')
    
        wsgi = WSGIAdapter(app)
        environ = {
            'REQUEST_METHOD': 'POST',
            'PATH_INFO': '/api/create',
            'QUERY_STRING': '',
            'REMOTE_ADDR': '127.0.0.1',
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': '8000',
            'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': '2',
            'wsgi.input': io.BytesIO(b'{}'),
        }
        status_holder = []
        headers_holder = []
        def start_response(status, headers, exc_info=None):
            status_holder.append(status)
            headers_holder.extend(headers)
        
        result = wsgi(environ, start_response)
        assert '201' in status_holder[0]
        custom = [v for k, v in headers_holder if k == 'X-Custom']
        assert custom == ['test']
    
    
    # ═══════════════════════════════════════════════════════════
    # 6. Advanced Template Engine
    # ═══════════════════════════════════════════════════════════
    print("\n--- Template Engine: Filters ---")
    
    @test("filter_upper")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|upper }}", {"name": "alice"})
        assert result == "ALICE"
    
    @test("filter_lower")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|lower }}", {"name": "ALICE"})
        assert result == "alice"
    
    @test("filter_title")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|title }}", {"name": "hello world"})
        assert result == "Hello World"
    
    @test("filter_capitalize")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|capitalize }}", {"name": "hello"})
        assert result == "Hello"
    
    @test("filter_strip")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|strip }}", {"name": "  hello  "})
        assert result == "hello"
    
    @test("filter_length")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|length }}", {"items": [1, 2, 3]})
        assert result == "3"
    
    @test("filter_reverse_string")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|reverse }}", {"name": "hello"})
        assert result == "olleh"
    
    @test("filter_reverse_list")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|reverse }}", {"items": [1, 2, 3]})
        assert result == "[3, 2, 1]"
    
    @test("filter_first")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|first }}", {"items": ["a", "b", "c"]})
        assert result == "a"
    
    @test("filter_last")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|last }}", {"items": ["a", "b", "c"]})
        assert result == "c"
    
    @test("filter_sort")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|sort }}", {"items": [3, 1, 2]})
        assert result == "[1, 2, 3]"
    
    @test("filter_join")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|join:, }}", {"items": ["a", "b", "c"]})
        assert result == "a,b,c"  # colon-delimited arg: separator is ','
    
    @test("filter_join_custom_sep")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ items|join:- }}", {"items": ["x", "y"]})
        assert result == "x-y"
    
    @test("filter_truncate")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ text|truncate:10 }}", {"text": "Hello World this is long"})
        assert result == "Hello Worl..."
    
    @test("filter_truncate_short")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ text|truncate:100 }}", {"text": "Short"})
        assert result == "Short"
    
    @test("filter_default")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ missing|default:N/A }}", {})
        assert result == "N/A"
    
    @test("filter_default_nonempty")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|default:anon }}", {"name": "alice"})
        assert result == "alice"
    
    @test("filter_replace")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ text|replace:world:earth }}", {"text": "hello world"})
        assert result == "hello earth"
    
    @test("filter_url_encode")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ q|url_encode }}", {"q": "hello world&foo=bar"})
        assert "hello%20world" in result
        assert "%26" in result  # & encoded
    
    @test("filter_nl2br")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ text|nl2br }}", {"text": "line1\nline2"})
        assert "<br>" in result
        assert "line1" in result
        assert "line2" in result
    
    @test("filter_json")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ data|json }}", {"data": {"key": "value"}})
        parsed = json.loads(result)
        assert parsed == {"key": "value"}
    
    @test("filter_abs")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ num|abs }}", {"num": -42})
        assert result == "42"
    
    @test("filter_int")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ num|int }}", {"num": "42.7"})
        assert result == "42"
    
    @test("filter_float")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ num|float }}", {"num": "3"})
        assert result == "3.0"
    
    @test("filter_round")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ num|round:2 }}", {"num": 3.14159})
        assert result == "3.14"
    
    @test("filter_safe_no_escape")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ html|safe }}", {"html": "<b>bold</b>"})
        assert result == "<b>bold</b>"
    
    @test("filter_chain_multiple")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ name|upper|truncate:3 }}", {"name": "hello"})
        assert result == "HEL..."
    
    @test("auto_escape_without_filter")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ text }}", {"text": "<script>alert(1)</script>"})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
    
    
    print("\n--- Template Engine: Ternary & Set ---")
    
    @test("template_ternary")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ yes if active else no }}", 
                                      {"active": True, "yes": "ON", "no": "OFF"})
        assert result == "ON"
    
    @test("template_ternary_false")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{{ yes if active else no }}",
                                      {"active": False, "yes": "ON", "no": "OFF"})
        assert result == "OFF"
    
    @test("template_ternary_string_literal")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string('{{ "Yes" if active else "No" }}',
                                      {"active": True})
        assert result == "Yes"
    
    @test("template_set_variable")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string('{% set greeting = "Hello" %}{{ greeting }}', {})
        assert result == "Hello"
    
    @test("template_set_number")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string('{% set count = 42 %}{{ count }}', {})
        assert result == "42"
    
    @test("template_set_from_var")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string('{% set name = user %}Hello {{ name }}',
                                      {"user": "alice"})
        assert result == "Hello alice"
    
    
    print("\n--- Template Engine: Existing Features ---")
    
    @test("template_for_loop")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{% for item in items %}{{ item }} {% endfor %}",
                                      {"items": ["a", "b", "c"]})
        assert "a" in result and "b" in result and "c" in result
    
    @test("template_if_else")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string(
            "{% if show %}visible{% else %}hidden{% endif %}",
            {"show": True}
        )
        assert result == "visible"
    
    @test("template_extends_blocks")
    def _():
        from epl.web import TemplateEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base template
            with open(os.path.join(tmpdir, 'base.html'), 'w') as f:
                f.write('<html>{% block content %}default{% endblock %}</html>')
            # Create child template
            child = '{% extends "base.html" %}{% block content %}custom{% endblock %}'
            engine = TemplateEngine(template_dir=tmpdir)
            result = engine.render_string(child, {})
            assert '<html>custom</html>' == result
    
    @test("template_include")
    def _():
        from epl.web import TemplateEngine
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'partial.html'), 'w') as f:
                f.write('INCLUDED')
            engine = TemplateEngine(template_dir=tmpdir)
            result = engine.render_string('Before {% include "partial.html" %} After', {})
            assert 'Before INCLUDED After' == result
    
    @test("template_raw")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string("{% raw %}{{ not_processed }}{% endraw %}", {})
        assert result == "{{ not_processed }}"
    
    @test("template_loop_context")
    def _():
        from epl.web import TemplateEngine
        engine = TemplateEngine()
        result = engine.render_string(
            "{% for i in items %}{{ loop.index1 }}{% endfor %}",
            {"items": ["a", "b", "c"]}
        )
        assert "1" in result and "2" in result and "3" in result
    
    
    # ═══════════════════════════════════════════════════════════
    # 7. EPLWebApp.configure_backends
    # ═══════════════════════════════════════════════════════════
    print("\n--- EPLWebApp.configure_backends ---")
    
    @test("app_configure_backends_method")
    def _():
        from epl.web import EPLWebApp
        app = EPLWebApp("test")
        assert hasattr(app, 'configure_backends')
        result = app.configure_backends(store='memory', session='memory')
        assert result is app  # returns self for chaining
    
    
    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'=' * 60}")
    print(f"  Advanced Features Tests: {PASSED}/{PASSED + FAILED} passed, {FAILED} failed")
    if FAILED == 0:
        print("  All tests passed!")
    else:
        print("  SOME TESTS FAILED")
    print(f"{'=' * 60}")
    return FAILED == 0


def test_advanced_features_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Advanced features suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
