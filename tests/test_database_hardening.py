"""
Phase 4 — Database defense-in-depth regression tests.

These verify that QueryBuilder (epl.database) and the low-level CRUD helpers
in epl.database_real reject SQL identifiers that don't match a strict
[A-Za-z_][A-Za-z0-9_]* pattern, and that the typed where_* / order_by /
limit / offset helpers refuse to interpolate untrusted strings into SQL.
"""

import os
import tempfile
import unittest

from epl.database import QueryBuilder, _quote_identifier
from epl.database_real import Database


class _FakeDB:
    """Stand-in Database for QueryBuilder unit tests — never actually queries."""

    def raw_query(self, sql, params):
        return []


class TestQueryBuilderHardening(unittest.TestCase):
    def setUp(self):
        self.db = _FakeDB()

    def test_table_name_must_be_valid_identifier(self):
        with self.assertRaises(ValueError):
            QueryBuilder(self.db, 'users; DROP TABLE users')

    def test_where_eq_rejects_bad_column(self):
        qb = QueryBuilder(self.db, 'users')
        with self.assertRaises(ValueError):
            qb.where_eq('name; --', 'Alice')

    def test_where_in_with_empty_list_does_not_raise_but_yields_false(self):
        qb = QueryBuilder(self.db, 'users').where_in('id', [])
        sql, params = qb.build()
        self.assertIn('1 = 0', sql)
        self.assertEqual(params, [])

    def test_select_rejects_bad_column(self):
        qb = QueryBuilder(self.db, 'users')
        with self.assertRaises(ValueError):
            qb.select('id', 'name; DROP TABLE users')

    def test_order_by_validates_direction(self):
        qb = QueryBuilder(self.db, 'users')
        with self.assertRaises(ValueError):
            qb.order_by('id', 'ASC; DROP TABLE users')

    def test_limit_offset_coerce_to_int(self):
        # Numeric strings work via int() coercion.
        qb = QueryBuilder(self.db, 'users').limit('10').offset('5')
        sql, _ = qb.build()
        self.assertIn('LIMIT 10', sql)
        self.assertIn('OFFSET 5', sql)
        # Injection attempts via the LIMIT/OFFSET slot fail loudly.
        with self.assertRaises(ValueError):
            QueryBuilder(self.db, 'users').limit('10; DROP TABLE x')
        with self.assertRaises(ValueError):
            QueryBuilder(self.db, 'users').offset('NOT A NUMBER')

    def test_group_by_quotes_identifiers(self):
        qb = QueryBuilder(self.db, 'users').group_by('age')
        sql, _ = qb.build()
        self.assertIn('"age"', sql)
        with self.assertRaises(ValueError):
            QueryBuilder(self.db, 'users').group_by('age; --')

    def test_join_quotes_table(self):
        qb = QueryBuilder(self.db, 'users').join('posts', 'users.id = posts.user_id')
        sql, _ = qb.build()
        self.assertIn('JOIN "posts"', sql)
        with self.assertRaises(ValueError):
            QueryBuilder(self.db, 'users').join('posts; DROP TABLE x', 'a = b')

    def test_built_sql_has_quoted_table(self):
        qb = QueryBuilder(self.db, 'users').where_eq('id', 5)
        sql, params = qb.build()
        self.assertIn('FROM "users"', sql)
        self.assertIn('"id" = ?', sql)
        self.assertEqual(params, [5])


class TestDatabaseRealHardening(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, 'test.db')
        self.db = Database(self.path)
        self.db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)')

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_insert_rejects_bad_table(self):
        with self.assertRaises(ValueError):
            self.db.insert('users; DROP TABLE users', {'name': 'Alice'})

    def test_insert_rejects_bad_column(self):
        with self.assertRaises(ValueError):
            self.db.insert('users', {'name; --': 'Alice'})

    def test_update_rejects_bad_table(self):
        with self.assertRaises(ValueError):
            self.db.update('users; --', {'name': 'X'}, 'id = ?', (1,))

    def test_delete_rejects_bad_table(self):
        with self.assertRaises(ValueError):
            self.db.delete('users; DROP TABLE users', 'id = ?', (1,))

    def test_count_rejects_bad_table(self):
        with self.assertRaises(ValueError):
            self.db.count('users; --')

    def test_find_by_id_rejects_bad_table(self):
        with self.assertRaises(ValueError):
            self.db.find_by_id('users; --', 1)

    def test_happy_path_insert_then_count(self):
        self.db.insert('users', {'name': 'Alice', 'age': 30})
        self.db.insert('users', {'name': 'Bob', 'age': 25})
        self.assertEqual(self.db.count('users'), 2)


if __name__ == '__main__':
    unittest.main()
