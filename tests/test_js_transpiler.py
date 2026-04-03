"""Pytest coverage for the EPL JavaScript transpiler."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from epl.js_transpiler import transpile_to_js, transpile_to_node
from epl.lexer import Lexer
from epl.parser import Parser


def to_js(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse()
    return transpile_to_js(program)


def to_node(src):
    tokens = Lexer(src).tokenize()
    program = Parser(tokens).parse()
    return transpile_to_node(program)


JS_IF = to_js('If x > 5 then\n  Print "big"\nEnd')
JS_IF_ELSE = to_js('If x > 5 then\n  Print "big"\nOtherwise\n  Print "small"\nEnd')
JS_FN = to_js('Function greet takes name\n  Print "Hello " + name\nEnd')
JS_FN_RETURN = to_js('Function add takes a and b\n  Return a + b\nEnd')
JS_CALL = to_js('Function sum takes a and b\n  Return a + b\nEnd\nresult = call sum with 3 and 4')
JS_TRY_CATCH = to_js('Try\n  Print 42\nCatch e\n  Print e\nEnd')
JS_MATCH = to_js('x = 2\nMatch x\n  When 1\n    Print "one"\n  When 2\n    Print "two"\nEnd')
JS_ENUM = to_js("Enum Color as RED, GREEN, BLUE")
JS_CLASS = to_js('Class Dog\n  name = "Rex"\n  Function speak\n    Print "Woof"\n  End\nEnd')
NODE_OUT = to_node('Print "Hello"')


JS_CASES = [
    ("print_string", lambda: 'console.log("Hello")' in to_js('Print "Hello"')),
    ("print_expr", lambda: "console.log((5 + 3))" in to_js("Print 5 + 3")),
    ("say_alias", lambda: 'console.log("hi")' in to_js('Say "hi"')),
    ("var_decl_let", lambda: "let x = 10;" in to_js("x = 10")),
    ("var_decl_str", lambda: 'let name = "Alice";' in to_js('name = "Alice"')),
    ("var_assign", lambda: "x = 20;" in to_js("x = 10\nSet x to 20")),
    ("var_list", lambda: "let items = [1, 2, 3];" in to_js("items = [1, 2, 3]")),
    ("var_bool", lambda: "let flag = true;" in to_js("flag = true")),
    ("expr_add", lambda: "(5 + 3)" in to_js("Print 5 + 3")),
    ("expr_mul", lambda: "(6 * 7)" in to_js("Print 6 * 7")),
    ("expr_mod", lambda: "(10 % 3)" in to_js("Print 10 % 3")),
    ("expr_power", lambda: "Math.pow(2, 10)" in to_js("Print 2 ** 10") or "**" in to_js("Print 2 ** 10")),
    ("if_statement", lambda: "if (" in JS_IF and 'console.log("big")' in JS_IF),
    ("if_else", lambda: "} else {" in JS_IF_ELSE),
    ("while_loop", lambda: "while (" in to_js("While x < 10\n  x += 1\nEnd")),
    (
        "repeat_loop",
        lambda: "for (let _i" in to_js('Repeat 5 times\n  Print "hi"\nEnd')
        and "< 5;" in to_js('Repeat 5 times\n  Print "hi"\nEnd'),
    ),
    ("for_range", lambda: "for (let i = 1; i <= 10; i += 1)" in to_js("For i from 1 to 10\n  Print i\nEnd")),
    ("for_range_step", lambda: "i += 2" in to_js("For i from 0 to 10 step 2\n  Print i\nEnd")),
    ("for_range_neg_step", lambda: "i >= 1" in to_js("For i from 5 to 1 step -1\n  Print i\nEnd")),
    ("for_each", lambda: "for (let item of" in to_js("items = [1, 2, 3]\nFor each item in items\n  Print item\nEnd")),
    ("func_def", lambda: "function greet(name)" in JS_FN),
    ("func_body_print", lambda: "console.log" in JS_FN),
    ("func_return", lambda: "return (a + b)" in JS_FN_RETURN),
    ("func_call_user", lambda: "sum(3, 4)" in JS_CALL),
    ("builtin_length", lambda: ".length" in to_js('Print length("hello")')),
    ("builtin_sqrt", lambda: "Math.sqrt" in to_js("Print sqrt(16)")),
    ("builtin_floor", lambda: "Math.floor" in to_js("Print floor(3.7)")),
    ("builtin_ceil", lambda: "Math.ceil" in to_js("Print ceil(3.2)")),
    ("builtin_abs", lambda: "Math.abs" in to_js("Print absolute(-5)")),
    ("builtin_max", lambda: "Math.max" in to_js("Print max(3, 7)")),
    ("builtin_round", lambda: "Math.round" in to_js("Print round(3.5)")),
    ("builtin_type_of", lambda: "typeof" in to_js("Print type_of(42)")),
    ("builtin_to_int", lambda: "parseInt" in to_js('Print to_integer("42")')),
    ("builtin_to_text", lambda: "String(" in to_js("Print to_text(42)")),
    ("builtin_random", lambda: "Math.random()" in to_js("x = random()")),
    ("range_1arg", lambda: "Array.from({length: 5}" in to_js("x = range(5)")),
    ("range_2arg", lambda: "5 - 2" in to_js("x = range(2, 5)")),
    ("str_upper", lambda: ".toUpperCase()" in to_js('x = "hello"\nPrint x.upper()')),
    ("str_lower", lambda: ".toLowerCase()" in to_js('x = "HELLO"\nPrint x.lower()')),
    ("str_trim", lambda: ".trim()" in to_js('x = "  hi  "\nPrint x.trim()')),
    ("str_contains", lambda: ".includes(" in to_js('x = "hello"\nPrint x.contains("ell")')),
    ("str_replace", lambda: ".replace(" in to_js('x = "hello"\nPrint x.replace("l", "r")')),
    ("str_split", lambda: ".split(" in to_js('x = "a,b,c"\nPrint x.split(",")')),
    ("str_starts_with", lambda: ".startsWith(" in to_js('x = "hello"\nPrint x.starts_with("hel")')),
    ("str_ends_with", lambda: ".endsWith(" in to_js('x = "hello"\nPrint x.ends_with("lo")')),
    ("list_add", lambda: ".push(" in to_js("items = [1]\nitems.add(2)")),
    ("list_sort", lambda: ".sort(" in to_js("items = [3, 1, 2]\nitems.sort()")),
    ("list_reverse", lambda: ".reverse()" in to_js("items = [1, 2, 3]\nitems.reverse()")),
    ("aug_plus", lambda: "x += 5;" in to_js("x = 10\nx += 5")),
    ("aug_minus", lambda: "x -= 3;" in to_js("x = 10\nx -= 3")),
    ("aug_mul", lambda: "x *= 2;" in to_js("x = 10\nx *= 2")),
    ("aug_div", lambda: "x /= 2;" in to_js("x = 10\nx /= 2")),
    (
        "ternary",
        lambda: "?" in to_js('x = 10\ny = "big" if x > 5 otherwise "small"')
        and ":" in to_js('x = 10\ny = "big" if x > 5 otherwise "small"'),
    ),
    ("break_stmt", lambda: "break;" in to_js("While true\n  Break\nEnd")),
    ("continue_stmt", lambda: "continue;" in to_js("For i from 1 to 10\n  Continue\nEnd")),
    ("try_catch", lambda: "try {" in JS_TRY_CATCH and "catch" in JS_TRY_CATCH),
    ("throw_stmt", lambda: "throw" in to_js('Throw "oops"')),
    ("match_switch", lambda: "switch" in JS_MATCH or "if" in JS_MATCH),
    ("enum_object", lambda: "Color" in JS_ENUM and "RED" in JS_ENUM),
    ("class_def", lambda: "class Dog" in JS_CLASS or "Dog" in JS_CLASS),
    ("const_decl", lambda: "const" in to_js("Constant PI = 3.14")),
    (
        "assert_stmt",
        lambda: "assert" in to_js("Assert 1 == 1").lower()
        or "throw" in to_js("Assert 1 == 1").lower()
        or "if" in to_js("Assert 1 == 1"),
    ),
    ("node_has_header", lambda: "Node.js target" in NODE_OUT),
    ("node_has_console", lambda: 'console.log("Hello")' in NODE_OUT),
    ("lambda_expr", lambda: "=>" in to_js("double = lambda x -> x * 2")),
    (
        "import_comment",
        lambda: "// import:" in to_js('Import "helper.epl"')
        or "import" in to_js('Import "helper.epl"').lower(),
    ),
]


@pytest.mark.parametrize(("name", "check_fn"), JS_CASES, ids=[name for name, _ in JS_CASES])
def test_js_transpiler_cases(name, check_fn):
    assert check_fn(), name
