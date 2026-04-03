"""Pytest coverage for strict type-system hardening."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.type_system import TypeChecker


def check(code, strict=True):
    tokens = Lexer(code).tokenize()
    tree = Parser(tokens).parse()
    tc = TypeChecker(strict=strict)
    return tc.check(tree)


def test_return_type_mismatch_detected():
    code = 'Function add takes a and returns integer\n    return "hello"\nEnd Function'
    diags = check(code)
    assert any("Return type" in d.message and d.level == "error" for d in diags), diags


def test_unreachable_code_detected():
    code = 'Function foo\n    return 10\n    print 20\nEnd Function'
    diags = check(code)
    assert any("Unreachable" in d.message for d in diags), diags


def test_too_many_arguments_detected():
    code = 'Function greet takes name\n    print name\nEnd Function\ngreet("Alice", "extra")'
    diags = check(code)
    assert any("Too many arguments" in d.message for d in diags), diags


def test_undeclared_variable_detected_in_strict_mode():
    code = "print unknownVar"
    diags = check(code)
    assert any("before declaration" in d.message for d in diags), diags


def test_assignment_type_mismatch_detected():
    code = 'create integer x as 10\nset x to "hello"'
    diags = check(code)
    assert any("Cannot assign" in d.message for d in diags), diags


def test_valid_code_has_no_errors():
    code = "create x as 10\nset x to 20\nprint x"
    diags = check(code)
    errors = [d for d in diags if d.level == "error"]
    assert errors == [], errors


def test_type_diagnostic_uses_level_field():
    diags = check("print unknownVar")
    for diagnostic in diags:
        assert hasattr(diagnostic, "level")
        assert diagnostic.level in ("error", "warning", "info")
