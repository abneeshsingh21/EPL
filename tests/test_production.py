"""
EPL Production Features Test Suite
Tests for new production features: rest params, operator overloading,
generators, modules, stdlib, builtins, string methods, and more.
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
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name} (unexpected error type: {type(e).__name__}: {e})")
            return False
test_error.__test__ = False


def run_suite():
    print("=" * 60)
    print("  EPL Production Features Test Suite")
    print("=" * 60)

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

    # ═══════════════════════════════════════════════════════
    #  1. REST PARAMETERS (varargs)
    # ═══════════════════════════════════════════════════════
    print("\n--- Rest Parameters (Varargs) ---")

    track(test("Rest param: sum variadic args",
        'Function sum_all takes rest numbers\n'
        '    Create total = 0\n'
        '    For each n in numbers\n'
        '        Set total to total + n\n'
        '    End for\n'
        '    Return total\n'
        'End\n'
        'Print Call sum_all with 1 and 2 and 3.',
        ["6"]))

    track(test("Rest param: single arg",
        'Function wrap takes rest items\n'
        '    Return items\n'
        'End\n'
        'Print Call wrap with 42.',
        ["[42]"]))

    track(test("Rest param: no extra args gives empty list",
        'Function echo takes rest items\n'
        '    Print Call length with items.\n'
        'End\n'
        'Call echo.',
        ["0"]))

    track(test("Rest param: with regular params",
        'Function greet takes greeting and rest names\n'
        '    For each name in names\n'
        '        Print greeting + " " + name\n'
        '    End for\n'
        'End\n'
        'Call greet with "Hello" and "Alice" and "Bob".',
        ["Hello Alice", "Hello Bob"]))

    track(test("Rest param: regular + rest with one extra",
        'Function f takes a and rest others\n'
        '    Print a\n'
        '    Print Call length with others.\n'
        'End\n'
        'Call f with 10 and 20.',
        ["10", "1"]))

    track(test("Rest param: regular + rest with no extras",
        'Function f takes a and rest others\n'
        '    Print a\n'
        '    Print Call length with others.\n'
        'End\n'
        'Call f with 10.',
        ["10", "0"]))

    # ═══════════════════════════════════════════════════════
    #  2. OPERATOR OVERLOADING
    # ═══════════════════════════════════════════════════════
    print("\n--- Operator Overloading ---")

    track(test("Operator overload: __add__ on class",
        'Class Vector\n'
        '    x = 0\n'
        '    y = 0\n'
        '\n'
        '    Function __add__ takes other\n'
        '        Create result = new Vector\n'
        '        result.x = this.x + other.x\n'
        '        result.y = this.y + other.y\n'
        '        Return result\n'
        '    End\n'
        'End\n'
        '\n'
        'Create v1 = new Vector\n'
        'v1.x = 1\n'
        'v1.y = 2\n'
        'Create v2 = new Vector\n'
        'v2.x = 3\n'
        'v2.y = 4\n'
        'Create v3 = v1 + v2\n'
        'Print v3.x\n'
        'Print v3.y',
        ["4", "6"]))

    track(test("Operator overload: __sub__",
        'Class Num\n'
        '    val = 0\n'
        '\n'
        '    Function __sub__ takes other\n'
        '        Create result = new Num\n'
        '        result.val = this.val - other.val\n'
        '        Return result\n'
        '    End\n'
        'End\n'
        '\n'
        'Create n1 = new Num\n'
        'n1.val = 10\n'
        'Create n2 = new Num\n'
        'n2.val = 3\n'
        'Create c = n1 - n2\n'
        'Print c.val',
        ["7"]))

    track(test("Operator overload: __mul__",
        'Class Num\n'
        '    val = 0\n'
        '\n'
        '    Function __mul__ takes other\n'
        '        Create result = new Num\n'
        '        result.val = this.val * other.val\n'
        '        Return result\n'
        '    End\n'
        'End\n'
        '\n'
        'Create n1 = new Num\n'
        'n1.val = 5\n'
        'Create n2 = new Num\n'
        'n2.val = 4\n'
        'Create c = n1 * n2\n'
        'Print c.val',
        ["20"]))

    track(test("Operator overload: __eq__",
        'Class Num\n'
        '    val = 0\n'
        '\n'
        '    Function __eq__ takes other\n'
        '        Return this.val == other.val\n'
        '    End\n'
        'End\n'
        '\n'
        'Create n1 = new Num\n'
        'n1.val = 5\n'
        'Create n2 = new Num\n'
        'n2.val = 5\n'
        'If n1 == n2 then\n'
        '    Print "equal"\n'
        'End if.',
        ["equal"]))

    track(test("Operator overload: __str__ via Print",
        'Class Greeting\n'
        '    msg = "hi"\n'
        '\n'
        '    Function __str__ takes nothing\n'
        '        Return this.msg\n'
        '    End\n'
        'End\n'
        '\n'
        'Create g = new Greeting\n'
        'g.msg = "Hello World"\n'
        'Print g.',
        ["Hello World"]))

    # ═══════════════════════════════════════════════════════
    #  3. GENERATORS (Yield)
    # ═══════════════════════════════════════════════════════
    print("\n--- Generators ---")

    track(test("Generator: basic yield with for-each",
        'Function count_up takes limit\n'
        '    Create i = 0\n'
        '    While i < limit\n'
        '        Yields i\n'
        '        Set i to i + 1\n'
        '    End while\n'
        'End\n'
        '\n'
        'Create gen = Call count_up with 3\n'
        'For each x in gen\n'
        '    Print x\n'
        'End for.',
        ["0", "1", "2"]))

    track(test("Generator: yield strings",
        'Function greetings\n'
        '    Yields "hello"\n'
        '    Yields "world"\n'
        'End\n'
        '\n'
        'Create gen = Call greetings\n'
        'For each g in gen\n'
        '    Print g\n'
        'End for.',
        ["hello", "world"]))

    track(test("Generator: single yield",
        'Function once\n'
        '    Yields 42\n'
        'End\n'
        '\n'
        'Create gen = Call once\n'
        'For each v in gen\n'
        '    Print v\n'
        'End for.',
        ["42"]))

    track(test("Generator: empty (no yields executed)",
        'Function empty takes n\n'
        '    If n > 0 then\n'
        '        Yields 1\n'
        '    End if\n'
        'End\n'
        '\n'
        'Create gen = Call empty with 0\n'
        'Create count = 0\n'
        'For each v in gen\n'
        '    Set count to count + 1\n'
        'End for\n'
        'Print count.',
        ["0"]))

    # ═══════════════════════════════════════════════════════
    #  4. FOR-EACH WITH GENERATORS
    # ═══════════════════════════════════════════════════════
    print("\n--- For-each with Generators ---")

    track(test("For-each generator: range-like",
        'Function my_range takes n\n'
        '    Create i = 0\n'
        '    While i < n\n'
        '        Yields i\n'
        '        Set i to i + 1\n'
        '    End while\n'
        'End\n'
        '\n'
        'For each x in Call my_range with 4\n'
        '    Print x\n'
        'End for.',
        ["0", "1", "2", "3"]))

    track(test("For-each generator: inline call",
        'Function doubles takes n\n'
        '    Create i = 1\n'
        '    While i <= n\n'
        '        Yields i * 2\n'
        '        Set i to i + 1\n'
        '    End while\n'
        'End\n'
        '\n'
        'For each val in Call doubles with 3\n'
        '    Print val\n'
        'End for.',
        ["2", "4", "6"]))

    # ═══════════════════════════════════════════════════════
    #  5. TYPE CHECKING FOR GENERATORS
    # ═══════════════════════════════════════════════════════
    print("\n--- Type Checking ---")

    track(test("typeof generator is 'generator'",
        'Function gen_func\n'
        '    Yields 1\n'
        'End\n'
        '\n'
        'Create g = Call gen_func\n'
        'Print Call typeof with g.',
        ["generator"]))

    track(test("typeof integer",
        'Print Call typeof with 42.',
        ["integer"]))

    track(test("typeof text",
        'Print Call typeof with "hello".',
        ["text"]))

    track(test("typeof list",
        'Create list named items equal to [1, 2, 3].\n'
        'Print Call typeof with items.',
        ["list"]))

    track(test("typeof boolean",
        'Print Call typeof with true.',
        ["boolean"]))

    # ═══════════════════════════════════════════════════════
    #  6. STDLIB HARDENING
    # ═══════════════════════════════════════════════════════
    print("\n--- Stdlib Functions ---")

    track(test("hash_md5 produces 32-char hex",
        'Create h = Call hash_md5 with "hello".\n'
        'Print Call length with h.',
        ["32"]))

    # ═══════════════════════════════════════════════════════
    #  7. VM / INTERPRETER BUILTINS
    # ═══════════════════════════════════════════════════════
    print("\n--- Builtins ---")

    track(test("to_boolean with 1",
        'Print Call to_boolean with 1.',
        ["true"]))

    track(test("to_boolean with 0",
        'Print Call to_boolean with 0.',
        ["false"]))

    track(test("to_boolean with empty string",
        'Print Call to_boolean with "".',
        ["false"]))

    track(test("to_boolean with non-empty string",
        'Print Call to_boolean with "yes".',
        ["true"]))

    track(test("to_integer conversion",
        'Print Call to_integer with "123".',
        ["123"]))

    track(test("to_text conversion",
        'Print Call to_text with 42.',
        ["42"]))

    track(test("to_decimal conversion",
        'Print Call to_decimal with "3.14".',
        ["3.14"]))

    track(test("length of string",
        'Print Call length with "hello".',
        ["5"]))

    track(test("length of list",
        'Create list named items equal to [10, 20, 30].\n'
        'Print Call length with items.',
        ["3"]))

    # ═══════════════════════════════════════════════════════
    #  8. STRING METHODS
    # ═══════════════════════════════════════════════════════
    print("\n--- String Methods ---")

    track(test("uppercase builtin",
        'Print Call uppercase with "hello".',
        ["HELLO"]))

    track(test("lowercase builtin",
        'Print Call lowercase with "WORLD".',
        ["world"]))

    track(test("uppercase mixed input",
        'Print Call uppercase with "Hello World".',
        ["HELLO WORLD"]))

    track(test("lowercase mixed input",
        'Print Call lowercase with "Hello World".',
        ["hello world"]))

    # ═══════════════════════════════════════════════════════
    #  9. MODULE / IMPORT TESTS
    # ═══════════════════════════════════════════════════════
    print("\n--- Modules ---")

    track(test("Module with function",
        'Module Math\n'
        '    Function square takes x\n'
        '        Return x * x\n'
        '    End\n'
        '    Export square\n'
        'End\n'
        'Print Math::square(5)',
        ["25"]))

    track(test("Module with multiple functions",
        'Module StringUtils\n'
        '    Function exclaim takes s\n'
        '        Return s + "!"\n'
        '    End\n'
        '    Function question takes s\n'
        '        Return s + "?"\n'
        '    End\n'
        '    Export exclaim\n'
        '    Export question\n'
        'End\n'
        'Print StringUtils::exclaim("Hello")\n'
        'Print StringUtils::question("Really")',
        ["Hello!", "Really?"]))

    track(test("Module with variable",
        'Module Config\n'
        '    Create version = "1.0"\n'
        'End\n'
        'Print Config::version.',
        ["1.0"]))

    # ═══════════════════════════════════════════════════════
    #  10. ADDITIONAL ROBUSTNESS TESTS
    # ═══════════════════════════════════════════════════════
    print("\n--- Additional Robustness ---")

    track(test("Math builtins: sqrt",
        'Print Call sqrt with 16.',
        ["4.0"]))

    track(test("Math builtins: power",
        'Print Call power with 2 and 10.',
        ["1024"]))

    track(test("Math builtins: floor",
        'Print Call floor with 3.7.',
        ["3"]))

    track(test("Math builtins: ceil",
        'Print Call ceil with 3.2.',
        ["4"]))

    track(test("Math builtins: absolute",
        'Print Call absolute with -5.',
        ["5"]))

    track(test("Math builtins: round",
        'Print Call round with 3.6.',
        ["4"]))

    track(test("List operations: append and iterate",
        'Create list named nums equal to [].\n'
        'Add 1 to nums.\n'
        'Add 2 to nums.\n'
        'Add 3 to nums.\n'
        'For each n in nums\n'
        '    Print n\n'
        'End for.',
        ["1", "2", "3"]))

    track(test("Sorted builtin",
        'Create list named nums equal to [3, 1, 2].\n'
        'Print Call sorted with nums.',
        ["[1, 2, 3]"]))

    track(test("Reversed builtin",
        'Create list named nums equal to [1, 2, 3].\n'
        'Print Call reversed with nums.',
        ["[3, 2, 1]"]))

    track(test("Random produces number in range",
        'Create r = Call random with 1 and 1.\n'
        'Print r.',
        ["1"]))

    track(test("is_integer type check",
        'Print Call is_integer with 42.',
        ["true"]))

    track(test("is_text type check",
        'Print Call is_text with "hello".',
        ["true"]))

    track(test("Nested function calls",
        'Function double takes x\n'
        '    Return x * 2\n'
        'End\n'
        'Function add_one takes x\n'
        '    Return x + 1\n'
        'End\n'
        'Print Call double with (Call add_one with 4).',
        ["10"]))

    track(test("Short function with default param",
        'Function greet takes name = "World"\n'
        '    Print "Hello " + name\n'
        'End\n'
        'Call greet.\n'
        'Call greet with "EPL".',
        ["Hello World", "Hello EPL"]))

    track(test("Class with init and properties",
        'Class Point\n'
        '    x = 0\n'
        '    y = 0\n'
        'End\n'
        '\n'
        'Create p = new Point\n'
        'p.x = 3\n'
        'p.y = 7\n'
        'Print p.x + p.y.',
        ["10"]))

    track(test("While loop with break",
        'Create i = 0\n'
        'While true\n'
        '    If i == 3 then\n'
        '        Break\n'
        '    End if\n'
        '    Print i\n'
        '    Set i to i + 1\n'
        'End while.',
        ["0", "1", "2"]))

    # ─── Summary ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  All tests passed!")
    else:
        print(f"  {failed} test(s) failed.")
    print("=" * 60)

    return failed == 0


def test_production_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Production suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
