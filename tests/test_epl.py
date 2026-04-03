"""
EPL Test Suite
Tests for the EPL lexer, parser, and interpreter.
"""

import sys
import os
import subprocess

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError


def run_epl(source: str) -> list:
    """Run EPL source code and return captured output lines."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines


def test(name: str, source: str, expected: list):
    """Run a test case and report result."""
    try:
        output = run_epl(source)
        if output == expected:
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            return False
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {e}")
        return False
test.__test__ = False


def test_error(name: str, source: str, expected_error_substring: str):
    """Test that a specific error is raised."""
    try:
        run_epl(source)
        print(f"  FAIL: {name} (expected error but none raised)")
        return False
    except EPLError as e:
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected error containing: {expected_error_substring}")
            print(f"    Got: {e}")
            return False
    except Exception as e:
        print(f"  FAIL: {name} (unexpected error type: {type(e).__name__}: {e})")
        return False
test_error.__test__ = False


def run_suite():
    print("=" * 55)
    print("  EPL Test Suite v0.1")
    print("=" * 55)

    passed = 0
    failed = 0
    total = 0

    def track(result):
        nonlocal passed, failed, total
        total += 1
        if result:
            passed += 1
        else:
            failed += 1

    # ─── Print Tests ──────────────────────────────────────
    print("\n📝 Print Statements:")
    track(test("Hello World", 'Print "Hello, World!".', ["Hello, World!"]))
    track(test("Print number", 'Print 42.', ["42"]))
    track(test("Print decimal", 'Print 3.14.', ["3.14"]))
    track(test("Print boolean", 'Print true.', ["true"]))
    track(test("Print nothing", 'Print nothing.', ["nothing"]))

    # ─── Variable Tests ──────────────────────────────────
    print("\n📦 Variables:")
    track(test("Integer variable",
        'Create integer named x equal to 42.\nPrint x.',
        ["42"]))
    track(test("Text variable",
        'Create text named msg equal to "Hello".\nPrint msg.',
        ["Hello"]))
    track(test("Decimal variable",
        'Create decimal named pi equal to 3.14.\nPrint pi.',
        ["3.14"]))
    track(test("Boolean variable",
        'Create boolean named flag equal to true.\nPrint flag.',
        ["true"]))
    track(test("Type inference",
        'Create name equal to "EPL".\nPrint name.',
        ["EPL"]))
    track(test("Set variable",
        'Create integer named x equal to 1.\nSet x to 2.\nPrint x.',
        ["2"]))

    # ─── Arithmetic Tests ────────────────────────────────
    print("\n🔢 Arithmetic:")
    track(test("Addition", 'Print 5 + 3.', ["8"]))
    track(test("Subtraction", 'Print 10 - 4.', ["6"]))
    track(test("Multiplication", 'Print 6 * 7.', ["42"]))
    track(test("Division exact", 'Print 10 / 2.', ["5"]))
    track(test("Division decimal", 'Print 7 / 2.', ["3.5"]))
    track(test("Modulo", 'Print 10 % 3.', ["1"]))
    track(test("Precedence", 'Print 2 + 3 * 4.', ["14"]))
    track(test("Parentheses", 'Print (2 + 3) * 4.', ["20"]))
    track(test("Negative number", 'Print -5.', ["-5"]))
    track(test("String concat", 'Print "Hello" + " " + "World".', ["Hello World"]))
    track(test("String + number", 'Print "Age: " + 20.', ["Age: 20"]))

    # ─── Comparison Tests ────────────────────────────────
    print("\n⚖️ Comparisons:")
    track(test("Greater than (symbol)",
        'If 10 > 5 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Less than (symbol)",
        'If 3 < 8 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Equal to (symbol)",
        'If 5 == 5 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Not equal (symbol)",
        'If 5 != 3 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Greater than (English)",
        'Create integer named x equal to 10.\nIf x is greater than 5 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Less than (English)",
        'Create integer named x equal to 3.\nIf x is less than 8 then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("Equal to (English)",
        'Create integer named x equal to 5.\nIf x is equal to 5 then\n    Print "yes".\nEnd if.',
        ["yes"]))

    # ─── Control Flow Tests ──────────────────────────────
    print("\n🔀 Control Flow:")
    track(test("If-then",
        'If true then\n    Print "yes".\nEnd if.',
        ["yes"]))
    track(test("If-otherwise",
        'If false then\n    Print "yes".\nOtherwise\n    Print "no".\nEnd if.',
        ["no"]))
    track(test("Nested if",
        'Create integer named x equal to 85.\n'
        'If x > 90 then\n    Print "A".\n'
        'Otherwise\n    If x > 80 then\n        Print "B".\n    '
        'Otherwise\n        Print "C".\n    End if.\nEnd if.',
        ["B"]))

    # ─── Loop Tests ──────────────────────────────────────
    print("\n🔁 Loops:")
    track(test("Repeat loop",
        'Repeat 3 times\n    Print "hi".\nEnd repeat.',
        ["hi", "hi", "hi"]))
    track(test("While loop",
        'Create integer named i equal to 0.\n'
        'While i < 3\n    Print i.\n    Increase i by 1.\nEnd while.',
        ["0", "1", "2"]))
    track(test("For each loop",
        'Create list named items equal to [1, 2, 3].\n'
        'For each item in items\n    Print item.\nEnd for.',
        ["1", "2", "3"]))
    track(test("Increase/Decrease",
        'Create integer named x equal to 5.\n'
        'Increase x by 3.\nPrint x.\nDecrease x by 2.\nPrint x.',
        ["8", "6"]))

    # ─── Function Tests ──────────────────────────────────
    print("\n🔧 Functions:")
    track(test("Simple function",
        'Define a function named hello.\n    Print "Hi!".\nEnd function.\nCall hello.',
        ["Hi!"]))
    track(test("Function with params",
        'Define a function named greet that takes text name.\n'
        '    Print "Hello, " + name + "!".\nEnd function.\n'
        'Call greet with "EPL".',
        ["Hello, EPL!"]))
    track(test("Function with return",
        'Define a function named add that takes integer a and integer b and returns integer.\n'
        '    Return a + b.\nEnd function.\n'
        'Create integer named r equal to call add with 3 and 4.\nPrint r.',
        ["7"]))
    track(test("Recursive function",
        'Define a function named fact that takes integer n and returns integer.\n'
        '    If n <= 1 then\n        Return 1.\n    End if.\n'
        '    Return n * (call fact with n - 1).\nEnd function.\n'
        'Print call fact with 5.',
        ["120"]))

    # ─── Error Tests ─────────────────────────────────────
    print("\n🚨 Error Handling:")
    track(test_error("Undefined variable",
        'Print x.',
        'has not been created'))
    track(test_error("Division by zero",
        'Print 10 / 0.',
        'divide by zero'))
    track(test_error("Incomplete expression",
        'x = 5 +.',
        'expected'))
    track(test_error("Type mismatch on assign",
        'Create integer named x equal to 5.\nSet x to "hello".',
        'cannot assign'))

    # ─── Summary ─────────────────────────────────────────
    print("\n" + "=" * 55)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  🎉 All tests passed!")
    else:
        print(f"  ⚠️  {failed} test(s) failed.")
    print("=" * 55)

    return failed == 0


def test_core_epl_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"EPL core suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
