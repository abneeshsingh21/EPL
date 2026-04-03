"""
EPL WSGI/ASGI Server Adapter v4.0
Production-grade web server with:
  - WSGI interface for compatibility with gunicorn, uWSGI, etc.
  - ASGI interface for async frameworks
  - Built-in production server (multi-process, graceful shutdown)
  - Middleware pipeline
  - Static file serving with caching
  - Request/response objects
  - WebSocket support via ASGI
"""

import os
import io
import json
import time
import signal
import socket
import threading
import traceback
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from epl import ast_nodes as ast
from epl.html_gen import generate_html


# ═══════════════════════════════════════════════════════════
#  Request / Response Objects
# ═══════════════════════════════════════════════════════════

class EPLRequest:
    """Production request object with full HTTP support."""

    def __init__(self, method, path, headers=None, body=b'', query_string='',
                 remote_addr='', route_params=None):
        self.method = method.upper()
        self.path = path
        self.headers = headers or {}
        self._body = body
        self.query_string = query_string
        self.remote_addr = remote_addr
        self.route_params = route_params or {}
        self._json = None
        self._form = None

    @property
    def body(self):
        return self._body

    @property
    def text(self):
        return self._body.decode('utf-8', errors='replace') if isinstance(self._body, bytes) else str(self._body)

    @property
    def json(self):
        if self._json is None:
            try:
                self._json = json.loads(self.text)
            except (json.JSONDecodeError, ValueError):
                self._json = {}
        return self._json

    @property
    def form(self):
        if self._form is None:
            try:
                self._form = dict(urllib.parse.parse_qsl(self.text))
            except Exception:
                self._form = {}
        return self._form

    @property
    def query(self):
        return dict(urllib.parse.parse_qsl(self.query_string))

    def get_header(self, name, default=None):
        return self.headers.get(name.lower(), default)


class EPLResponse:
    """Production response object."""

    def __init__(self, body='', status=200, content_type='text/html', headers=None):
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}
        self._body = body
        self._cookies = []

    @property
    def body(self):
        if isinstance(self._body, str):
            return self._body.encode('utf-8')
        return self._body

    def set_cookie(self, name, value, max_age=3600, path='/', httponly=True, secure=False, samesite='Lax'):
        parts = [f'{name}={value}', f'Path={path}', f'Max-Age={max_age}', f'SameSite={samesite}']
        if httponly:
            parts.append('HttpOnly')
        if secure:
            parts.append('Secure')
        self._cookies.append('; '.join(parts))

    def json_response(self, data, status=200):
        self._body = json.dumps(data)
        self.content_type = 'application/json'
        self.status = status
        return self

    def redirect(self, url, status=302):
        self.status = status
        self.headers['Location'] = url
        return self

    def get_headers(self):
        """Return full header list for HTTP response."""
        headers = [
            ('Content-Type', self.content_type),
            ('Content-Length', str(len(self.body))),
            ('X-Content-Type-Options', 'nosniff'),
            ('X-Frame-Options', 'DENY'),
            ('X-XSS-Protection', '1; mode=block'),
        ]
        for k, v in self.headers.items():
            headers.append((k, v))
        for cookie in self._cookies:
            headers.append(('Set-Cookie', cookie))
        return headers


# ═══════════════════════════════════════════════════════════
#  WSGI Application
# ═══════════════════════════════════════════════════════════

class EPLWSGIApp:
    """WSGI-compatible application wrapper for EPL web apps."""

    def __init__(self):
        self.routes = []       # list of (method, pattern_re, param_names, handler)
        self.middleware = []   # list of middleware functions
        self.error_handlers = {}  # status_code → handler
        self.static_dir = None
        self.static_prefix = '/static/'

    def route(self, path, methods=None):
        """Decorator to register a route handler."""
        methods = methods or ['GET']
        def decorator(handler):
            pattern, param_names = self._compile_route(path)
            for method in methods:
                self.routes.append((method.upper(), pattern, param_names, handler))
            return handler
        return decorator

    def add_route(self, method, path, handler):
        """Programmatic route registration."""
        pattern, param_names = self._compile_route(path)
        self.routes.append((method.upper(), pattern, param_names, handler))

    def add_middleware(self, middleware_func):
        """Add middleware to the pipeline."""
        self.middleware.append(middleware_func)

    def serve_static(self, directory, prefix='/static/'):
        """Enable static file serving."""
        self.static_dir = os.path.abspath(directory)
        self.static_prefix = prefix

    def _compile_route(self, path):
        """Convert '/users/:id/posts' to regex with named groups."""
        import re
        param_names = []
        parts = path.split('/')
        regex_parts = []
        for part in parts:
            if part.startswith(':'):
                name = part[1:]
                param_names.append(name)
                regex_parts.append(f'(?P<{name}>[^/]+)')
            elif part == '*':
                regex_parts.append('.*')
            else:
                regex_parts.append(re.escape(part))
        pattern = re.compile('^' + '/'.join(regex_parts) + '$')
        return pattern, param_names

    def _match_route(self, method, path):
        """Find matching route for a request."""
        for route_method, pattern, param_names, handler in self.routes:
            if route_method == method or route_method == '*':
                m = pattern.match(path)
                if m:
                    return handler, m.groupdict()
        return None, {}

    def __call__(self, environ, start_response):
        """WSGI entry point."""
        # Parse request
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        query_string = environ.get('QUERY_STRING', '')
        remote_addr = environ.get('REMOTE_ADDR', '')

        # Read body
        content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        body = environ['wsgi.input'].read(content_length) if content_length > 0 else b''

        # Parse headers
        headers = {}
        for key, value in environ.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].replace('_', '-').lower()
                headers[header_name] = value
        if 'CONTENT_TYPE' in environ:
            headers['content-type'] = environ['CONTENT_TYPE']

        # Static files
        if self.static_dir and path.startswith(self.static_prefix):
            return self._serve_static(path, environ, start_response)

        # Route matching
        handler, params = self._match_route(method, path)

        request = EPLRequest(method, path, headers, body, query_string, remote_addr, params)
        response = EPLResponse()

        try:
            # Run middleware pipeline
            for mw in self.middleware:
                result = mw(request, response)
                if result is not None:
                    response = result
                    break
            else:
                if handler:
                    result = handler(request, response)
                    if isinstance(result, EPLResponse):
                        response = result
                    elif isinstance(result, dict):
                        response.json_response(result)
                    elif isinstance(result, str):
                        response._body = result
                else:
                    response.status = 404
                    response._body = '<h1>404 Not Found</h1>'

        except Exception as e:
            error_handler = self.error_handlers.get(500)
            if error_handler:
                response = error_handler(request, e)
            else:
                response.status = 500
                response._body = f'<h1>500 Internal Server Error</h1><p>{e}</p>'

        # Send response
        status_line = f'{response.status} {self._status_text(response.status)}'
        response_headers = response.get_headers()
        start_response(status_line, response_headers)
        return [response.body]

    def _serve_static(self, path, environ, start_response):
        """Serve a static file with caching headers."""
        import mimetypes
        relative = path[len(self.static_prefix):]
        # Prevent path traversal
        safe_path = os.path.normpath(relative)
        if safe_path.startswith('..') or os.path.isabs(safe_path):
            start_response('403 Forbidden', [('Content-Type', 'text/plain')])
            return [b'Forbidden']

        full_path = os.path.join(self.static_dir, safe_path)
        if not os.path.isfile(full_path):
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']

        content_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
        stat = os.stat(full_path)
        headers = [
            ('Content-Type', content_type),
            ('Content-Length', str(stat.st_size)),
            ('Cache-Control', 'public, max-age=3600'),
        ]
        start_response('200 OK', headers)
        with open(full_path, 'rb') as f:
            return [f.read()]

    @staticmethod
    def _status_text(code):
        return {
            200: 'OK', 201: 'Created', 204: 'No Content',
            301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified',
            400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
            404: 'Not Found', 405: 'Method Not Allowed', 409: 'Conflict',
            422: 'Unprocessable Entity', 429: 'Too Many Requests',
            500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable',
        }.get(code, 'Unknown')


# ═══════════════════════════════════════════════════════════
#  ASGI Application
# ═══════════════════════════════════════════════════════════

class EPLASGIApp:
    """ASGI-compatible application for async request handling."""

    def __init__(self, wsgi_app=None):
        self._wsgi_app = wsgi_app or EPLWSGIApp()
        self._ws_handlers = {}  # path → handler

    def websocket(self, path):
        """Register a WebSocket handler."""
        def decorator(handler):
            self._ws_handlers[path] = handler
            return handler
        return decorator

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            await self._handle_http(scope, receive, send)
        elif scope['type'] == 'websocket':
            await self._handle_websocket(scope, receive, send)

    async def _handle_http(self, scope, receive, send):
        """Handle HTTP request through WSGI app."""
        # Build environ from ASGI scope
        body_parts = []
        while True:
            msg = await receive()
            body_parts.append(msg.get('body', b''))
            if not msg.get('more_body', False):
                break
        body = b''.join(body_parts)

        environ = {
            'REQUEST_METHOD': scope['method'],
            'PATH_INFO': scope['path'],
            'QUERY_STRING': scope.get('query_string', b'').decode('utf-8'),
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': io.BytesIO(body),
            'REMOTE_ADDR': scope.get('client', ['', 0])[0] if scope.get('client') else '',
        }
        for name, value in scope.get('headers', []):
            key = 'HTTP_' + name.decode('latin-1').upper().replace('-', '_')
            environ[key] = value.decode('latin-1')
        if b'content-type' in dict(scope.get('headers', [])):
            environ['CONTENT_TYPE'] = dict(scope.get('headers', []))[b'content-type'].decode('latin-1')

        # Call WSGI app
        response_started = False
        status_code = 200
        response_headers = []

        def start_response(status, headers, exc_info=None):
            nonlocal response_started, status_code, response_headers
            status_code = int(status.split(' ')[0])
            response_headers = headers
            response_started = True

        body_parts = self._wsgi_app(environ, start_response)

        await send({
            'type': 'http.response.start',
            'status': status_code,
            'headers': [(k.encode(), v.encode()) for k, v in response_headers],
        })
        for chunk in body_parts:
            await send({
                'type': 'http.response.body',
                'body': chunk,
            })

    async def _handle_websocket(self, scope, receive, send):
        """Handle WebSocket connections."""
        path = scope['path']
        handler = self._ws_handlers.get(path)
        if not handler:
            await send({'type': 'websocket.close', 'code': 4004})
            return

        # Accept connection
        msg = await receive()
        if msg['type'] == 'websocket.connect':
            await send({'type': 'websocket.accept'})

        ws = ASGIWebSocket(receive, send)
        try:
            await handler(ws)
        except Exception:
            pass
        finally:
            if not ws._closed:
                await send({'type': 'websocket.close', 'code': 1000})


class ASGIWebSocket:
    """WebSocket wrapper for ASGI."""

    def __init__(self, receive, send):
        self._receive = receive
        self._send = send
        self._closed = False

    async def receive(self):
        msg = await self._receive()
        if msg['type'] == 'websocket.disconnect':
            self._closed = True
            return None
        return msg.get('text', msg.get('bytes', None))

    async def send(self, data):
        if isinstance(data, str):
            await self._send({'type': 'websocket.send', 'text': data})
        else:
            await self._send({'type': 'websocket.send', 'bytes': data})

    async def close(self, code=1000):
        self._closed = True
        await self._send({'type': 'websocket.close', 'code': code})


# ═══════════════════════════════════════════════════════════
#  Production Server (threaded, graceful shutdown)
# ═══════════════════════════════════════════════════════════

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class _WSGIRequestHandler(BaseHTTPRequestHandler):
    """Adapts WSGI app to stdlib HTTP server."""

    wsgi_app = None
    server_version = 'EPL/4.0'

    def do_request(self):
        content_length = int(self.headers.get('Content-Length', 0) or 0)
        body = self.rfile.read(content_length) if content_length > 0 else b''

        environ = {
            'REQUEST_METHOD': self.command,
            'PATH_INFO': urllib.parse.urlparse(self.path).path,
            'QUERY_STRING': urllib.parse.urlparse(self.path).query,
            'CONTENT_LENGTH': str(len(body)),
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'REMOTE_ADDR': self.client_address[0],
            'wsgi.input': io.BytesIO(body),
        }
        for key, value in self.headers.items():
            env_key = 'HTTP_' + key.upper().replace('-', '_')
            environ[env_key] = value

        response_started = [False]
        status_code = [200]
        response_headers_list = [[]]

        def start_response(status, headers, exc_info=None):
            status_code[0] = int(status.split(' ')[0])
            response_headers_list[0] = headers
            response_started[0] = True

        body_parts = self.wsgi_app(environ, start_response)

        self.send_response(status_code[0])
        for name, value in response_headers_list[0]:
            self.send_header(name, value)
        self.end_headers()
        for chunk in body_parts:
            self.wfile.write(chunk)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = lambda self: self.do_request()

    def log_message(self, format, *args):
        pass  # suppress default logging


def serve(app, host='0.0.0.0', port=8000):
    """Start a production-grade threaded HTTP server."""
    _WSGIRequestHandler.wsgi_app = app
    server = _ThreadedHTTPServer((host, port), _WSGIRequestHandler)

    def shutdown_handler(sig, frame):
        print(f"\n  Shutting down EPL server...")
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"  EPL Production Server v4.0")
    print(f"  Listening on http://{host}:{port}")
    print(f"  Press Ctrl+C to stop\n")

    server.serve_forever()


# ═══════════════════════════════════════════════════════════
#  Built-in Middleware
# ═══════════════════════════════════════════════════════════

def cors_middleware(allowed_origins='*'):
    """CORS middleware factory."""
    def middleware(request, response):
        origin = request.get_header('origin', '')
        if allowed_origins == '*' or origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = allowed_origins if isinstance(allowed_origins, str) else origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, PATCH, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            if request.method == 'OPTIONS':
                response.status = 204
                response._body = ''
                return response
        return None
    return middleware


def rate_limit_middleware(max_requests=100, window_seconds=60):
    """Rate limiting middleware."""
    _buckets = {}
    _lock = threading.Lock()

    def middleware(request, response):
        ip = request.remote_addr
        now = time.time()
        with _lock:
            if ip not in _buckets:
                _buckets[ip] = []
            _buckets[ip] = [t for t in _buckets[ip] if t > now - window_seconds]
            if len(_buckets[ip]) >= max_requests:
                response.status = 429
                response._body = json.dumps({'error': 'Too many requests'})
                response.content_type = 'application/json'
                return response
            _buckets[ip].append(now)
        return None
    return middleware


def auth_middleware(token_validator):
    """Token-based auth middleware."""
    def middleware(request, response):
        auth_header = request.get_header('authorization', '')
        if not auth_header.startswith('Bearer '):
            # Skip auth for public routes
            return None
        token = auth_header[7:]
        user = token_validator(token)
        if user is None:
            response.status = 401
            response._body = json.dumps({'error': 'Invalid token'})
            response.content_type = 'application/json'
            return response
        request.user = user
        return None
    return middleware


def logging_middleware():
    """Request logging middleware."""
    def middleware(request, response):
        start = time.time()
        # Store start time for post-processing
        request._start_time = start
        return None
    return middleware
