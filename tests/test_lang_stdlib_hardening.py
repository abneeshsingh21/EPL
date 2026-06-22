"""
EPL language / stdlib hardening regression tests.

Covers four audited issues:

* #6 — bundled stdlib modules were unparseable/unimportable because they use
       the ``Note "..."`` comment form and natural names that collide with
       reserved tokens (``match``, ``fetch``, ``delete``, ``where``).
* #5 — ``db_create_table`` rejected legitimate multi-word constraints
       (``INTEGER PRIMARY KEY``, ``TEXT NOT NULL``) and parameterized types
       (``VARCHAR(255)``) while still needing to block SQL injection.
* #1 — ``Map with`` literals could not span multiple lines.
* #4 — ``Create x equal to Create WebApp ...`` produced an opaque error.

Run with: python -m pytest tests/test_lang_stdlib_hardening.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.interpreter import EPLDict, Interpreter
from epl.lexer import Lexer
from epl.parser import Parser, ParserError


def run_epl(source: str) -> list:
    """Lex → parse → execute an EPL program, returning its output lines."""
    interp = Interpreter()
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp.execute(program)
    return interp.output_lines


def parse_epl(source: str):
    return Parser(Lexer(source).tokenize()).parse()


# ═══════════════════════════════════════════════════════════════
# #6 — Note "..." comments and stdlib module imports
# ═══════════════════════════════════════════════════════════════


class TestNoteStringComment:
    def test_note_string_form_is_a_comment(self):
        """`Note "..."` (no colon) must be ignored like `Note:`."""
        out = run_epl('Note "this is a header comment"\nSay "after"\n')
        assert out == ['after']

    def test_note_string_with_leading_spaces(self):
        out = run_epl('Note    "spaced before the string"\nSay "ok"\n')
        assert out == ['ok']

    def test_note_colon_form_still_works(self):
        out = run_epl('Note: classic comment\nSay "ok"\n')
        assert out == ['ok']

    def test_note_remains_usable_as_identifier(self):
        """A variable literally named `note` must still work."""
        out = run_epl('Create note equal to 5\nSay note\n')
        assert out == ['5']


class TestStdlibModuleImports:
    """Every bundled stdlib module must parse and import cleanly."""

    MODULES = ['json', 'encoding', 'net', 'os', 'regex', 'sql']

    @pytest.mark.parametrize('module', MODULES)
    def test_module_parses(self, module):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, 'epl', 'stdlib', f'{module}.epl')
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
        # Should not raise — previously these all failed to parse.
        parse_epl(source)

    def test_regex_match_keyword_function_name(self):
        """`match` is a reserved token but must work as a wrapper function."""
        out = run_epl('Import "regex" as RE\nSay RE.match("[0-9]+", "123abc")\n')
        assert out == ['123']

    def test_encoding_roundtrip(self):
        out = run_epl('Import "encoding" as ENC\nSay ENC.to_base64("hi")\n')
        assert out == ['aGk=']

    def test_json_via_alias(self):
        """`json` is a reserved type token, so it must be imported with an alias."""
        out = run_epl(
            'Import "json" as J\nCreate r equal to J.parse("{\\"a\\": 1}")\nSay J.stringify(r)\n'
        )
        assert out == ['{"a": 1}']

    def test_sql_reserved_names_import(self):
        """sql wrappers use `delete` (fn) and `where` (param) — both reserved."""
        out = run_epl('Import "sql" as DB\nSay "sql ok"\n')
        assert out == ['sql ok']


# ═══════════════════════════════════════════════════════════════
# #5 — db_create_table constraint / type validation
# ═══════════════════════════════════════════════════════════════


class TestDbCreateTableConstraints:
    def _create(self, columns: dict):
        from epl.stdlib import _db_close, _db_create_table, _db_open

        conn = _db_open(':memory:')
        try:
            return _db_create_table(conn, 'tbl', EPLDict(dict(columns)))
        finally:
            _db_close(conn)

    def test_multi_word_constraints_allowed(self):
        assert self._create(
            {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT NOT NULL', 'email': 'VARCHAR(255) UNIQUE'}
        )

    def test_parameterized_types_allowed(self):
        assert self._create({'price': 'DECIMAL(10,2)', 'code': 'CHAR(8)'})

    @pytest.mark.parametrize(
        'bad_type',
        [
            'TEXT); DROP TABLE users;--',
            'VARCHAR(255 OR 1=1)',
            'TEXT; DELETE',
            'BOGUSTYPE',
        ],
    )
    def test_injection_and_bogus_types_rejected(self, bad_type):
        with pytest.raises(RuntimeError, match='Invalid column type component'):
            self._create({'x': bad_type})


# ═══════════════════════════════════════════════════════════════
# #1 — multi-line Map literals
# ═══════════════════════════════════════════════════════════════


class TestMultiLineMapLiterals:
    def test_single_line_still_terminates(self):
        """Regression: a single-line map must not swallow the next statement."""
        out = run_epl('Create m equal to Map with a = 1 and b = 2\nSay "after"\n')
        assert out == ['after']

    def test_and_at_end_of_line(self):
        out = run_epl(
            'Create m equal to Map with\n    name = "Alice" and\n    age = 30\nSay m.age\n'
        )
        assert out == ['30']

    def test_and_at_start_of_line(self):
        out = run_epl(
            'Create m equal to Map with\n    name = "Bob"\n    and age = 40\nSay m.name\n'
        )
        assert out == ['Bob']


# ═══════════════════════════════════════════════════════════════
# #4 — Create WebApp used as an expression
# ═══════════════════════════════════════════════════════════════


class TestWebAppExpressionError:
    def test_webapp_as_expression_gives_guidance(self):
        with pytest.raises(ParserError, match='statement, not a value'):
            parse_epl('Create app equal to Create WebApp called myapp\n')

    def test_correct_webapp_statement_parses(self):
        # Should not raise.
        parse_epl('Create WebApp called app\n')
