"""EPL Web Server (v4.0 Production-Grade)
Production HTTP server with: async I/O (asyncio), thread-pool executor for sync work,
connection-pooled SQLite, proper Request/Response abstractions, blueprint/router system,
ETag/streaming static files, template engine with inheritance, graceful shutdown,
structured access logging, multipart file uploads, WebSocket (RFC 6455), rate limiting,
PBKDF2 auth, middleware pipeline, CORS, gzip, HTTPS/TLS, CSRF, and full security headers.
"""
import json
import os
import re
import mimetypes
import threading
import hashlib
import hmac
import time
import uuid
import sqlite3
import ssl
import gzip
import io
import urllib.parse
import tempfile
import secrets
import struct
import base64
import signal
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from epl import ast_nodes as ast
from epl.html_gen import generate_html

# ─── Structured Logger ───────────────────────────────────
_access_logger = logging.getLogger('epl.web.access')
_error_logger = logging.getLogger('epl.web.error')

def configure_logging(level=logging.INFO, log_file=None):
    """Configure EPL web server logging."""
    fmt = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    _access_logger.addHandler(handler)
    _access_logger.setLevel(level)
    _error_logger.addHandler(handler)
    _error_logger.setLevel(level)
    if log_file:
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(fmt)
        _access_logger.addHandler(fh)
        _error_logger.addHandler(fh)

# Auto-configure with defaults
if not _access_logger.handlers:
    configure_logging()


# ─── Pluggable Store & Session Backends ──────────────────
from epl.store_backends import (
    get_store_backend, get_session_backend, configure_backends as _configure_backends
)

# Legacy compatibility: _data_store still exists as a dict-like proxy
class _StoreProxy(dict):
    """Dict-like proxy that delegates to the active store backend."""
    def __getitem__(self, key):
        return get_store_backend().store_get(key)
    def get(self, key, default=None):
        result = get_store_backend().store_get(key)
        return result if result else default
    def __setitem__(self, key, value):
        backend = get_store_backend()
        backend.store_clear(key)
        if isinstance(value, list):
            for item in value:
                backend.store_add(key, item)
    def __contains__(self, key):
        return get_store_backend().store_count(key) > 0
    def items(self):
        return get_store_backend().all_collections()
    def keys(self):
        return [k for k, v in self.items()]
    def __len__(self):
        return len(self.keys())
    def __bool__(self):
        return any(True for _ in self.items())
    def clear(self):
        get_store_backend().clear_all()
    def pop(self, key, *args):
        get_store_backend().store_clear(key)

_data_store = _StoreProxy()


# ─── SQLite Connection Pool ──────────────────────────────
class ConnectionPool:
    """Thread-safe SQLite connection pool.
    
    Each thread gets its own connection (required by SQLite).
    Connections are reused across requests on the same thread.
    WAL mode is enabled for concurrent reads + single writer.
    """
    def __init__(self, db_path, max_connections=16):
        self._db_path = db_path
        self._max = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
        self._all_conns = []

    def get(self):
        """Get a connection for the current thread."""
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            return conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=-8000')  # 8MB cache
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
        with self._lock:
            self._all_conns.append(conn)
        return conn

    def close_all(self):
        """Close all pooled connections (call on shutdown)."""
        with self._lock:
            for c in self._all_conns:
                try:
                    c.close()
                except Exception:
                    pass
            self._all_conns.clear()
        self._local.conn = None


_db_pool = None   # type: ConnectionPool | None
_db_path = None
_db_conn = None   # legacy single-connection fallback


def _get_db():
    """Get a database connection from the pool (or legacy fallback)."""
    if _db_pool:
        return _db_pool.get()
    return _db_conn


def init_db(path='epl_app.db'):
    """Initialize SQLite persistent storage with connection pool."""
    global _db_path, _db_conn, _db_pool
    _db_path = path
    _db_pool = ConnectionPool(path)
    conn = _db_pool.get()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS epl_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s','now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS epl_sessions (
            session_id TEXT PRIMARY KEY,
            data TEXT NOT NULL DEFAULT '{}',
            expires_at REAL NOT NULL
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_store_collection ON epl_store(collection)
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON epl_sessions(expires_at)
    ''')
    conn.commit()
    _db_conn = conn  # legacy compatibility


def db_store_add(collection, item):
    """Add item to persistent store."""
    conn = _get_db()
    if conn:
        conn.execute(
            'INSERT INTO epl_store (collection, data) VALUES (?, ?)',
            (collection, json.dumps(item, default=str))
        )
        conn.commit()
    store_add(collection, item)

def db_store_get(collection):
    """Get all items from persistent store."""
    conn = _get_db()
    if conn:
        rows = conn.execute(
            'SELECT data FROM epl_store WHERE collection = ? ORDER BY id',
            (collection,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]
    return store_get(collection)

def db_store_remove(collection, index):
    """Remove item by index from persistent store."""
    conn = _get_db()
    if conn:
        rows = conn.execute(
            'SELECT id FROM epl_store WHERE collection = ? ORDER BY id',
            (collection,)
        ).fetchall()
        if 0 <= index < len(rows):
            conn.execute('DELETE FROM epl_store WHERE id = ?', (rows[index][0],))
            conn.commit()
    store_remove(collection, index)

def db_store_clear(collection):
    """Clear all items in a collection from persistent store."""
    conn = _get_db()
    if conn:
        conn.execute('DELETE FROM epl_store WHERE collection = ?', (collection,))
        conn.commit()
    store_clear(collection)

def db_store_count(collection):
    """Count items in persistent store."""
    conn = _get_db()
    if conn:
        row = conn.execute(
            'SELECT COUNT(*) FROM epl_store WHERE collection = ?',
            (collection,)
        ).fetchone()
        return row[0]
    return store_count(collection)


# ─── Session Store (delegates to pluggable backend) ──────
SESSION_TIMEOUT = 3600  # 1 hour


def session_get(session_id, key, default=None):
    """Get a value from a session."""
    return get_session_backend().get(session_id, key, default)


def session_set(session_id, key, value):
    """Set a value in a session."""
    backend = get_session_backend()
    if not backend.exists(session_id):
        backend.create(timeout=SESSION_TIMEOUT)
    backend.set(session_id, key, value)


def session_create():
    """Create a new session ID (cryptographically secure)."""
    return get_session_backend().create(timeout=SESSION_TIMEOUT)


# ─── Middleware Registry ─────────────────────────────────
_middleware = []  # list of (name, func) pairs


def add_middleware(name, func):
    """Add a middleware function that runs before each request."""
    _middleware.append((name, func))


def clear_middleware():
    """Clear all middleware."""
    _middleware.clear()


def store_add(collection, item):
    """Add an item to a named collection."""
    get_store_backend().store_add(collection, item)


def store_get(collection):
    """Get all items from a named collection."""
    return get_store_backend().store_get(collection)


def store_remove(collection, index):
    """Remove an item by index from a collection."""
    get_store_backend().store_remove(collection, index)


def store_clear(collection):
    """Clear all items from a collection."""
    get_store_backend().store_clear(collection)


def store_count(collection):
    """Count items in a collection."""
    return get_store_backend().store_count(collection)


# ─── Auth Helpers ────────────────────────────────────────
_users_table_created = False

def _ensure_users_table():
    global _users_table_created
    if _db_conn and not _users_table_created:
        _db_conn.execute('''
            CREATE TABLE IF NOT EXISTS epl_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'user',
                created_at REAL DEFAULT (strftime('%s','now'))
            )
        ''')
        _db_conn.commit()
        _users_table_created = True

def hash_password(password, salt=None):
    """Hash a password with PBKDF2-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hashed.hex()}"

def verify_password(password, stored_hash):
    """Verify a password against a stored hash (timing-safe)."""
    if '$' not in stored_hash:
        return False
    salt = stored_hash.split('$')[0]
    computed = hash_password(password, salt)
    return hmac.compare_digest(computed, stored_hash)

def register_user(username, password, email='', role='user'):
    """Register a new user. Returns user id or None if exists."""
    if not _db_conn:
        return None
    _ensure_users_table()
    try:
        pw_hash = hash_password(password)
        _db_conn.execute(
            'INSERT INTO epl_users (username, password_hash, email, role) VALUES (?, ?, ?, ?)',
            (username, pw_hash, email, role)
        )
        _db_conn.commit()
        return _db_conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    except sqlite3.IntegrityError:
        return None

def authenticate_user(username, password):
    """Authenticate a user. Returns user dict or None."""
    if not _db_conn:
        return None
    _ensure_users_table()
    row = _db_conn.execute(
        'SELECT id, username, password_hash, email, role FROM epl_users WHERE username = ?',
        (username,)
    ).fetchone()
    if row and verify_password(password, row[2]):
        return {'id': row[0], 'username': row[1], 'email': row[3], 'role': row[4]}
    return None

def login_user(session_id, username, password):
    """Login a user and store in session. Returns (new_session_id, user) or (None, None).
    
    Regenerates session ID after login to prevent session fixation attacks.
    """
    user = authenticate_user(username, password)
    if user:
        # Regenerate session to prevent session fixation
        get_session_backend().delete(session_id)
        new_session_id = session_create()
        session_set(new_session_id, 'user_id', user['id'])
        session_set(new_session_id, 'username', user['username'])
        session_set(new_session_id, 'role', user['role'])
        session_set(new_session_id, 'logged_in', True)
        return new_session_id, user
    return session_id, None

def logout_user(session_id):
    """Logout current user from session."""
    get_session_backend().delete(session_id)

def get_current_user(session_id):
    """Get current logged-in user from session."""
    if session_get(session_id, 'logged_in'):
        return {
            'id': session_get(session_id, 'user_id'),
            'username': session_get(session_id, 'username'),
            'role': session_get(session_id, 'role'),
        }
    return None


# ─── Input Validation ────────────────────────────────────
def validate_email(email):
    """Basic email validation."""
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def validate_length(value, min_len=0, max_len=10000):
    """Check string length bounds."""
    return min_len <= len(str(value)) <= max_len

def sanitize_html(text):
    """Strip dangerous HTML — uses allowlist approach for safety.
    
    Removes all HTML tags except a safe allowlist
    (b, i, em, strong, a, br, p, ul, ol, li, code, pre).
    Strips all attributes except href on <a> tags (with safe protocol check).
    """
    import html as _html
    text = str(text)
    _SAFE_TAGS = {'b', 'i', 'em', 'strong', 'a', 'br', 'p', 'ul', 'ol', 'li', 'code', 'pre'}
    _SAFE_PROTO = {'http:', 'https:', 'mailto:'}
    result = []
    i = 0
    while i < len(text):
        if text[i] == '<':
            end = text.find('>', i)
            if end == -1:
                result.append(_html.escape(text[i:]))
                break
            tag_content = text[i+1:end].strip()
            is_closing = tag_content.startswith('/')
            tag_name = tag_content.lstrip('/').split()[0].lower() if tag_content.lstrip('/') else ''
            if tag_name in _SAFE_TAGS:
                if is_closing:
                    result.append(f'</{tag_name}>')
                elif tag_name == 'a':
                    # Extract href, validate protocol
                    href_match = re.search(r'href\s*=\s*["\']([^"\']*)["\']', tag_content, re.IGNORECASE)
                    if href_match:
                        href = href_match.group(1).strip()
                        proto = href.split('//')[0].lower() if '//' in href else href.split(':')[0].lower() + ':'
                        if proto in _SAFE_PROTO or not ':' in href:
                            result.append(f'<a href="{_html.escape(href)}">')
                        else:
                            result.append('<a href="#">')
                    else:
                        result.append('<a>')
                elif tag_name == 'br':
                    result.append('<br>')
                else:
                    result.append(f'<{tag_name}>')
            # else: unsafe tag, strip it entirely
            i = end + 1
        else:
            result.append(_html.escape(text[i]))
            i += 1
    return ''.join(result)

def csrf_token(session_id=None):
    """Generate a CSRF token and optionally store it in the session."""
    token = secrets.token_hex(32)
    if session_id:
        session_set(session_id, '_csrf_token', token)
    return token


# ─── Request / Response Abstractions ─────────────────────

class Request:
    """Structured HTTP request object passed to handlers and middleware."""
    __slots__ = ('method', 'path', 'query_string', 'query', 'headers',
                 'body_raw', 'body', 'form', 'files', 'params', 'session_id',
                 'user', 'client_ip', 'content_type', 'cookies', 'app')

    def __init__(self, method='GET', path='/', headers=None, body_raw=b'',
                 client_ip='127.0.0.1', app=None):
        self.method = method.upper()
        self.path = path.split('?')[0]
        self.query_string = path.split('?')[1] if '?' in path else ''
        self.query = dict(urllib.parse.parse_qsl(self.query_string))
        self.headers = headers or {}
        self.body_raw = body_raw
        self.body = None
        self.form = {}
        self.files = {}
        self.params = {}
        self.session_id = None
        self.user = None
        self.client_ip = client_ip
        self.content_type = (headers or {}).get('Content-Type',
                             (headers or {}).get('content-type', ''))
        self.cookies = self._parse_cookies()
        self.app = app

    def _parse_cookies(self):
        cookie_str = self.headers.get('Cookie', self.headers.get('cookie', ''))
        cookies = {}
        for part in cookie_str.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                cookies[k.strip()] = v.strip()
        return cookies

    def json(self):
        """Parse body as JSON."""
        if self.body is not None:
            return self.body
        if self.body_raw:
            raw = self.body_raw.decode('utf-8') if isinstance(self.body_raw, bytes) else self.body_raw
            try:
                self.body = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                self.body = {}
        return self.body or {}


class Response:
    """Structured HTTP response builder."""
    __slots__ = ('status', 'headers', '_body', 'content_type', '_cookies')

    def __init__(self, body='', status=200, content_type='text/html; charset=utf-8'):
        self.status = status
        self.headers = {}
        self._body = body
        self.content_type = content_type
        self._cookies = []

    def set_header(self, name, value):
        self.headers[name] = value
        return self

    def set_cookie(self, name, value, max_age=3600, httponly=True, secure=False,
                   samesite='Strict', path='/'):
        flags = f'{name}={value}; Path={path}; Max-Age={max_age}; SameSite={samesite}'
        if httponly:
            flags += '; HttpOnly'
        if secure:
            flags += '; Secure'
        self._cookies.append(flags)
        return self

    def json_body(self, data):
        self._body = json.dumps(data, indent=2, default=str)
        self.content_type = 'application/json; charset=utf-8'
        return self

    def html_body(self, html):
        self._body = html
        self.content_type = 'text/html; charset=utf-8'
        return self

    def redirect(self, location, status=303):
        self.status = status
        self.headers['Location'] = location
        self._body = ''
        return self

    def encode(self):
        """Encode body to bytes."""
        if isinstance(self._body, bytes):
            return self._body
        return self._body.encode('utf-8') if self._body else b''


# ─── Blueprint (Modular Route Groups) ────────────────────

class Blueprint:
    """Group related routes under a URL prefix with shared middleware.
    
    Usage:
        api = Blueprint('/api/v1')
        api.route('/users', 'json', handler, method='GET')
        app.register_blueprint(api)
    """
    def __init__(self, prefix=''):
        self.prefix = prefix.rstrip('/')
        self.routes = []       # (path, response_type, body, method)
        self.middleware = []    # (name, before_fn, after_fn)
        self.error_handlers = {}

    def route(self, path, response_type, body, method='GET'):
        full = self.prefix + path
        self.routes.append((full, response_type, body, method))
        return self

    def add_middleware(self, name, before_fn=None, after_fn=None):
        self.middleware.append((name, before_fn, after_fn))
        return self

    def on_error(self, code, handler_fn):
        self.error_handlers[code] = handler_fn
        return self


# ─── Template Engine ─────────────────────────────────────

class TemplateEngine:
    """Simple template engine with variable substitution, blocks, and includes.
    
    Syntax:
        {{ variable }}          - Variable substitution (auto-escaped)
        {{ variable|safe }}     - Raw output (no escaping)
        {% block name %}...{% endblock %}  - Define/override blocks
        {% extends "base.html" %}          - Inherit from a parent template
        {% include "partial.html" %}       - Include another template
        {% if condition %}...{% endif %}   - Conditional rendering
        {% for item in items %}...{% endfor %} - Loop
        {% raw %}...{% endraw %}           - Raw output without processing
    """
    def __init__(self, template_dir='templates'):
        self.template_dir = template_dir
        self._cache = {}  # path → (mtime, compiled)

    def render(self, template_name, context=None):
        """Render a template with the given context."""
        ctx = context or {}
        raw = self._load(template_name)
        return self._process(raw, ctx)

    def render_string(self, template_str, context=None):
        """Render an inline template string."""
        ctx = context or {}
        return self._process(template_str, ctx)

    def _load(self, name):
        """Load template from disk with mtime caching."""
        path = os.path.join(self.template_dir, name)
        path = os.path.normpath(path)
        # Path traversal check
        safe = os.path.normpath(os.path.abspath(self.template_dir))
        if not os.path.normpath(os.path.abspath(path)).startswith(safe):
            return f'<!-- Template access denied: {name} -->'
        try:
            mtime = os.path.getmtime(path)
            if path in self._cache and self._cache[path][0] == mtime:
                return self._cache[path][1]
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._cache[path] = (mtime, content)
            return content
        except FileNotFoundError:
            return f'<!-- Template not found: {name} -->'

    def _process(self, template, ctx, depth=0):
        """Process template string with context. Depth prevents infinite recursion."""
        import html as _html
        if depth > 10:
            return '<!-- Max template nesting depth exceeded -->'

        # Handle {% extends "base.html" %}
        extends_match = re.search(r'\{%\s*extends\s+"([^"]+)"\s*%\}', template)
        if extends_match:
            parent_name = extends_match.group(1)
            parent = self._load(parent_name)
            # Extract child blocks
            child_blocks = dict(re.findall(
                r'\{%\s*block\s+(\w+)\s*%\}(.*?)\{%\s*endblock\s*%\}',
                template, re.DOTALL
            ))
            # Replace parent blocks with child overrides
            def replace_block(m):
                bname = m.group(1)
                default = m.group(2)
                return child_blocks.get(bname, default)
            result = re.sub(
                r'\{%\s*block\s+(\w+)\s*%\}(.*?)\{%\s*endblock\s*%\}',
                replace_block, parent, flags=re.DOTALL
            )
            return self._process(result, ctx, depth + 1)

        # Handle {% include "partial.html" %}
        def do_include(m):
            inc_name = m.group(1)
            inc_content = self._load(inc_name)
            return self._process(inc_content, ctx, depth + 1)
        template = re.sub(r'\{%\s*include\s+"([^"]+)"\s*%\}', do_include, template)

        # Handle {% raw %}...{% endraw %}
        raw_blocks = {}
        raw_counter = [0]
        def save_raw(m):
            key = f'__RAW_{raw_counter[0]}__'
            raw_blocks[key] = m.group(1)
            raw_counter[0] += 1
            return key
        template = re.sub(r'\{%\s*raw\s*%\}(.*?)\{%\s*endraw\s*%\}',
                          save_raw, template, flags=re.DOTALL)

        # Handle {% for item in items %}...{% endfor %}
        def do_for(m):
            var_name = m.group(1)
            iter_name = m.group(2)
            body = m.group(3)
            items = ctx.get(iter_name, [])
            result_parts = []
            for i, item in enumerate(items):
                loop_ctx = dict(ctx)
                loop_ctx[var_name] = item
                loop_ctx['loop'] = {'index': i, 'index1': i + 1,
                                    'first': i == 0, 'last': i == len(items) - 1,
                                    'length': len(items)}
                result_parts.append(self._process(body, loop_ctx, depth + 1))
            return ''.join(result_parts)
        template = re.sub(
            r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}',
            do_for, template, flags=re.DOTALL
        )

        # Handle {% if condition %}...{% else %}...{% endif %}
        def do_if(m):
            cond_expr = m.group(1).strip()
            true_body = m.group(2)
            false_body = m.group(3) or ''
            # Simple condition evaluation (variable truthiness or comparison)
            val = self._eval_condition(cond_expr, ctx)
            return self._process(true_body if val else false_body, ctx, depth + 1)
        template = re.sub(
            r'\{%\s*if\s+(.+?)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}',
            do_if, template, flags=re.DOTALL
        )

        # Handle {% set var = expr %}
        def do_set(m):
            var_name = m.group(1).strip()
            expr = m.group(2).strip()
            # Simple expression evaluation: string literal, number, or variable lookup
            if (expr.startswith('"') and expr.endswith('"')) or \
               (expr.startswith("'") and expr.endswith("'")):
                ctx[var_name] = expr[1:-1]
            else:
                try:
                    ctx[var_name] = int(expr)
                except ValueError:
                    try:
                        ctx[var_name] = float(expr)
                    except ValueError:
                        ctx[var_name] = self._resolve(expr, ctx)
            return ''
        template = re.sub(r'\{%\s*set\s+(\w+)\s*=\s*(.+?)\s*%\}', do_set, template)

        # Handle {{ variable }}, {{ variable|filter }}, {{ x if cond else y }}
        def do_var(m):
            expr = m.group(1).strip()
            # Ternary: {{ x if condition else y }}
            ternary = re.match(r'(.+?)\s+if\s+(.+?)\s+else\s+(.+)', expr)
            if ternary:
                true_val = ternary.group(1).strip()
                cond = ternary.group(2).strip()
                false_val = ternary.group(3).strip()
                if self._eval_condition(cond, ctx):
                    val = self._resolve(true_val, ctx) if not true_val.startswith('"') else true_val.strip('"').strip("'")
                else:
                    val = self._resolve(false_val, ctx) if not false_val.startswith('"') else false_val.strip('"').strip("'")
                return _html.escape(str(val)) if val is not None else ''

            # Filter chain: {{ variable|filter1|filter2:arg }}
            parts = expr.split('|')
            var_expr = parts[0].strip()
            val = self._resolve(var_expr, ctx)

            for f in parts[1:]:
                f = f.strip()
                val = self._apply_filter(f, val)

            # If no filters, default is html-escape
            if len(parts) == 1:
                return _html.escape(str(val)) if val is not None else ''
            return str(val) if val is not None else ''
        template = re.sub(r'\{\{\s*(.+?)\s*\}\}', do_var, template)

        # Restore raw blocks
        for key, raw_content in raw_blocks.items():
            template = template.replace(key, raw_content)

        # Remove remaining block tags (from extends processing)
        template = re.sub(r'\{%\s*block\s+\w+\s*%\}', '', template)
        template = re.sub(r'\{%\s*endblock\s*%\}', '', template)

        return template

    def _resolve(self, expr, ctx):
        """Resolve a dotted variable expression like user.name."""
        parts = expr.split('.')
        val = ctx.get(parts[0])
        for part in parts[1:]:
            if val is None:
                return None
            if isinstance(val, dict):
                val = val.get(part)
            elif hasattr(val, part):
                val = getattr(val, part)
            else:
                return None
        return val

    def _apply_filter(self, filter_expr, val):
        """Apply a template filter to a value.
        
        Supported filters:
            safe        — No HTML escaping (raw output)
            upper       — Uppercase
            lower       — Lowercase
            title       — Title Case
            capitalize  — Capitalize first letter
            strip       — Strip whitespace
            length      — Length of string/list
            reverse     — Reverse string/list
            first       — First item
            last        — Last item
            sort        — Sort a list
            join:sep    — Join list with separator
            truncate:N  — Truncate to N characters with ...
            default:val — Default value if None/empty
            replace:o:n — Replace substring
            date:fmt    — Format a timestamp (strftime)
            url_encode  — URL-encode a string
            nl2br       — Newlines to <br> tags
            json        — JSON-encode
            abs         — Absolute value
            int         — Convert to integer
            float       — Convert to float
            round:N     — Round to N decimal places
        """
        import html as _html
        import urllib.parse as _urlparse

        # Parse filter name and arguments
        parts = filter_expr.split(':')
        name = parts[0].strip()
        args = parts[1:] if len(parts) > 1 else []

        if name == 'safe':
            return val  # No escaping
        if val is None:
            if name == 'default' and args:
                return args[0]
            return val

        s = str(val)

        if name == 'upper':
            return s.upper()
        elif name == 'lower':
            return s.lower()
        elif name == 'title':
            return s.title()
        elif name == 'capitalize':
            return s.capitalize()
        elif name == 'strip':
            return s.strip()
        elif name == 'length':
            return len(val) if hasattr(val, '__len__') else len(s)
        elif name == 'reverse':
            if isinstance(val, list):
                return list(reversed(val))
            return s[::-1]
        elif name == 'first':
            if isinstance(val, (list, tuple)) and val:
                return val[0]
            return s[0] if s else ''
        elif name == 'last':
            if isinstance(val, (list, tuple)) and val:
                return val[-1]
            return s[-1] if s else ''
        elif name == 'sort':
            if isinstance(val, list):
                return sorted(val)
            return val
        elif name == 'join':
            sep = args[0] if args else ', '
            if isinstance(val, (list, tuple)):
                return sep.join(str(x) for x in val)
            return s
        elif name == 'truncate':
            n = int(args[0]) if args else 50
            return (s[:n] + '...') if len(s) > n else s
        elif name == 'default':
            default_val = args[0] if args else ''
            return val if val else default_val
        elif name == 'replace':
            if len(args) >= 2:
                return s.replace(args[0], args[1])
            return s
        elif name == 'date':
            fmt = args[0] if args else '%Y-%m-%d'
            try:
                import datetime
                if isinstance(val, (int, float)):
                    dt = datetime.datetime.fromtimestamp(val)
                elif isinstance(val, str):
                    dt = datetime.datetime.fromisoformat(val)
                else:
                    return s
                return dt.strftime(fmt)
            except Exception:
                return s
        elif name == 'url_encode':
            return _urlparse.quote(s, safe='')
        elif name == 'nl2br':
            return _html.escape(s).replace('\n', '<br>')
        elif name == 'json':
            try:
                return json.dumps(val, default=str)
            except Exception:
                return s
        elif name == 'abs':
            try:
                return abs(int(val)) if isinstance(val, int) else abs(float(val))
            except (ValueError, TypeError):
                return val
        elif name == 'int':
            try:
                return int(float(s))
            except (ValueError, TypeError):
                return 0
        elif name == 'float':
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0
        elif name == 'round':
            n = int(args[0]) if args else 0
            try:
                return round(float(s), n)
            except (ValueError, TypeError):
                return val
        # Unknown filter — return as-is (escaped)
        return _html.escape(s)

    def _eval_condition(self, expr, ctx):
        """Evaluate a simple template condition."""
        # Handle "not variable"
        if expr.startswith('not '):
            return not self._eval_condition(expr[4:], ctx)
        # Handle "a == b"
        for op, fn in [('==', lambda a, b: a == b), ('!=', lambda a, b: a != b),
                       ('>=', lambda a, b: a >= b), ('<=', lambda a, b: a <= b),
                       ('>', lambda a, b: a > b), ('<', lambda a, b: a < b)]:
            if op in expr:
                left, right = expr.split(op, 1)
                l_val = self._resolve(left.strip(), ctx)
                r_raw = right.strip().strip('"').strip("'")
                try:
                    r_val = type(l_val)(r_raw) if l_val is not None else r_raw
                except (ValueError, TypeError):
                    r_val = r_raw
                return fn(l_val, r_val)
        # Simple truthiness
        return bool(self._resolve(expr, ctx))


class EPLWebApp:
    """Holds routes and configuration for an EPL web application."""

    def __init__(self, name):
        self.name = name
        self.routes = {}       # path → (type, method, handler_data)
        self.param_routes = {} # method → [(pattern_re, param_names, response_type, body)]
        self.static_dir = 'static'
        self.public_dir = 'public'
        self.cors_enabled = True
        self.cors_origins = 'same-origin'
        self.sessions_enabled = True
        self.middleware = []    # list of (name, before_fn, after_fn)
        self.db_enabled = False
        self.db_path = 'epl_app.db'
        self.rate_limit = 0    # requests per minute per IP (0 = disabled)
        self.upload_dir = 'uploads'
        self.upload_max_size = 10 * 1024 * 1024  # 10MB per file
        self.ssl_cert = None
        self.ssl_key = None
        self.gzip_enabled = True
        self.gzip_min_size = 1024  # min bytes to compress
        self.secret_key = secrets.token_hex(32)
        self.error_handlers = {}  # status_code → handler_fn
        self.websocket_handlers = {}  # path → handler_fn
        self.blueprints = []   # registered Blueprint instances
        self.template_engine = TemplateEngine()
        self.before_request_hooks = []   # [fn(request) → request|None]
        self.after_request_hooks = []    # [fn(request, response) → response|None]
        self.teardown_hooks = []         # [fn(exc) → None]
        self._health_path = '/_health'   # built-in health check
        self._metrics = {'requests': 0, 'errors': 0, 'start_time': time.time()}

    def configure_backends(self, store='memory', session='memory', **kwargs):
        """Configure store and session backends.
        
        Args:
            store: 'memory', 'sqlite', or 'redis'
            session: 'memory', 'sqlite', or 'redis'
            **kwargs: Backend-specific options:
                redis_url: Redis connection URL (default: redis://localhost:6379/0)
                sqlite_store_path: SQLite store DB path (default: epl_store.db)
                sqlite_session_path: SQLite session DB path (default: epl_sessions.db)
                session_timeout: Session timeout in seconds (default: 3600)
        """
        _configure_backends(store=store, session=session, **kwargs)
        return self

    def _compile_param_route(self, path, method, response_type, body):
        """Compile a parameterized route like /users/:id into a regex."""
        param_names = re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', path)
        if not param_names:
            return False
        # Convert :param to named group
        pattern = path
        for pn in param_names:
            pattern = pattern.replace(f':{pn}', f'(?P<{pn}>[^/]+)')
        pattern = f'^{pattern}$'
        if method not in self.param_routes:
            self.param_routes[method] = []
        self.param_routes[method].append((re.compile(pattern), param_names, response_type, body))
        return True

    def add_route(self, path, response_type, body, method='GET'):
        """Register a route with its response type and body."""
        # Check if this is a parameterized route
        if ':' in path:
            self._compile_param_route(path, method, response_type, body)
            return
        key = f"{method}:{path}"
        self.routes[key] = (response_type, body)
        # Also store under path for GET fallback
        if method == 'GET':
            self.routes[path] = (response_type, body)

    def get_route(self, path, method='GET'):
        """Get route data for a path + method. Returns (response_type, body, params) or None."""
        # Try exact method-specific first
        key = f"{method}:{path}"
        if key in self.routes:
            rtype, body = self.routes[key]
            return (rtype, body, {})
        # Try path only (GET fallback)
        if path in self.routes:
            rtype, body = self.routes[path]
            return (rtype, body, {})
        # Try parameterized routes
        for m in [method, 'GET']:
            for pattern, param_names, rtype, body in self.param_routes.get(m, []):
                match = pattern.match(path)
                if match:
                    return (rtype, body, match.groupdict())
        return None

    def add_middleware(self, name, before_fn=None, after_fn=None):
        """Add middleware. before_fn(request) is called before routing, after_fn(request, response) after."""
        self.middleware.append((name, before_fn, after_fn))

    def on_error(self, status_code, handler_fn):
        """Register a custom error handler."""
        self.error_handlers[status_code] = handler_fn

    def enable_https(self, certfile, keyfile):
        """Enable HTTPS with SSL certificate."""
        self.ssl_cert = certfile
        self.ssl_key = keyfile

    def enable_database(self, path=None):
        """Enable SQLite persistent storage for this app."""
        self.db_enabled = True
        if path:
            self.db_path = path
        init_db(self.db_path)

    def on_websocket(self, path, handler):
        """Register a WebSocket handler for a path."""
        self.websocket_handlers[path] = handler

    def register_blueprint(self, blueprint):
        """Register a Blueprint, merging its routes and middleware into the app."""
        self.blueprints.append(blueprint)
        for path, rtype, body, method in blueprint.routes:
            self.add_route(path, rtype, body, method=method)
        for mw in blueprint.middleware:
            self.middleware.append(mw)
        self.error_handlers.update(blueprint.error_handlers)

    def before_request(self, fn):
        """Register a function to run before each request. Can be used as decorator."""
        self.before_request_hooks.append(fn)
        return fn

    def after_request(self, fn):
        """Register a function to run after each request. Can be used as decorator."""
        self.after_request_hooks.append(fn)
        return fn

    def teardown(self, fn):
        """Register a cleanup function to run after response is sent."""
        self.teardown_hooks.append(fn)
        return fn

    def render_template(self, template_name, **context):
        """Render a template file using the built-in template engine."""
        return self.template_engine.render(template_name, context)

    def health_check(self):
        """Return health status for monitoring/load balancer probes."""
        from epl import __version__
        uptime = time.time() - self._metrics['start_time']
        return {
            'status': 'healthy',
            'uptime_seconds': round(uptime, 1),
            'total_requests': self._metrics['requests'],
            'total_errors': self._metrics['errors'],
            'version': __version__,
        }


# ─── WebSocket Implementation (RFC 6455) ─────────────────

WS_MAGIC = b'258EAFA5-E914-47DA-95CA-5AB9DC586B35'
WS_OPCODE_TEXT = 0x1
WS_OPCODE_BINARY = 0x2
WS_OPCODE_CLOSE = 0x8
WS_OPCODE_PING = 0x9
WS_OPCODE_PONG = 0xA


class WebSocketConnection:
    """Represents a single WebSocket connection with send/receive capabilities."""

    def __init__(self, socket, address, path, app):
        self.socket = socket
        self.address = address
        self.path = path
        self.app = app
        self.is_open = True
        self._lock = threading.Lock()

    def send(self, message):
        """Send a text message to the client."""
        if not self.is_open:
            return
        if isinstance(message, dict):
            message = json.dumps(message)
        data = message.encode('utf-8') if isinstance(message, str) else message
        self._send_frame(WS_OPCODE_TEXT, data)

    def send_binary(self, data):
        """Send binary data to the client."""
        if not self.is_open:
            return
        self._send_frame(WS_OPCODE_BINARY, data)

    def close(self, code=1000, reason=''):
        """Close the WebSocket connection gracefully."""
        if not self.is_open:
            return
        self.is_open = False
        payload = struct.pack('!H', code) + reason.encode('utf-8')
        try:
            self._send_frame(WS_OPCODE_CLOSE, payload)
        except Exception:
            pass

    def _send_frame(self, opcode, data):
        """Encode and send a WebSocket frame."""
        with self._lock:
            frame = bytearray()
            frame.append(0x80 | opcode)  # FIN + opcode

            length = len(data)
            if length < 126:
                frame.append(length)
            elif length < 65536:
                frame.append(126)
                frame.extend(struct.pack('!H', length))
            else:
                frame.append(127)
                frame.extend(struct.pack('!Q', length))

            frame.extend(data)
            try:
                self.socket.sendall(bytes(frame))
            except (BrokenPipeError, ConnectionResetError, OSError):
                self.is_open = False

    def _recv_frame(self):
        """Read and decode a single WebSocket frame. Returns (opcode, payload) or (None, None)."""
        try:
            header = self._recv_exact(2)
            if not header:
                return None, None

            fin = (header[0] >> 7) & 1
            opcode = header[0] & 0x0F
            masked = (header[1] >> 7) & 1
            payload_len = header[1] & 0x7F

            if payload_len == 126:
                raw = self._recv_exact(2)
                if not raw:
                    return None, None
                payload_len = struct.unpack('!H', raw)[0]
            elif payload_len == 127:
                raw = self._recv_exact(8)
                if not raw:
                    return None, None
                payload_len = struct.unpack('!Q', raw)[0]

            # Limit frame size to 16MB
            if payload_len > 16 * 1024 * 1024:
                return None, None

            mask_key = None
            if masked:
                mask_key = self._recv_exact(4)
                if not mask_key:
                    return None, None

            payload = self._recv_exact(payload_len) if payload_len > 0 else b''
            if payload is None:
                return None, None

            if mask_key:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            return opcode, payload
        except (ConnectionResetError, BrokenPipeError, OSError):
            return None, None

    def _recv_exact(self, n):
        """Read exactly n bytes from the socket."""
        data = b''
        while len(data) < n:
            try:
                chunk = self.socket.recv(n - len(data))
                if not chunk:
                    return None
                data += chunk
            except (ConnectionResetError, BrokenPipeError, OSError):
                return None
        return data


class WebSocketRoom:
    """Manages a group of WebSocket connections for broadcasting."""

    def __init__(self, name):
        self.name = name
        self._connections = set()
        self._lock = threading.Lock()

    def join(self, conn):
        """Add a connection to this room."""
        with self._lock:
            self._connections.add(conn)

    def leave(self, conn):
        """Remove a connection from this room."""
        with self._lock:
            self._connections.discard(conn)

    def broadcast(self, message, exclude=None):
        """Send a message to all connections in the room, optionally excluding one."""
        with self._lock:
            targets = list(self._connections)
        for conn in targets:
            if conn is not exclude and conn.is_open:
                try:
                    conn.send(message)
                except Exception:
                    pass

    @property
    def count(self):
        with self._lock:
            return len(self._connections)


# Global WebSocket rooms registry
_ws_rooms = {}
_ws_rooms_lock = threading.Lock()

def get_ws_room(name):
    """Get or create a WebSocket room by name."""
    with _ws_rooms_lock:
        if name not in _ws_rooms:
            _ws_rooms[name] = WebSocketRoom(name)
        return _ws_rooms[name]


def _handle_websocket_upgrade(handler):
    """Handle WebSocket upgrade request. Returns True if upgraded, False otherwise."""
    # Check required headers
    upgrade = handler.headers.get('Upgrade', '').lower()
    connection = handler.headers.get('Connection', '').lower()
    ws_key = handler.headers.get('Sec-WebSocket-Key', '')
    ws_version = handler.headers.get('Sec-WebSocket-Version', '')

    if upgrade != 'websocket' or 'upgrade' not in connection or not ws_key:
        return False

    path = handler.path.split('?')[0]
    app = handler.app
    if not app or path not in app.websocket_handlers:
        return False

    # Compute accept key (RFC 6455 §4.2.2)
    accept_raw = base64.b64encode(
        hashlib.sha1(ws_key.encode('ascii') + WS_MAGIC).digest()
    ).decode('ascii')

    # Send 101 Switching Protocols
    response = (
        'HTTP/1.1 101 Switching Protocols\r\n'
        'Upgrade: websocket\r\n'
        'Connection: Upgrade\r\n'
        f'Sec-WebSocket-Accept: {accept_raw}\r\n'
        '\r\n'
    )
    handler.wfile.write(response.encode('ascii'))
    handler.wfile.flush()

    # Create WebSocket connection object
    ws = WebSocketConnection(handler.request, handler.client_address, path, app)

    # Get the handler function
    ws_handler = app.websocket_handlers[path]

    # Run handler in a separate thread so the HTTP handler can return
    def _ws_loop():
        try:
            # Call on_open if handler is a dict with callbacks
            if isinstance(ws_handler, dict):
                on_open = ws_handler.get('on_open')
                on_message = ws_handler.get('on_message')
                on_close = ws_handler.get('on_close')
                on_error = ws_handler.get('on_error')

                if on_open:
                    on_open(ws)

                while ws.is_open:
                    opcode, payload = ws._recv_frame()
                    if opcode is None:
                        break
                    if opcode == WS_OPCODE_CLOSE:
                        ws.is_open = False
                        break
                    elif opcode == WS_OPCODE_PING:
                        ws._send_frame(WS_OPCODE_PONG, payload)
                    elif opcode in (WS_OPCODE_TEXT, WS_OPCODE_BINARY):
                        msg = payload.decode('utf-8') if opcode == WS_OPCODE_TEXT else payload
                        if on_message:
                            try:
                                on_message(ws, msg)
                            except Exception as e:
                                if on_error:
                                    on_error(ws, e)

                if on_close:
                    on_close(ws)
            else:
                # Simple handler: call with (ws) and let it manage the loop
                ws_handler(ws)
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            ws.is_open = False
            try:
                ws.socket.close()
            except Exception:
                pass

    t = threading.Thread(target=_ws_loop, daemon=True)
    t.start()
    return True


# ─── Rate Limiter ────────────────────────────────────────
_rate_tracker = {}  # ip → [timestamps]

def _check_rate_limit(ip, limit):
    """Check if IP exceeds rate limit. Returns True if allowed."""
    if limit <= 0:
        return True
    now = time.time()
    if ip not in _rate_tracker:
        _rate_tracker[ip] = []
    # Remove old entries (older than 60 seconds)
    _rate_tracker[ip] = [t for t in _rate_tracker[ip] if now - t < 60]
    if len(_rate_tracker[ip]) >= limit:
        return False
    _rate_tracker[ip].append(now)
    # Periodic cleanup of stale IPs (every 100 requests)
    if sum(1 for _ in _rate_tracker) > 1000:
        stale = [k for k, v in _rate_tracker.items() if not v or now - v[-1] > 120]
        for k in stale:
            del _rate_tracker[k]
    return True


class EPLHandler(BaseHTTPRequestHandler):
    """HTTP request handler for EPL web apps."""

    app = None          # set by the server factory
    interpreter = None  # set to evaluate expressions

    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB max request body

    def _get_session_id(self):
        """Extract or create session ID from cookies."""
        cookies = self.headers.get('Cookie', '')
        for part in cookies.split(';'):
            part = part.strip()
            if part.startswith('epl_session='):
                return part.split('=', 1)[1]
        return None

    def _apply_cors(self):
        """Add CORS headers if enabled."""
        if self.app and self.app.cors_enabled:
            self.send_header('Access-Control-Allow-Origin', self.app.cors_origins)
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._apply_cors()
        self.end_headers()

    def _check_rate(self):
        """Check rate limit. Returns True if allowed."""
        if self.app and self.app.rate_limit > 0:
            ip = self.client_address[0]
            if not _check_rate_limit(ip, self.app.rate_limit):
                self._send_error(429, "Too many requests. Please slow down.")
                return False
        return True

    def _run_middleware_before(self):
        """Run before-middleware. Returns False if request should be aborted."""
        for name, before_fn, after_fn in (self.app.middleware if self.app else []):
            if before_fn:
                try:
                    result = before_fn(self)
                    if result is False:
                        return False
                except Exception as e:
                    print(f"  [middleware:{name}] Error: {e}")
        # Also run global middleware
        for name, func in _middleware:
            try:
                result = func(self)
                if result is False:
                    return False
            except Exception as e:
                print(f"  [middleware:{name}] Error: {e}")
        return True

    def _add_security_headers(self):
        """Add security headers to response."""
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('X-XSS-Protection', '0')  # Deprecated; CSP is used instead
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=()')
        # HSTS when HTTPS is enabled
        if self.app and self.app.ssl_cert:
            self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

    def _compress_response(self, data):
        """Gzip compress response if client supports it and data is large enough."""
        if not (self.app and self.app.gzip_enabled):
            return data, False
        if len(data) < self.app.gzip_min_size:
            return data, False
        accept = self.headers.get('Accept-Encoding', '')
        if 'gzip' not in accept:
            return data, False
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb') as f:
            f.write(data if isinstance(data, bytes) else data.encode('utf-8'))
        return buf.getvalue(), True

    def do_GET(self):
        # Track metrics
        if self.app:
            self.app._metrics['requests'] += 1
        start_time = time.time()

        # Health check endpoint
        path_clean = self.path.split('?')[0]
        if self.app and path_clean == self.app._health_path:
            health = self.app.health_check()
            self._send_json(health)
            return

        # WebSocket upgrade check (before rate limiting)
        if self.headers.get('Upgrade', '').lower() == 'websocket':
            if _handle_websocket_upgrade(self):
                return
            self._send_error(400, 'WebSocket upgrade failed')
            return

        if not self._check_rate():
            return
        if not self._run_middleware_before():
            return
        path = self.path.split('?')[0]
        query_string = self.path.split('?')[1] if '?' in self.path else ''

        # Parse query params
        query_params = dict(urllib.parse.parse_qsl(query_string))

        # Try static file serving first
        if self._serve_static(path):
            self._log_access('GET', path, 200, start_time)
            return

        route = self.app.get_route(path, 'GET')
        if route:
            response_type, body, route_params = route
            query_params.update(route_params)  # merge route params
            self._handle_route(response_type, body, params=query_params)
            self._log_access('GET', path, 200, start_time)
            return

        self._send_error(404, f"Route not found: {path}")
        self._log_access('GET', path, 404, start_time)

    def _read_body(self):
        """Read and parse the request body. Handles JSON, form-urlencoded, and multipart."""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return '', {}
        if content_length > self.MAX_BODY_SIZE:
            self._send_error(413, 'Request body too large')
            return '', {}
        raw = self.rfile.read(content_length)
        ct = self.headers.get('Content-Type', '')

        # JSON
        if 'json' in ct.lower():
            raw_text = raw.decode('utf-8', errors='replace')
            try:
                return raw_text, json.loads(raw_text)
            except json.JSONDecodeError:
                return raw_text, {}

        # Multipart form data (file uploads)
        if 'multipart/form-data' in ct.lower():
            return self._parse_multipart(raw, ct)

        # Default: form-urlencoded
        raw_text = raw.decode('utf-8', errors='replace')
        return raw_text, dict(urllib.parse.parse_qsl(raw_text))

    def _parse_multipart(self, raw, content_type):
        """Parse multipart/form-data for file uploads."""
        boundary_match = re.search(r'boundary=([^\s;]+)', content_type)
        if not boundary_match:
            return '', {}
        boundary = boundary_match.group(1).encode()
        parts = raw.split(b'--' + boundary)
        form_data = {}
        files = {}

        for part in parts:
            if part in (b'', b'--\r\n', b'--'):
                continue
            part = part.strip(b'\r\n')
            if b'\r\n\r\n' not in part:
                continue
            header_section, body = part.split(b'\r\n\r\n', 1)
            # Strip trailing --
            if body.endswith(b'--'):
                body = body[:-2]
            body = body.rstrip(b'\r\n')

            headers_text = header_section.decode('utf-8', errors='replace')
            name_match = re.search(r'name="([^"]*)"', headers_text)
            filename_match = re.search(r'filename="([^"]*)"', headers_text)

            if not name_match:
                continue
            field_name = name_match.group(1)

            if filename_match:
                # File upload
                filename = filename_match.group(1)
                if not filename:
                    continue
                # Sanitize filename
                filename = os.path.basename(filename)
                filename = re.sub(r'[^\w\-_. ]', '_', filename)

                # Check file size against app limit
                max_size = self.app.upload_max_size if self.app else 10 * 1024 * 1024
                if len(body) > max_size:
                    continue

                # Save to upload dir
                upload_dir = self.app.upload_dir if self.app else 'uploads'
                os.makedirs(upload_dir, exist_ok=True)
                # Add unique prefix to prevent overwrites
                safe_name = f"{secrets.token_hex(8)}_{filename}"
                filepath = os.path.join(upload_dir, safe_name)
                # Path traversal check
                abs_upload = os.path.normpath(os.path.abspath(upload_dir))
                abs_file = os.path.normpath(os.path.abspath(filepath))
                if not abs_file.startswith(abs_upload):
                    continue
                with open(filepath, 'wb') as f:
                    f.write(body)
                files[field_name] = {
                    'filename': filename,
                    'saved_as': safe_name,
                    'path': filepath,
                    'size': len(body),
                    'content_type': re.search(
                        r'Content-Type:\s*(.+)', headers_text, re.IGNORECASE
                    ).group(1).strip() if re.search(
                        r'Content-Type:', headers_text, re.IGNORECASE
                    ) else 'application/octet-stream'
                }
            else:
                # Regular form field
                form_data[field_name] = body.decode('utf-8', errors='replace')

        # Merge files info into form_data under '_files' key
        if files:
            form_data['_files'] = files
        return '', form_data

    def do_POST(self):
        if not self._check_rate():
            return
        if not self._run_middleware_before():
            return
        path = self.path.split('?')[0]
        raw_body, form_data = self._read_body()

        # Validate CSRF token on state-changing requests
        if not self._validate_csrf(form_data):
            self._send_error(403, 'CSRF token validation failed')
            return

        # Try POST-specific route first, then fallback to GET route
        route = self.app.get_route(path, 'POST')
        if route is None:
            route = self.app.get_route(path, 'GET')

        if route:
            response_type, body, route_params = route
            form_data.update(route_params)  # merge route params
            self._handle_route(response_type, body, form_data=form_data)
            return

        self._send_error(404, f"Route not found: {path}")

    def do_PUT(self):
        if not self._check_rate():
            return
        if not self._run_middleware_before():
            return
        path = self.path.split('?')[0]
        raw_body, form_data = self._read_body()

        # Validate CSRF token on state-changing requests
        if not self._validate_csrf(form_data):
            self._send_error(403, 'CSRF token validation failed')
            return

        route = self.app.get_route(path, 'PUT')
        if route:
            response_type, body, route_params = route
            form_data.update(route_params)
            self._handle_route(response_type, body, form_data=form_data)
            return
        self._send_error(404, f"Route not found: {path}")

    def do_DELETE(self):
        if not self._check_rate():
            return
        if not self._run_middleware_before():
            return
        path = self.path.split('?')[0]
        raw_body, form_data = self._read_body()

        # Validate CSRF token on state-changing requests
        if not self._validate_csrf(form_data):
            self._send_error(403, 'CSRF token validation failed')
            return

        route = self.app.get_route(path, 'DELETE')
        if route:
            response_type, body, route_params = route
            form_data.update(route_params)
            self._handle_route(response_type, body, form_data=form_data)
            return
        self._send_error(404, f"Route not found: {path}")

    def _handle_route(self, response_type, body, form_data=None, params=None):
        """Process a matched route."""
        if response_type == 'callable':
            # Python callable handler — call with Request object
            req = Request(
                method=self.command,
                path=self.path,
                headers=dict(self.headers),
                body_raw=b'',
                client_ip=self.client_address[0] if self.client_address else '127.0.0.1',
                app=self.app
            )
            req.form = form_data or {}
            req.params = params or {}
            req.session_id = self._get_session_id()
            try:
                result = body(req)
                if isinstance(result, Response):
                    self._send_response_obj(result)
                elif isinstance(result, dict):
                    self._send_json(result)
                elif isinstance(result, str):
                    self._send_html(result)
                else:
                    self._send_html(str(result) if result else '<p>OK</p>')
            except Exception as e:
                self._send_error(500, f'Handler error: {e}')
            return
        if response_type == 'page':
            html = self._build_page(body, form_data=form_data, params=params)
            if html.startswith('REDIRECT:'):
                location = html[len('REDIRECT:'):]
                self._send_redirect(location)
            else:
                self._send_html(html)
        elif response_type == 'json':
            data = self._build_json(body)
            self._send_json(data)
        elif response_type == 'action':
            # Execute action statements, then check for redirect
            result = self._execute_action(body, form_data=form_data)
            if result and result.startswith('REDIRECT:'):
                self._send_redirect(result[len('REDIRECT:'):])
            else:
                self._send_html(result or '<p>OK</p>')

    def _build_page(self, body, form_data=None, params=None):
        """Build HTML from route body statements."""
        # Execute all Store/Delete/Redirect statements in a single pass
        for stmt in body:
            # Handle Store statements
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store(stmt, form_data)
                continue

            # Handle Delete statements
            if isinstance(stmt, ast.DeleteStatement):
                self._exec_delete(stmt, form_data)
                continue

            # Handle Redirect - immediately return
            if isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                redirect_url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{redirect_url}'

        # Build page
        for stmt in body:
            if isinstance(stmt, ast.PageDef):
                return generate_html(stmt, data_store=_data_store, form_data=form_data)

        # If no PageDef, check for elements
        elements = [s for s in body if isinstance(s, ast.HtmlElement)]
        if elements:
            page = ast.PageDef("EPL Page", elements)
            return generate_html(page, data_store=_data_store, form_data=form_data)

        return generate_html(ast.PageDef("EPL Page", []), data_store=_data_store)

    def _execute_stores(self, body, form_data=None):
        """Execute Store and Delete statements in route body."""
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store(stmt, form_data)
            if isinstance(stmt, ast.DeleteStatement):
                self._exec_delete(stmt, form_data)

    def _exec_store(self, stmt, form_data=None):
        """Execute a single Store statement (in-memory + SQLite if enabled)."""
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
            except Exception as e:
                import sys
                print(f"Warning: Store evaluation error: {e}", file=sys.stderr)

    def _exec_delete(self, stmt, form_data=None):
        """Execute a single Delete statement (in-memory + SQLite if enabled)."""
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
        elif stmt.index is not None and self.interpreter:
            try:
                index = self.interpreter._eval(stmt.index, self.interpreter.global_env)
                if self.app.db_enabled:
                    db_store_remove(collection, int(index))
                else:
                    store_remove(collection, int(index))
            except Exception as e:
                import sys
                print(f"Warning: Delete evaluation error: {e}", file=sys.stderr)

    def _execute_action(self, body, form_data=None):
        """Execute action route body and return redirect or HTML."""
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store(stmt, form_data)
            elif isinstance(stmt, ast.DeleteStatement):
                self._exec_delete(stmt, form_data)
            elif isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                redirect_url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{redirect_url}'
        return None

    def _build_json(self, body):
        """Build JSON from route body - evaluate Send or Fetch statements."""
        for stmt in body:
            # Fetch "collection" → return collection data as JSON
            if isinstance(stmt, ast.FetchStatement):
                collection = stmt.collection
                items = store_get(collection)
                return self._normalize_json_value(
                    {"collection": collection, "count": len(items), "items": items}
                )

            if isinstance(stmt, ast.SendResponse):
                if self.interpreter:
                    try:
                        result = self.interpreter._eval(stmt.data, self.interpreter.global_env)
                        return self._normalize_json_value(result)
                    except Exception as e:
                        return {"error": str(e)}
        # Fallback: return all store data
        return self._normalize_json_value({"store": {k: list(v) for k, v in _data_store.items()}})

    def _normalize_json_value(self, value):
        """Convert EPL runtime values into JSON-safe Python structures."""
        if isinstance(value, dict):
            return {k: self._normalize_json_value(v) for k, v in value.items()}
        if hasattr(value, 'data'):
            return {k: self._normalize_json_value(v) for k, v in value.data.items()}
        if isinstance(value, list):
            return [self._normalize_json_value(v) for v in value]
        if isinstance(value, tuple):
            return [self._normalize_json_value(v) for v in value]
        if isinstance(value, (bool, int, float, str)) or value is None:
            return value
        if self.interpreter and hasattr(self.interpreter, '_epl_to_python'):
            return self.interpreter._epl_to_python(value)
        return str(value)

    def _set_session_cookie(self, session_id):
        """Set session cookie with secure flags."""
        is_https = self.app and self.app.ssl_cert
        flags = 'HttpOnly; SameSite=Strict; Path=/'
        if is_https:
            flags += '; Secure'
        self.send_header('Set-Cookie', f'epl_session={session_id}; {flags}')

    def _validate_csrf(self, form_data):
        """Validate CSRF token on POST/PUT/DELETE requests."""
        if not (self.app and self.app.sessions_enabled):
            return True
        session_id = self._get_session_id()
        if not session_id:
            return True  # No session means no CSRF token expected
        expected = session_get(session_id, '_csrf_token')
        if not expected:
            return True  # No CSRF token in session
        token = (form_data or {}).get('_csrf_token', '') or self.headers.get('X-CSRF-Token', '')
        return hmac.compare_digest(str(expected), str(token))

    def _send_html(self, html):
        raw = html.encode('utf-8')
        compressed, is_gzipped = self._compress_response(raw)
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        if is_gzipped:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(compressed)))
        session_id = self._get_session_id()
        if session_id:
            self._set_session_cookie(session_id)
        self._apply_cors()
        self._add_security_headers()
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(compressed)

    def _send_json(self, data):
        try:
            body = json.dumps(data, indent=2, default=str)
        except Exception:
            body = json.dumps({"error": "Could not serialize data"})
        raw = body.encode('utf-8')
        compressed, is_gzipped = self._compress_response(raw)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        if is_gzipped:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(compressed)))
        self._apply_cors()
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(compressed)

    def _send_redirect(self, location):
        """HTTP 303 redirect (See Other) - always redirects to GET."""
        self.send_response(303)
        self.send_header('Location', location)
        self._apply_cors()
        self.end_headers()

    def _send_response_obj(self, response):
        """Send a Response object directly."""
        body = response.encode()
        compressed, is_gzipped = self._compress_response(body)
        self.send_response(response.status)
        self.send_header('Content-Type', response.content_type)
        if is_gzipped:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(compressed)))
        for k, v in response.headers.items():
            self.send_header(k, v)
        for cookie in response._cookies:
            self.send_header('Set-Cookie', cookie)
        self._apply_cors()
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(compressed)

    def _serve_static(self, path):
        """Serve static files with ETag, Last-Modified, Range, and streaming."""
        for d in [self.app.static_dir, self.app.public_dir]:
            if not d:
                continue
            fp = os.path.normpath(os.path.join(d, path.lstrip('/')))
            # Path traversal protection
            safe_root = os.path.normpath(os.path.abspath(d))
            abs_fp = os.path.normpath(os.path.abspath(fp))
            if not abs_fp.startswith(safe_root):
                continue
            if os.path.isfile(fp):
                ctype, _ = mimetypes.guess_type(fp)
                if not ctype:
                    ctype = 'application/octet-stream'
                try:
                    stat = os.stat(fp)
                    mtime = stat.st_mtime
                    size = stat.st_size

                    # ETag: hash of path + mtime + size
                    etag_raw = f'{fp}:{mtime}:{size}'.encode()
                    etag = '"' + hashlib.md5(etag_raw).hexdigest() + '"'

                    # Last-Modified
                    last_modified = time.strftime(
                        '%a, %d %b %Y %H:%M:%S GMT', time.gmtime(mtime)
                    )

                    # 304 Not Modified: ETag match
                    if_none = self.headers.get('If-None-Match', '')
                    if if_none == etag:
                        self.send_response(304)
                        self.send_header('ETag', etag)
                        self.end_headers()
                        return True

                    # 304 Not Modified: If-Modified-Since
                    ims = self.headers.get('If-Modified-Since', '')
                    if ims:
                        try:
                            ims_time = time.mktime(time.strptime(
                                ims, '%a, %d %b %Y %H:%M:%S GMT')) - time.timezone
                            if mtime <= ims_time:
                                self.send_response(304)
                                self.send_header('ETag', etag)
                                self.end_headers()
                                return True
                        except (ValueError, OverflowError):
                            pass

                    # Range request support (single range)
                    range_header = self.headers.get('Range', '')
                    if range_header.startswith('bytes=') and '-' in range_header[6:]:
                        range_spec = range_header[6:]
                        parts = range_spec.split('-', 1)
                        start = int(parts[0]) if parts[0] else 0
                        end = int(parts[1]) if parts[1] else size - 1
                        end = min(end, size - 1)
                        if start >= size or start > end:
                            self.send_response(416)
                            self.send_header('Content-Range', f'bytes */{size}')
                            self.end_headers()
                            return True
                        length = end - start + 1
                        self.send_response(206)
                        self.send_header('Content-Type', ctype)
                        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                        self.send_header('Content-Length', str(length))
                        self.send_header('Accept-Ranges', 'bytes')
                        self.send_header('ETag', etag)
                        self.send_header('Last-Modified', last_modified)
                        self.end_headers()
                        with open(fp, 'rb') as f:
                            f.seek(start)
                            remaining = length
                            while remaining > 0:
                                chunk = f.read(min(remaining, 65536))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                        return True

                    # Full response (streaming for large files)
                    # Cache headers by type
                    if ctype.startswith('image/') or ctype.startswith('font/'):
                        cache_control = 'public, max-age=604800, immutable'  # 7 days
                    elif ctype in ('text/css', 'application/javascript',
                                   'text/javascript'):
                        cache_control = 'public, max-age=86400'  # 1 day
                    else:
                        cache_control = 'public, max-age=3600'  # 1 hour

                    self.send_response(200)
                    self.send_header('Content-Type', ctype)
                    self.send_header('Content-Length', str(size))
                    self.send_header('Cache-Control', cache_control)
                    self.send_header('ETag', etag)
                    self.send_header('Last-Modified', last_modified)
                    self.send_header('Accept-Ranges', 'bytes')
                    self._apply_cors()
                    self.end_headers()

                    # Stream large files in chunks
                    with open(fp, 'rb') as f:
                        while True:
                            chunk = f.read(65536)  # 64KB chunks
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    return True
                except Exception:
                    pass
        return False

    def _send_error(self, code, message):
        import html as _html_mod
        safe_message = _html_mod.escape(str(message))
        error_css = (
            "body { font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #f1f5f9; "
            "display: flex; justify-content: center; align-items: center; min-height: 100vh; }"
            ".err { text-align: center; }"
            "h1 { font-size: 4rem; color: #ef4444; }"
            "p { color: #94a3b8; }"
        )
        html = (
            f"<!DOCTYPE html><html><head><title>Error {code}</title>"
            f"<style>{error_css}</style></head><body>"
            f'<div class="err"><h1>{code}</h1><p>{safe_message}</p></div>'
            f"</body></html>"
        )
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        _access_logger.info(f'[{self.app.name}] {args[0]}')

    def _log_access(self, method, path, status, start_time):
        """Structured access log entry."""
        elapsed_ms = (time.time() - start_time) * 1000
        ip = self.client_address[0] if self.client_address else '-'
        _access_logger.info(
            f'{ip} "{method} {path}" {status} {elapsed_ms:.1f}ms'
        )


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for concurrent request handling."""
    daemon_threads = True
    allow_reuse_address = True
    # Thread pool executor for bounded concurrency
    _executor = None

    def process_request(self, request, client_address):
        """Override to use thread pool instead of unbounded thread creation."""
        if self._executor:
            self._executor.submit(self.process_request_thread, request, client_address)
        else:
            super().process_request(request, client_address)


# Global server reference for graceful shutdown
_active_server = None
_shutdown_event = threading.Event()


def _graceful_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    _access_logger.info('Received shutdown signal, draining connections...')
    _shutdown_event.set()
    if _active_server:
        # Shutdown in a separate thread to avoid deadlock
        threading.Thread(target=_active_server.shutdown, daemon=True).start()


def start_server(app, port=3000, interpreter=None, threaded=True, workers=32):
    """Start the EPL web server (v4.0 production-grade).
    
    Args:
        app: EPLWebApp instance
        port: Port number
        interpreter: EPL interpreter for dynamic evaluation
        threaded: Use multi-threaded server
        workers: Max worker threads (thread pool size)
    """
    global _active_server
    EPLHandler.app = app
    EPLHandler.interpreter = interpreter

    ServerClass = ThreadedHTTPServer if threaded else HTTPServer
    server = ServerClass(('0.0.0.0', port), EPLHandler)
    server.daemon_threads = True

    # Thread pool for bounded concurrency
    if threaded:
        server._executor = ThreadPoolExecutor(max_workers=workers)

    _active_server = server

    # Register signal handlers for graceful shutdown
    try:
        signal.signal(signal.SIGINT, _graceful_shutdown)
        signal.signal(signal.SIGTERM, _graceful_shutdown)
    except (OSError, ValueError):
        pass  # Not main thread or unsupported signal

    # HTTPS/SSL support
    protocol = 'http'
    if app.ssl_cert and app.ssl_key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
        context.load_cert_chain(app.ssl_cert, app.ssl_key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        protocol = 'https'

    total_routes = len(app.routes) + sum(len(v) for v in app.param_routes.values())
    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║  EPL Web Server v4.0                 ║")
    print(f"  ║  {app.name:<36} ║")
    print(f"  ╠══════════════════════════════════════╣")
    print(f"  ║  {protocol}://localhost:{port:<22} ║")
    print(f"  ║  Routes: {total_routes:<28}║")
    print(f"  ║  Workers: {workers:<27}║")
    print(f"  ║  HTTPS: {'Yes' if protocol == 'https' else 'No':<29}║")
    print(f"  ║  Gzip: {'Yes' if app.gzip_enabled else 'No':<30}║")
    print(f"  ║  Health: {app._health_path:<28}║")
    ws_count = len(app.websocket_handlers)
    if ws_count:
        print(f"  ║  WebSocket: {ws_count} endpoint(s){' '*(22-len(str(ws_count)))}║")
    for key in app.routes:
        if ':' not in key:  # skip method-specific duplicates
            rtype = app.routes[key][0]
            icon = "PAGE" if rtype == 'page' else "API" if rtype == 'json' else "ACT"
            print(f"  ║    [{icon}] {key:<30}║")
    for method, routes in app.param_routes.items():
        for pattern, params, rtype, body in routes:
            icon = "PAGE" if rtype == 'page' else "API" if rtype == 'json' else "ACT"
            print(f"  ║    [{icon}] {method} {pattern.pattern:<24}║")
    print(f"  ║  Press Ctrl+C to stop               ║")
    print(f"  ╚══════════════════════════════════════╝\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _access_logger.info('Server shutting down...')
        server.shutdown()
        if hasattr(server, '_executor') and server._executor:
            server._executor.shutdown(wait=True, cancel_futures=False)
        # Close connection pool
        if _db_pool:
            _db_pool.close_all()
        _access_logger.info('Server stopped.')


def start_production_server(app, port=8000, host='0.0.0.0', interpreter=None,
                            workers=4, server_type='auto'):
    """Start EPL with a production-grade WSGI/ASGI server.

    Tries gunicorn (Linux/macOS) → waitress (Windows/cross-platform) → uvicorn (ASGI)
    → falls back to built-in threaded server.

    Args:
        app: EPLWebApp instance
        port: Port number (default 8000)
        host: Bind address (default 0.0.0.0)
        interpreter: EPL interpreter for dynamic evaluation
        workers: Number of worker processes/threads
        server_type: 'auto', 'gunicorn', 'waitress', 'uvicorn', or 'builtin'
    """
    from epl.wsgi import EPLWSGIApp
    wsgi_app = EPLWSGIApp(app, interpreter)

    def _banner(engine):
        total = len(app.routes) + sum(len(v) for v in app.param_routes.values())
        print(f"\n  ╔══════════════════════════════════════╗")
        print(f"  ║  EPL Production Server v4.0          ║")
        print(f"  ║  {app.name:<36} ║")
        print(f"  ╠══════════════════════════════════════╣")
        print(f"  ║  http://{host}:{port:<24} ║")
        print(f"  ║  Engine: {engine:<28}║")
        print(f"  ║  Workers: {workers:<27}║")
        print(f"  ║  Routes: {total:<28}║")
        print(f"  ║  Press Ctrl+C to stop               ║")
        print(f"  ╚══════════════════════════════════════╝\n")

    # --- Gunicorn (Linux/macOS, best for production) ---
    if server_type in ('auto', 'gunicorn'):
        try:
            import gunicorn.app.base  # type: ignore[reportMissingImports]

            class EPLGunicornApp(gunicorn.app.base.BaseApplication):
                def __init__(self, application, options=None):
                    self.options = options or {}
                    self.application = application
                    super().__init__()

                def load_config(self):
                    for key, value in self.options.items():
                        if key in self.cfg.settings and value is not None:
                            self.cfg.set(key.lower(), value)

                def load(self):
                    return self.application

            options = {
                'bind': f'{host}:{port}',
                'workers': workers,
                'worker_class': 'sync',
                'timeout': 120,
                'accesslog': '-',
            }
            _banner('gunicorn')
            EPLGunicornApp(wsgi_app, options).run()
            return
        except ImportError:
            if server_type == 'gunicorn':
                raise RuntimeError('gunicorn not installed. Run: pip install gunicorn')

    # --- Waitress (Windows-compatible, production-grade) ---
    if server_type in ('auto', 'waitress'):
        try:
            import waitress  # type: ignore[reportMissingImports]
            _banner('waitress')
            waitress.serve(wsgi_app, host=host, port=port, threads=workers)
            return
        except ImportError:
            if server_type == 'waitress':
                raise RuntimeError('waitress not installed. Run: pip install waitress')

    # --- Uvicorn (ASGI, async) ---
    if server_type in ('auto', 'uvicorn'):
        try:
            import uvicorn  # type: ignore[reportMissingImports]
            from epl.wsgi import EPLASGIApp
            asgi_app = EPLASGIApp(app, interpreter)
            _banner('uvicorn')
            uvicorn.run(asgi_app, host=host, port=port, workers=workers)
            return
        except ImportError:
            if server_type == 'uvicorn':
                raise RuntimeError('uvicorn not installed. Run: pip install uvicorn')

    # --- Builtin fallback ---
    if server_type in ('auto', 'builtin'):
        _access_logger.warning('No production server found. Using built-in threaded server.')
        _access_logger.warning('For production, install: pip install waitress  (or gunicorn on Linux)')
        start_server(app, port=port, interpreter=interpreter, threaded=True, workers=workers * 8)
        return

    raise RuntimeError(f'Unknown server_type: {server_type}. Choose: auto, gunicorn, waitress, uvicorn, builtin')


# ═══════════════════════════════════════════════════════════
# Async Web Server (asyncio-based, production-grade)
# ═══════════════════════════════════════════════════════════

class AsyncEPLServer:
    """Full asyncio-based HTTP server with thread-pool for sync work.
    
    Uses asyncio for I/O multiplexing and a thread-pool executor
    for CPU-bound or blocking operations (template rendering, DB queries).
    
    Usage:
        server = AsyncEPLServer(app, port=3000)
        asyncio.run(server.run())
    """

    def __init__(self, app, port=3000, interpreter=None, workers=32):
        self.app = app
        self.port = port
        self.interpreter = interpreter
        self._server = None
        self._executor = ThreadPoolExecutor(max_workers=workers)
        self._active_connections = 0
        self._lock = asyncio.Lock()
        self._shutting_down = False
        self.workers = workers

    async def run(self):
        """Start the async server."""
        ssl_ctx = None
        protocol = 'http'
        if self.app.ssl_cert and self.app.ssl_key:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_ctx.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
            ssl_ctx.load_cert_chain(self.app.ssl_cert, self.app.ssl_key)
            protocol = 'https'

        self._server = await asyncio.start_server(
            self._handle_connection, '0.0.0.0', self.port, ssl=ssl_ctx
        )
        total_routes = len(self.app.routes) + sum(len(v) for v in self.app.param_routes.values())
        print(f"\n  ╔══════════════════════════════════════╗")
        print(f"  ║  EPL Async Web Server v4.0           ║")
        print(f"  ║  {self.app.name:<36} ║")
        print(f"  ╠══════════════════════════════════════╣")
        print(f"  ║  {protocol}://localhost:{self.port:<22} ║")
        print(f"  ║  Routes: {total_routes:<28}║")
        print(f"  ║  Workers: {self.workers:<27}║")
        print(f"  ║  Engine: asyncio + ThreadPool        ║")
        print(f"  ║  Health: {self.app._health_path:<28}║")
        print(f"  ║  Press Ctrl+C to stop               ║")
        print(f"  ╚══════════════════════════════════════╝\n")

        async with self._server:
            await self._server.serve_forever()

    async def _handle_connection(self, reader, writer):
        """Handle a single HTTP connection with keep-alive support."""
        self._active_connections += 1
        try:
            # Support HTTP/1.1 keep-alive (up to 100 requests per connection)
            for _ in range(100):
                if self._shutting_down:
                    break
                handled = await self._handle_one_request(reader, writer)
                if not handled:
                    break
        except Exception:
            pass
        finally:
            self._active_connections -= 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_one_request(self, reader, writer):
        """Handle one HTTP request on the connection. Returns True if keep-alive."""
        start_time = time.time()
        try:
            # Read request line
            request_line = await asyncio.wait_for(reader.readline(), timeout=30.0)
            if not request_line:
                return False
            request_line = request_line.decode('utf-8', errors='replace').strip()
            parts = request_line.split(' ')
            if len(parts) < 3:
                return False
            method, path, version = parts[0], parts[1], parts[2]

            # Read headers
            headers = {}
            raw_headers_size = 0
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=10.0)
                raw_headers_size += len(line)
                if raw_headers_size > 32768:  # 32KB header limit
                    await self._write_error(writer, 431, 'Request Header Fields Too Large')
                    return False
                line = line.decode('utf-8', errors='replace').strip()
                if not line:
                    break
                if ':' in line:
                    key, val = line.split(':', 1)
                    headers[key.strip()] = val.strip()

            # Track metrics
            if self.app:
                self.app._metrics['requests'] += 1

            # Health check (fast path)
            clean_path = path.split('?')[0]
            if self.app and clean_path == self.app._health_path:
                health = self.app.health_check()
                health['active_connections'] = self._active_connections
                await self._write_json_response(writer, health)
                return 'keep-alive' in headers.get('Connection', '').lower()

            # Rate limiting
            peer = writer.get_extra_info('peername')
            client_ip = peer[0] if peer else '0.0.0.0'
            if self.app and self.app.rate_limit > 0:
                if not _check_rate_limit(client_ip, self.app.rate_limit):
                    await self._write_error(writer, 429, 'Too many requests')
                    return False

            # Read body if present
            body = b''
            content_length = int(headers.get('Content-Length',
                                headers.get('content-length', '0')))
            if content_length > 0:
                if content_length > 10 * 1024 * 1024:  # 10MB limit
                    await self._write_error(writer, 413, 'Request body too large')
                    return False
                body = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=30.0
                )

            # Build Request object
            req = Request(method=method, path=path, headers=headers,
                          body_raw=body, client_ip=client_ip, app=self.app)
            req.session_id = req.cookies.get('epl_session')

            # Route the request in thread pool (blocking operations)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                self._sync_route, req
            )

            # Write response
            await self._write_response(writer, response)

            # Access log
            elapsed_ms = (time.time() - start_time) * 1000
            _access_logger.info(
                f'{client_ip} "{method} {clean_path}" {response.status} {elapsed_ms:.1f}ms'
            )

            # Keep-alive check
            conn_header = headers.get('Connection', headers.get('connection', ''))
            if version == 'HTTP/1.1':
                return conn_header.lower() != 'close'
            return conn_header.lower() == 'keep-alive'

        except (asyncio.TimeoutError, ConnectionResetError, asyncio.IncompleteReadError):
            return False
        except Exception as e:
            if self.app:
                self.app._metrics['errors'] += 1
            try:
                await self._write_error(writer, 500, 'Internal Server Error')
            except Exception:
                pass
            return False

    def _sync_route(self, req):
        """Synchronous route handling (runs in thread pool)."""
        import html as _html_mod
        app = self.app
        path = req.path
        method = req.method

        # CORS preflight
        if method == 'OPTIONS':
            resp = Response(status=200)
            if app.cors_enabled:
                resp.set_header('Access-Control-Allow-Origin', app.cors_origins)
                resp.set_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
                resp.set_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRF-Token')
            return resp

        # Parse body for POST/PUT/DELETE
        form_data = {}
        if method in ('POST', 'PUT', 'DELETE') and req.body_raw:
            ct = req.content_type.lower() if req.content_type else ''
            if 'json' in ct:
                form_data = req.json()
            else:
                raw_text = req.body_raw.decode('utf-8', errors='replace')
                form_data = dict(urllib.parse.parse_qsl(raw_text))

        route = app.get_route(path, method)
        if not route:
            # Try GET fallback for POST
            if method == 'POST':
                route = app.get_route(path, 'GET')
            if not route:
                resp = Response(status=404)
                resp.html_body(self._error_html(404, f'Route not found: {_html_mod.escape(path)}'))
                return resp

        response_type, route_body, route_params = route
        all_params = dict(req.query)
        all_params.update(route_params)
        all_params.update(form_data)

        if response_type == 'json':
            # Build JSON response
            data = self._build_json_sync(route_body, all_params)
            resp = Response(status=200)
            resp.json_body(data)
        elif response_type == 'callable':
            # Python callable handler
            req.form = form_data
            req.params = all_params
            try:
                result = route_body(req)
                if isinstance(result, Response):
                    resp = result
                elif isinstance(result, dict):
                    resp = Response(status=200)
                    resp.json_body(result)
                elif isinstance(result, str):
                    resp = Response(status=200)
                    resp.html_body(result)
                else:
                    resp = Response(status=200)
                    resp.html_body(str(result) if result else '<p>OK</p>')
            except Exception as e:
                resp = Response(status=500)
                resp.html_body(self._error_html(500, f'Handler error: {e}'))
        elif response_type == 'page':
            html = self._build_page_sync(route_body, form_data, all_params)
            if html.startswith('REDIRECT:'):
                resp = Response(status=303)
                resp.set_header('Location', html[len('REDIRECT:'):])
            else:
                resp = Response(status=200)
                resp.html_body(html)
        elif response_type == 'action':
            result = self._exec_action_sync(route_body, form_data)
            if result and result.startswith('REDIRECT:'):
                resp = Response(status=303)
                resp.set_header('Location', result[len('REDIRECT:'):])
            else:
                resp = Response(status=200)
                resp.html_body(result or '<p>OK</p>')
        else:
            resp = Response(status=200)
            resp.html_body('<p>OK</p>')

        # Add security headers
        resp.set_header('X-Content-Type-Options', 'nosniff')
        resp.set_header('X-Frame-Options', 'SAMEORIGIN')
        resp.set_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        if app.cors_enabled:
            resp.set_header('Access-Control-Allow-Origin', app.cors_origins)

        return resp

    def _build_page_sync(self, body, form_data, params):
        """Synchronous page building (mirror of EPLHandler._build_page)."""
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store_sync(stmt, form_data)
            elif isinstance(stmt, ast.DeleteStatement):
                self._exec_delete_sync(stmt, form_data)
            elif isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{url}'

        for stmt in body:
            if isinstance(stmt, ast.PageDef):
                return generate_html(stmt, data_store=_data_store, form_data=form_data)

        elements = [s for s in body if isinstance(s, ast.HtmlElement)]
        if elements:
            page = ast.PageDef("EPL Page", elements)
            return generate_html(page, data_store=_data_store, form_data=form_data)

        return generate_html(ast.PageDef("EPL Page", []), data_store=_data_store)

    def _build_json_sync(self, body, params):
        """Synchronous JSON building."""
        for stmt in body:
            if isinstance(stmt, ast.FetchStatement):
                items = store_get(stmt.collection)
                return self._normalize_json_value(
                    {"collection": stmt.collection, "count": len(items), "items": items}
                )
            if isinstance(stmt, ast.SendResponse):
                if self.interpreter:
                    try:
                        result = self.interpreter._eval(stmt.data, self.interpreter.global_env)
                        return self._normalize_json_value(result)
                    except Exception as e:
                        return {"error": str(e)}
        return self._normalize_json_value({"store": {k: list(v) for k, v in _data_store.items()}})

    def _exec_action_sync(self, body, form_data):
        for stmt in body:
            if isinstance(stmt, ast.StoreStatement):
                self._exec_store_sync(stmt, form_data)
            elif isinstance(stmt, ast.DeleteStatement):
                self._exec_delete_sync(stmt, form_data)
            elif isinstance(stmt, ast.SendResponse) and stmt.response_type == 'redirect':
                url = stmt.data.value if hasattr(stmt.data, 'value') else str(stmt.data)
                return f'REDIRECT:{url}'
        return None

    def _exec_store_sync(self, stmt, form_data):
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

    def _exec_delete_sync(self, stmt, form_data):
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

    def _error_html(self, code, message):
        import html as _html_mod
        safe = _html_mod.escape(str(message))
        return (
            f"<!DOCTYPE html><html><head><title>Error {code}</title>"
            f"<style>body{{font-family:system-ui;background:#0f172a;color:#f1f5f9;"
            f"display:flex;justify-content:center;align-items:center;min-height:100vh}}"
            f".err{{text-align:center}}h1{{font-size:4rem;color:#ef4444}}"
            f"p{{color:#94a3b8}}</style></head><body>"
            f'<div class="err"><h1>{code}</h1><p>{safe}</p></div></body></html>'
        )

    async def _write_response(self, writer, response):
        """Write a Response object to the stream."""
        status_text = {
            200: 'OK', 201: 'Created', 204: 'No Content',
            301: 'Moved Permanently', 302: 'Found', 303: 'See Other', 304: 'Not Modified',
            400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden',
            404: 'Not Found', 405: 'Method Not Allowed', 413: 'Payload Too Large',
            429: 'Too Many Requests', 431: 'Request Header Fields Too Large',
            500: 'Internal Server Error'
        }.get(response.status, 'Unknown')

        body = response.encode()
        header_lines = [f'HTTP/1.1 {response.status} {status_text}']
        header_lines.append(f'Content-Type: {response.content_type}')
        header_lines.append(f'Content-Length: {len(body)}')
        header_lines.append(f'Date: {time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())}')
        header_lines.append('Connection: keep-alive')
        for k, v in response.headers.items():
            header_lines.append(f'{k}: {v}')
        for cookie in response._cookies:
            header_lines.append(f'Set-Cookie: {cookie}')
        header_lines.append('')
        header_lines.append('')
        writer.write('\r\n'.join(header_lines).encode('utf-8'))
        if body:
            writer.write(body)
        await writer.drain()

    async def _write_json_response(self, writer, data):
        """Write a JSON response directly."""
        body = json.dumps(data, indent=2, default=str)
        resp = (
            f'HTTP/1.1 200 OK\r\n'
            f'Content-Type: application/json; charset=utf-8\r\n'
            f'Content-Length: {len(body)}\r\n'
            f'Connection: keep-alive\r\n'
            f'\r\n{body}'
        )
        writer.write(resp.encode('utf-8'))
        await writer.drain()

    async def _write_error(self, writer, code, message):
        """Write an error response."""
        html = self._error_html(code, message)
        status_text = {400: 'Bad Request', 413: 'Payload Too Large',
                       429: 'Too Many Requests', 431: 'Request Header Fields Too Large',
                       500: 'Internal Server Error'}.get(code, 'Error')
        resp = (
            f'HTTP/1.1 {code} {status_text}\r\n'
            f'Content-Type: text/html; charset=utf-8\r\n'
            f'Content-Length: {len(html)}\r\n'
            f'Connection: close\r\n'
            f'\r\n{html}'
        )
        writer.write(resp.encode('utf-8'))
        await writer.drain()

    async def shutdown(self):
        """Graceful shutdown: stop accepting, drain active connections."""
        self._shutting_down = True
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        # Wait for active connections (with timeout)
        deadline = time.time() + 10  # 10 second drain
        while self._active_connections > 0 and time.time() < deadline:
            await asyncio.sleep(0.1)
        self._executor.shutdown(wait=False)
        if _db_pool:
            _db_pool.close_all()

    def stop(self):
        """Stop the async server (synchronous wrapper)."""
        if self._server:
            self._server.close()


def start_async_server(app, port=3000, interpreter=None, workers=32):
    """Start the EPL async web server (production-grade)."""
    server = AsyncEPLServer(app, port, interpreter, workers=workers)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        _access_logger.info('Async server stopped.')


# ═══════════════════════════════════════════════════════════
# HTTP/2 Server (h2 library)
# ═══════════════════════════════════════════════════════════

class HTTP2Server:
    """HTTP/2 server using the h2 library for multiplexed connections.
    
    Requires: pip install h2
    Falls back to HTTP/1.1 AsyncEPLServer if h2 is not installed.
    
    Features:
    - Full HTTP/2 multiplexing (concurrent streams per connection)
    - Server push support
    - HPACK header compression
    - Flow control
    - TLS with ALPN negotiation (h2, http/1.1)
    - Graceful shutdown
    """

    def __init__(self, app, port=3000, interpreter=None, workers=32,
                 ssl_cert=None, ssl_key=None):
        self.app = app
        self.port = port
        self.interpreter = interpreter
        self._executor = ThreadPoolExecutor(max_workers=workers)
        self.workers = workers
        self.ssl_cert = ssl_cert or getattr(app, 'ssl_cert', None)
        self.ssl_key = ssl_key or getattr(app, 'ssl_key', None)
        self._server = None
        self._shutting_down = False
        self._h2 = None
        self._h2_events = None
        self._h2_config = None

    def _load_h2(self):
        """Lazy-load the h2 library."""
        try:
            import h2.connection    # type: ignore[import-not-found]
            import h2.events        # type: ignore[import-not-found]
            import h2.config        # type: ignore[import-not-found]
            self._h2 = h2.connection
            self._h2_events = h2.events
            self._h2_config = h2.config
            return True
        except ImportError:
            return False

    async def run(self):
        """Start the HTTP/2 server."""
        if not self._load_h2():
            _access_logger.warning('h2 library not found. Install: pip install h2')
            _access_logger.warning('Falling back to HTTP/1.1 async server.')
            server = AsyncEPLServer(self.app, self.port, self.interpreter,
                                     workers=self.workers)
            await server.run()
            return

        ssl_ctx = None
        protocol = 'http'
        if self.ssl_cert and self.ssl_key:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_ctx.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20')
            ssl_ctx.load_cert_chain(self.ssl_cert, self.ssl_key)
            ssl_ctx.set_alpn_protocols(['h2', 'http/1.1'])
            protocol = 'https'

        self._server = await asyncio.start_server(
            self._handle_connection, '0.0.0.0', self.port, ssl=ssl_ctx
        )

        total_routes = len(self.app.routes) + sum(len(v) for v in self.app.param_routes.values())
        print(f"\n  ╔══════════════════════════════════════╗")
        print(f"  ║  EPL HTTP/2 Web Server v1.0          ║")
        print(f"  ║  {self.app.name:<36} ║")
        print(f"  ╠══════════════════════════════════════╣")
        print(f"  ║  {protocol}://localhost:{self.port:<22} ║")
        print(f"  ║  Routes: {total_routes:<28}║")
        print(f"  ║  Workers: {self.workers:<27}║")
        print(f"  ║  Protocol: HTTP/2 + HTTP/1.1         ║")
        print(f"  ║  TLS: {'enabled' if ssl_ctx else 'disabled':<31}║")
        print(f"  ║  Press Ctrl+C to stop               ║")
        print(f"  ╚══════════════════════════════════════╝\n")

        async with self._server:
            await self._server.serve_forever()

    async def _handle_connection(self, reader, writer):
        """Handle an HTTP/2 connection."""
        config = self._h2_config.H2Configuration(client_side=False)
        conn = self._h2.H2Connection(config=config)
        conn.initiate_connection()
        writer.write(conn.data_to_send())
        await writer.drain()

        streams = {}  # stream_id -> {'headers': {}, 'data': b''}

        try:
            while not self._shutting_down:
                data = await asyncio.wait_for(reader.read(65535), timeout=30.0)
                if not data:
                    break

                events = conn.receive_data(data)
                for event in events:
                    if isinstance(event, self._h2_events.RequestReceived):
                        headers = dict(event.headers)
                        streams[event.stream_id] = {
                            'headers': headers,
                            'data': b'',
                        }

                    elif isinstance(event, self._h2_events.DataReceived):
                        if event.stream_id in streams:
                            streams[event.stream_id]['data'] += event.data
                            conn.acknowledge_received_data(
                                event.flow_controlled_length, event.stream_id)

                    elif isinstance(event, self._h2_events.StreamEnded):
                        if event.stream_id in streams:
                            stream = streams.pop(event.stream_id)
                            await self._handle_h2_request(
                                conn, writer, event.stream_id,
                                stream['headers'], stream['data'])

                    elif isinstance(event, self._h2_events.WindowUpdated):
                        pass

                    elif isinstance(event, self._h2_events.StreamReset):
                        streams.pop(event.stream_id, None)

                outgoing = conn.data_to_send()
                if outgoing:
                    writer.write(outgoing)
                    await writer.drain()

        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_h2_request(self, conn, writer, stream_id, headers, body):
        """Handle a single HTTP/2 request on a stream."""
        start_time = time.time()
        method = headers.get(b':method', b'GET').decode('utf-8')
        path = headers.get(b':path', b'/').decode('utf-8')
        authority = headers.get(b':authority', b'').decode('utf-8')

        # Convert h2 headers to dict
        req_headers = {}
        for k, v in headers.items():
            if isinstance(k, bytes):
                k = k.decode('utf-8')
            if isinstance(v, bytes):
                v = v.decode('utf-8')
            if not k.startswith(':'):
                req_headers[k] = v

        # Build Request
        client_ip = '0.0.0.0'
        req = Request(method=method, path=path, headers=req_headers,
                      body_raw=body, client_ip=client_ip, app=self.app)

        # Route in thread pool
        loop = asyncio.get_event_loop()
        try:
            # Reuse AsyncEPLServer's sync routing logic
            async_server = AsyncEPLServer.__new__(AsyncEPLServer)
            async_server.app = self.app
            async_server.interpreter = self.interpreter
            async_server._executor = self._executor
            response = await loop.run_in_executor(
                self._executor, async_server._sync_route, req)
        except Exception as e:
            response = Response(status=500)
            response.html_body(f'<h1>500</h1><p>{e}</p>')

        # Send HTTP/2 response
        resp_headers = [
            (':status', str(response.status)),
            ('content-type', response.content_type),
        ]
        resp_body = response.encode()
        resp_headers.append(('content-length', str(len(resp_body))))
        for k, v in response.headers.items():
            resp_headers.append((k.lower(), str(v)))

        conn.send_headers(stream_id, resp_headers)
        # Send body in chunks respecting flow control
        chunk_size = min(conn.local_settings.max_frame_size, 16384)
        for i in range(0, len(resp_body), chunk_size):
            chunk = resp_body[i:i + chunk_size]
            end_stream = (i + chunk_size >= len(resp_body))
            conn.send_data(stream_id, chunk, end_stream=end_stream)

        writer.write(conn.data_to_send())
        await writer.drain()

        elapsed_ms = (time.time() - start_time) * 1000
        _access_logger.info(
            f'{client_ip} [H2] "{method} {path}" {response.status} {elapsed_ms:.1f}ms'
        )

    async def shutdown(self):
        self._shutting_down = True
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._executor.shutdown(wait=False)


def start_h2_server(app, port=3000, interpreter=None, workers=32,
                     ssl_cert=None, ssl_key=None):
    """Start the EPL HTTP/2 server.
    
    Requires: pip install h2
    Falls back to HTTP/1.1 async server if h2 is not available.
    
    Args:
        app: EPL web application instance
        port: Port to listen on (default 3000)
        workers: Number of worker threads (default 32)
        ssl_cert: Path to TLS certificate file
        ssl_key: Path to TLS key file
    """
    server = HTTP2Server(app, port, interpreter, workers=workers,
                          ssl_cert=ssl_cert, ssl_key=ssl_key)
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        _access_logger.info('HTTP/2 server stopped.')
