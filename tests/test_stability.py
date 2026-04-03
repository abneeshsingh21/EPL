"""Pytest coverage for interpreter stability edge cases."""

from __future__ import annotations

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epl.errors import EPLError
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser


def run_epl(code: str):
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    error = None
    try:
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interpreter = Interpreter()
        interpreter.execute(program)
    except EPLError as exc:
        error = str(exc)
    except Exception as exc:
        error = f"PYTHON CRASH: {type(exc).__name__}: {exc}"
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    return output.strip(), error


def assert_output(code: str, expected: str):
    output, error = run_epl(code)
    assert error is None, f"Unexpected error: {error}"
    assert output == expected


def assert_error(code: str, keyword: str | None = None):
    output, error = run_epl(code)
    assert not (error and "PYTHON CRASH" in error), f"Python crash instead of EPL error: {error}"
    assert error is not None, f"Expected error but got output: {output!r}"
    if keyword:
        assert keyword.lower() in error.lower(), error


ERROR_CASES = [
    ("max_empty_list", "Print max([])", "empty"),
    ("min_empty_list", "Print min([])", "empty"),
    ("sum_non_numeric", 'Create items equal to ["a", "b"]\nPrint sum(items)\n', "numeric"),
    ("sorted_mixed_types", 'Create items equal to [3, "hello", 1]\nPrint sorted(items)\n', "same type"),
    ("sqrt_negative", "Print sqrt(-1)", "negative"),
    ("log_zero", "Print log(0)", "positive"),
    ("log_negative", "Print log(-5)", "positive"),
    ("round_non_numeric", 'Print round("hello")', "number"),
    ("repeat_negative", 'Repeat -3 times\n    Print "hello"\nEnd\n', "negative"),
    ("reduce_empty_no_init", 'Create items equal to []\nCreate fn equal to lambda a, b -> a + b\nPrint items.reduce(fn)\n', "empty"),
    ("power_huge_exponent", "Create x equal to 10 ** 1000000000\n", "too large"),
    ("div_by_zero", "Print 10 / 0", "zero"),
    ("mod_by_zero", "Print 10 % 0", "zero"),
    ("floor_div_by_zero", "Print 10 // 0", "zero"),
    ("add_bool_to_int", "Create x equal to 5 - true\n", ""),
    ("list_index_out", "Create items equal to [1, 2, 3]\nPrint items[5]\n", "out of range"),
    ("list_negative_index", "Create items equal to [1, 2, 3]\nPrint items[-1]\n", "out of range"),
    ("string_index_out", 'Create s equal to "abc"\nPrint s[10]\n', "out of range"),
]


OUTPUT_CASES = [
    ("max_normal", "Print max(3, 7, 2)", "7"),
    ("min_normal", "Print min(3, 7, 2)", "2"),
    ("sum_normal", "Print sum([1, 2, 3])", "6"),
    ("sorted_normal", "Print sorted([3, 1, 2])", "[1, 2, 3]"),
    ("sqrt_normal", "Print sqrt(16)", "4.0"),
    ("round_normal", "Print round(3.7)", "4"),
    (
        "and_short_circuit",
        'Create items equal to []\nIf length(items) > 0 and items[0] == "hello" Then\n    Print "found"\nOtherwise\n    Print "safe"\nEnd\n',
        "safe",
    ),
    (
        "or_short_circuit",
        "Create x equal to 5\nIf x > 0 or x / 0 > 1 Then\n    Print \"safe\"\nEnd\n",
        "safe",
    ),
    ("and_both_true", 'If true and true Then\n    Print "yes"\nEnd\n', "yes"),
    ("or_both_false", 'If false or false Then\n    Print "yes"\nOtherwise\n    Print "no"\nEnd\n', "no"),
    ("repeat_zero", 'Create count equal to 0\nRepeat count times\n    Print "hello"\nEnd\nPrint "done"\n', "done"),
    ("reduce_with_init", 'Create items equal to []\nCreate fn equal to lambda a, b -> a + b\nPrint items.reduce(fn, 0)\n', "0"),
    ("reduce_normal", 'Create items equal to [1, 2, 3, 4]\nCreate fn equal to lambda a, b -> a + b\nPrint items.reduce(fn)\n', "10"),
    ("power_normal", "Print 2 ** 10", "1024"),
    ("div_normal", "Print 10 / 2", "5"),
    ("empty_list_length", "Create items equal to []\nPrint length(items)\n", "0"),
    ("empty_list_foreach", 'Create items equal to []\nFor each item in items\n    Print item\nEnd\nPrint "done"\n', "done"),
    ("empty_string", 'Create s equal to ""\nPrint length(s)\n', "0"),
    ("string_concat_with_num", 'Create x equal to "age: " + 25\nPrint x\n', "age: 25"),
    ("string_concat_with_bool", 'Create x equal to "flag: " + true\nPrint x\n', "flag: true"),
    (
        "recursion_normal",
        "Function fib takes n\n    If n <= 1 Then\n        Return n\n    End\n    Return fib(n - 1) + fib(n - 2)\nEnd\nPrint fib(10)\n",
        "55",
    ),
    ("chained_math", "Print 2 + 3 * 4 - 1", "13"),
    ("nested_function_calls", "Print absolute(0 - max(3, 7, 2))", "7"),
    ("list_method_chain", "Create items equal to [5, 3, 1, 4, 2]\nPrint sorted(items)\n", "[1, 2, 3, 4, 5]"),
]


@pytest.mark.parametrize(("name", "code", "keyword"), ERROR_CASES, ids=[name for name, _, _ in ERROR_CASES])
def test_stability_error_cases(name, code, keyword):
    assert_error(code, keyword or None)


@pytest.mark.parametrize(("name", "code", "expected"), OUTPUT_CASES, ids=[name for name, _, _ in OUTPUT_CASES])
def test_stability_output_cases(name, code, expected):
    assert_output(code, expected)
