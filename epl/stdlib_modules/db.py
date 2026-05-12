"""
epl.stdlib_modules.db — Database domain public API.

Facade over the database functions in stdlib.py and database.py.
"""

from __future__ import annotations

FUNCTIONS = frozenset(
    {
        # SQLite / Simple DB
        'db_open',
        'db_close',
        'db_execute',
        'db_query',
        'db_query_one',
        'db_insert',
        'db_tables',
        'db_create_table',
        'db_update',
        'db_delete',
        'db_count',
        'db_table_info',
        'db_begin',
        'db_commit',
        'db_rollback',
        'db_backup',
        # ORM
        'orm_open',
        'orm_close',
        'orm_define_model',
        'orm_add_field',
        'orm_migrate',
        'orm_create',
        'orm_find',
        'orm_find_by_id',
        'orm_update',
        'orm_delete',
        'orm_delete_where',
        'orm_query',
        'orm_raw_query',
        'orm_raw_execute',
        'orm_transaction_begin',
        'orm_transaction_commit',
        'orm_transaction_rollback',
        'orm_table_exists',
        'orm_has_many',
        'orm_belongs_to',
        'orm_with_related',
        'orm_paginate',
        'orm_order_by',
        'orm_count_where',
        'orm_seed',
        'orm_add_index',
        'orm_first',
        'orm_last',
        # Production DB (PostgreSQL / MySQL)
        'real_db_connect',
        'real_db_get',
        'real_db_close',
        'real_db_close_all',
        'real_db_execute',
        'real_db_execute_many',
        'real_db_query',
        'real_db_query_one',
        'real_db_insert',
        'real_db_update',
        'real_db_delete',
        'real_db_find_by_id',
        'real_db_create_table',
        'real_db_count',
        'real_db_table_exists',
        'real_db_begin',
        'real_db_commit',
        'real_db_rollback',
        'real_db_migrate',
        'real_db_table',
    }
)

DOCS: dict[str, str] = {
    'db_open': 'Open or create a SQLite database file.',
    'db_close': 'Close a database connection.',
    'db_execute': 'Execute a SQL statement (INSERT/UPDATE/DELETE).',
    'db_query': 'Run a SELECT and return all rows as a list.',
    'db_query_one': 'Run a SELECT and return the first row.',
    'db_insert': 'Insert a row into a table.',
    'db_create_table': 'Create a table with schema definition.',
    'db_tables': 'List all table names in the database.',
    'db_count': 'Count rows in a table.',
    'db_begin': 'Begin a transaction.',
    'db_commit': 'Commit the current transaction.',
    'db_rollback': 'Rollback the current transaction.',
    'orm_open': 'Open ORM database connection.',
    'orm_define_model': 'Define an ORM model (table).',
    'orm_add_field': 'Add a field to an ORM model.',
    'orm_migrate': 'Run pending migrations (create/alter tables).',
    'orm_create': 'Create and persist a new record.',
    'orm_find': 'Find all records for a model.',
    'orm_find_by_id': 'Find a record by its primary key.',
    'orm_update': 'Update a record by ID.',
    'orm_delete': 'Delete a record by ID.',
    'orm_order_by': 'Query records ordered by a field.',
    'orm_paginate': 'Paginate records with limit and offset.',
    'orm_first': 'Find the first record.',
    'orm_last': 'Find the last record.',
    'orm_count_where': 'Count records matching a condition.',
    'real_db_connect': 'Connect to PostgreSQL, MySQL, or SQLite via URL.',
    'real_db_query': 'Run a query on a production database.',
    'real_db_execute': 'Execute a statement on a production database.',
    'real_db_begin': 'Begin a production DB transaction.',
    'real_db_commit': 'Commit a production DB transaction.',
    'real_db_rollback': 'Rollback a production DB transaction.',
}


def get_functions() -> frozenset[str]:
    return FUNCTIONS


def describe(fn_name: str) -> str:
    return DOCS.get(fn_name, f'{fn_name}: no documentation available.')
