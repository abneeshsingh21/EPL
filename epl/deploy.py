"""EPL Production Deployment Module (v4.0)

Provides production deployment adapters and config generators:
- WSGI adapter (Gunicorn, uWSGI, mod_wsgi)
- ASGI adapter (Uvicorn, Daphne, Hypercorn)
- Nginx reverse proxy config generator
- Gunicorn config generator
- Tomcat AJP/HTTP proxy config generator  
- Docker/docker-compose generator
- Systemd service file generator
- Production health monitoring
"""
import json
import os
import re
import time
import secrets
import textwrap
import urllib.parse
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

_logger = logging.getLogger('epl.deploy')

# ═══════════════════════════════════════════════════════════
# WSGI Adapter — enables Gunicorn / uWSGI / mod_wsgi
# ═══════════════════════════════════════════════════════════

class WSGIAdapter:
    """WSGI-compliant adapter wrapping an EPLWebApp.
    
    Usage with Gunicorn:
        # wsgi.py
        from epl.web import EPLWebApp
        from epl.deploy import WSGIAdapter
        
        app = EPLWebApp("MyApp")
        app.add_route("/", "page", [...])
        application = WSGIAdapter(app)
        
        # Then: gunicorn wsgi:application -w 4 -b 0.0.0.0:8000
    """

    def __init__(self, app, interpreter=None, static_url='/static', static_dir=None):
        self.app = app
        self.interpreter = interpreter
        self.static_url = static_url.rstrip('/')
        self.static_dir = static_dir or app.static_dir
        self._import_web()

    def _import_web(self):
        """Import web module components lazily."""
        from epl.web import (
            _data_store, store_get, store_add, store_remove,
            db_store_add, db_store_get, db_store_remove,
            _check_rate_limit, generate_html, Request, Response
        )
        self._data_store = _data_store
        self._store_get = store_get
        self._store_add = store_add
        self._store_remove = store_remove
        self._db_store_add = db_store_add
        self._db_store_get = db_store_get
        self._db_store_remove = db_store_remove
        self._check_rate_limit = _check_rate_limit
        self._generate_html = generate_html
        self._Request = Request
        self._Response = Response

    def __call__(self, environ, start_response):
        """WSGI entry point — translate environ to Request, route, return Response."""
        import html as _html_mod
        from epl import ast_nodes as ast

        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        query_string = environ.get('QUERY_STRING', '')
        
        # Update metrics
        if self.app:
            self.app._metrics['requests'] += 1

        # Build headers dict from environ
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
        if 'CONTENT_TYPE' in environ:
            headers['Content-Type'] = environ['CONTENT_TYPE']
        if 'CONTENT_LENGTH' in environ:
            headers['Content-Length'] = environ['CONTENT_LENGTH']

        # Read body
        body_raw = b''
        content_length = int(environ.get('CONTENT_LENGTH') or 0)
        if content_length > 0:
            max_body = 10 * 1024 * 1024  # 10MB
            if content_length > max_body:
                return self._error_response(start_response, 413, 'Request body too large')
            body_raw = environ['wsgi.input'].read(content_length)

        client_ip = environ.get('REMOTE_ADDR', '0.0.0.0')
        # Trust X-Forwarded-For behind reverse proxy
        forwarded = headers.get('X-Forwarded-For', '')
        if forwarded:
            client_ip = forwarded.split(',')[0].strip()

        # Health check (fast path)
        clean_path = path.split('?')[0]
        if clean_path == self.app._health_path:
            health = self.app.health_check()
            health['wsgi'] = True
            body = json.dumps(health, indent=2, default=str)
            return self._json_response(start_response, 200, body)

        # Rate limiting
        if self.app.rate_limit > 0:
            if not self._check_rate_limit(client_ip, self.app.rate_limit):
                return self._error_response(start_response, 429, 'Too many requests')

        # Static file serving
        if clean_path.startswith(self.static_url + '/'):
            return self._serve_static(start_response, clean_path, environ)

        # Build Request object
        req = self._Request(
            method=method, path=path, headers=headers,
            body_raw=body_raw, client_ip=client_ip, app=self.app
        )
        req.session_id = req.cookies.get('epl_session')

        # CORS preflight
        if method == 'OPTIONS' and self.app.cors_enabled:
            resp_headers = [
                ('Access-Control-Allow-Origin', self.app.cors_origins),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token'),
            ]
            start_response('200 OK', resp_headers)
            return [b'']

        # Parse body for POST/PUT/DELETE
        form_data = {}
        if method in ('POST', 'PUT', 'DELETE') and body_raw:
            ct = (headers.get('Content-Type') or '').lower()
            if 'json' in ct:
                try:
                    form_data = json.loads(body_raw.decode('utf-8', errors='replace'))
                except (json.JSONDecodeError, ValueError):
                    form_data = {}
            else:
                raw_text = body_raw.decode('utf-8', errors='replace')
                form_data = dict(urllib.parse.parse_qsl(raw_text))

        # Route
        route = self.app.get_route(clean_path, method)
        if not route:
            if method == 'POST':
                route = self.app.get_route(clean_path, 'GET')
            if not route:
                return self._error_response(start_response, 404,
                    f'Route not found: {_html_mod.escape(clean_path)}')

        response_type, route_body, route_params = route
        all_params = dict(urllib.parse.parse_qsl(query_string))
        all_params.update(route_params)
        all_params.update(form_data)

        # Build response
        try:
            if response_type == 'callable':
                # Python callable handler
                result = route_body(req)
                if isinstance(result, self._Response):
                    body_bytes = result.encode()
                    resp_headers = [
                        ('Content-Type', result.content_type),
                        ('Content-Length', str(len(body_bytes))),
                    ] + self._security_headers()
                    for k, v in result.headers.items():
                        resp_headers.append((k, v))
                    for cookie in result._cookies:
                        resp_headers.append(('Set-Cookie', cookie))
                    status_text = {200: '200 OK', 201: '201 Created', 204: '204 No Content',
                                   301: '301 Moved Permanently', 303: '303 See Other',
                                   400: '400 Bad Request', 404: '404 Not Found',
                                   500: '500 Internal Server Error'}.get(result.status, f'{result.status} Unknown')
                    start_response(status_text, resp_headers)
                    resp = [body_bytes]
                elif isinstance(result, dict):
                    body = json.dumps(result, indent=2, default=str)
                    resp = self._json_response(start_response, 200, body)
                elif isinstance(result, str):
                    resp = self._html_response(start_response, 200, result)
                else:
                    resp = self._html_response(start_response, 200, str(result) if result else '<p>OK</p>')
            elif response_type == 'json':
                data = self._build_json(route_body, all_params)
                body = json.dumps(data, indent=2, default=str)
                resp = self._json_response(start_response, 200, body)
            elif response_type == 'page':
                html = self._build_page(route_body, form_data, all_params)
                if html.startswith('REDIRECT:'):
                    location = html[len('REDIRECT:'):]
                    resp = self._redirect_response(start_response, location)
                else:
                    resp = self._html_response(start_response, 200, html)
            elif response_type == 'action':
                result = self._exec_action(route_body, form_data)
                if result and result.startswith('REDIRECT:'):
                    location = result[len('REDIRECT:'):]
                    resp = self._redirect_response(start_response, location)
                else:
                    resp = self._html_response(start_response, 200, result or '<p>OK</p>')
            else:
                resp = self._html_response(start_response, 200, '<p>OK</p>')
        except Exception as e:
            if self.app:
                self.app._metrics['errors'] += 1
            _logger.error(f'Route error: {e}')
            return self._error_response(start_response, 500, 'Internal Server Error')

        return resp

    def _build_page(self, body, form_data, params):
        """Build HTML page response."""
        from epl import ast_nodes as ast
        from epl.web import _data_store
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store(stmt, form_data)
            elif isinstance(stmt, ast.DeleteStatement):
                self._exec_delete(stmt, form_data)
            elif isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{url}'
        for stmt in body:
            if isinstance(stmt, ast.PageDef):
                return self._generate_html(stmt, data_store=_data_store, form_data=form_data)
        from epl import ast_nodes as ast
        elements = [s for s in body if isinstance(s, ast.HtmlElement)]
        if elements:
            page = ast.PageDef("EPL Page", elements)
            return self._generate_html(page, data_store=_data_store, form_data=form_data)
        return self._generate_html(ast.PageDef("EPL Page", []), data_store=_data_store)

    def _build_json(self, body, params):
        """Build JSON response."""
        from epl import ast_nodes as ast
        from epl.web import store_get, _data_store
        for stmt in body:
            if isinstance(stmt, ast.FetchStatement):
                items = store_get(stmt.collection)
                return {"collection": stmt.collection, "count": len(items), "items": items}
            if isinstance(stmt, ast.SendResponse):
                if self.interpreter:
                    try:
                        result = self.interpreter._eval(stmt.data, self.interpreter.global_env)
                        if hasattr(result, 'data'):
                            result = result.data
                        return result
                    except Exception as e:
                        return {"error": str(e)}
        return {"store": {k: list(v) for k, v in _data_store.items()}}

    def _exec_action(self, body, form_data):
        """Execute action route."""
        from epl import ast_nodes as ast
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store(stmt, form_data)
            elif isinstance(stmt, ast.DeleteStatement):
                self._exec_delete(stmt, form_data)
            elif isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{url}'
        return None

    def _exec_store(self, stmt, form_data):
        from epl.web import store_add, db_store_add
        collection = stmt.collection
        if form_data and stmt.field_name:
            value = form_data.get(stmt.field_name, '')
            if self.app.db_enabled:
                db_store_add(collection, value)
            else:
                store_add(collection, value)
        elif stmt.value and self.interpreter:
            try:
                val = self.interpreter._eval(stmt.value, self.interpreter.global_env)
                if self.app.db_enabled:
                    db_store_add(collection, val)
                else:
                    store_add(collection, val)
            except Exception:
                pass

    def _exec_delete(self, stmt, form_data):
        from epl.web import store_remove, db_store_remove
        collection = stmt.collection
        if form_data and 'index' in form_data:
            try:
                index = int(form_data['index'])
                if self.app.db_enabled:
                    db_store_remove(collection, index)
                else:
                    store_remove(collection, index)
            except (ValueError, IndexError):
                pass

    def _serve_static(self, start_response, path, environ):
        """Serve static files via WSGI."""
        import mimetypes
        rel = path[len(self.static_url) + 1:]
        # Prevent path traversal
        safe = os.path.normpath(rel)
        if safe.startswith('..') or os.path.isabs(safe):
            return self._error_response(start_response, 403, 'Forbidden')
        filepath = os.path.join(self.static_dir, safe)
        abs_base = os.path.normpath(os.path.abspath(self.static_dir))
        abs_file = os.path.normpath(os.path.abspath(filepath))
        if not abs_file.startswith(abs_base):
            return self._error_response(start_response, 403, 'Forbidden')
        if not os.path.isfile(filepath):
            return self._error_response(start_response, 404, 'Not Found')
        
        ctype, _ = mimetypes.guess_type(filepath)
        ctype = ctype or 'application/octet-stream'
        with open(filepath, 'rb') as f:
            data = f.read()
        
        start_response('200 OK', [
            ('Content-Type', ctype),
            ('Content-Length', str(len(data))),
            ('Cache-Control', 'public, max-age=86400'),
        ])
        return [data]

    def _security_headers(self):
        """Return common security headers."""
        headers = [
            ('X-Content-Type-Options', 'nosniff'),
            ('X-Frame-Options', 'SAMEORIGIN'),
            ('Referrer-Policy', 'strict-origin-when-cross-origin'),
            ('Permissions-Policy', 'camera=(), microphone=(), geolocation=()'),
        ]
        if self.app.cors_enabled:
            headers.append(('Access-Control-Allow-Origin', self.app.cors_origins))
        return headers

    def _html_response(self, start_response, status, html):
        body = html.encode('utf-8') if isinstance(html, str) else html
        status_text = {200: '200 OK', 201: '201 Created', 204: '204 No Content',
                       400: '400 Bad Request', 404: '404 Not Found',
                       500: '500 Internal Server Error'}.get(status, f'{status} Unknown')
        headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body))),
        ] + self._security_headers()
        start_response(status_text, headers)
        return [body]

    def _json_response(self, start_response, status, body_str):
        body = body_str.encode('utf-8')
        status_text = {200: '200 OK', 201: '201 Created'}.get(status, f'{status} Unknown')
        headers = [
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Content-Length', str(len(body))),
        ] + self._security_headers()
        start_response(status_text, headers)
        return [body]

    def _error_response(self, start_response, status, message):
        import html as _html_mod
        safe = _html_mod.escape(str(message))
        html = (
            f"<!DOCTYPE html><html><head><title>Error {status}</title>"
            f"<style>body{{font-family:system-ui;background:#0f172a;color:#f1f5f9;"
            f"display:flex;justify-content:center;align-items:center;min-height:100vh}}"
            f".err{{text-align:center}}h1{{font-size:4rem;color:#ef4444}}"
            f"p{{color:#94a3b8}}</style></head><body>"
            f'<div class="err"><h1>{status}</h1><p>{safe}</p></div></body></html>'
        )
        body = html.encode('utf-8')
        status_text = {
            400: '400 Bad Request', 403: '403 Forbidden', 404: '404 Not Found',
            413: '413 Payload Too Large', 429: '429 Too Many Requests',
            500: '500 Internal Server Error'
        }.get(status, f'{status} Error')
        start_response(status_text, [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Content-Length', str(len(body))),
        ])
        return [body]

    def _redirect_response(self, start_response, location):
        start_response('303 See Other', [
            ('Location', location),
            ('Content-Length', '0'),
        ])
        return [b'']


# ═══════════════════════════════════════════════════════════
# ASGI Adapter — enables Uvicorn / Daphne / Hypercorn
# ═══════════════════════════════════════════════════════════

class ASGIAdapter:
    """ASGI-compliant adapter wrapping an EPLWebApp.
    
    Usage with Uvicorn:
        # asgi.py
        from epl.web import EPLWebApp
        from epl.deploy import ASGIAdapter
        
        app = EPLWebApp("MyApp")
        app.add_route("/", "page", [...])
        application = ASGIAdapter(app)
        
        # Then: uvicorn asgi:application --host 0.0.0.0 --port 8000 --workers 4
    """

    def __init__(self, app, interpreter=None):
        self.app = app
        self.interpreter = interpreter
        self._wsgi = WSGIAdapter(app, interpreter)
        self._executor = ThreadPoolExecutor(max_workers=32)

    async def __call__(self, scope, receive, send):
        """ASGI entry point."""
        if scope['type'] == 'http':
            await self._handle_http(scope, receive, send)
        elif scope['type'] == 'websocket':
            await self._handle_websocket(scope, receive, send)
        elif scope['type'] == 'lifespan':
            await self._handle_lifespan(scope, receive, send)
        else:
            # Unsupported protocol type
            pass

    async def _handle_http(self, scope, receive, send):
        """Handle HTTP request via ASGI."""
        import asyncio

        method = scope.get('method', 'GET')
        path = scope.get('path', '/')
        query_string = scope.get('query_string', b'').decode('utf-8')
        
        # Build headers dict
        headers = {}
        for name, value in scope.get('headers', []):
            headers[name.decode('latin-1').title()] = value.decode('latin-1')
        
        # Read body
        body = b''
        while True:
            message = await receive()
            body += message.get('body', b'')
            if not message.get('more_body', False):
                break

        # Build WSGI-like environ for reuse
        client = scope.get('client', ('0.0.0.0', 0))
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'QUERY_STRING': query_string,
            'REMOTE_ADDR': client[0] if client else '0.0.0.0',
            'SERVER_NAME': scope.get('server', ('localhost', 8000))[0],
            'SERVER_PORT': str(scope.get('server', ('localhost', 8000))[1]),
            'wsgi.input': _BytesIO(body),
        }
        if 'Content-Type' in headers:
            environ['CONTENT_TYPE'] = headers['Content-Type']
        if 'Content-Length' in headers:
            environ['CONTENT_LENGTH'] = headers['Content-Length']
        elif body:
            environ['CONTENT_LENGTH'] = str(len(body))
        for key, val in headers.items():
            wsgi_key = 'HTTP_' + key.upper().replace('-', '_')
            environ[wsgi_key] = val

        # Run WSGI adapter in thread pool (it may do blocking I/O)
        loop = asyncio.get_event_loop()
        response_started = False
        response_status = '200 OK'
        response_headers = []

        def start_response(status, headers, exc_info=None):
            nonlocal response_started, response_status, response_headers
            response_status = status
            response_headers = headers
            response_started = True

        result = await loop.run_in_executor(
            self._executor,
            self._wsgi.__call__, environ, start_response
        )

        # Parse status code
        status_code = int(response_status.split(' ', 1)[0])
        
        # Convert headers to ASGI format
        asgi_headers = [(k.lower().encode('latin-1'), v.encode('latin-1'))
                        for k, v in response_headers]

        # Send response
        await send({
            'type': 'http.response.start',
            'status': status_code,
            'headers': asgi_headers,
        })

        body_bytes = b''.join(result) if result else b''
        await send({
            'type': 'http.response.body',
            'body': body_bytes,
        })

    async def _handle_lifespan(self, scope, receive, send):
        """Handle ASGI lifespan events (startup/shutdown)."""
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                _logger.info('ASGI lifespan startup')
                await send({'type': 'lifespan.startup.complete'})
            elif message['type'] == 'lifespan.shutdown':
                _logger.info('ASGI lifespan shutdown')
                self._executor.shutdown(wait=False)
                await send({'type': 'lifespan.shutdown.complete'})
                return

    async def _handle_websocket(self, scope, receive, send):
        """Handle WebSocket connections via ASGI."""
        await _asgi_websocket_handler(scope, receive, send, self.app)


class _BytesIO:
    """Minimal file-like object for WSGI environ wsgi.input."""
    def __init__(self, data):
        self._data = data
        self._pos = 0

    def read(self, size=-1):
        if size < 0:
            result = self._data[self._pos:]
            self._pos = len(self._data)
        else:
            result = self._data[self._pos:self._pos + size]
            self._pos += size
        return result


# ─── ASGI WebSocket handler ──────────────────────────────

class _ASGIWebSocket:
    """WebSocket connection wrapper for ASGI WebSocket scope."""

    def __init__(self, send, receive, path):
        self.path = path
        self.is_open = True
        self._send = send
        self._receive = receive
        self._accepted = False

    async def accept(self):
        """Accept the WebSocket connection."""
        if not self._accepted:
            await self._send({'type': 'websocket.accept'})
            self._accepted = True

    async def send(self, message):
        """Send a text message."""
        if not self.is_open:
            return
        if isinstance(message, dict):
            message = json.dumps(message)
        await self._send({
            'type': 'websocket.send',
            'text': str(message)
        })

    async def send_bytes(self, data):
        """Send binary data."""
        if not self.is_open:
            return
        await self._send({
            'type': 'websocket.send',
            'bytes': data
        })

    async def receive(self):
        """Receive a message. Returns text or bytes, or None on close."""
        msg = await self._receive()
        if msg['type'] == 'websocket.receive':
            return msg.get('text') or msg.get('bytes')
        if msg['type'] == 'websocket.disconnect':
            self.is_open = False
            return None
        return None

    async def close(self, code=1000):
        """Close the connection."""
        self.is_open = False
        try:
            await self._send({'type': 'websocket.close', 'code': code})
        except Exception:
            pass


async def _asgi_websocket_handler(scope, receive, send, app):
    """Handle a WebSocket connection via the ASGI protocol."""
    path = scope.get('path', '/')
    handler = app.websocket_handlers.get(path) if app else None

    if not handler:
        await send({'type': 'websocket.close', 'code': 4004})
        return

    ws = _ASGIWebSocket(send, receive, path)
    await ws.accept()

    try:
        if isinstance(handler, dict):
            on_open = handler.get('on_open')
            on_message = handler.get('on_message')
            on_close = handler.get('on_close')
            on_error = handler.get('on_error')

            if on_open:
                result = on_open(ws)
                if asyncio.iscoroutine(result):
                    await result

            while ws.is_open:
                msg = await ws.receive()
                if msg is None:
                    break
                if on_message:
                    try:
                        result = on_message(ws, msg)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        if on_error:
                            result = on_error(ws, e)
                            if asyncio.iscoroutine(result):
                                await result
            if on_close:
                result = on_close(ws)
                if asyncio.iscoroutine(result):
                    await result
        else:
            # Simple handler
            result = handler(ws)
            if asyncio.iscoroutine(result):
                await result
    except Exception as e:
        _logger.error(f'WebSocket handler error: {e}')
    finally:
        ws.is_open = False


# ═══════════════════════════════════════════════════════════
# Cross-Platform Server (Waitress on Windows, Gunicorn on Linux)
# ═══════════════════════════════════════════════════════════

def serve(app_or_wsgi, host='0.0.0.0', port=8000, workers=4, reload=False, engine=None):
    """Start a production WSGI server — auto-detects platform.
    
    - Windows: Uses Waitress (pip install waitress)
    - Linux/macOS: Uses Gunicorn if available, else Waitress
    - reload=True: Enables hot-reload via EPL's file watcher
    
    Args:
        app_or_wsgi: EPLWebApp or WSGIAdapter instance
        host: Bind address
        port: Port number
        workers: Number of workers
        reload: Enable hot-reload (dev mode)
        engine: Force a specific server: 'waitress', 'gunicorn', 'uvicorn', 'builtin'
    """
    import sys
    import platform

    # Wrap EPLWebApp in WSGIAdapter if needed
    from epl.web import EPLWebApp
    if isinstance(app_or_wsgi, EPLWebApp):
        wsgi_app = WSGIAdapter(app_or_wsgi)
    else:
        wsgi_app = app_or_wsgi

    def _start_server():
        is_windows = platform.system() == 'Windows'

        # If engine is explicitly specified, use that
        if engine == 'builtin':
            _fallback_serve(wsgi_app, host, port)
            return
        if engine == 'waitress':
            import waitress
            print(f'\n  EPL Production Server (Waitress)')
            print(f'  Listening on {host}:{port} (workers={workers})')
            print(f'  Press Ctrl+C to stop\n')
            waitress.serve(wsgi_app, host=host, port=port,
                          threads=workers, channel_timeout=120,
                          map_size=100000, url_scheme='http')
            return
        if engine == 'gunicorn':
            _run_gunicorn(wsgi_app, host, port, workers)
            return
        if engine == 'uvicorn':
            import uvicorn
            from epl.deploy import ASGIAdapter
            asgi_app = ASGIAdapter(app_or_wsgi) if not isinstance(app_or_wsgi, ASGIAdapter) else app_or_wsgi
            print(f'\n  EPL Production Server (Uvicorn)')
            print(f'  Listening on {host}:{port} (workers={workers})')
            print(f'  Press Ctrl+C to stop\n')
            uvicorn.run(asgi_app, host=host, port=port, workers=workers)
            return

        # Auto-detect best available server
        if is_windows:
            # Windows: Use Waitress
            try:
                import waitress  # type: ignore[reportMissingModuleSource]
                print(f'\n  EPL Production Server (Waitress)')
                print(f'  Listening on {host}:{port} (workers={workers})')
                print(f'  Press Ctrl+C to stop\n')
                waitress.serve(wsgi_app, host=host, port=port,
                              threads=workers, channel_timeout=120,
                              map_size=100000, url_scheme='http')
            except ImportError:
                print('  Waitress not installed. Install with: pip install waitress')
                print('  Falling back to built-in server...')
                _fallback_serve(wsgi_app, host, port)
        else:
            # Linux/macOS: Try Gunicorn first
            try:
                import gunicorn  # type: ignore[reportMissingModuleSource]
                # Gunicorn needs to be run via command line, not imported
                _run_gunicorn(wsgi_app, host, port, workers)
            except ImportError:
                try:
                    import waitress  # type: ignore[reportMissingModuleSource]
                    print(f'\n  EPL Production Server (Waitress)')
                    print(f'  Listening on {host}:{port} (workers={workers})')
                    print(f'  Press Ctrl+C to stop\n')
                    waitress.serve(wsgi_app, host=host, port=port,
                                  threads=workers, channel_timeout=120)
                except ImportError:
                    print('  No production server found. Install: pip install waitress')
                    print('  Falling back to built-in server...')
                    _fallback_serve(wsgi_app, host, port)

    if reload:
        from epl.hot_reload import HotReloader
        reloader = HotReloader(
            watch_dirs=['.', 'epl', 'templates'],
            patterns=['*.py', '*.epl', '*.html'],
            interval=1.0
        )
        reloader.run_with_reload(_start_server)
    else:
        _start_server()


def _fallback_serve(wsgi_app, host, port):
    """Fallback: use Python's built-in WSGI server."""
    from wsgiref.simple_server import make_server
    print(f'\n  EPL Development Server (wsgiref)')
    print(f'  Listening on {host}:{port}')
    print(f'  WARNING: Not for production use!\n')
    server = make_server(host, port, wsgi_app)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _run_gunicorn(wsgi_app, host, port, workers):
    """Run Gunicorn programmatically."""
    import sys
    import tempfile
    import textwrap
    # SECURITY: Store app on module attribute (Gunicorn --preload shares memory).
    # Eliminates pickle serialization which was a Remote Code Execution risk.
    _mod = sys.modules[__name__]
    _mod._gunicorn_app = wsgi_app

    # Write a temp WSGI entry module that workers can import
    _entry = tempfile.NamedTemporaryFile(mode='w', suffix='_epl_wsgi.py', delete=False, dir='.')
    _entry.write(textwrap.dedent("""\
        import sys
        sys.path.insert(0, '.')
        from epl.deploy import _gunicorn_app as app
    """))
    _entry_name = _entry.name
    _entry.close()

    import subprocess
    cmd = [
        sys.executable, '-m', 'gunicorn',
        '--bind', f'{host}:{port}',
        '--workers', str(workers),
        '--timeout', '120',
        '--preload',
        'epl.deploy:_gunicorn_app'
    ]
    print(f'\n  EPL Production Server (Gunicorn)')
    print(f'  Listening on {host}:{port} (workers={workers})')
    print(f'  Press Ctrl+C to stop\n')
    try:
        subprocess.run(cmd)
    finally:
        try:
            os.unlink(_entry_name)
        except OSError:
            pass


# Global reference for Gunicorn
_gunicorn_app = None


# ═══════════════════════════════════════════════════════════
# Gunicorn Config Generator
# ═══════════════════════════════════════════════════════════

def generate_gunicorn_config(app_name='MyApp', port=8000, workers=None,
                              bind='0.0.0.0', timeout=120, log_level='info',
                              ssl_cert=None, ssl_key=None, max_requests=1000,
                              preload=True):
    """Generate a production-ready gunicorn.conf.py."""
    import multiprocessing
    if workers is None:
        workers = (multiprocessing.cpu_count() * 2) + 1

    config = textwrap.dedent(f'''\
        """Gunicorn configuration for EPL Web Application: {app_name}
        
        Start with:
            gunicorn -c gunicorn_conf.py wsgi:application
        
        Or directly:
            gunicorn wsgi:application -w {workers} -b {bind}:{port}
        """
        import multiprocessing

        # ─── Server Socket ────────────────────────────────
        bind = "{bind}:{port}"
        backlog = 2048

        # ─── Worker Processes ─────────────────────────────
        workers = {workers}
        worker_class = "sync"         # Use "gevent" or "uvicorn.workers.UvicornWorker" for async
        worker_connections = 1000
        max_requests = {max_requests}       # Restart workers after N requests (prevent memory leaks)
        max_requests_jitter = 50    # Add randomness to prevent all workers restarting at once
        timeout = {timeout}              # Worker silent for N seconds → killed
        graceful_timeout = 30       # Seconds for graceful worker shutdown
        keepalive = 5               # Seconds to wait for keep-alive requests

        # ─── Pre-loading ─────────────────────────────────
        preload_app = {preload}          # Load app before forking workers (saves memory)

        # ─── Logging ─────────────────────────────────────
        accesslog = "-"             # "-" = stdout, or file path
        errorlog = "-"
        loglevel = "{log_level}"
        access_log_format = '%%(h)s %%(l)s %%(u)s %%(t)s "%%(r)s" %%(s)s %%(b)s "%%(f)s" "%%(a)s" %%(D)sμs'

        # ─── Process Naming ──────────────────────────────
        proc_name = "epl-{app_name.lower().replace(' ', '-')}"

        # ─── Security ────────────────────────────────────
        limit_request_line = 8190
        limit_request_fields = 100
        limit_request_field_size = 8190
    ''')

    if ssl_cert and ssl_key:
        config += textwrap.dedent(f'''
        # ─── SSL/TLS ─────────────────────────────────────
        certfile = "{ssl_cert}"
        keyfile = "{ssl_key}"
        ssl_version = 5              # TLS 1.2+
        ciphers = "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20"
        ''')

    config += textwrap.dedent('''
        # ─── Server Hooks ────────────────────────────────
        def on_starting(server):
            """Called just before the master process is initialized."""
            pass

        def post_fork(server, worker):
            """Called just after a worker has been forked."""
            server.log.info(f"Worker spawned (pid: {worker.pid})")

        def pre_exec(server):
            """Called just before a new master process is forked."""
            server.log.info("Forked child, re-executing.")

        def when_ready(server):
            """Called just after the server is started."""
            server.log.info("Server is ready. Spawning workers")

        def worker_int(worker):
            """Called when a worker receives SIGINT."""
            worker.log.info("worker received INT or QUIT signal")

        def worker_abort(worker):
            """Called when a worker receives SIGABRT."""
            worker.log.info("worker received SIGABRT signal")
    ''')

    return config


def _resolve_deploy_app(project_root=None, app_file=None):
    """Resolve the project root and EPL entry file used by deployment adapters."""
    from epl.package_manager import find_project_root, load_manifest

    base_dir = os.path.abspath(project_root or os.getcwd())
    project_root = find_project_root(base_dir) or base_dir
    manifest = load_manifest(project_root)

    entry = app_file
    if not entry and manifest:
        entry = manifest.get('entry')
    if not entry:
        for candidate in ('src/main.epl', 'main.epl', 'app.epl'):
            if os.path.isfile(os.path.join(project_root, candidate)):
                entry = candidate
                break
    if not entry:
        entry = 'app.epl'

    if os.path.isabs(entry):
        app_path = os.path.normpath(entry)
    else:
        app_path = os.path.normpath(os.path.join(project_root, entry))

    return project_root, app_path


def _relative_deploy_path(target_path, base_dir):
    """Return a portable path from base_dir to target_path when possible."""
    target_path = os.path.abspath(target_path)
    base_dir = os.path.abspath(base_dir)
    try:
        relpath = os.path.relpath(target_path, base_dir)
    except ValueError:
        relpath = target_path
    return relpath.replace('\\', '/')


def _resolve_runtime_subdir(project_root, output_dir):
    """Return the deploy runtime subdir when output_dir sits inside project_root."""
    relpath = _relative_deploy_path(output_dir, project_root)
    if relpath in ('.', '') or relpath.startswith('../'):
        return '.'
    return relpath


def generate_requirements_txt(manifest=None, epl_requirement=None):
    """Generate Python requirements for Docker/runtime deployment."""
    from epl import __version__ as epl_version

    manifest = manifest or {}
    if epl_requirement is None:
        epl_requirement = f'epl-lang>={epl_version}'

    requirements = [str(epl_requirement).strip(), 'gunicorn>=21.2']
    python_deps = manifest.get('python-dependencies', {}) or {}
    for import_name, requirement in sorted(python_deps.items()):
        normalized = str(requirement).strip() if requirement is not None else ''
        if not normalized or normalized == '*':
            normalized = str(import_name).strip()
        if normalized and normalized not in requirements:
            requirements.append(normalized)

    return '\n'.join(requirements) + '\n'


def generate_wsgi_entry(app_module='app', app_var='app', app_file=None, project_root='.'):
    """Generate wsgi.py entry point for Gunicorn."""
    if app_file is None:
        app_file = f'{app_module}.epl'
    app_file_literal = json.dumps(app_file)
    project_root_literal = json.dumps(project_root or '.')

    return textwrap.dedent(f'''\
        """WSGI entry point for EPL web application.
        
        Usage:
            gunicorn wsgi:application -w 4 -b 0.0.0.0:8000
            gunicorn -c gunicorn_conf.py wsgi:application
        """
        from pathlib import Path
        import os
        import sys

        from epl.web import EPLWebApp
        from epl.deploy import WSGIAdapter
        from epl.interpreter import Interpreter
        from epl.lexer import Lexer
        from epl.parser import Parser

        APP_FILE = Path({app_file_literal})
        PROJECT_ROOT = Path({project_root_literal})

        def _resolve_candidates(path_value):
            raw = Path(path_value)
            candidates = []
            if raw.is_absolute():
                candidates.append(raw)
            else:
                base_dir = Path(__file__).resolve().parent
                candidates.append((base_dir / raw).resolve())
                candidates.append((Path.cwd() / raw).resolve())
            candidates.append(raw)

            resolved = []
            seen = set()
            for candidate in candidates:
                try:
                    key = str(candidate.resolve()) if candidate.exists() else str(candidate)
                except OSError:
                    key = str(candidate)
                if key not in seen:
                    seen.add(key)
                    resolved.append(candidate)
            return resolved

        for _root in _resolve_candidates(PROJECT_ROOT):
            if _root.exists():
                _root_str = str(_root)
                if _root_str not in sys.path:
                    sys.path.insert(0, _root_str)

        # ─── Load your EPL application ───────────────────
        # Option 1: Load from .epl file
        def _find_web_app(env):
            for binding in getattr(env, "variables", {{}}).values():
                value = binding.get("value") if isinstance(binding, dict) else binding
                if isinstance(value, EPLWebApp):
                    return value
            for module_env in getattr(env, "modules", {{}}).values():
                found = _find_web_app(module_env)
                if found is not None:
                    return found
            return None

        def load_epl_app(filepath):
            """Load an EPL web app from a .epl file."""
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interpreter = Interpreter()
            interpreter.execute(program)
            # Find the EPLWebApp created by the script
            app = _find_web_app(interpreter.global_env)
            if app is not None:
                return app, interpreter
            raise RuntimeError("No EPLWebApp found in the EPL file")

        # Option 2: Build programmatically (uncomment and modify)
        # {app_var} = EPLWebApp("MyApp")
        # {app_var}.add_route("/", "json", [...])

        # ─── Create WSGI application ────────────────────
        try:
            _app = None
            _interp = None
            for _candidate in _resolve_candidates(
                Path(os.environ.get("EPL_APP_FILE")) if os.environ.get("EPL_APP_FILE") else APP_FILE
            ):
                if _candidate.is_file():
                    _app, _interp = load_epl_app(_candidate)
                    break
            if _app is None:
                raise FileNotFoundError(f"No EPL app file found for {{APP_FILE}}")
            application = WSGIAdapter(_app, interpreter=_interp)
        except FileNotFoundError:
            # Fallback: minimal health-check app
            _app = EPLWebApp("EPL-Fallback")
            application = WSGIAdapter(_app)
    ''')


# ═══════════════════════════════════════════════════════════
# Nginx Config Generator
# ═══════════════════════════════════════════════════════════

def generate_nginx_config(server_name='localhost', upstream_port=8000,
                           ssl_cert=None, ssl_key=None,
                           static_dir='/var/www/epl/static',
                           workers=None, enable_websocket=False,
                           rate_limit='10r/s', client_max_body='10m',
                           enable_gzip=True, cache_static=True,
                           upstream_name='epl_backend',
                           listen_port=80, ssl_listen_port=443):
    """Generate production-ready Nginx reverse proxy configuration."""
    import multiprocessing
    if workers is None:
        workers = multiprocessing.cpu_count()

    config = textwrap.dedent(f'''\
        # ═══════════════════════════════════════════════════════════
        # Nginx Configuration for EPL Web Application
        # Generated by EPL Deploy v4.0
        #
        # Install: sudo cp epl_nginx.conf /etc/nginx/sites-available/{server_name}
        #          sudo ln -s /etc/nginx/sites-available/{server_name} /etc/nginx/sites-enabled/
        #          sudo nginx -t && sudo systemctl reload nginx
        # ═══════════════════════════════════════════════════════════

        worker_processes {workers};
        worker_rlimit_nofile 65535;

        events {{
            worker_connections 4096;
            multi_accept on;
            use epoll;
        }}

        http {{
            # ─── Basic Settings ───────────────────────────────
            sendfile on;
            tcp_nopush on;
            tcp_nodelay on;
            keepalive_timeout 65;
            keepalive_requests 1000;
            types_hash_max_size 2048;
            server_tokens off;    # Hide Nginx version

            include /etc/nginx/mime.types;
            default_type application/octet-stream;

            # ─── Logging ──────────────────────────────────────
            log_format epl_combined '$remote_addr - $remote_user [$time_local] '
                                    '"$request" $status $body_bytes_sent '
                                    '"$http_referer" "$http_user_agent" '
                                    '$request_time $upstream_response_time';

            access_log /var/log/nginx/{server_name}_access.log epl_combined;
            error_log /var/log/nginx/{server_name}_error.log warn;

            # ─── Rate Limiting ────────────────────────────────
            limit_req_zone $binary_remote_addr zone=epl_limit:10m rate={rate_limit};
            limit_req_status 429;

            # ─── Client Body ──────────────────────────────────
            client_max_body_size {client_max_body};
            client_body_buffer_size 128k;
            client_header_buffer_size 1k;
            large_client_header_buffers 4 4k;
    ''')

    # Gzip
    if enable_gzip:
        config += textwrap.dedent('''\

            # ─── Gzip Compression ─────────────────────────────
            gzip on;
            gzip_vary on;
            gzip_proxied any;
            gzip_comp_level 6;
            gzip_min_length 256;
            gzip_types
                text/plain
                text/css
                text/xml
                text/javascript
                application/json
                application/javascript
                application/xml
                application/rss+xml
                image/svg+xml;
        ''')

    # Upstream
    config += textwrap.dedent(f'''
            # ─── Upstream (EPL Backend) ───────────────────────
            upstream {upstream_name} {{
                server 127.0.0.1:{upstream_port};
                keepalive 32;
            }}
    ''')

    # SSL redirect server block
    if ssl_cert and ssl_key:
        config += textwrap.dedent(f'''
            # ─── HTTP → HTTPS Redirect ───────────────────────
            server {{
                listen {listen_port};
                listen [::]:{listen_port};
                server_name {server_name};
                return 301 https://$server_name$request_uri;
            }}
        ''')

    # Main server block
    if ssl_cert and ssl_key:
        config += textwrap.dedent(f'''
            # ─── Main Server (HTTPS) ─────────────────────────
            server {{
                listen {ssl_listen_port} ssl http2;
                listen [::]:{ssl_listen_port} ssl http2;
                server_name {server_name};

                # SSL Configuration
                ssl_certificate {ssl_cert};
                ssl_certificate_key {ssl_key};
                ssl_protocols TLSv1.2 TLSv1.3;
                ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
                ssl_prefer_server_ciphers off;
                ssl_session_timeout 1d;
                ssl_session_cache shared:SSL:50m;
                ssl_session_tickets off;

                # HSTS
                add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
        ''')
    else:
        config += textwrap.dedent(f'''
            # ─── Main Server (HTTP) ──────────────────────────
            server {{
                listen {listen_port};
                listen [::]:{listen_port};
                server_name {server_name};
        ''')

    # Security headers
    config += textwrap.dedent('''\

                # ─── Security Headers ─────────────────────────
                add_header X-Content-Type-Options nosniff always;
                add_header X-Frame-Options SAMEORIGIN always;
                add_header X-XSS-Protection "0" always;
                add_header Referrer-Policy "strict-origin-when-cross-origin" always;
                add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    ''')

    # Static files
    if cache_static:
        config += textwrap.dedent(f'''
                # ─── Static Files (served by Nginx directly) ──
                location /static/ {{
                    alias {static_dir}/;
                    expires 30d;
                    add_header Cache-Control "public, immutable";
                    access_log off;
                    tcp_nodelay off;
                    open_file_cache max=3000 inactive=120s;
                    open_file_cache_valid 45s;
                    open_file_cache_min_uses 2;
                    open_file_cache_errors off;
                }}

                location /favicon.ico {{
                    alias {static_dir}/favicon.ico;
                    expires 30d;
                    access_log off;
                }}
        ''')

    # WebSocket support
    if enable_websocket:
        config += textwrap.dedent(f'''
                # ─── WebSocket Support ────────────────────────
                location /ws/ {{
                    proxy_pass http://{upstream_name};
                    proxy_http_version 1.1;
                    proxy_set_header Upgrade $http_upgrade;
                    proxy_set_header Connection "upgrade";
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto $scheme;
                    proxy_read_timeout 86400;
                }}
        ''')

    # Main proxy
    config += textwrap.dedent(f'''
                # ─── Proxy to EPL Backend ─────────────────────
                location / {{
                    limit_req zone=epl_limit burst=20 nodelay;

                    proxy_pass http://{upstream_name};
                    proxy_http_version 1.1;
                    proxy_set_header Host $host;
                    proxy_set_header X-Real-IP $remote_addr;
                    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                    proxy_set_header X-Forwarded-Proto $scheme;
                    proxy_set_header X-Request-ID $request_id;
                    proxy_set_header Connection "";

                    # Timeouts
                    proxy_connect_timeout 10s;
                    proxy_send_timeout 30s;
                    proxy_read_timeout 60s;

                    # Buffering
                    proxy_buffering on;
                    proxy_buffer_size 4k;
                    proxy_buffers 8 16k;

                    # Error pages
                    proxy_intercept_errors on;
                    error_page 502 503 504 /50x.html;
                }}

                # ─── Health Check (no rate limiting) ──────────
                location /_health {{
                    proxy_pass http://{upstream_name}/_health;
                    access_log off;
                }}

                # ─── Custom Error Pages ──────────────────────
                location = /50x.html {{
                    root /usr/share/nginx/html;
                    internal;
                }}
            }}
        }}
    ''')

    return config


# ═══════════════════════════════════════════════════════════
# Tomcat Reverse Proxy Config Generator (AJP/HTTP)
# ═══════════════════════════════════════════════════════════

def generate_tomcat_config(server_name='localhost', upstream_port=8000,
                            ajp_port=8009, http_port=8080,
                            ssl_cert=None, ssl_key=None,
                            context_path='/', app_name='epl'):
    """Generate Apache Tomcat configuration for proxying to EPL.
    
    Generates:
    1. server.xml connector snippets
    2. Apache mod_proxy/mod_jk configuration  
    3. Tomcat valve configuration for logging
    """
    configs = {}

    # 1. Tomcat server.xml snippets
    server_xml = textwrap.dedent(f'''\
        <!-- ═══════════════════════════════════════════════════════
             Tomcat Configuration for EPL Web Application
             Generated by EPL Deploy v4.0
             
             Add these snippets to your Tomcat server.xml
             ($CATALINA_HOME/conf/server.xml)
             ═══════════════════════════════════════════════════════ -->

        <!-- HTTP Connector -->
        <Connector port="{http_port}"
                   protocol="HTTP/1.1"
                   connectionTimeout="20000"
                   redirectPort="8443"
                   maxThreads="200"
                   minSpareThreads="10"
                   acceptCount="100"
                   enableLookups="false"
                   compression="on"
                   compressibleMimeType="text/html,text/xml,text/plain,text/css,text/javascript,application/javascript,application/json"
                   server="EPL" />

        <!-- AJP Connector (for Apache httpd fronting) -->  
        <Connector port="{ajp_port}"
                   protocol="AJP/1.3"
                   redirectPort="8443"
                   maxThreads="200"
                   secretRequired="true"
                   secret="CHANGE_THIS_SECRET"
                   address="127.0.0.1" />
    ''')

    if ssl_cert and ssl_key:
        server_xml += textwrap.dedent(f'''
        <!-- HTTPS Connector -->
        <Connector port="8443"
                   protocol="org.apache.coyote.http11.Http11NioProtocol"
                   maxThreads="200"
                   SSLEnabled="true"
                   scheme="https"
                   secure="true">
            <SSLHostConfig>
                <Certificate certificateFile="{ssl_cert}"
                             certificateKeyFile="{ssl_key}"
                             type="RSA" />
            </SSLHostConfig>
        </Connector>
        ''')

    # Access log valve
    server_xml += textwrap.dedent('''\

        <!-- Access Log Valve (add inside <Host> element) -->
        <Valve className="org.apache.catalina.valves.AccessLogValve"
               directory="logs"
               prefix="epl_access_log"
               suffix=".txt"
               pattern="%h %l %u %t &quot;%r&quot; %s %b %D" />

        <!-- Remote IP Valve (for correct client IP behind proxy) -->
        <Valve className="org.apache.catalina.valves.RemoteIpValve"
               remoteIpHeader="X-Forwarded-For"
               protocolHeader="X-Forwarded-Proto" />
    ''')
    configs['server.xml'] = server_xml

    # 2. Apache mod_proxy config (for httpd + Tomcat)
    mod_proxy = textwrap.dedent(f'''\
        # ═══════════════════════════════════════════════════════
        # Apache mod_proxy Configuration for EPL via Tomcat
        # Generated by EPL Deploy v4.0
        #
        # Install: sudo cp epl_proxy.conf /etc/httpd/conf.d/
        #          sudo systemctl restart httpd
        # ═══════════════════════════════════════════════════════

        <VirtualHost *:80>
            ServerName {server_name}

            # ─── Proxy to EPL Backend (HTTP) ──────────────
            ProxyPreserveHost On
            ProxyRequests Off

            # Pass requests to EPL backend
            ProxyPass {context_path} http://127.0.0.1:{upstream_port}{context_path}
            ProxyPassReverse {context_path} http://127.0.0.1:{upstream_port}{context_path}

            # Health check bypass
            <Location /_health>
                ProxyPass http://127.0.0.1:{upstream_port}/_health
                ProxyPassReverse http://127.0.0.1:{upstream_port}/_health
            </Location>

            # ─── Security Headers ─────────────────────────
            Header always set X-Content-Type-Options nosniff
            Header always set X-Frame-Options SAMEORIGIN
            Header always set Referrer-Policy "strict-origin-when-cross-origin"

            # ─── Logging ──────────────────────────────────
            ErrorLog /var/log/httpd/{app_name}_error.log
            CustomLog /var/log/httpd/{app_name}_access.log combined

            # ─── Timeouts ────────────────────────────────
            ProxyTimeout 60
            Timeout 120
        </VirtualHost>
    ''')

    if ssl_cert and ssl_key:
        mod_proxy += textwrap.dedent(f'''
        <VirtualHost *:443>
            ServerName {server_name}

            SSLEngine on
            SSLCertificateFile {ssl_cert}
            SSLCertificateKeyFile {ssl_key}
            SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1

            ProxyPreserveHost On
            ProxyRequests Off
            ProxyPass {context_path} http://127.0.0.1:{upstream_port}{context_path}
            ProxyPassReverse {context_path} http://127.0.0.1:{upstream_port}{context_path}

            Header always set Strict-Transport-Security "max-age=63072000"
            Header always set X-Content-Type-Options nosniff
            Header always set X-Frame-Options SAMEORIGIN

            ErrorLog /var/log/httpd/{app_name}_ssl_error.log
            CustomLog /var/log/httpd/{app_name}_ssl_access.log combined
        </VirtualHost>
        ''')

    configs['mod_proxy.conf'] = mod_proxy

    # 3. AJP proxy config (alternative to mod_proxy HTTP)
    ajp_config = textwrap.dedent(f'''\
        # ═══════════════════════════════════════════════════════
        # Apache mod_proxy_ajp Configuration (Tomcat AJP)
        # Generated by EPL Deploy v4.0
        #
        # Requires: mod_proxy, mod_proxy_ajp
        # ═══════════════════════════════════════════════════════

        <VirtualHost *:80>
            ServerName {server_name}

            ProxyPreserveHost On
            ProxyRequests Off

            # AJP proxy to Tomcat  
            ProxyPass {context_path} ajp://127.0.0.1:{ajp_port}{context_path} secret=CHANGE_THIS_SECRET
            ProxyPassReverse {context_path} ajp://127.0.0.1:{ajp_port}{context_path}

            ErrorLog /var/log/httpd/{app_name}_ajp_error.log
            CustomLog /var/log/httpd/{app_name}_ajp_access.log combined
        </VirtualHost>
    ''')
    configs['mod_proxy_ajp.conf'] = ajp_config

    return configs


# ═══════════════════════════════════════════════════════════
# Docker Config Generator
# ═══════════════════════════════════════════════════════════

def generate_dockerfile(app_file='app.epl', port=8000, workers=4, runtime_subdir='.'):
    """Generate a production Dockerfile for EPL web application."""
    runtime_subdir = (runtime_subdir or '.').replace('\\', '/').strip('/')
    workdir = '/app' if not runtime_subdir or runtime_subdir == '.' else f'/app/{runtime_subdir}'
    return textwrap.dedent(f'''\
        # ═══════════════════════════════════════════════════════
        # Dockerfile for EPL Web Application
        # Generated by EPL Deploy v4.0
        #
        # Build:  docker build -t epl-app .
        # Run:    docker run -p {port}:{port} epl-app
        # ═══════════════════════════════════════════════════════

        FROM python:3.11-slim AS base

        # Security: run as non-root user
        RUN groupadd -r epl && useradd -r -g epl -d /app -s /sbin/nologin epl

        WORKDIR {workdir}

        # Install system dependencies
        RUN apt-get update && apt-get install -y --no-install-recommends \\
            curl \\
            && rm -rf /var/lib/apt/lists/*

        # Copy application
        COPY . /app

        # Install runtime dependencies from the generated deploy requirements
        RUN pip install --no-cache-dir -r requirements.txt

        # Create necessary directories
        RUN mkdir -p /app/static /app/uploads /app/templates /app/logs \\
            && chown -R epl:epl /app

        # Switch to non-root user
        USER epl

        # Health check
        HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
            CMD curl -f http://localhost:{port}/_health || exit 1

        # Expose port
        EXPOSE {port}

        # Environment variables
        ENV EPL_PORT={port}
        ENV EPL_WORKERS={workers}
        ENV PYTHONUNBUFFERED=1
        ENV PYTHONDONTWRITEBYTECODE=1

        # Start with Gunicorn
        CMD ["gunicorn", "-c", "gunicorn_conf.py", "wsgi:application"]
    ''')


def generate_docker_compose(app_name='epl-app', port=8000, workers=4,
                             enable_nginx=True, enable_redis=False,
                             enable_postgres=False, build_context='.',
                             dockerfile='Dockerfile', uploads_dir='./uploads',
                             logs_dir='./logs', static_dir='./static',
                             nginx_config='./nginx/epl_nginx.conf',
                             certs_dir='./nginx/certs'):
    """Generate docker-compose.yml for EPL production deployment."""
    compose = {
        'version': '3.8',
        'services': {},
        'networks': {
            'epl-network': {'driver': 'bridge'}
        },
        'volumes': {}
    }

    # EPL App service
    app_service = {
        'build': {
            'context': build_context,
            'dockerfile': dockerfile,
        },
        'container_name': app_name,
        'restart': 'unless-stopped',
        'environment': [
            f'EPL_PORT={port}',
            f'EPL_WORKERS={workers}',
        ],
        'volumes': [
            f'{uploads_dir}:/app/uploads',
            f'{logs_dir}:/app/logs',
        ],
        'networks': ['epl-network'],
        'healthcheck': {
            'test': ['CMD', 'curl', '-f', f'http://localhost:{port}/_health'],
            'interval': '30s',
            'timeout': '5s',
            'retries': 3,
            'start_period': '10s',
        },
    }

    if not enable_nginx:
        app_service['ports'] = [f'{port}:{port}']

    compose['services']['app'] = app_service

    # Nginx service
    if enable_nginx:
        compose['services']['nginx'] = {
            'image': 'nginx:alpine',
            'container_name': f'{app_name}-nginx',
            'restart': 'unless-stopped',
            'ports': ['80:80', '443:443'],
            'volumes': [
                f'{nginx_config}:/etc/nginx/nginx.conf:ro',
                f'{static_dir}:/var/www/epl/static:ro',
                f'{certs_dir}:/etc/nginx/certs:ro',
            ],
            'depends_on': {'app': {'condition': 'service_healthy'}},
            'networks': ['epl-network'],
        }

    # Redis (optional - for sessions/caching)
    if enable_redis:
        compose['services']['redis'] = {
            'image': 'redis:7-alpine',
            'container_name': f'{app_name}-redis',
            'restart': 'unless-stopped',
            'volumes': ['redis-data:/data'],
            'networks': ['epl-network'],
            'command': 'redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru',
        }
        compose['volumes']['redis-data'] = {}
        app_service['environment'].append('REDIS_URL=redis://redis:6379')
        app_service['depends_on'] = {'redis': {'condition': 'service_started'}}

    # PostgreSQL (optional)
    if enable_postgres:
        compose['services']['postgres'] = {
            'image': 'postgres:16-alpine',
            'container_name': f'{app_name}-postgres',
            'restart': 'unless-stopped',
            'environment': [
                'POSTGRES_DB=epl_app',
                'POSTGRES_USER=epl',
                'POSTGRES_PASSWORD_FILE=/run/secrets/db_password',
            ],
            'volumes': ['pg-data:/var/lib/postgresql/data'],
            'networks': ['epl-network'],
            'healthcheck': {
                'test': ['CMD-SHELL', 'pg_isready -U epl -d epl_app'],
                'interval': '10s',
                'timeout': '5s',
                'retries': 5,
            },
        }
        compose['volumes']['pg-data'] = {}

    # Convert to YAML manually (avoid PyYAML dependency)
    return _dict_to_yaml(compose)


def _dict_to_yaml(d, indent=0):
    """Convert dict to YAML string (minimal, no external deps)."""
    lines = []
    prefix = '  ' * indent
    if isinstance(d, dict):
        for key, val in d.items():
            if isinstance(val, dict) and val:
                lines.append(f'{prefix}{key}:')
                lines.append(_dict_to_yaml(val, indent + 1))
            elif isinstance(val, list):
                lines.append(f'{prefix}{key}:')
                for item in val:
                    if isinstance(item, str):
                        lines.append(f'{prefix}  - "{item}"')
                    elif isinstance(item, dict):
                        # First key-value on same line as dash
                        items = list(item.items())
                        if items:
                            k0, v0 = items[0]
                            if isinstance(v0, str):
                                lines.append(f'{prefix}  - {k0}: "{v0}"')
                            else:
                                lines.append(f'{prefix}  - {k0}: {v0}')
                            for k, v in items[1:]:
                                if isinstance(v, str):
                                    lines.append(f'{prefix}    {k}: "{v}"')
                                else:
                                    lines.append(f'{prefix}    {k}: {v}')
                    else:
                        lines.append(f'{prefix}  - {item}')
            elif isinstance(val, str):
                lines.append(f'{prefix}{key}: "{val}"')
            elif isinstance(val, bool):
                lines.append(f'{prefix}{key}: {"true" if val else "false"}')
            elif val is None:
                lines.append(f'{prefix}{key}: null')
            else:
                lines.append(f'{prefix}{key}: {val}')
    return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════
# Systemd Service Generator
# ═══════════════════════════════════════════════════════════

def generate_systemd_service(app_name='epl-app', app_dir='/opt/epl-app',
                               port=8000, workers=4, user='epl', group='epl',
                               runtime_subdir='.'):
    """Generate a systemd service unit file for EPL applications."""
    app_dir = app_dir.rstrip('/')
    runtime_subdir = (runtime_subdir or '.').replace('\\', '/').strip('/')
    runtime_dir = app_dir if not runtime_subdir or runtime_subdir == '.' else f'{app_dir}/{runtime_subdir}'
    return textwrap.dedent(f'''\
        # ═══════════════════════════════════════════════════════
        # Systemd Service for EPL Web Application
        # Generated by EPL Deploy v4.0
        #
        # Install:
        #   sudo cp {app_name}.service /etc/systemd/system/
        #   sudo systemctl daemon-reload
        #   sudo systemctl enable {app_name}
        #   sudo systemctl start {app_name}
        # ═══════════════════════════════════════════════════════

        [Unit]
        Description=EPL Web Application ({app_name})
        Documentation=https://github.com/epl-lang/epl
        After=network.target
        Wants=network-online.target

        [Service]
        Type=notify
        User={user}
        Group={group}
        WorkingDirectory={runtime_dir}
        Environment="PATH={app_dir}/venv/bin:/usr/local/bin:/usr/bin"
        Environment="EPL_PORT={port}"
        Environment="EPL_WORKERS={workers}"

        ExecStart={app_dir}/venv/bin/gunicorn \\
            -c {runtime_dir}/gunicorn_conf.py \\
            wsgi:application

        ExecReload=/bin/kill -s HUP $MAINPID

        # Restart policy
        Restart=on-failure
        RestartSec=5
        StartLimitBurst=5
        StartLimitIntervalSec=60

        # Security hardening
        NoNewPrivileges=yes
        PrivateTmp=yes
        ProtectSystem=strict
        ProtectHome=yes
        ReadWritePaths={app_dir}/uploads {app_dir}/logs {app_dir}/data

        # Resource limits
        LimitNOFILE=65535
        LimitNPROC=4096

        # Logging
        StandardOutput=journal
        StandardError=journal
        SyslogIdentifier={app_name}

        [Install]
        WantedBy=multi-user.target
    ''')


# ═══════════════════════════════════════════════════════════
# ASGI Entry Point Generator
# ═══════════════════════════════════════════════════════════

def generate_asgi_entry(app_module='app', app_file=None, project_root='.'):
    """Generate asgi.py entry point for Uvicorn/Daphne/Hypercorn."""
    if app_file is None:
        app_file = f'{app_module}.epl'
    app_file_literal = json.dumps(app_file)
    project_root_literal = json.dumps(project_root or '.')

    return textwrap.dedent(f'''\
        """ASGI entry point for EPL web application.
        
        Usage:
            uvicorn asgi:application --host 0.0.0.0 --port 8000 --workers 4
            hypercorn asgi:application -b 0.0.0.0:8000 -w 4
            daphne asgi:application -b 0.0.0.0 -p 8000
        """
        from pathlib import Path
        import os
        import sys

        from epl.web import EPLWebApp
        from epl.deploy import ASGIAdapter
        from epl.interpreter import Interpreter
        from epl.lexer import Lexer
        from epl.parser import Parser

        APP_FILE = Path({app_file_literal})
        PROJECT_ROOT = Path({project_root_literal})

        def _resolve_candidates(path_value):
            raw = Path(path_value)
            candidates = []
            if raw.is_absolute():
                candidates.append(raw)
            else:
                base_dir = Path(__file__).resolve().parent
                candidates.append((base_dir / raw).resolve())
                candidates.append((Path.cwd() / raw).resolve())
            candidates.append(raw)

            resolved = []
            seen = set()
            for candidate in candidates:
                try:
                    key = str(candidate.resolve()) if candidate.exists() else str(candidate)
                except OSError:
                    key = str(candidate)
                if key not in seen:
                    seen.add(key)
                    resolved.append(candidate)
            return resolved

        for _root in _resolve_candidates(PROJECT_ROOT):
            if _root.exists():
                _root_str = str(_root)
                if _root_str not in sys.path:
                    sys.path.insert(0, _root_str)

        def _find_web_app(env):
            for binding in getattr(env, "variables", {{}}).values():
                value = binding.get("value") if isinstance(binding, dict) else binding
                if isinstance(value, EPLWebApp):
                    return value
            for module_env in getattr(env, "modules", {{}}).values():
                found = _find_web_app(module_env)
                if found is not None:
                    return found
            return None

        def load_epl_app(filepath):
            """Load an EPL web app from a .epl file."""
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interpreter = Interpreter()
            interpreter.execute(program)
            app = _find_web_app(interpreter.global_env)
            if app is not None:
                return app, interpreter
            raise RuntimeError("No EPLWebApp found in the EPL file")

        try:
            _app = None
            _interp = None
            for _candidate in _resolve_candidates(
                Path(os.environ.get("EPL_APP_FILE")) if os.environ.get("EPL_APP_FILE") else APP_FILE
            ):
                if _candidate.is_file():
                    _app, _interp = load_epl_app(_candidate)
                    break
            if _app is None:
                raise FileNotFoundError(f"No EPL app file found for {{APP_FILE}}")
            application = ASGIAdapter(_app, interpreter=_interp)
        except FileNotFoundError:
            _app = EPLWebApp("EPL-Fallback")
            application = ASGIAdapter(_app)
    ''')


# ═══════════════════════════════════════════════════════════
# Deploy CLI — generate all configs at once
# ═══════════════════════════════════════════════════════════

def deploy_generate(target, output_dir='.', **kwargs):
    """Generate deployment configuration files.
    
    Args:
        target: 'gunicorn', 'nginx', 'tomcat', 'docker', 'systemd', 'all'
        output_dir: Directory to write config files
        **kwargs: Options passed to individual generators
    """
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    generated = []
    
    app_name = kwargs.get('app_name', 'epl-app')
    port = kwargs.get('port', 8000)
    workers = kwargs.get('workers', None)
    ssl_cert = kwargs.get('ssl_cert', None)
    ssl_key = kwargs.get('ssl_key', None)
    server_name = kwargs.get('server_name', 'localhost')
    project_root, app_path = _resolve_deploy_app(
        project_root=kwargs.get('project_root'),
        app_file=kwargs.get('app_file'),
    )
    from epl.package_manager import load_manifest
    manifest = load_manifest(project_root) or {}
    app_file_ref = _relative_deploy_path(app_path, output_dir)
    project_root_ref = _relative_deploy_path(project_root, output_dir)
    runtime_subdir = _resolve_runtime_subdir(project_root, output_dir)

    def _project_ref(path_fragment):
        path_fragment = path_fragment.replace('\\', '/').lstrip('/')
        if project_root_ref in ('.', ''):
            return f'./{path_fragment}'
        return f'{project_root_ref}/{path_fragment}'

    if target in ('gunicorn', 'all'):
        # gunicorn_conf.py
        config = generate_gunicorn_config(
            app_name=app_name, port=port, workers=workers,
            ssl_cert=ssl_cert, ssl_key=ssl_key
        )
        path = os.path.join(output_dir, 'gunicorn_conf.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(config)
        generated.append(path)

        # wsgi.py
        wsgi = generate_wsgi_entry(app_file=app_file_ref, project_root=project_root_ref)
        path = os.path.join(output_dir, 'wsgi.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(wsgi)
        generated.append(path)

    if target in ('nginx', 'all'):
        config = generate_nginx_config(
            server_name=server_name, upstream_port=port,
            ssl_cert=ssl_cert, ssl_key=ssl_key,
            enable_websocket=kwargs.get('websocket', False)
        )
        nginx_dir = os.path.join(output_dir, 'nginx')
        os.makedirs(nginx_dir, exist_ok=True)
        path = os.path.join(nginx_dir, 'epl_nginx.conf')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(config)
        generated.append(path)

    if target in ('tomcat', 'all'):
        configs = generate_tomcat_config(
            server_name=server_name, upstream_port=port,
            ssl_cert=ssl_cert, ssl_key=ssl_key,
            app_name=app_name
        )
        tomcat_dir = os.path.join(output_dir, 'tomcat')
        os.makedirs(tomcat_dir, exist_ok=True)
        for name, content in configs.items():
            path = os.path.join(tomcat_dir, f'epl_{name}')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            generated.append(path)

    if target in ('docker', 'all'):
        requirements_txt = generate_requirements_txt(
            manifest=manifest,
            epl_requirement=kwargs.get('epl_requirement'),
        )
        path = os.path.join(output_dir, 'requirements.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(requirements_txt)
        generated.append(path)

        # Dockerfile
        df = generate_dockerfile(
            app_file=app_file_ref,
            port=port,
            workers=workers or 4,
            runtime_subdir=runtime_subdir,
        )
        path = os.path.join(output_dir, 'Dockerfile')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(df)
        generated.append(path)

        # docker-compose.yml
        if runtime_subdir == '.':
            build_context = '.'
            dockerfile_ref = 'Dockerfile'
        else:
            build_context = project_root_ref
            dockerfile_ref = f'{runtime_subdir}/Dockerfile'
        dc = generate_docker_compose(
            app_name=app_name, port=port, workers=workers or 4,
            enable_nginx=kwargs.get('nginx', True),
            build_context=build_context,
            dockerfile=dockerfile_ref,
            uploads_dir=_project_ref('uploads'),
            logs_dir=_project_ref('logs'),
            static_dir=_project_ref('static'),
        )
        path = os.path.join(output_dir, 'docker-compose.yml')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(dc)
        generated.append(path)

    if target in ('systemd', 'all'):
        service = generate_systemd_service(
            app_name=app_name,
            app_dir=kwargs.get('app_dir', '/opt/epl-app'),
            port=port,
            workers=workers or 4,
            runtime_subdir=runtime_subdir,
        )
        path = os.path.join(output_dir, f'{app_name}.service')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(service)
        generated.append(path)

    if target in ('asgi', 'all'):
        asgi = generate_asgi_entry(app_file=app_file_ref, project_root=project_root_ref)
        path = os.path.join(output_dir, 'asgi.py')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(asgi)
        generated.append(path)

    return generated


def deploy_cli(args):
    """Handle 'epl deploy' CLI command."""
    if not args:
        print("EPL Deploy — Production Deployment Generator")
        print()
        print("Usage:")
        print("  python main.py deploy <target> [options]")
        print()
        print("Targets:")
        print("  gunicorn        Generate Gunicorn config + WSGI entry point")
        print("  nginx           Generate Nginx reverse proxy config")
        print("  tomcat          Generate Tomcat/Apache proxy configs")
        print("  docker          Generate Dockerfile + docker-compose.yml")
        print("  systemd         Generate systemd service file")
        print("  asgi            Generate ASGI entry point (Uvicorn/Daphne)")
        print("  all             Generate everything")
        print()
        print("Options:")
        print("  --port <N>          Application port (default: 8000)")
        print("  --workers <N>       Number of workers (default: auto)")
        print("  --name <name>       Application name")
        print("  --server <hostname> Server hostname (default: localhost)")
        print("  --ssl-cert <path>   SSL certificate file path")
        print("  --ssl-key <path>    SSL key file path")
        print("  --output <dir>      Output directory (default: ./deploy)")
        print("  --websocket         Enable WebSocket proxy support")
        print()
        print("Examples:")
        print("  python main.py deploy all")
        print("  python main.py deploy gunicorn --port 8000 --workers 4")
        print("  python main.py deploy nginx --server example.com --ssl-cert cert.pem --ssl-key key.pem")
        print("  python main.py deploy docker --name my-epl-app")
        print("  python main.py deploy tomcat --port 8000")
        return

    target = args[0]
    valid_targets = ('gunicorn', 'nginx', 'tomcat', 'docker', 'systemd', 'asgi', 'all')
    if target not in valid_targets:
        print(f"EPL Error: Unknown deploy target '{target}'")
        print(f"Valid targets: {', '.join(valid_targets)}")
        return

    # Parse options
    kwargs = {}
    i = 1
    output_dir = './deploy'
    while i < len(args):
        if args[i] == '--port' and i + 1 < len(args):
            kwargs['port'] = int(args[i + 1])
            i += 2
        elif args[i] == '--workers' and i + 1 < len(args):
            kwargs['workers'] = int(args[i + 1])
            i += 2
        elif args[i] == '--name' and i + 1 < len(args):
            kwargs['app_name'] = args[i + 1]
            i += 2
        elif args[i] == '--server' and i + 1 < len(args):
            kwargs['server_name'] = args[i + 1]
            i += 2
        elif args[i] == '--ssl-cert' and i + 1 < len(args):
            kwargs['ssl_cert'] = args[i + 1]
            i += 2
        elif args[i] == '--ssl-key' and i + 1 < len(args):
            kwargs['ssl_key'] = args[i + 1]
            i += 2
        elif args[i] == '--output' and i + 1 < len(args):
            output_dir = args[i + 1]
            i += 2
        elif args[i] == '--websocket':
            kwargs['websocket'] = True
            i += 1
        else:
            print(f"EPL Warning: Unknown option '{args[i]}'")
            i += 1

    # Generate
    generated = deploy_generate(target, output_dir=output_dir, **kwargs)

    if generated:
        print(f"\n  ╔══════════════════════════════════════╗")
        print(f"  ║  EPL Deploy — Files Generated        ║")
        print(f"  ╠══════════════════════════════════════╣")
        for path in generated:
            display = os.path.relpath(path, '.')
            print(f"  ║  ✓ {display:<34}║")
        print(f"  ╚══════════════════════════════════════╝")
        print()
        if target in ('gunicorn', 'all'):
            print("  Start with Gunicorn:")
            print(f"    gunicorn --chdir {output_dir} -c gunicorn_conf.py wsgi:application")
            print()
        if target in ('nginx', 'all'):
            print("  Install Nginx config:")
            print(f"    sudo cp {output_dir}/nginx/epl_nginx.conf /etc/nginx/sites-available/")
            print("    sudo nginx -t && sudo systemctl reload nginx")
            print()
        if target in ('docker', 'all'):
            print("  Build & run with Docker:")
            print(f"    docker compose -f {output_dir}/docker-compose.yml up -d --build")
            print()
        if target in ('tomcat', 'all'):
            print("  Tomcat configs generated in:")
            print(f"    {output_dir}/tomcat/")
            print()
    else:
        print("  No files generated.")
