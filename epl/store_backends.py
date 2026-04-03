"""EPL Store Backends (v4.1)

Pluggable session and data store backends:
- MemoryBackend: In-process dict (default, fast, not shared)
- SQLiteBackend: File-based persistent store (shared across restarts, not workers)
- RedisBackend: Redis-backed store (shared across workers + restarts)

All backends implement the same interface so they are interchangeable.
"""
import json
import time
import secrets
import threading
import logging

_logger = logging.getLogger('epl.store')


# ═══════════════════════════════════════════════════════════
# Abstract Interface
# ═══════════════════════════════════════════════════════════

class StoreBackend:
    """Base class for store backends."""

    def store_add(self, collection, item):
        raise NotImplementedError

    def store_get(self, collection):
        raise NotImplementedError

    def store_remove(self, collection, index):
        raise NotImplementedError

    def store_clear(self, collection):
        raise NotImplementedError

    def store_count(self, collection):
        raise NotImplementedError

    def all_collections(self):
        """Return list of (collection_name, items_list) tuples."""
        raise NotImplementedError

    def clear_all(self):
        """Clear all collections."""
        raise NotImplementedError

    def close(self):
        pass


class SessionBackend:
    """Base class for session backends."""

    def create(self, timeout=3600):
        raise NotImplementedError

    def get(self, session_id, key, default=None):
        raise NotImplementedError

    def set(self, session_id, key, value, timeout=3600):
        raise NotImplementedError

    def delete(self, session_id):
        raise NotImplementedError

    def exists(self, session_id):
        raise NotImplementedError

    def close(self):
        pass


# ═══════════════════════════════════════════════════════════
# Memory Backend (default — fast, single-process)
# ═══════════════════════════════════════════════════════════

class MemoryStoreBackend(StoreBackend):
    """In-memory data store. Fast but not shared across workers."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def store_add(self, collection, item):
        with self._lock:
            if collection not in self._data:
                self._data[collection] = []
            self._data[collection].append(item)

    def store_get(self, collection):
        with self._lock:
            return list(self._data.get(collection, []))

    def store_remove(self, collection, index):
        with self._lock:
            if collection in self._data and 0 <= index < len(self._data[collection]):
                self._data[collection].pop(index)

    def store_clear(self, collection):
        with self._lock:
            self._data[collection] = []

    def store_count(self, collection):
        with self._lock:
            return len(self._data.get(collection, []))

    def all_collections(self):
        with self._lock:
            return list(self._data.items())

    def clear_all(self):
        with self._lock:
            self._data.clear()

    @property
    def data(self):
        """Direct access to internal dict (for backward compatibility)."""
        return self._data


class MemorySessionBackend(SessionBackend):
    """In-memory session store. Fast but not shared across workers."""

    def __init__(self, max_sessions=10000):
        self._sessions = {}
        self._max = max_sessions
        self._lock = threading.Lock()

    def create(self, timeout=3600):
        sid = secrets.token_hex(32)
        with self._lock:
            self._sessions[sid] = {'_expires': time.time() + timeout}
            if len(self._sessions) > self._max:
                self._cleanup()
        return sid

    def get(self, session_id, key, default=None):
        with self._lock:
            s = self._sessions.get(session_id)
            if s and time.time() < s.get('_expires', 0):
                return s.get(key, default)
            elif s:
                del self._sessions[session_id]
        return default

    def set(self, session_id, key, value, timeout=3600):
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {'_expires': time.time() + timeout}
            self._sessions[session_id][key] = value
            self._sessions[session_id]['_expires'] = time.time() + timeout

    def delete(self, session_id):
        with self._lock:
            self._sessions.pop(session_id, None)

    def exists(self, session_id):
        with self._lock:
            s = self._sessions.get(session_id)
            if s and time.time() < s.get('_expires', 0):
                return True
            elif s:
                del self._sessions[session_id]
            return False

    def _cleanup(self):
        now = time.time()
        expired = [k for k, v in self._sessions.items() if v.get('_expires', 0) < now]
        for k in expired:
            del self._sessions[k]

    @property
    def sessions(self):
        return self._sessions


# ═══════════════════════════════════════════════════════════
# SQLite Backend (persistent, survives restarts)
# ═══════════════════════════════════════════════════════════

class SQLiteStoreBackend(StoreBackend):
    """SQLite-backed persistent data store. Survives restarts but not shared across processes."""

    def __init__(self, db_path='epl_store.db'):
        import sqlite3
        self._path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._conns = []
        self._init_db()

    def _get_conn(self):
        import sqlite3
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self._path, check_same_thread=False, timeout=30)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=5000')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            with self._lock:
                self._conns.append(conn)
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute('''CREATE TABLE IF NOT EXISTS epl_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s','now'))
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_store_coll ON epl_store(collection)')
        conn.commit()

    def store_add(self, collection, item):
        conn = self._get_conn()
        conn.execute('INSERT INTO epl_store (collection, data) VALUES (?, ?)',
                     (collection, json.dumps(item, default=str)))
        conn.commit()

    def store_get(self, collection):
        conn = self._get_conn()
        rows = conn.execute('SELECT data FROM epl_store WHERE collection=? ORDER BY id',
                            (collection,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def store_remove(self, collection, index):
        conn = self._get_conn()
        rows = conn.execute('SELECT id FROM epl_store WHERE collection=? ORDER BY id',
                            (collection,)).fetchall()
        if 0 <= index < len(rows):
            conn.execute('DELETE FROM epl_store WHERE id=?', (rows[index][0],))
            conn.commit()

    def store_clear(self, collection):
        conn = self._get_conn()
        conn.execute('DELETE FROM epl_store WHERE collection=?', (collection,))
        conn.commit()

    def store_count(self, collection):
        conn = self._get_conn()
        row = conn.execute('SELECT COUNT(*) FROM epl_store WHERE collection=?',
                           (collection,)).fetchone()
        return row[0]

    def all_collections(self):
        conn = self._get_conn()
        rows = conn.execute('SELECT DISTINCT collection FROM epl_store').fetchall()
        result = []
        for r in rows:
            items = self.store_get(r[0])
            result.append((r[0], items))
        return result

    def clear_all(self):
        conn = self._get_conn()
        conn.execute('DELETE FROM epl_store')
        conn.commit()

    def close(self):
        with self._lock:
            for c in self._conns:
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()


class SQLiteSessionBackend(SessionBackend):
    """SQLite-backed session store. Survives restarts."""

    def __init__(self, db_path='epl_sessions.db'):
        import sqlite3
        self._path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._conns = []
        self._init_db()

    def _get_conn(self):
        import sqlite3
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self._path, check_same_thread=False, timeout=30)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=5000')
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            with self._lock:
                self._conns.append(conn)
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute('''CREATE TABLE IF NOT EXISTS epl_sessions (
            session_id TEXT PRIMARY KEY,
            data TEXT NOT NULL DEFAULT '{}',
            expires_at REAL NOT NULL
        )''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sess_exp ON epl_sessions(expires_at)')
        conn.commit()

    def create(self, timeout=3600):
        sid = secrets.token_hex(32)
        conn = self._get_conn()
        conn.execute('INSERT INTO epl_sessions (session_id, data, expires_at) VALUES (?, ?, ?)',
                     (sid, '{}', time.time() + timeout))
        conn.commit()
        return sid

    def get(self, session_id, key, default=None):
        conn = self._get_conn()
        row = conn.execute('SELECT data, expires_at FROM epl_sessions WHERE session_id=?',
                           (session_id,)).fetchone()
        if row and time.time() < row[1]:
            data = json.loads(row[0])
            return data.get(key, default)
        elif row:
            conn.execute('DELETE FROM epl_sessions WHERE session_id=?', (session_id,))
            conn.commit()
        return default

    def set(self, session_id, key, value, timeout=3600):
        conn = self._get_conn()
        row = conn.execute('SELECT data FROM epl_sessions WHERE session_id=?',
                           (session_id,)).fetchone()
        if row:
            data = json.loads(row[0])
        else:
            data = {}
        data[key] = value
        conn.execute('''INSERT OR REPLACE INTO epl_sessions (session_id, data, expires_at)
                        VALUES (?, ?, ?)''',
                     (session_id, json.dumps(data, default=str), time.time() + timeout))
        conn.commit()

    def delete(self, session_id):
        conn = self._get_conn()
        conn.execute('DELETE FROM epl_sessions WHERE session_id=?', (session_id,))
        conn.commit()

    def exists(self, session_id):
        conn = self._get_conn()
        row = conn.execute('SELECT expires_at FROM epl_sessions WHERE session_id=?',
                           (session_id,)).fetchone()
        if row and time.time() < row[0]:
            return True
        elif row:
            conn.execute('DELETE FROM epl_sessions WHERE session_id=?', (session_id,))
            conn.commit()
        return False

    def close(self):
        with self._lock:
            for c in self._conns:
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()


# ═══════════════════════════════════════════════════════════
# Redis Backend (shared across workers + restarts)
# ═══════════════════════════════════════════════════════════

class RedisStoreBackend(StoreBackend):
    """Redis-backed data store. Shared across all workers and survives restarts.

    Requires: pip install redis
    Usage: backend = RedisStoreBackend('redis://localhost:6379/0')
    """

    def __init__(self, url='redis://localhost:6379/0', prefix='epl:store:'):
        try:
            import redis
        except ImportError:
            raise ImportError("Redis backend requires 'redis' package: pip install redis")
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        # Verify connection
        self._redis.ping()
        _logger.info(f'Redis store connected: {url}')

    def _key(self, collection):
        return f'{self._prefix}{collection}'

    def store_add(self, collection, item):
        self._redis.rpush(self._key(collection), json.dumps(item, default=str))

    def store_get(self, collection):
        items = self._redis.lrange(self._key(collection), 0, -1)
        return [json.loads(i) for i in items]

    def store_remove(self, collection, index):
        key = self._key(collection)
        # Redis doesn't have direct index-delete; use sentinel approach
        sentinel = f'__DELETED_{secrets.token_hex(8)}__'
        self._redis.lset(key, index, sentinel)
        self._redis.lrem(key, 1, sentinel)

    def store_clear(self, collection):
        self._redis.delete(self._key(collection))

    def store_count(self, collection):
        return self._redis.llen(self._key(collection))

    def all_collections(self):
        keys = self._redis.keys(f'{self._prefix}*')
        result = []
        for k in keys:
            name = k[len(self._prefix):]
            items = self.store_get(name)
            result.append((name, items))
        return result

    def clear_all(self):
        keys = self._redis.keys(f'{self._prefix}*')
        if keys:
            self._redis.delete(*keys)

    def close(self):
        self._redis.close()


class RedisSessionBackend(SessionBackend):
    """Redis-backed session store. Shared across all workers and survives restarts.

    Requires: pip install redis
    Usage: backend = RedisSessionBackend('redis://localhost:6379/0')
    """

    def __init__(self, url='redis://localhost:6379/0', prefix='epl:session:'):
        try:
            import redis
        except ImportError:
            raise ImportError("Redis backend requires 'redis' package: pip install redis")
        self._redis = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._redis.ping()
        _logger.info(f'Redis sessions connected: {url}')

    def _key(self, session_id):
        return f'{self._prefix}{session_id}'

    def create(self, timeout=3600):
        sid = secrets.token_hex(32)
        self._redis.setex(self._key(sid), timeout, '{}')
        return sid

    def get(self, session_id, key, default=None):
        raw = self._redis.get(self._key(session_id))
        if raw:
            data = json.loads(raw)
            return data.get(key, default)
        return default

    def set(self, session_id, key, value, timeout=3600):
        k = self._key(session_id)
        raw = self._redis.get(k)
        data = json.loads(raw) if raw else {}
        data[key] = value
        self._redis.setex(k, timeout, json.dumps(data, default=str))

    def delete(self, session_id):
        self._redis.delete(self._key(session_id))

    def exists(self, session_id):
        return self._redis.exists(self._key(session_id)) > 0

    def close(self):
        self._redis.close()


# ═══════════════════════════════════════════════════════════
# Backend Registry — global access point
# ═══════════════════════════════════════════════════════════

_store_backend = None    # type: StoreBackend | None
_session_backend = None  # type: SessionBackend | None


def get_store_backend():
    """Get the active store backend (auto-creates MemoryStoreBackend if none set)."""
    global _store_backend
    if _store_backend is None:
        _store_backend = MemoryStoreBackend()
    return _store_backend


def get_session_backend():
    """Get the active session backend (auto-creates MemorySessionBackend if none set)."""
    global _session_backend
    if _session_backend is None:
        _session_backend = MemorySessionBackend()
    return _session_backend


def configure_backends(store='memory', session='memory', **kwargs):
    """Configure store and session backends.

    Args:
        store: 'memory', 'sqlite', or 'redis'
        session: 'memory', 'sqlite', or 'redis'
        **kwargs: Backend-specific options:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
            sqlite_store_path: SQLite store DB path (default: epl_store.db)
            sqlite_session_path: SQLite session DB path (default: epl_sessions.db)
    """
    global _store_backend, _session_backend

    redis_url = kwargs.get('redis_url', 'redis://localhost:6379/0')
    sqlite_store = kwargs.get('sqlite_store_path', 'epl_store.db')
    sqlite_session = kwargs.get('sqlite_session_path', 'epl_sessions.db')

    # Store backend
    if store == 'redis':
        _store_backend = RedisStoreBackend(redis_url)
    elif store == 'sqlite':
        _store_backend = SQLiteStoreBackend(sqlite_store)
    else:
        _store_backend = MemoryStoreBackend()

    # Session backend
    if session == 'redis':
        _session_backend = RedisSessionBackend(redis_url)
    elif session == 'sqlite':
        _session_backend = SQLiteSessionBackend(sqlite_session)
    else:
        _session_backend = MemorySessionBackend()

    _logger.info(f'Backends configured: store={store}, session={session}')
    return _store_backend, _session_backend
