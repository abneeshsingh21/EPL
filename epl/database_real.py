"""
EPL Database Module v2.0
========================
Real database connectivity using Python's sqlite3 (built-in)
with PostgreSQL (psycopg2) and MySQL (mysql-connector-python) support.

Provides:
- SQLite connections (zero-config, file-based)
- PostgreSQL connections (via psycopg2-binary)
- MySQL connections (via mysql-connector-python)
- Connection pooling
- Query builder (fluent API)
- Migrations with version tracking
- Transaction support with savepoints
- Prepared statements (parameterized queries)
- ORM-style model definitions with real SQL persistence
"""

import sqlite3
import threading
import json
import os
import time
from contextlib import contextmanager
from typing import Any, Optional


# ─── Dialect detection ────────────────────────────────────────

def _detect_dialect(path_or_dsn: str) -> str:
    """Detect database dialect from connection string."""
    s = path_or_dsn.strip().lower()
    if s.startswith('postgres://') or s.startswith('postgresql://'):
        return 'postgres'
    if s.startswith('mysql://') or s.startswith('mysql+'):
        return 'mysql'
    return 'sqlite'


def _parse_dsn(dsn: str) -> dict:
    """Parse a URI-style DSN into connection parameters."""
    import urllib.parse
    parsed = urllib.parse.urlparse(dsn)
    params = {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port,
        'user': parsed.username,
        'database': parsed.path.lstrip('/') if parsed.path else None,
    }
    if parsed.password:
        params['password'] = parsed.password
    # Remove None values
    return {k: v for k, v in params.items() if v is not None}


# ─── Connection Pool ──────────────────────────────────────────

class ConnectionPool:
    """Thread-safe connection pool for SQLite, PostgreSQL, and MySQL."""

    def __init__(self, db_path: str, max_connections: int = 10, dialect: str = 'sqlite',
                 connect_args: dict = None):
        self.db_path = db_path
        self.max_connections = max_connections
        self.dialect = dialect
        self.connect_args = connect_args or {}
        self._pool: list = []
        self._in_use: set = set()
        self._lock = threading.Lock()

    def _create_connection(self):
        """Create a new connection for the appropriate dialect."""
        if self.dialect == 'sqlite':
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        elif self.dialect == 'postgres':
            try:
                import psycopg2  # type: ignore[import-untyped]
                import psycopg2.extras  # type: ignore[import-untyped]
            except ImportError:
                raise RuntimeError(
                    'PostgreSQL support requires psycopg2. '
                    'Run: pip install psycopg2-binary')
            conn = psycopg2.connect(**self.connect_args)
            conn.autocommit = False
            return conn
        elif self.dialect == 'mysql':
            try:
                import mysql.connector  # type: ignore[import-untyped]
            except ImportError:
                raise RuntimeError(
                    'MySQL support requires mysql-connector-python. '
                    'Run: pip install mysql-connector-python')
            conn = mysql.connector.connect(**self.connect_args)
            return conn
        else:
            raise ValueError(f'Unsupported dialect: {self.dialect}')

    def get_connection(self):
        with self._lock:
            # Reuse idle connection
            if self._pool:
                conn = self._pool.pop()
                # Health check
                if self._is_alive(conn):
                    self._in_use.add(id(conn))
                    return conn
                else:
                    self._safe_close(conn)
            # Create new connection
            if len(self._in_use) < self.max_connections:
                conn = self._create_connection()
                self._in_use.add(id(conn))
                return conn
            raise RuntimeError("Connection pool exhausted")

    def _is_alive(self, conn) -> bool:
        """Check if a connection is still alive."""
        try:
            if self.dialect == 'sqlite':
                conn.execute("SELECT 1")
            elif self.dialect == 'postgres':
                conn.cursor().execute("SELECT 1")
            elif self.dialect == 'mysql':
                conn.ping(reconnect=False)
            return True
        except Exception:
            return False

    def _safe_close(self, conn):
        try:
            conn.close()
        except Exception:
            pass

    def release(self, conn):
        with self._lock:
            cid = id(conn)
            if cid in self._in_use:
                self._in_use.discard(cid)
                self._pool.append(conn)

    def close_all(self):
        with self._lock:
            for conn in self._pool:
                self._safe_close(conn)
            self._pool.clear()
            self._in_use.clear()

    @contextmanager
    def connection(self):
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.release(conn)


# ─── Database Connection ──────────────────────────────────────

class Database:
    """
    Main database interface supporting SQLite, PostgreSQL, and MySQL.

    Usage from EPL:
        Set db To Database("my_app.db")                              # SQLite
        Set db To Database("postgresql://user:pass@localhost/mydb")   # PostgreSQL
        Set db To Database("mysql://user:pass@localhost/mydb")        # MySQL
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        db.insert("users", {"name": "Alice"})
        Set users To db.query("SELECT * FROM users")
    """

    def __init__(self, path: str = ":memory:", pool_size: int = 5):
        self.path = path
        self.dialect = _detect_dialect(path)
        if self.dialect in ('postgres', 'mysql'):
            connect_args = _parse_dsn(path)
            self.pool = ConnectionPool(path, pool_size, self.dialect, connect_args)
        else:
            self.pool = ConnectionPool(path, pool_size, 'sqlite')
        self._conn = self.pool.get_connection()
        self._models: dict = {}
        self._migration_version = 0
        self._in_manual_transaction = False
        # Placeholder for parameterized query style
        self._param = '?' if self.dialect == 'sqlite' else '%s'
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        if self.dialect == 'sqlite':
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS _epl_migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL,
                    name TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._conn.commit()
            row = self._conn.execute(
                "SELECT MAX(version) FROM _epl_migrations"
            ).fetchone()
            self._migration_version = row[0] or 0
        else:
            # PostgreSQL / MySQL
            cursor = self._conn.cursor()
            if self.dialect == 'postgres':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS _epl_migrations (
                        id SERIAL PRIMARY KEY,
                        version INTEGER NOT NULL,
                        name TEXT,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS _epl_migrations (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        version INT NOT NULL,
                        name TEXT,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            self._conn.commit()
            cursor.execute("SELECT MAX(version) FROM _epl_migrations")
            row = cursor.fetchone()
            self._migration_version = (row[0] or 0) if row else 0
            cursor.close()

    # ─── Core Operations ──────────────────────────────────────

    def _adapt_sql(self, sql: str) -> str:
        """Adapt SQL parameter placeholders for the current dialect."""
        if self.dialect != 'sqlite':
            return sql.replace('?', '%s')
        return sql

    def _execute(self, sql: str, params=(), cursor=None):
        """Execute SQL through the appropriate driver interface."""
        sql = self._adapt_sql(sql)
        if self.dialect == 'sqlite':
            return self._conn.execute(sql, params)
        else:
            cur = cursor or self._conn.cursor()
            cur.execute(sql, params)
            return cur

    def _commit(self):
        if not self._in_manual_transaction:
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> int:
        """Execute SQL and return rows affected."""
        cursor = self._execute(sql, params)
        self._commit()
        return cursor.rowcount

    def execute_many(self, sql: str, params_list: list) -> int:
        """Execute SQL with multiple parameter sets."""
        sql = self._adapt_sql(sql)
        if self.dialect == 'sqlite':
            cursor = self._conn.executemany(sql, params_list)
        else:
            cursor = self._conn.cursor()
            cursor.executemany(sql, params_list)
        self._commit()
        return cursor.rowcount

    def query(self, sql: str, params: tuple = ()) -> list:
        """Execute query and return list of dicts."""
        cursor = self._execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        if self.dialect == 'sqlite':
            return [dict(zip(columns, row)) for row in rows]
        else:
            return [dict(zip(columns, row)) for row in rows]

    def query_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute query and return first row as dict."""
        cursor = self._execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None

    def query_value(self, sql: str, params: tuple = ()):
        """Execute query and return single scalar value."""
        cursor = self._execute(sql, params)
        row = cursor.fetchone()
        return row[0] if row else None

    # ─── CRUD Helpers ─────────────────────────────────────────

    def insert(self, table: str, data: dict) -> int:
        """Insert row and return last row ID."""
        columns = ', '.join(data.keys())
        placeholders = ', '.join([self._param] * len(data))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = self._execute(sql, tuple(data.values()))
        self._commit()
        if self.dialect == 'sqlite':
            return cursor.lastrowid
        elif self.dialect == 'postgres':
            # PostgreSQL: use RETURNING id if available
            try:
                self._execute(sql + " RETURNING id", tuple(data.values()))
                row = cursor.fetchone()
                return row[0] if row else 0
            except Exception:
                return cursor.rowcount
        else:
            return cursor.lastrowid if hasattr(cursor, 'lastrowid') else 0

    def insert_many(self, table: str, rows: list) -> int:
        """Insert multiple rows."""
        if not rows:
            return 0
        columns = ', '.join(rows[0].keys())
        placeholders = ', '.join([self._param] * len(rows[0]))
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        sql_adapted = self._adapt_sql(sql)
        if self.dialect == 'sqlite':
            cursor = self._conn.executemany(sql_adapted, [tuple(r.values()) for r in rows])
        else:
            cursor = self._conn.cursor()
            cursor.executemany(sql_adapted, [tuple(r.values()) for r in rows])
        self._commit()
        return cursor.rowcount

    def update(self, table: str, data: dict, where: str, params: tuple = ()) -> int:
        """Update rows matching condition."""
        set_clause = ', '.join(f"{k} = {self._param}" for k in data.keys())
        where_adapted = self._adapt_sql(where) if self.dialect != 'sqlite' else where
        sql = f"UPDATE {table} SET {set_clause} WHERE {where_adapted}"
        all_params = tuple(data.values()) + params
        cursor = self._execute(sql, all_params)
        self._commit()
        return cursor.rowcount

    def delete(self, table: str, where: str, params: tuple = ()) -> int:
        """Delete rows matching condition."""
        where_adapted = self._adapt_sql(where) if self.dialect != 'sqlite' else where
        sql = f"DELETE FROM {table} WHERE {where_adapted}"
        cursor = self._execute(sql, params)
        self._commit()
        return cursor.rowcount

    def find_by_id(self, table: str, id_val) -> Optional[dict]:
        """Find row by primary key."""
        return self.query_one(f"SELECT * FROM {table} WHERE id = {self._param}", (id_val,))

    def count(self, table: str, where: str = "1=1", params: tuple = ()) -> int:
        """Count rows matching condition."""
        where_adapted = self._adapt_sql(where) if self.dialect != 'sqlite' else where
        return self.query_value(f"SELECT COUNT(*) FROM {table} WHERE {where_adapted}", params)

    def exists(self, table: str, where: str, params: tuple = ()) -> bool:
        """Check if any rows match condition."""
        return self.count(table, where, params) > 0

    # ─── Transaction Support ──────────────────────────────────

    @contextmanager
    def transaction(self):
        """Context manager for transactions with auto-rollback."""
        if self.dialect == 'sqlite':
            self._conn.execute("BEGIN")
        else:
            self._in_manual_transaction = True
        try:
            yield self
            if self.dialect == 'sqlite':
                self._conn.execute("COMMIT")
            else:
                self._conn.commit()
        except Exception:
            if self.dialect == 'sqlite':
                self._conn.execute("ROLLBACK")
            else:
                self._conn.rollback()
            raise
        finally:
            self._in_manual_transaction = False

    def savepoint(self, name: str):
        """Create a savepoint."""
        self._conn.execute(f"SAVEPOINT {name}")

    def release_savepoint(self, name: str):
        """Release a savepoint."""
        self._conn.execute(f"RELEASE SAVEPOINT {name}")

    def rollback_to(self, name: str):
        """Rollback to a savepoint."""
        self._conn.execute(f"ROLLBACK TO SAVEPOINT {name}")

    # ─── Schema Operations ────────────────────────────────────

    def create_table(self, name: str, columns: dict, if_not_exists: bool = True):
        """
        Create table from column definitions.
        columns: {"name": "TEXT NOT NULL", "age": "INTEGER DEFAULT 0"}
        Auto-adapts types for PostgreSQL/MySQL.
        """
        exists = "IF NOT EXISTS " if if_not_exists else ""
        adapted_cols = {}
        for col, typedef in columns.items():
            adapted_cols[col] = self._adapt_type(typedef)
        col_defs = ', '.join(f"{col} {typedef}" for col, typedef in adapted_cols.items())
        self._execute(f"CREATE TABLE {exists}{name} ({col_defs})")
        self._conn.commit()

    def _adapt_type(self, typedef: str) -> str:
        """Adapt SQLite type definitions for PostgreSQL/MySQL."""
        if self.dialect == 'sqlite':
            return typedef
        t = typedef.upper()
        if self.dialect == 'postgres':
            t = t.replace('INTEGER PRIMARY KEY AUTOINCREMENT',
                          'SERIAL PRIMARY KEY')
            t = t.replace('AUTOINCREMENT', '')
        elif self.dialect == 'mysql':
            t = t.replace('AUTOINCREMENT', 'AUTO_INCREMENT')
            t = t.replace('TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                          'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        return t if self.dialect != 'sqlite' else typedef

    def drop_table(self, name: str, if_exists: bool = True):
        exists = "IF EXISTS " if if_exists else ""
        self._execute(f"DROP TABLE {exists}{name}")
        self._conn.commit()

    def table_exists(self, name: str) -> bool:
        if self.dialect == 'sqlite':
            row = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (name,)
            ).fetchone()
            return row is not None
        elif self.dialect == 'postgres':
            row = self.query_one(
                "SELECT tablename FROM pg_tables WHERE tablename = %s",
                (name,))
            return row is not None
        else:
            row = self.query_one(
                "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_NAME = %s",
                (name,))
            return row is not None

    def tables(self) -> list:
        """List all tables."""
        if self.dialect == 'sqlite':
            rows = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_epl_%'"
            ).fetchall()
            return [row[0] for row in rows]
        elif self.dialect == 'postgres':
            result = self.query(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename NOT LIKE '_epl_%'")
            return [r['tablename'] for r in result]
        else:
            result = self.query(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME NOT LIKE '_epl_%'")
            return [r['TABLE_NAME'] for r in result]

    def columns(self, table: str) -> list:
        """Get column info for a table."""
        if self.dialect == 'sqlite':
            rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            return [{"name": r[1], "type": r[2], "notnull": bool(r[3]),
                     "default": r[4], "pk": bool(r[5])} for r in rows]
        elif self.dialect == 'postgres':
            result = self.query(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns WHERE table_name = %s "
                "ORDER BY ordinal_position", (table,))
            return [{"name": r['column_name'], "type": r['data_type'],
                     "notnull": r['is_nullable'] == 'NO',
                     "default": r['column_default'], "pk": False} for r in result]
        else:
            result = self.query(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY "
                "FROM information_schema.COLUMNS WHERE TABLE_NAME = %s "
                "AND TABLE_SCHEMA = DATABASE() ORDER BY ORDINAL_POSITION", (table,))
            return [{"name": r['COLUMN_NAME'], "type": r['DATA_TYPE'],
                     "notnull": r['IS_NULLABLE'] == 'NO',
                     "default": r['COLUMN_DEFAULT'],
                     "pk": r['COLUMN_KEY'] == 'PRI'} for r in result]

    def add_column(self, table: str, name: str, typedef: str):
        """Add a column to existing table."""
        self._execute(f"ALTER TABLE {table} ADD COLUMN {name} {self._adapt_type(typedef)}")
        self._conn.commit()

    # ─── Migrations ───────────────────────────────────────────

    def migrate(self, version: int, name: str, up_sql: str, down_sql: str = ""):
        """Apply a migration if not already applied."""
        if version <= self._migration_version:
            return False
        self._execute(up_sql)
        self._execute(
            f"INSERT INTO _epl_migrations (version, name) VALUES ({self._param}, {self._param})",
            (version, name)
        )
        self._conn.commit()
        self._migration_version = version
        return True

    def migration_status(self) -> list:
        """Get list of applied migrations."""
        return self.query("SELECT * FROM _epl_migrations ORDER BY version")

    # ─── Query Builder ────────────────────────────────────────

    def table(self, name: str):
        """Start a fluent query on a table."""
        return QueryBuilder(self, name)

    # ─── Model/ORM ────────────────────────────────────────────

    def define_model(self, name: str, fields: dict, table_name: str = None):
        """
        Define a model for ORM-style operations.
        fields: {"name": "TEXT NOT NULL", "email": "TEXT UNIQUE"}
        Adds 'id INTEGER PRIMARY KEY AUTOINCREMENT' automatically.
        """
        tbl = table_name or name.lower() + 's'
        model = Model(self, tbl, fields)
        self._models[name] = model
        return model

    def model(self, name: str):
        """Get a defined model."""
        return self._models.get(name)

    # ─── Cleanup ──────────────────────────────────────────────

    def close(self):
        self.pool.release(self._conn)
        self.pool.close_all()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self):
        return f"<Database path='{self.path}'>"


# ─── Query Builder ────────────────────────────────────────────

class QueryBuilder:
    """Fluent SQL query builder with cross-dialect support."""

    def __init__(self, db: Database, table: str):
        self._db = db
        self._table = table
        self._param = db._param  # '?' for sqlite, '%s' for postgres/mysql
        self._select_cols = '*'
        self._where_clauses: list = []
        self._where_params: list = []
        self._order_by: Optional[str] = None
        self._limit_val: Optional[int] = None
        self._offset_val: Optional[int] = None
        self._group_by: Optional[str] = None
        self._having: Optional[str] = None
        self._joins: list = []

    def select(self, *columns):
        self._select_cols = ', '.join(columns) if columns else '*'
        return self

    def where(self, condition: str, *params):
        self._where_clauses.append(condition)
        self._where_params.extend(params)
        return self

    def where_eq(self, column: str, value):
        return self.where(f"{column} = {self._param}", value)

    def where_in(self, column: str, values: list):
        placeholders = ', '.join([self._param] * len(values))
        self._where_clauses.append(f"{column} IN ({placeholders})")
        self._where_params.extend(values)
        return self

    def where_like(self, column: str, pattern: str):
        return self.where(f"{column} LIKE {self._param}", pattern)

    def where_between(self, column: str, low, high):
        return self.where(f"{column} BETWEEN {self._param} AND {self._param}", low, high)

    def where_null(self, column: str):
        self._where_clauses.append(f"{column} IS NULL")
        return self

    def where_not_null(self, column: str):
        self._where_clauses.append(f"{column} IS NOT NULL")
        return self

    def order_by(self, column: str, direction: str = "ASC"):
        self._order_by = f"{column} {direction.upper()}"
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    def offset(self, n: int):
        self._offset_val = n
        return self

    def group_by(self, *columns):
        self._group_by = ', '.join(columns)
        return self

    def having(self, condition: str, *params):
        self._having = condition
        self._where_params.extend(params)
        return self

    def join(self, table: str, on: str, join_type: str = "INNER"):
        self._joins.append(f"{join_type} JOIN {table} ON {on}")
        return self

    def left_join(self, table: str, on: str):
        return self.join(table, on, "LEFT")

    def right_join(self, table: str, on: str):
        return self.join(table, on, "RIGHT")

    def _build_sql(self):
        sql = f"SELECT {self._select_cols} FROM {self._table}"
        for j in self._joins:
            sql += f" {j}"
        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
        if self._group_by:
            sql += f" GROUP BY {self._group_by}"
        if self._having:
            sql += f" HAVING {self._having}"
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        if self._offset_val is not None:
            sql += f" OFFSET {self._offset_val}"
        return sql

    def get(self) -> list:
        """Execute and return all rows."""
        return self._db.query(self._build_sql(), tuple(self._where_params))

    def first(self) -> Optional[dict]:
        """Execute and return first row."""
        self._limit_val = 1
        return self._db.query_one(self._build_sql(), tuple(self._where_params))

    def count(self) -> int:
        """Count matching rows."""
        old_select = self._select_cols
        self._select_cols = 'COUNT(*) as cnt'
        result = self._db.query_value(self._build_sql(), tuple(self._where_params))
        self._select_cols = old_select
        return result or 0

    def sum(self, column: str):
        old_select = self._select_cols
        self._select_cols = f'SUM({column})'
        result = self._db.query_value(self._build_sql(), tuple(self._where_params))
        self._select_cols = old_select
        return result or 0

    def avg(self, column: str):
        old_select = self._select_cols
        self._select_cols = f'AVG({column})'
        result = self._db.query_value(self._build_sql(), tuple(self._where_params))
        self._select_cols = old_select
        return result

    def max(self, column: str):
        old_select = self._select_cols
        self._select_cols = f'MAX({column})'
        result = self._db.query_value(self._build_sql(), tuple(self._where_params))
        self._select_cols = old_select
        return result

    def min(self, column: str):
        old_select = self._select_cols
        self._select_cols = f'MIN({column})'
        result = self._db.query_value(self._build_sql(), tuple(self._where_params))
        self._select_cols = old_select
        return result

    def delete(self) -> int:
        """Delete matching rows."""
        sql = f"DELETE FROM {self._table}"
        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
        return self._db.execute(sql, tuple(self._where_params))

    def update(self, data: dict) -> int:
        """Update matching rows."""
        set_clause = ', '.join(f"{k} = {self._param}" for k in data.keys())
        sql = f"UPDATE {self._table} SET {set_clause}"
        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)
        params = tuple(data.values()) + tuple(self._where_params)
        return self._db.execute(sql, params)

    def insert(self, data: dict) -> int:
        """Insert a row."""
        return self._db.insert(self._table, data)

    def insert_many(self, rows: list) -> int:
        """Insert multiple rows."""
        return self._db.insert_many(self._table, rows)

    def paginate(self, page: int, per_page: int = 20) -> dict:
        """Paginate results."""
        total = self.count()
        self._limit_val = per_page
        self._offset_val = (page - 1) * per_page
        data = self.get()
        return {
            'data': data,
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
        }

    def to_sql(self) -> str:
        """Return the SQL string without executing."""
        return self._build_sql()


# ─── Model (ORM) ─────────────────────────────────────────────

class Model:
    """ORM-style model backed by real SQLite table."""

    def __init__(self, db: Database, table: str, fields: dict):
        self.db = db
        self.table = table
        self.fields = fields
        self._ensure_table()

    def _ensure_table(self):
        """Create table if it doesn't exist."""
        cols = {"id": "INTEGER PRIMARY KEY AUTOINCREMENT"}
        cols.update(self.fields)
        cols["created_at"] = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        cols["updated_at"] = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        self.db.create_table(self.table, cols, if_not_exists=True)

    def create(self, data: dict) -> dict:
        """Create a new record."""
        row_id = self.db.insert(self.table, data)
        return self.find(row_id)

    def find(self, id_val) -> Optional[dict]:
        """Find by ID."""
        return self.db.find_by_id(self.table, id_val)

    def all(self) -> list:
        """Get all records."""
        return self.db.query(f"SELECT * FROM {self.table}")

    def where(self, condition: str, *params) -> list:
        """Find records matching condition."""
        return self.db.query(
            f"SELECT * FROM {self.table} WHERE {condition}", params
        )

    def first(self, condition: str = "1=1", *params) -> Optional[dict]:
        """Find first record matching condition."""
        return self.db.query_one(
            f"SELECT * FROM {self.table} WHERE {condition} LIMIT 1", params
        )

    def update_record(self, id_val, data: dict) -> int:
        """Update a record by ID."""
        data['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        return self.db.update(self.table, data, "id = ?", (id_val,))

    def delete_record(self, id_val) -> int:
        """Delete a record by ID."""
        return self.db.delete(self.table, "id = ?", (id_val,))

    def count(self) -> int:
        return self.db.count(self.table)

    def query(self):
        """Start a query builder for this model."""
        return self.db.table(self.table)

    def __repr__(self):
        return f"<Model table='{self.table}' fields={list(self.fields.keys())}>"


# ─── EPL Integration Functions ────────────────────────────────

_databases: dict = {}


def db_connect(path: str = ":memory:", name: str = "default") -> Database:
    """Connect to a database (or create it).

    Supports connection URIs:
        db_connect("my_app.db")                               # SQLite file
        db_connect(":memory:")                                 # SQLite in-memory
        db_connect("postgresql://user:pass@localhost/mydb")    # PostgreSQL
        db_connect("mysql://user:pass@localhost/mydb")         # MySQL
    """
    db = Database(path)
    _databases[name] = db
    return db


def db_get(name: str = "default") -> Optional[Database]:
    """Get a named database connection."""
    return _databases.get(name)


def db_close(name: str = "default"):
    """Close a named database connection."""
    db = _databases.pop(name, None)
    if db:
        db.close()


def db_close_all():
    """Close all database connections."""
    for db in _databases.values():
        db.close()
    _databases.clear()
