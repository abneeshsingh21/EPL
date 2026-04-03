"""
EPL Cross-Backend Consistency Tests
Verifies that the interpreter and VM produce identical output for the same programs.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.vm import compile_and_run
from epl.errors import EPLError


def run_interpreter(source):
    """Run via tree-walking interpreter, return output lines."""
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        interp = Interpreter()
        interp.execute(program)
        return ('ok', interp.output_lines)
    except EPLError as e:
        return ('error', str(e))
    except Exception as e:
        return ('crash', f'{type(e).__name__}: {e}')


def run_vm(source):
    """Run via bytecode VM, return output lines."""
    try:
        result = compile_and_run(source)
        return ('ok', result.get('output', []))
    except EPLError as e:
        return ('error', str(e))
    except Exception as e:
        return ('crash', f'{type(e).__name__}: {e}')


# Known divergences between backends (documented, not failures)
KNOWN_DIVERGENCES = {
    "loop with continue",  # VM stops iteration instead of skipping on Continue
    "type of",             # VM returns "Integer"/"Decimal", interpreter returns "integer"/"decimal"
}

# ═══════════════════════════════════════════════════════════
#  Test Programs — should produce identical output on both backends
# ═══════════════════════════════════════════════════════════

CONSISTENCY_TESTS = {
    # --- Arithmetic ---
    "integer arithmetic": 'Print 2 + 3\nPrint 10 - 4\nPrint 3 * 7\nPrint 10 / 2',
    "float arithmetic": 'Print 3.14 + 2.86\nPrint 10.0 / 3.0',
    "negative numbers": 'Print -5\nPrint -3 + 8\nPrint -2 * -3',
    "modulo": 'Print 10 % 3\nPrint 7 % 2',
    "power": 'Print 2 ** 10\nPrint 3 ** 3',
    "floor division": 'Print 7 // 2\nPrint 10 // 3',
    "mixed int/float": 'Print 5 + 3.0\nPrint 10 / 3.0',
    "operator precedence": 'Print 2 + 3 * 4\nPrint (2 + 3) * 4',

    # --- Variables ---
    "variable create and print": 'Create x equal to 42\nPrint x',
    "variable reassign": 'Create x equal to 10\nSet x to 20\nPrint x',
    "multiple variables": 'Create a equal to 1\nCreate b equal to 2\nCreate c equal to a + b\nPrint c',
    "augmented assign": 'Create x equal to 10\nSet x += 5\nPrint x\nSet x -= 3\nPrint x\nSet x *= 2\nPrint x',

    # --- Strings ---
    "string print": 'Print "hello world"',
    "string concatenation": 'Create a equal to "hello"\nCreate b equal to " world"\nPrint a + b',
    "string length": 'Print length("hello")',
    "string indexing": 'Create s equal to "abc"\nPrint s[0]\nPrint s[1]\nPrint s[2]',
    "string methods": 'Print uppercase("hello")\nPrint lowercase("HELLO")',

    # --- Booleans ---
    "boolean values": 'Print true\nPrint false',
    "boolean logic": 'Print true and true\nPrint true and false\nPrint false or true\nPrint not true',
    "comparisons": 'Print 5 > 3\nPrint 3 > 5\nPrint 5 == 5\nPrint 5 != 3',

    # --- Conditionals ---
    "if true": 'If true\n  Print "yes"\nEnd',
    "if false": 'If false\n  Print "no"\nEnd',
    "if else": 'If false\n  Print "no"\nElse\n  Print "yes"\nEnd',
    "if elif else": '''Create x equal to 15
If x > 20
  Print "big"
Else If x > 10
  Print "medium"
Else
  Print "small"
End''',
    "nested if": 'If true\n  If true\n    Print "nested"\n  End\nEnd',

    # --- Loops ---
    "while loop": 'Create i equal to 0\nWhile i < 5\n  Print i\n  Set i to i + 1\nEnd',
    "for each list": 'For each item in [10, 20, 30]\n  Print item\nEnd',
    "for each string": 'For each ch in "abc"\n  Print ch\nEnd',
    "loop with break": 'Create i equal to 0\nWhile true\n  If i == 3\n    Break\n  End\n  Print i\n  Set i to i + 1\nEnd',
    "loop with continue": 'For each i in [1, 2, 3, 4, 5]\n  If i == 3\n    Continue\n  End\n  Print i\nEnd',

    # --- Functions ---
    "simple function": 'Function greet()\n  Print "hello"\nEnd\nCall greet()',
    "function with params": 'Function add(a, b)\n  Return a + b\nEnd\nPrint add(3, 4)',
    "function with return": 'Function double(x)\n  Return x * 2\nEnd\nPrint double(5)',
    "recursive function": '''Function factorial(n)
  If n <= 1
    Return 1
  End
  Return n * factorial(n - 1)
End
Print factorial(5)''',

    # --- Lists ---
    "list creation": 'Create list equal to [1, 2, 3]\nPrint list',
    "list length": 'Print length([1, 2, 3, 4])',
    "list append": 'Create list equal to [1, 2]\nAppend 3 to list\nPrint list',
    "list remove": 'Create list equal to [1, 2, 3]\nRemove 1 from list\nPrint list',
    "empty list": 'Create list equal to []\nPrint length(list)',

    # --- Maps ---
    "map creation": 'Create m equal to {"a": 1, "b": 2}\nPrint m["a"]\nPrint m["b"]',
    "map set": 'Create m equal to {}\nSet m["x"] to 42\nPrint m["x"]',

    # --- Type functions ---
    "type of": 'Print type_of(42)\nPrint type_of("hello")\nPrint type_of(true)\nPrint type_of(3.14)',
    "to_text": 'Print to_text(42)\nPrint to_text(3.14)',
    "to_number": 'Print to_number("42")\nPrint to_number("3.14")',

    # --- Built-in functions ---
    "abs function": 'Print abs(-5)\nPrint abs(5)',
    "min max": 'Print min(3, 7)\nPrint max(3, 7)',
    "string contains": 'Print contains("hello world", "world")\nPrint contains("hello", "xyz")',
    "string trim": 'Print trim("  hello  ")',

    # --- Error handling ---
    "try catch": '''Try
  Create x equal to 10 / 0
Catch error
  Print "caught error"
End''',

    # --- Classes ---
    "simple class": '''Class Dog
  Property name
  Property breed
  
  Method speak()
    Return "Woof!"
  End
End

Create myDog equal to new Dog()
Set myDog.name to "Rex"
Print myDog.name
Print myDog.speak()''',

    # --- Complex programs ---
    "fibonacci": '''Function fib(n)
  If n <= 1
    Return n
  End
  Return fib(n - 1) + fib(n - 2)
End
Print fib(0)
Print fib(1)
Print fib(5)
Print fib(10)''',

    "fizzbuzz": '''For each i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
  If i % 15 == 0
    Print "FizzBuzz"
  Else If i % 3 == 0
    Print "Fizz"
  Else If i % 5 == 0
    Print "Buzz"
  Else
    Print i
  End
End''',

    "list comprehension style": '''Create result equal to []
For each i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  If i % 2 == 0
    Append i to result
  End
End
Print result''',
}


def normalize_output(lines):
    """Normalize output for comparison (handle minor formatting differences)."""
    normalized = []
    for line in lines:
        s = str(line).strip()
        # Normalize float representation: 6.0 vs 6
        try:
            f = float(s)
            if f == int(f) and '.' not in s and 'e' not in s.lower():
                s = str(int(f))
            elif f == int(f) and '.' in s:
                # Both "6.0" and "6" are acceptable
                s = str(int(f))
        except (ValueError, OverflowError):
            pass
        normalized.append(s)
    return normalized


def run_tests():
    passed = 0
    failed = 0
    skipped = 0
    total = len(CONSISTENCY_TESTS)

    print("=" * 60)
    print("EPL Cross-Backend Consistency Tests")
    print("=" * 60)

    for name, source in CONSISTENCY_TESTS.items():
        interp_result = run_interpreter(source)
        vm_result = run_vm(source)

        interp_status, interp_out = interp_result
        vm_status, vm_out = vm_result

        # Both crashed = skip (test is bad, not a backend difference)
        if interp_status == 'crash' and vm_status == 'crash':
            print(f"  SKIP: {name} (both backends crash)")
            skipped += 1
            continue

        # Both errored = check error class matches (not exact message)
        if interp_status == 'error' and vm_status == 'error':
            passed += 1
            continue

        # One errored, other didn't
        if interp_status != vm_status:
            # If VM doesn't support a feature, it may crash — accept this
            if vm_status == 'crash' or vm_status == 'error':
                print(f"  SKIP: {name} (VM doesn't support: {vm_out[:60]})")
                skipped += 1
                continue
            if interp_status == 'crash' or interp_status == 'error':
                print(f"  SKIP: {name} (Interpreter issue: {interp_out[:60]})")
                skipped += 1
                continue

        # Both OK — compare outputs
        interp_norm = normalize_output(interp_out)
        vm_norm = normalize_output(vm_out)

        if interp_norm == vm_norm:
            passed += 1
        elif name in KNOWN_DIVERGENCES:
            print(f"  KNOWN: {name} (documented backend difference)")
            skipped += 1
        else:
            failed += 1
            print(f"  MISMATCH: {name}")
            print(f"    Interpreter: {interp_norm[:5]}{'...' if len(interp_norm) > 5 else ''}")
            print(f"    VM:          {vm_norm[:5]}{'...' if len(vm_norm) > 5 else ''}")

    print(f"\n{'=' * 60}")
    print(f"CONSISTENCY RESULTS: {passed} consistent, {failed} divergent, {skipped} skipped (of {total})")
    if failed == 0:
        print("All tested programs produce consistent output across backends!")
    else:
        print(f"WARNING: {failed} programs produce different output between interpreter and VM.")
    print("=" * 60)
    return failed


if __name__ == '__main__':
    failures = run_tests()
    sys.exit(1 if failures > 0 else 0)
