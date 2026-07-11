"""Substring-level coverage for the EPL → Python transpiler.

`test_transpiler_fidelity.py` proves byte-for-byte interpreter/Python parity
over a corpus; this module pins the *emitted code shape* — operator routing
through the `_epl_*` helpers, the split between idiomatic `builtin_map`
mappings and the faithful `_epl_call` shim, conditional prelude emission, and
the `TranspileError` correct-or-loud guards.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.python_transpiler import PythonTranspiler, TranspileError, transpile_to_python


def to_python(src):
    return transpile_to_python(Parser(Lexer(src).tokenize()).parse())


PY_CASES = [
    # `+` and `/` always route through the overloaded EPL helpers (not raw
    # Python `+`/`/`), matching interpreter coercion/int-preserving division.
    ('add_via_helper', lambda: '_epl_add(5, 3)' in to_python('display 5 + 3')),
    ('div_via_helper', lambda: '_epl_div(10, 2)' in to_python('display 10 / 2')),
    ('assignment', lambda: 'x = 42' in to_python('set x to 42')),
    # Idiomatic 1:1 builtin_map mappings.
    ('length_to_len', lambda: 'len(' in to_python('display length("hi")')),
    ('absolute_to_abs', lambda: 'abs(' in to_python('display absolute(-5)')),
    ('floor_to_math', lambda: 'math.floor' in to_python('display floor(3.7)')),
    ('maximum_to_max', lambda: 'max(3, 7)' in to_python('display maximum(3, 7)')),
    # Builtins whose semantics diverge from Python route through the faithful
    # `_epl_call` shim instead of a lossy idiomatic mapping.
    ('max_via_shim', lambda: "_epl_call('max', 3, 7)" in to_python('display max(3, 7)')),
    ('gcd_via_shim', lambda: "_epl_call('gcd', 12, 8)" in to_python('display gcd(12, 8)')),
    (
        'factorial_via_shim',
        lambda: "_epl_call('factorial', 5)" in to_python('display factorial(5)'),
    ),
    ('type_of_via_shim', lambda: "_epl_call('type_of', 42)" in to_python('display type_of(42)')),
    # `trim` coerces non-text in the interpreter (str.strip would raise), so it
    # must go through the shim, not `str.strip`.
    ('trim_via_shim', lambda: "_epl_call('trim', 123)" in to_python('display trim(123)')),
]


HEADER_CASES = [
    ('shebang', lambda: to_python('set x to 1').startswith('#!/usr/bin/env python3')),
    ('autogen_comment', lambda: 'Auto-generated from EPL' in to_python('set x to 1')),
    ('empty_still_has_header', lambda: to_python('').startswith('#!/usr/bin/env python3')),
    # Prelude helpers are emitted only when used: a bare assignment pulls in none.
    ('no_helper_when_unused', lambda: '_epl_' not in to_python('set x to 42')),
    ('helper_when_used', lambda: '_epl_add' in to_python('display 1 + 2')),
]


class _Alien:
    """A node type the transpiler cannot recognise (line attr for the message)."""

    line = 7


@pytest.mark.parametrize(('name', 'check_fn'), PY_CASES, ids=[n for n, _ in PY_CASES])
def test_python_transpiler_cases(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), HEADER_CASES, ids=[n for n, _ in HEADER_CASES])
def test_python_transpiler_header(name, check_fn):
    assert check_fn(), name


def test_unknown_statement_raises_transpile_error():
    with pytest.raises(TranspileError):
        PythonTranspiler()._emit_stmt(_Alien())


def test_unknown_expression_raises_transpile_error():
    with pytest.raises(TranspileError):
        PythonTranspiler()._expr(_Alien())
