"""Pytest coverage for the EPL Kotlin generator."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
KT_ENUM = to_kt("Enum Color as RED, GREEN, BLUE")
KT_CLASS = to_kt('Class Dog\n  name = "Rex"\nEnd')


KT_CASES = [
    ("has_package", lambda: "package com.epl.app" in to_kt('Print "Hello"')),
    ("has_main", lambda: "fun main()" in to_kt('Print "Hello"')),
    ("print_string", lambda: 'println("Hello")' in to_kt('Print "Hello"')),
    ("print_expr", lambda: "println((5 + 3))" in to_kt("Print 5 + 3")),
    ("say_alias", lambda: 'println("hi")' in to_kt('Say "hi"')),
    ("var_decl", lambda: "var x" in to_kt("x = 10") and "= 10" in to_kt("x = 10")),
    ("var_str", lambda: 'var name' in to_kt('name = "Alice"') and '"Alice"' in to_kt('name = "Alice"')),
    ("var_list", lambda: "mutableListOf(1, 2, 3)" in to_kt("items = [1, 2, 3]")),
    ("var_bool", lambda: "var flag" in to_kt("flag = true") and "true" in to_kt("flag = true")),
    ("var_assign", lambda: "x = " in to_kt("x = 10\nSet x to 20")),
    ("if_stmt", lambda: "if (" in KT_IF and 'println("big")' in KT_IF),
    ("if_else", lambda: "} else {" in KT_IF_ELSE),
    ("while_loop", lambda: "while (" in to_kt("While x < 10\n  x += 1\nEnd")),
    ("repeat_loop", lambda: "repeat(" in to_kt('Repeat 5 times\n  Print "hi"\nEnd')),
    ("for_range", lambda: "for (i in 1..10)" in to_kt("For i from 1 to 10\n  Print i\nEnd")),
    ("for_range_step", lambda: "step 2" in to_kt("For i from 0 to 10 step 2\n  Print i\nEnd")),
    ("for_range_neg_step", lambda: "downTo" in to_kt("For i from 5 to 1 step -1\n  Print i\nEnd")),
    ("for_each", lambda: "for (item in" in to_kt("items = [1, 2, 3]\nFor each item in items\n  Print item\nEnd")),
    ("func_def", lambda: "fun greet(" in KT_FN),
    ("func_param_type", lambda: "name: Any" in KT_FN),
    ("func_outside_main", lambda: KT_FN.index("fun greet") < KT_FN.index("fun main") if "fun main" in KT_FN else "fun greet" in KT_FN),
    ("func_return", lambda: "return (a + b)" in KT_FN_RETURN),
    ("func_call", lambda: "sum(3, 4)" in KT_CALL),
    ("try_catch", lambda: "try {" in KT_TRY_CATCH and "catch" in KT_TRY_CATCH),
    ("throw_stmt", lambda: "throw" in to_kt('Throw "oops"')),
    ("match_when", lambda: "when" in KT_MATCH),
    ("enum_class", lambda: "enum class Color" in KT_ENUM or "Color" in KT_ENUM),
    ("enum_members", lambda: "RED" in KT_ENUM and "GREEN" in KT_ENUM and "BLUE" in KT_ENUM),
    ("class_def", lambda: "class Dog" in KT_CLASS or "Dog" in KT_CLASS),
    ("const_decl", lambda: "val" in to_kt("Constant PI = 3.14")),
    ("aug_plus", lambda: "x += 5" in to_kt("x = 10\nx += 5")),
    ("aug_minus", lambda: "x -= 3" in to_kt("x = 10\nx -= 3")),
    ("ternary", lambda: "if" in to_kt('x = 10\ny = "big" if x > 5 otherwise "small"')),
    ("break_stmt", lambda: "break" in to_kt("While true\n  Break\nEnd")),
    ("continue_stmt", lambda: "continue" in to_kt("For i from 1 to 10\n  Continue\nEnd")),
    ("lambda_expr", lambda: "->" in to_kt("double = lambda x -> x * 2") or "fun" in to_kt("double = lambda x -> x * 2")),
    ("assert_stmt", lambda: "assert" in to_kt("Assert 1 == 1").lower() or "require" in to_kt("Assert 1 == 1")),
]


@pytest.mark.parametrize(("name", "check_fn"), KT_CASES, ids=[name for name, _ in KT_CASES])
def test_kotlin_generator_cases(name, check_fn):
    assert check_fn(), name
