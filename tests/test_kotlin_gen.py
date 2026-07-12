"""Pytest coverage for the EPL Kotlin generator."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.kotlin_gen import transpile_to_kotlin
from epl.lexer import Lexer
from epl.parser import Parser


def to_kt(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse()
    return transpile_to_kotlin(program)


KT_IF = to_kt('If x > 5 then\n  Print "big"\nEnd')
KT_IF_ELSE = to_kt('If x > 5 then\n  Print "big"\nOtherwise\n  Print "small"\nEnd')
KT_FN = to_kt('Function greet takes name\n  Print "Hello " + name\nEnd')
KT_FN_RETURN = to_kt('Function add takes a and b\n  Return a + b\nEnd')
KT_CALL = to_kt('Function sum takes a and b\n  Return a + b\nEnd\nresult = call sum with 3 and 4')
KT_TRY_CATCH = to_kt('Try\n  Print 42\nCatch e\n  Print e\nEnd')
KT_MATCH = to_kt('x = 2\nMatch x\n  When 1\n    Print "one"\n  When 2\n    Print "two"\nEnd')
KT_ENUM = to_kt('Enum Color as RED, GREEN, BLUE')
KT_CLASS = to_kt('Class Dog\n  name = "Rex"\nEnd')


KT_CASES = [
    ('has_package', lambda: 'package com.epl.app' in to_kt('Print "Hello"')),
    ('has_main', lambda: 'fun main()' in to_kt('Print "Hello"')),
    ('print_string', lambda: 'println("Hello")' in to_kt('Print "Hello"')),
    ('print_expr', lambda: 'println((5 + 3))' in to_kt('Print 5 + 3')),
    ('say_alias', lambda: 'println("hi")' in to_kt('Say "hi"')),
    ('var_decl', lambda: 'var x' in to_kt('x = 10') and '= 10' in to_kt('x = 10')),
    (
        'var_str',
        lambda: 'var name' in to_kt('name = "Alice"') and '"Alice"' in to_kt('name = "Alice"'),
    ),
    ('var_list', lambda: 'mutableListOf(1, 2, 3)' in to_kt('items = [1, 2, 3]')),
    ('var_bool', lambda: 'var flag' in to_kt('flag = true') and 'true' in to_kt('flag = true')),
    ('var_assign', lambda: 'x = ' in to_kt('x = 10\nSet x to 20')),
    ('if_stmt', lambda: 'if (' in KT_IF and 'println("big")' in KT_IF),
    ('if_else', lambda: '} else {' in KT_IF_ELSE),
    ('while_loop', lambda: 'while (' in to_kt('While x < 10\n  x += 1\nEnd')),
    ('repeat_loop', lambda: 'repeat(' in to_kt('Repeat 5 times\n  Print "hi"\nEnd')),
    ('for_range', lambda: 'for (i in 1..10)' in to_kt('For i from 1 to 10\n  Print i\nEnd')),
    ('for_range_step', lambda: 'step 2' in to_kt('For i from 0 to 10 step 2\n  Print i\nEnd')),
    ('for_range_neg_step', lambda: 'downTo' in to_kt('For i from 5 to 1 step -1\n  Print i\nEnd')),
    (
        'for_each',
        lambda: (
            'for (item in' in to_kt('items = [1, 2, 3]\nFor each item in items\n  Print item\nEnd')
        ),
    ),
    ('func_def', lambda: 'fun greet(' in KT_FN),
    ('func_param_type', lambda: 'name: Any' in KT_FN),
    (
        'func_outside_main',
        lambda: (
            KT_FN.index('fun greet') < KT_FN.index('fun main')
            if 'fun main' in KT_FN
            else 'fun greet' in KT_FN
        ),
    ),
    # Untyped params are Any; `Any + Any` doesn't compile, so EPL `+` lowers to
    # the eplAdd runtime helper (numeric add or concat, matching EPL semantics).
    ('func_return', lambda: 'EPLRuntime.eplAdd(a, b)' in KT_FN_RETURN),
    ('func_call', lambda: 'sum(3, 4)' in KT_CALL),
    ('try_catch', lambda: 'try {' in KT_TRY_CATCH and 'catch' in KT_TRY_CATCH),
    ('throw_stmt', lambda: 'throw' in to_kt('Throw "oops"')),
    ('match_when', lambda: 'when' in KT_MATCH),
    ('enum_class', lambda: 'enum class Color' in KT_ENUM or 'Color' in KT_ENUM),
    ('enum_members', lambda: 'RED' in KT_ENUM and 'GREEN' in KT_ENUM and 'BLUE' in KT_ENUM),
    ('class_def', lambda: 'class Dog' in KT_CLASS or 'Dog' in KT_CLASS),
    ('const_decl', lambda: 'val' in to_kt('Constant PI = 3.14')),
    ('aug_plus', lambda: 'x += 5' in to_kt('x = 10\nx += 5')),
    ('aug_minus', lambda: 'x -= 3' in to_kt('x = 10\nx -= 3')),
    ('ternary', lambda: 'if' in to_kt('x = 10\ny = "big" if x > 5 otherwise "small"')),
    ('break_stmt', lambda: 'break' in to_kt('While true\n  Break\nEnd')),
    ('continue_stmt', lambda: 'continue' in to_kt('For i from 1 to 10\n  Continue\nEnd')),
    (
        'lambda_expr',
        lambda: (
            '->' in to_kt('double = lambda x -> x * 2')
            or 'fun' in to_kt('double = lambda x -> x * 2')
        ),
    ),
    (
        'assert_stmt',
        lambda: 'assert' in to_kt('Assert 1 == 1').lower() or 'require' in to_kt('Assert 1 == 1'),
    ),
]


@pytest.mark.parametrize(('name', 'check_fn'), KT_CASES, ids=[name for name, _ in KT_CASES])
def test_kotlin_generator_cases(name, check_fn):
    assert check_fn(), name


def test_string_literal_escapes_dollar_no_injection():
    """H2: `$` in an EPL string must be escaped so Kotlin does not interpolate
    it into live code in the generated app."""
    from epl.kotlin_gen import KotlinGenerator

    payload = '${Runtime.getRuntime().exec("calc")}'
    literal = KotlinGenerator._kotlin_str_literal(payload)
    assert literal.startswith('"\\${'), literal  # dollar escaped
    assert '"${' not in literal, 'unescaped Kotlin interpolation leaked into output'


def test_string_literal_escapes_preserved():
    """Ordinary escaping (quote, backslash) still works after the shared
    literal-helper refactor."""
    from epl.kotlin_gen import KotlinGenerator

    literal = KotlinGenerator._kotlin_str_literal('a"b\\c')
    assert '\\"' in literal and '\\\\' in literal


def test_reassignment_declares_once():
    """`x = 5` then `x = 10` must emit one `var` and a bare reassignment,
    not two conflicting declarations."""
    kt = to_kt('x = 5\nx = 10\nPrint x')
    assert kt.count('var x') == 1
    assert 'x = 10' in kt


def test_ambiguous_plus_uses_runtime_helper():
    """`a + b` on untyped params can't compile as `Any + Any`; it must lower to
    the eplAdd runtime helper (numeric add or concat)."""
    kt = to_kt('Function add takes a and b\n  Return a + b\nEnd')
    assert 'EPLRuntime.eplAdd(a, b)' in kt


def test_division_uses_runtime_helper():
    """EPL `/` is float division that raises on zero, so it lowers to eplDiv
    rather than Kotlin integer division (which would give a wrong value)."""
    kt = to_kt('r = 10 / 4\nPrint r')
    assert 'EPLRuntime.eplDiv(10, 4)' in kt


def test_db_and_file_builtins_bridge_to_runtime():
    """db_create_table / db_tables / file_* must map to EPLRuntime methods,
    not pass through as unresolved snake_case calls."""
    kt = to_kt(
        'db = db_open("t.db")\n'
        'cols = Map with id = "INTEGER"\n'
        'db_create_table(db, "users", cols)\n'
        'names = db_tables(db)\n'
        'file_delete("x.txt")\n'
    )
    assert 'EPLRuntime.dbCreateTable(' in kt
    assert 'EPLRuntime.dbTables(' in kt
    assert 'EPLRuntime.fileDelete(' in kt


def test_class_method_call_return_type_resolved():
    """A call on a user-class instance resolves the class's declared method
    return type, not the generic builtin `.add` ⇒ Unit mapping."""
    kt = to_kt(
        'Class Calc\n'
        '  Function addup takes a and b\n'
        '    Return a + b\n'
        '  End\n'
        'End\n'
        'c = new Calc\n'
        's = c.addup(1, 2)\n'
        'Print s'
    )
    assert 'var s: Unit' not in kt


def test_python_interop_flagged_unportable():
    """`Use python` has no native runtime; the portability report must flag it
    rather than silently emit uncompilable references."""
    from epl.native_portability import analyze

    tokens = Lexer('Use python "math"\nPrint math.sqrt(9)').tokenize()
    program = Parser(tokens).parse()
    report = analyze(program, 'android')
    assert report.has_blocking
    assert any('python' in i.detail.lower() for i in report.issues)
