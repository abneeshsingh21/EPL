"""Tests for v9.3.0 Phase 5 — SQL injection hardening.

Each test demonstrates a specific injection vector that *was* exploitable
before the hardening and proves it is now refused.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.interpreter import EPLDict
from epl.stdlib import _assert_sql_identifier, call_stdlib

# ── _assert_sql_identifier (the cross-cutting helper) ─────────────────────


class TestAssertSqlIdentifier:
    @pytest.mark.parametrize(
        'name',
        ['users', 'user_id', '_private', 'Order123', 'a', 'A_B_C'],
    )
    def test_accepts_valid_identifiers(self, name):
        assert _assert_sql_identifier(name) == name

    @pytest.mark.parametrize(
        'bad',
        [
            '1abc',                       # leading digit
            'name; DROP TABLE users',     # statement injection
            'id=1 OR 1=1 --',             # predicate injection
            'col WITH spaces',            # whitespace
            '',                           # empty
            'col-name',                   # dash
            'col*',                       # wildcard
            'col"; --',                   # quote-break
            'col`name',                   # backtick
        ],
    )
    def test_rejects_injection_attempts(self, bad):
        with pytest.raises(RuntimeError, match='Invalid SQL'):
            _assert_sql_identifier(bad)

    def test_rejects_non_string(self):
        for v in (None, 123, ['name']):
            with pytest.raises(RuntimeError):
                _assert_sql_identifier(v)

    def test_kind_appears_in_error(self):
        with pytest.raises(RuntimeError, match='Invalid SQL table'):
            _assert_sql_identifier('1bad', kind='table')
        with pytest.raises(RuntimeError, match='Invalid SQL column'):
            _assert_sql_identifier('1bad', kind='column')


# ── real_db_update / real_db_delete via the public stdlib dispatcher ──────


@pytest.fixture
def db():
    """In-memory SQLite via real_db_connect, with seed rows."""
    from epl import stdlib

    stdlib._real_db_instances.pop('inj_test', None)
    handle = call_stdlib('real_db_connect', [':memory:', 'inj_test'], 0)
    cols = EPLDict({'name': 'TEXT', 'email': 'TEXT'})
    call_stdlib('real_db_create_table', [handle, 'users', cols], 0)
    call_stdlib('real_db_insert', [handle, 'users', EPLDict({'name': 'alice', 'email': 'a@x'})], 0)
    call_stdlib('real_db_insert', [handle, 'users', EPLDict({'name': 'bob', 'email': 'b@x'})], 0)
    yield handle
    stdlib._real_db_instances.pop('inj_test', None)


def _all_emails(db_handle):
    rows = call_stdlib('real_db_query', [db_handle, 'SELECT email FROM users ORDER BY name'], 0)
    return [r.data['email'] for r in rows]


class TestRealDbUpdateInjection:
    def test_dict_where_with_clean_column_works(self, db):
        # Baseline: legitimate use still works.
        call_stdlib(
            'real_db_update',
            [db, 'users', EPLDict({'email': 'new@x'}), EPLDict({'name': 'alice'})],
            0,
        )
        assert _all_emails(db) == ['new@x', 'b@x']

    def test_dict_where_with_injection_column_rejected(self, db):
        # Attack: a malicious column name that, before hardening, would have
        # produced `WHERE name = 'alice' OR 1=1 -- = ?`, updating EVERY row.
        with pytest.raises(EPLRuntimeError, match='Invalid SQL'):
            call_stdlib(
                'real_db_update',
                [
                    db,
                    'users',
                    EPLDict({'email': 'pwned@x'}),
                    EPLDict({"name = 'alice' OR 1=1 --": 'ignored'}),
                ],
                0,
            )
        assert _all_emails(db) == ['a@x', 'b@x']  # unchanged

    def test_string_where_without_params_refused(self, db):
        # Attack: bare string WHERE with no params tuple — the classic footgun.
        with pytest.raises(EPLRuntimeError, match='requires a params tuple'):
            call_stdlib(
                'real_db_update',
                [db, 'users', EPLDict({'email': 'pwned@x'}), "name = 'alice' OR 1=1"],
                0,
            )
        assert _all_emails(db) == ['a@x', 'b@x']

    def test_string_where_with_params_still_works(self, db):
        # Power-user path: caller takes responsibility via placeholders.
        call_stdlib(
            'real_db_update',
            [db, 'users', EPLDict({'email': 'placeholder@x'}), 'name = ?', ('alice',)],
            0,
        )
        assert _all_emails(db) == ['placeholder@x', 'b@x']


class TestRealDbDeleteInjection:
    def test_dict_where_with_injection_column_rejected(self, db):
        with pytest.raises(EPLRuntimeError, match='Invalid SQL'):
            call_stdlib(
                'real_db_delete',
                [db, 'users', EPLDict({"name = 'alice' OR 1=1 --": 'ignored'})],
                0,
            )
        assert _all_emails(db) == ['a@x', 'b@x']  # nothing deleted

    def test_string_where_without_params_refused(self, db):
        with pytest.raises(EPLRuntimeError, match='requires a params tuple'):
            call_stdlib('real_db_delete', [db, 'users', "name = 'alice' OR 1=1"], 0)
        assert _all_emails(db) == ['a@x', 'b@x']

    def test_dict_where_clean_column_works(self, db):
        call_stdlib('real_db_delete', [db, 'users', EPLDict({'name': 'alice'})], 0)
        assert _all_emails(db) == ['b@x']
