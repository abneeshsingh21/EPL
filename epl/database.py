"""
EPL Database ORM & Connection Pool v1.0
Production-grade database abstraction with ORM, migrations, and connection pooling.

Supports:
- SQLite (built-in)
- PostgreSQL (via psycopg2, optional)
- MySQL (via mysql-connector-python, optional)

Features:
- Model definition with typed fields
- Auto-migration (CREATE TABLE, ALTER TABLE)
- CRUD operations (create, find, update, delete)
- Query builder with chaining
- Connection pooling with health checks
- Transaction support
- Relationship mapping (has_many, belongs_to)

Usage from EPL:
    Set db to Database("sqlite", "app.db")
    
    Define Model "User"
        Field "name" as text
        Field "email" as text unique
        Field "age" as integer default 0
    End
    
    db.migrate()
    db.create("User", {"name": "Alice", "age": 30})
    Set users to db.find("User", {"age": 30})
"""

import sqlite3
import threading
import time
import queue
import os
import re as _re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# SQL identifier validation regex
_VALID_IDENTIFIER = _re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def _quote_identifier(name: str) -> str:
    """Quote a SQL identifier to prevent injection. Raises on invalid names."""
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f'Invalid SQL identifier: {name!r}')
    return f'"{name}"'


# ═══════════════════════════════════════════════════════════
# Field Definitions
# ═══════════════════════════════════════════════════════════

@dataclass
class FieldDef:
    """Schema field definition."""
    name: str
    field_type: str  # 'text', 'integer', 'decimal', 'boolean', 'datetime', 'blob'
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    default: Any = None
    foreign_key: str = None  # "TableName.column"
    auto_increment: bool = False

    def sql_type(self, dialect: str = 'sqlite') -> str:
        """Get SQL type for this field."""
        ft = self.field_type.lower()
        type_map = {
            'sqlite': {
                'text': 'TEXT', 'string': 'TEXT', 'integer': 'INTEGER', 'int': 'INTEGER',
                'decimal': 'REAL', 'float': 'REAL', 'double': 'REAL',
                'boolean': 'INTEGER', 'bool': 'INTEGER',
                'datetime': 'TEXT', 'date': 'TEXT', 'time': 'TEXT',
                'blob': 'BLOB', 'json': 'TEXT',
            },
            'postgres': {
                'text': 'TEXT', 'string': 'VARCHAR(255)', 'integer': 'INTEGER',
                'int': 'INTEGER', 'decimal': 'DOUBLE PRECISION', 'float': 'REAL',
                'double': 'DOUBLE PRECISION', 'boolean': 'BOOLEAN', 'bool': 'BOOLEAN',
                'datetime': 'TIMESTAMP', 'date': 'DATE', 'time': 'TIME',
                'blob': 'BYTEA', 'json': 'JSONB',
            },
            'mysql': {
                'text': 'TEXT', 'string': 'VARCHAR(255)', 'integer': 'INT',
                'int': 'INT', 'decimal': 'DOUBLE', 'float': 'FLOAT',
                'double': 'DOUBLE', 'boolean': 'TINYINT(1)', 'bool': 'TINYINT(1)',
                'datetime': 'DATETIME', 'date': 'DATE', 'time': 'TIME',
                'blob': 'BLOB', 'json': 'JSON',
            },
        }
        return type_map.get(dialect, type_map['sqlite']).get(ft, 'TEXT')

    def to_sql_column(self, dialect: str = 'sqlite') -> str:
        """Generate SQL column definition."""
        col_name = _quote_identifier(self.name)
        parts = [col_name, self.sql_type(dialect)]
        if self.primary_key:
            parts.append('PRIMARY KEY')
            if self.auto_increment and dialect == 'sqlite':
                parts.append('AUTOINCREMENT')
        if not self.nullable and not self.primary_key:
            parts.append('NOT NULL')
        if self.unique and not self.primary_key:
            parts.append('UNIQUE')
        if self.default is not None:
            if isinstance(self.default, str):
                parts.append(f"DEFAULT '{self.default}'")
            elif isinstance(self.default, bool):
                parts.append(f"DEFAULT {1 if self.default else 0}")
            else:
                parts.append(f"DEFAULT {self.default}")
        if self.foreign_key:
            table, col = self.foreign_key.split('.')
            parts.append(f'REFERENCES {table}({col})')
        return ' '.join(parts)


# ═══════════════════════════════════════════════════════════
# Model Definition
# ═══════════════════════════════════════════════════════════

class Model:
    """ORM Model — represents a database table."""

    def __init__(self, name: str):
        self.name = name
        self.table_name = name.lower() + 's'  # Convention: User -> users
        self.fields: List[FieldDef] = [
            FieldDef('id', 'integer', primary_key=True, auto_increment=True, nullable=False)
        ]
        self.relationships: Dict[str, dict] = {}  # name -> {type, model, fk}
        self.timestamps = True  # auto-add created_at, updated_at

    def add_field(self, name: str, field_type: str, **kwargs) -> 'Model':
        """Add a field to the model."""
        self.fields.append(FieldDef(name=name, field_type=field_type, **kwargs))
        return self

    def has_many(self, model_name: str, foreign_key: str = None) -> 'Model':
        """Define a one-to-many relationship."""
        fk = foreign_key or f'{self.name.lower()}_id'
        self.relationships[model_name] = {
            'type': 'has_many', 'model': model_name, 'foreign_key': fk
        }
        return self

    def belongs_to(self, model_name: str, foreign_key: str = None) -> 'Model':
        """Define a many-to-one relationship."""
        fk = foreign_key or f'{model_name.lower()}_id'
        # Add foreign key field
        self.add_field(fk, 'integer', foreign_key=f'{model_name.lower()}s.id')
        self.relationships[model_name] = {
            'type': 'belongs_to', 'model': model_name, 'foreign_key': fk
        }
        return self

    def create_table_sql(self, dialect: str = 'sqlite') -> str:
        """Generate CREATE TABLE SQL."""
        tbl = _quote_identifier(self.table_name)
        columns = []
        for f in self.fields:
            columns.append(f'  {f.to_sql_column(dialect)}')
        if self.timestamps:
            columns.append("  created_at TEXT DEFAULT (datetime('now'))")
            columns.append("  updated_at TEXT DEFAULT (datetime('now'))")
        return f'CREATE TABLE IF NOT EXISTS {tbl} (\n' + ',\n'.join(columns) + '\n);'


# ═══════════════════════════════════════════════════════════
# Connection Pool
# ═══════════════════════════════════════════════════════════

class ConnectionPool:
    """Thread-safe database connection pool."""

    _mem_counter = 0
    _mem_lock = threading.Lock()

    def __init__(self, dialect: str, connect_args: dict, min_size: int = 2,
                 max_size: int = 10, max_idle: float = 300):
        self.dialect = dialect
        self.connect_args = connect_args
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle = max_idle
        self._pool: queue.Queue = queue.Queue(maxsize=max_size)
        self._size = 0
        self._lock = threading.Lock()
        self._closed = False

        # Assign a unique URI for in-memory SQLite so each Database gets its own
        self._mem_uri = None
        if dialect == 'sqlite' and connect_args.get('database', ':memory:') == ':memory:':
            with ConnectionPool._mem_lock:
                ConnectionPool._mem_counter += 1
                self._mem_uri = f'file:memdb_{ConnectionPool._mem_counter}?mode=memory&cache=shared'

        # Pre-fill pool with minimum connections
        for _ in range(min_size):
            conn = self._create_connection()
            self._pool.put((conn, time.time()))
            self._size += 1

    def _create_connection(self):
        """Create a new database connection."""
        if self.dialect == 'sqlite':
            db_path = self.connect_args.get('database', ':memory:')
            if self._mem_uri:
                conn = sqlite3.connect(self._mem_uri, uri=True, check_same_thread=False)
            elif db_path == ':memory:':
                conn = sqlite3.connect(':memory:', check_same_thread=False)
            else:
                conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            if not self._mem_uri and db_path != ':memory:':
                conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
            return conn
        elif self.dialect == 'postgres':
            try:
                import psycopg2  # type: ignore[reportMissingModuleSource]
                import psycopg2.extras  # type: ignore[reportMissingModuleSource]
                conn = psycopg2.connect(**self.connect_args)
                conn.autocommit = False
                return conn
            except ImportError:
                raise RuntimeError('psycopg2 not installed. Run: pip install psycopg2-binary')
        elif self.dialect == 'mysql':
            try:
                import mysql.connector  # type: ignore[reportMissingImports]
                conn = mysql.connector.connect(**self.connect_args)
                return conn
            except ImportError:
                raise RuntimeError('mysql-connector not installed. Run: pip install mysql-connector-python')
        else:
            raise ValueError(f'Unsupported dialect: {self.dialect}')

    def get(self, timeout: float = 5.0, _retries: int = 0):
        """Get a connection from the pool."""
        if self._closed:
            raise RuntimeError('Connection pool is closed')
        if _retries > 3:
            raise RuntimeError('Connection pool: too many retry attempts')

        try:
            conn, ts = self._pool.get(timeout=0.1)
            # Check if connection is stale
            if time.time() - ts > self.max_idle:
                self._close_connection(conn)
                with self._lock:
                    self._size -= 1
                return self.get(timeout, _retries + 1)
            # Health check
            if self._is_alive(conn):
                return conn
            else:
                self._close_connection(conn)
                with self._lock:
                    self._size -= 1
                return self.get(timeout, _retries + 1)
        except queue.Empty:
            # Create new connection if under limit
            with self._lock:
                if self._size < self.max_size:
                    conn = self._create_connection()
                    self._size += 1
                    return conn
            # Wait for available connection
            try:
                conn, ts = self._pool.get(timeout=timeout)
                return conn
            except queue.Empty:
                raise RuntimeError('Connection pool exhausted')

    def put(self, conn):
        """Return a connection to the pool."""
        if self._closed:
            self._close_connection(conn)
            return
        try:
            self._pool.put((conn, time.time()), timeout=1)
        except queue.Full:
            self._close_connection(conn)
            with self._lock:
                self._size -= 1

    def _is_alive(self, conn) -> bool:
        """Check if connection is still alive."""
        try:
            if self.dialect == 'sqlite':
                conn.execute('SELECT 1')
            elif self.dialect == 'postgres':
                cursor = conn.cursor()
                try:
                    cursor.execute('SELECT 1')
                finally:
                    cursor.close()
            elif self.dialect == 'mysql':
                conn.ping(reconnect=False)
            return True
        except Exception:
            return False

    def _close_connection(self, conn):
        """Safely close a connection."""
        try:
            conn.close()
        except Exception:
            pass

    def close_all(self):
        """Close all connections in the pool."""
        self._closed = True
        while not self._pool.empty():
            try:
                conn, _ = self._pool.get_nowait()
                self._close_connection(conn)
            except queue.Empty:
                break
        self._size = 0

    @property
    def stats(self) -> dict:
        """Pool statistics."""
        return {
            'size': self._size,
            'available': self._pool.qsize(),
            'in_use': self._size - self._pool.qsize(),
            'max_size': self.max_size,
        }


# ═══════════════════════════════════════════════════════════
# Query Builder
# ═══════════════════════════════════════════════════════════

class QueryBuilder:
    """Chainable SQL query builder."""

    def __init__(self, db: 'Database', table: str):
        self._db = db
        self._table = table
        self._select_cols = ['*']
        self._where_clauses: List[Tuple[str, Any]] = []
        self._order_by: List[str] = []
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._join_clauses: List[str] = []
        self._group_by: List[str] = []
        self._having: Optional[str] = None

    def select(self, *columns) -> 'QueryBuilder':
        self._select_cols = list(columns) if columns else ['*']
        return self

    def where(self, condition: str, value: Any = None) -> 'QueryBuilder':
        self._where_clauses.append((condition, value))
        return self

    def where_eq(self, column: str, value: Any) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} = ?', value))
        return self

    def where_like(self, column: str, pattern: str) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} LIKE ?', pattern))
        return self

    def where_in(self, column: str, values: list) -> 'QueryBuilder':
        placeholders = ','.join(['?' for _ in values])
        self._where_clauses.append((f'{column} IN ({placeholders})', values))
        return self

    def where_gt(self, column: str, value: Any) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} > ?', value))
        return self

    def where_lt(self, column: str, value: Any) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} < ?', value))
        return self

    def where_between(self, column: str, low: Any, high: Any) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} BETWEEN ? AND ?', (low, high)))
        return self

    def where_null(self, column: str) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} IS NULL', None))
        return self

    def where_not_null(self, column: str) -> 'QueryBuilder':
        self._where_clauses.append((f'{column} IS NOT NULL', None))
        return self

    def order_by(self, column: str, direction: str = 'ASC') -> 'QueryBuilder':
        self._order_by.append(f'{column} {direction}')
        return self

    def limit(self, n: int) -> 'QueryBuilder':
        self._limit_val = n
        return self

    def offset(self, n: int) -> 'QueryBuilder':
        self._offset_val = n
        return self

    def join(self, table: str, on: str) -> 'QueryBuilder':
        self._join_clauses.append(f'JOIN {table} ON {on}')
        return self

    def left_join(self, table: str, on: str) -> 'QueryBuilder':
        self._join_clauses.append(f'LEFT JOIN {table} ON {on}')
        return self

    def group_by(self, *columns) -> 'QueryBuilder':
        self._group_by.extend(columns)
        return self

    def having(self, condition: str) -> 'QueryBuilder':
        self._having = condition
        return self

    def build(self) -> Tuple[str, list]:
        """Build the SQL query and parameters."""
        sql = f'SELECT {", ".join(self._select_cols)} FROM {self._table}'
        params = []

        for join in self._join_clauses:
            sql += f' {join}'

        if self._where_clauses:
            conditions = []
            for cond, val in self._where_clauses:
                conditions.append(cond)
                if val is not None:
                    if isinstance(val, (list, tuple)):
                        params.extend(val)
                    else:
                        params.append(val)
            sql += ' WHERE ' + ' AND '.join(conditions)

        if self._group_by:
            sql += f' GROUP BY {", ".join(self._group_by)}'
        if self._having:
            sql += f' HAVING {self._having}'
        if self._order_by:
            sql += f' ORDER BY {", ".join(self._order_by)}'
        if self._limit_val is not None:
            sql += f' LIMIT {self._limit_val}'
        if self._offset_val is not None:
            sql += f' OFFSET {self._offset_val}'

        return sql, params

    def execute(self) -> List[dict]:
        """Execute the query and return results."""
        sql, params = self.build()
        return self._db.raw_query(sql, params)

    def first(self) -> Optional[dict]:
        """Get first result."""
        self._limit_val = 1
        results = self.execute()
        return results[0] if results else None

    def count(self) -> int:
        """Get count of matching rows."""
        self._select_cols = ['COUNT(*) as count']
        results = self.execute()
        return results[0]['count'] if results else 0

    def exists(self) -> bool:
        """Check if any rows match."""
        return self.count() > 0

    def pluck(self, column: str) -> list:
        """Get a list of values for a single column."""
        self._select_cols = [column]
        return [row[column] for row in self.execute()]


# ═══════════════════════════════════════════════════════════
# Database (ORM + Connection Pool)
# ═══════════════════════════════════════════════════════════

class Database:
    """Main database interface with ORM, query builder, and connection pooling."""

    def __init__(self, dialect: str = 'sqlite', database: str = ':memory:',
                 pool_size: int = 5, **kwargs):
        self.dialect = dialect
        self.database = database
        self.models: Dict[str, Model] = {}
        connect_args = {'database': database, **kwargs}
        self.pool = ConnectionPool(dialect, connect_args, max_size=pool_size)

    def define_model(self, name: str) -> Model:
        """Define a new model."""
        model = Model(name)
        self.models[name] = model
        return model

    def get_model(self, name: str) -> Model:
        """Get a model by name."""
        if name not in self.models:
            raise ValueError(f'Model "{name}" not defined')
        return self.models[name]

    def migrate(self):
        """Run migrations: create tables that don't exist, add missing columns."""
        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            for model in self.models.values():
                # Create table
                cursor.execute(model.create_table_sql(self.dialect))
                # Check for missing columns
                if self.dialect == 'sqlite':
                    tbl = _quote_identifier(model.table_name)
                    cursor.execute(f'PRAGMA table_info({tbl})')
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    for field_def in model.fields:
                        if field_def.name not in existing_cols:
                            alter = f'ALTER TABLE {tbl} ADD COLUMN {field_def.to_sql_column(self.dialect)}'
                            cursor.execute(alter)
            conn.commit()
        finally:
            self.pool.put(conn)

    # ─── CRUD Operations ────────────────────────────

    def create(self, model_name: str, data: dict) -> int:
        """Insert a new record. Returns the new row ID."""
        model = self.get_model(model_name)
        # Filter out id and timestamps
        field_names = [f.name for f in model.fields if f.name != 'id']
        columns = [k for k in data.keys() if k in field_names or k in [f.name for f in model.fields]]
        values = [data[k] for k in columns]
        placeholders = ', '.join(['?' for _ in columns])
        quoted_cols = ', '.join(_quote_identifier(c) for c in columns)
        tbl = _quote_identifier(model.table_name)
        sql = f'INSERT INTO {tbl} ({quoted_cols}) VALUES ({placeholders})'

        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid
        finally:
            self.pool.put(conn)

    def find(self, model_name: str, conditions: dict = None) -> List[dict]:
        """Find records matching conditions."""
        model = self.get_model(model_name)
        qb = QueryBuilder(self, model.table_name)
        if conditions:
            for k, v in conditions.items():
                qb.where_eq(k, v)
        return qb.execute()

    def find_by_id(self, model_name: str, record_id: int) -> Optional[dict]:
        """Find a single record by ID."""
        model = self.get_model(model_name)
        results = QueryBuilder(self, model.table_name).where_eq('id', record_id).first()
        return results

    def update(self, model_name: str, record_id: int, data: dict) -> bool:
        """Update a record by ID."""
        model = self.get_model(model_name)
        set_parts = []
        values = []
        for k, v in data.items():
            set_parts.append(f'{_quote_identifier(k)} = ?')
            values.append(v)
        values.append(record_id)
        tbl = _quote_identifier(model.table_name)
        sql = f'UPDATE {tbl} SET {", ".join(set_parts)} WHERE id = ?'

        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.pool.put(conn)

    def delete(self, model_name: str, record_id: int) -> bool:
        """Delete a record by ID."""
        model = self.get_model(model_name)
        tbl = _quote_identifier(model.table_name)
        sql = f'DELETE FROM {tbl} WHERE id = ?'

        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, [record_id])
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.pool.put(conn)

    def delete_where(self, model_name: str, conditions: dict) -> int:
        """Delete records matching conditions. Returns count deleted."""
        model = self.get_model(model_name)
        where_parts = []
        values = []
        for k, v in conditions.items():
            where_parts.append(f'{_quote_identifier(k)} = ?')
            values.append(v)
        tbl = _quote_identifier(model.table_name)
        sql = f'DELETE FROM {tbl} WHERE {" AND ".join(where_parts)}'

        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount
        finally:
            self.pool.put(conn)

    # ─── Query Builder ──────────────────────────────

    def query(self, model_name: str) -> QueryBuilder:
        """Start building a query for a model."""
        model = self.get_model(model_name)
        return QueryBuilder(self, model.table_name)

    # ─── Raw SQL ────────────────────────────────────

    def raw_query(self, sql: str, params: list = None) -> List[dict]:
        """Execute raw SQL and return results as dicts."""
        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or [])
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            conn.commit()
            return []
        finally:
            self.pool.put(conn)

    def raw_execute(self, sql: str, params: list = None) -> int:
        """Execute raw SQL (INSERT/UPDATE/DELETE). Returns affected rows."""
        conn = self.pool.get()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or [])
            conn.commit()
            return cursor.rowcount
        finally:
            self.pool.put(conn)

    # ─── Transactions ───────────────────────────────

    def transaction(self):
        """Context manager for transactions."""
        return Transaction(self)

    # ─── Utility ────────────────────────────────────

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        if self.dialect == 'sqlite':
            results = self.raw_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                [table_name]
            )
            return len(results) > 0
        return False

    def close(self):
        """Close all connections."""
        self.pool.close_all()

    @property
    def pool_stats(self) -> dict:
        return self.pool.stats


class Transaction:
    """Transaction context manager."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = None

    def __enter__(self):
        self.conn = self.db.pool.get()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.db.pool.put(self.conn)
        return False

    def execute(self, sql: str, params: list = None):
        cursor = self.conn.cursor()
        cursor.execute(sql, params or [])
        return cursor


# ═══════════════════════════════════════════════════════════
# Networking Module
# ═══════════════════════════════════════════════════════════

class EPLSocket:
    """TCP/UDP socket wrapper for EPL."""

    def __init__(self, protocol: str = 'tcp'):
        import socket
        self.protocol = protocol
        if protocol == 'tcp':
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        elif protocol == 'udp':
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            raise ValueError(f'Unknown protocol: {protocol}')
        self._socket.settimeout(30)

    def connect(self, host: str, port: int):
        """Connect to a remote host."""
        self._socket.connect((host, port))
        return self

    def bind(self, host: str, port: int):
        """Bind to an address."""
        self._socket.setsockopt(1, 2, 1)  # SO_REUSEADDR
        self._socket.bind((host, port))
        return self

    def listen(self, backlog: int = 5):
        """Start listening for connections."""
        self._socket.listen(backlog)
        return self

    def accept(self):
        """Accept a connection. Returns (EPLSocket, address)."""
        conn, addr = self._socket.accept()
        wrapper = EPLSocket.__new__(EPLSocket)
        wrapper.protocol = self.protocol
        wrapper._socket = conn
        return wrapper, addr

    def send(self, data):
        """Send data."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._socket.sendall(data)
        return self

    def receive(self, size: int = 4096) -> str:
        """Receive data."""
        data = self._socket.recv(size)
        return data.decode('utf-8')

    def send_to(self, data, host: str, port: int):
        """UDP: Send data to address."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        self._socket.sendto(data, (host, port))

    def receive_from(self, size: int = 4096):
        """UDP: Receive data with sender address."""
        data, addr = self._socket.recvfrom(size)
        return data.decode('utf-8'), addr

    def close(self):
        """Close the socket."""
        self._socket.close()

    def set_timeout(self, seconds: float):
        """Set socket timeout."""
        self._socket.settimeout(seconds)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class HTTPClient:
    """Simple HTTP client for EPL."""

    @staticmethod
    def get(url: str, headers: dict = None, timeout: float = 30) -> dict:
        """HTTP GET request."""
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, method='GET')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    'status': resp.status,
                    'headers': dict(resp.headers),
                    'body': resp.read().decode('utf-8'),
                }
        except urllib.error.HTTPError as e:
            return {'status': e.code, 'headers': dict(e.headers), 'body': e.read().decode('utf-8')}
        except Exception as e:
            return {'status': 0, 'headers': {}, 'body': '', 'error': str(e)}

    @staticmethod
    def post(url: str, body: str = '', headers: dict = None,
             content_type: str = 'application/json', timeout: float = 30) -> dict:
        """HTTP POST request."""
        import urllib.request
        import urllib.error
        data = body.encode('utf-8') if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, method='POST')
        req.add_header('Content-Type', content_type)
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {
                    'status': resp.status,
                    'headers': dict(resp.headers),
                    'body': resp.read().decode('utf-8'),
                }
        except urllib.error.HTTPError as e:
            return {'status': e.code, 'headers': dict(e.headers), 'body': e.read().decode('utf-8')}
        except Exception as e:
            return {'status': 0, 'headers': {}, 'body': '', 'error': str(e)}

    @staticmethod
    def put(url: str, body: str = '', headers: dict = None, timeout: float = 30) -> dict:
        """HTTP PUT request."""
        import urllib.request
        data = body.encode('utf-8') if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, method='PUT')
        req.add_header('Content-Type', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {'status': resp.status, 'body': resp.read().decode('utf-8')}
        except Exception as e:
            return {'status': 0, 'body': '', 'error': str(e)}

    @staticmethod
    def delete(url: str, headers: dict = None, timeout: float = 30) -> dict:
        """HTTP DELETE request."""
        import urllib.request
        req = urllib.request.Request(url, method='DELETE')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {'status': resp.status, 'body': resp.read().decode('utf-8')}
        except Exception as e:
            return {'status': 0, 'body': '', 'error': str(e)}


# ═══════════════════════════════════════════════════════════
# Convenience Constructors (for EPL builtins)
# ═══════════════════════════════════════════════════════════

def create_database(dialect='sqlite', database=':memory:', **kwargs):
    """Create a database connection with ORM."""
    return Database(dialect, database, **kwargs)

def create_socket(protocol='tcp'):
    """Create a network socket."""
    return EPLSocket(protocol)

def http_get(url, headers=None):
    """Quick HTTP GET."""
    return HTTPClient.get(url, headers)

def http_post(url, body='', headers=None):
    """Quick HTTP POST."""
    return HTTPClient.post(url, body, headers)

def http_put(url, body='', headers=None):
    """Quick HTTP PUT."""
    return HTTPClient.put(url, body, headers)

def http_delete(url, headers=None):
    """Quick HTTP DELETE."""
    return HTTPClient.delete(url, headers)
