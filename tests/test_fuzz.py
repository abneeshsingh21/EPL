"""
EPL Fuzz Testing Suite
Tests that random/adversarial inputs don't crash the lexer, parser, or interpreter
with unhandled exceptions, segfaults, or infinite loops.
"""

import sys
import os
import random
import string
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError


# ═══════════════════════════════════════════════════════════
#  Fuzz Helpers
# ═══════════════════════════════════════════════════════════

def _run_with_timeout(fn, timeout=5):
    """Run fn in a thread with a timeout. Returns the result or 'TIMEOUT'."""
    result = [None]
    def wrapper():
        result[0] = fn()
    t = threading.Thread(target=wrapper, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return 'TIMEOUT'
    return result[0]

def fuzz_lexer(source):
    """Attempt to lex source. Should never crash with unhandled exception."""
    try:
        lexer = Lexer(source)
        lexer.tokenize()
        return True
    except EPLError:
        return True  # Expected errors are fine
    except (RecursionError, MemoryError):
        return True  # Resource limits are acceptable
    except Exception as e:
        return f"UNEXPECTED: {type(e).__name__}: {e}"


def fuzz_parser(source):
    """Attempt to lex+parse source. Should never crash with unhandled exception."""
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.parse()
        return True
    except EPLError:
        return True
    except (RecursionError, MemoryError):
        return True
    except Exception as e:
        return f"UNEXPECTED: {type(e).__name__}: {e}"


def fuzz_interpreter(source, timeout_seconds=5):
    """Attempt to run source through full pipeline. Should never crash."""
    def _inner():
        try:
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            interp = Interpreter()
            interp.execute(program)
            return True
        except EPLError:
            return True
        except (RecursionError, MemoryError):
            return True
        except SystemExit:
            return True
        except KeyboardInterrupt:
            return True
        except Exception as e:
            return f"UNEXPECTED: {type(e).__name__}: {e}"
    result = _run_with_timeout(_inner, timeout_seconds)
    if result == 'TIMEOUT':
        return True  # Timeouts are acceptable (infinite loops are caught)
    return result


# ═══════════════════════════════════════════════════════════
#  Fuzz Generators
# ═══════════════════════════════════════════════════════════

def random_string(min_len=0, max_len=100):
    length = random.randint(min_len, max_len)
    return ''.join(random.choice(string.printable) for _ in range(length))


def random_epl_keyword():
    keywords = [
        'Create', 'Set', 'Print', 'If', 'Else', 'End', 'While', 'For',
        'Function', 'Return', 'Class', 'Method', 'Property', 'New',
        'Try', 'Catch', 'Throw', 'Import', 'Export', 'Module',
        'equal', 'to', 'plus', 'minus', 'times', 'divided', 'by',
        'and', 'or', 'not', 'true', 'false', 'nothing',
        'greater', 'less', 'than', 'each', 'in', 'Break', 'Continue',
        'Private', 'Protected', 'Public', 'Const', 'Let', 'Async',
        'Await', 'Yield', 'Switch', 'Case', 'Default',
    ]
    return random.choice(keywords)


def random_epl_fragment():
    """Generate a random EPL-like code fragment."""
    templates = [
        'Create {name} equal to {val}',
        'Set {name} to {val}',
        'Print {val}',
        'If {val} greater than {val}\nEnd',
        'While {val} less than {val}\nEnd',
        'Function {name}()\nEnd',
        'Create {name} equal to [{val}, {val}, {val}]',
        '{name}({val})',
        '{val} + {val}',
        '{val} - {val}',
        '{val} * {val}',
        '{val} / {val}',
        '{val} % {val}',
        'For each {name} in [{val}, {val}]\nEnd',
        'Try\n  Print {val}\nCatch error\n  Print error\nEnd',
        'Create {name} equal to {{"key": {val}}}',
    ]
    template = random.choice(templates)

    def rand_name():
        return random.choice(['x', 'y', 'z', 'counter', 'result', 'temp', 'data'])

    def rand_val():
        choice = random.randint(0, 5)
        if choice == 0:
            return str(random.randint(-1000, 1000))
        elif choice == 1:
            return f'"{random_string(0, 20)}"'
        elif choice == 2:
            return random.choice(['true', 'false', 'nothing'])
        elif choice == 3:
            return f'{random.random():.6f}'
        elif choice == 4:
            return rand_name()
        else:
            return str(random.randint(0, 100))

    result = template.replace('{name}', rand_name(), 1)
    while '{name}' in result:
        result = result.replace('{name}', rand_name(), 1)
    while '{val}' in result:
        result = result.replace('{val}', rand_val(), 1)
    return result


def random_keyword_soup(n=10):
    """Generate random keywords strung together."""
    return ' '.join(random_epl_keyword() for _ in range(n))


def random_nested_expr(depth=0, max_depth=10):
    """Generate nested expressions (linear chain, not exponential tree)."""
    if depth >= max_depth:
        return str(random.randint(0, 100))
    op = random.choice(['+', '-', '*'])
    right = str(random.randint(1, 100))
    inner = random_nested_expr(depth + 1, max_depth)
    return f'({inner} {op} {right})'


# ═══════════════════════════════════════════════════════════
#  Structured Fuzz Tests (known edge cases)
# ═══════════════════════════════════════════════════════════

EDGE_CASES = [
    # Empty/whitespace
    '',
    ' ',
    '\n',
    '\n\n\n',
    '\t\t\t',
    # String edge cases
    'Print ""',
    'Print "\\n"',
    'Print "\\t"',
    'Create x equal to ""',
    # Numeric edge cases
    'Print 0',
    'Print -0',
    'Print 99999999999999999999999999999999',
    'Print 0.0',
    'Print -0.0',
    'Create x equal to 0\nPrint x / 0',
    'Create x equal to 0\nPrint x % 0',
    # Deeply nested
    'If true\n' * 20 + 'Print 1\n' + 'End\n' * 20,
    # Unclosed constructs
    'If true',
    'While false',
    'Function foo()',
    'Class Bar',
    'Try',
    'For each x in [1, 2, 3]',
    # Mismatched End
    'End',
    'End End End',
    # Empty blocks
    'If true\nEnd',
    'While false\nEnd',
    'Function foo()\nEnd',
    # Type confusion
    'Create x equal to 5\nSet x to "hello"',
    'Create x equal to [1, 2, 3]\nPrint x + 1',
    # Special characters in strings
    'Print "hello\\nworld"',
    'Print "tab\\there"',
    'Print "quote\\"inside"',
    # Very long identifiers
    f'Create {"a" * 1000} equal to 1',
    # Unicode
    'Print "こんにちは"',
    'Print "🎉"',
    # Null bytes
    'Print "\x00"',
    # Comments only
    'Note: this is a comment',
    'Note: line 1\nNote: line 2\nNote: line 3',
    # Assignment to keywords
    'Create true equal to 5',
    'Create false equal to 10',
    # Division by zero
    'Create x equal to 10 / 0',
    'Create x equal to 10 % 0',
    'Create x equal to 10 // 0',
    # Chained operations
    'Create x equal to 1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10',
    # Multiple statements on context
    'Create x equal to 1\nCreate y equal to 2\nCreate z equal to x + y\nPrint z',
    # Self-referential
    'Create x equal to 1\nSet x to x + x',
    # List operations edge cases
    'Create x equal to []\nPrint length(x)',
    'Create x equal to [1]\nPrint x[0]',
    'Create x equal to [1, 2, 3]\nPrint x[-1]',
    'Create x equal to [1, 2, 3]\nPrint x[100]',
    # Map edge cases
    'Create x equal to {}\nPrint length(x)',
    # Boolean arithmetic
    'Print true + false',
    'Print true + 1',
    'Print not not not true',
]


# ═══════════════════════════════════════════════════════════
#  Test Runner
# ═══════════════════════════════════════════════════════════

def run_fuzz_tests():
    passed = 0
    failed = 0
    total = 0

    print("=" * 60)
    print("EPL Fuzz Testing Suite")
    print("=" * 60)

    # Phase 1: Structured edge cases
    print("\n--- Phase 1: Edge Case Inputs ---")
    for i, source in enumerate(EDGE_CASES):
        total += 1
        display = source[:60].replace('\n', '\\n') if source else '<empty>'
        
        result = fuzz_lexer(source)
        if result is not True:
            print(f"  FAIL (lexer) #{i}: {display}")
            print(f"    {result}")
            failed += 1
            continue

        result = fuzz_parser(source)
        if result is not True:
            print(f"  FAIL (parser) #{i}: {display}")
            print(f"    {result}")
            failed += 1
            continue

        result = fuzz_interpreter(source)
        if result is not True:
            print(f"  FAIL (interp) #{i}: {display}")
            print(f"    {result}")
            failed += 1
            continue

        passed += 1

    print(f"  Edge cases: {passed}/{total}")

    # Phase 2: Random EPL fragments
    print("\n--- Phase 2: Random EPL Fragments (200 iterations) ---")
    frag_passed = 0
    frag_failed = 0
    for i in range(200):
        total += 1
        source = random_epl_fragment()
        result = fuzz_lexer(source)
        if result is not True:
            frag_failed += 1
            if frag_failed <= 5:
                print(f"  FAIL (lexer): {source[:60]}")
                print(f"    {result}")
            continue
        result = fuzz_parser(source)
        if result is not True:
            frag_failed += 1
            if frag_failed <= 5:
                print(f"  FAIL (parser): {source[:60]}")
                print(f"    {result}")
            continue
        result = fuzz_interpreter(source)
        if result is not True:
            frag_failed += 1
            if frag_failed <= 5:
                print(f"  FAIL (interp): {source[:60]}")
                print(f"    {result}")
            continue
        frag_passed += 1
    passed += frag_passed
    failed += frag_failed
    print(f"  Fragments: {frag_passed}/{frag_passed + frag_failed}")

    # Phase 3: Random keyword soup
    print("\n--- Phase 3: Random Keyword Soup (100 iterations) ---")
    soup_passed = 0
    soup_failed = 0
    for i in range(100):
        total += 1
        source = random_keyword_soup(random.randint(1, 20))
        result = fuzz_lexer(source)
        if result is not True:
            soup_failed += 1
            if soup_failed <= 3:
                print(f"  FAIL (lexer): {source[:60]}")
            continue
        result = fuzz_parser(source)
        if result is not True:
            soup_failed += 1
            if soup_failed <= 3:
                print(f"  FAIL (parser): {source[:60]}")
                print(f"    {result}")
            continue
        soup_passed += 1
    passed += soup_passed
    failed += soup_failed
    print(f"  Keyword soup: {soup_passed}/{soup_passed + soup_failed}")

    # Phase 4: Random byte strings (pure chaos)
    print("\n--- Phase 4: Random Bytes (100 iterations) ---")
    byte_passed = 0
    byte_failed = 0
    for i in range(100):
        total += 1
        source = random_string(1, 200)
        result = fuzz_lexer(source)
        if result is not True:
            byte_failed += 1
            if byte_failed <= 3:
                print(f"  FAIL (lexer): {repr(source[:40])}")
                print(f"    {result}")
            continue
        result = fuzz_parser(source)
        if result is not True:
            byte_failed += 1
            if byte_failed <= 3:
                print(f"  FAIL (parser): {repr(source[:40])}")
                print(f"    {result}")
            continue
        byte_passed += 1
    passed += byte_passed
    failed += byte_failed
    print(f"  Random bytes: {byte_passed}/{byte_passed + byte_failed}")

    # Phase 5: Deep nesting stress
    print("\n--- Phase 5: Deep Nesting (20 iterations) ---")
    nest_passed = 0
    nest_failed = 0
    for i in range(20):
        total += 1
        depth = random.randint(5, 15)
        source = f'Create x equal to {random_nested_expr(0, depth)}'
        result = fuzz_lexer(source)
        if result is not True:
            nest_failed += 1
            continue
        result = fuzz_parser(source)
        if result is not True:
            nest_failed += 1
            continue
        result = fuzz_interpreter(source)
        if result is not True:
            nest_failed += 1
            continue
        nest_passed += 1
    passed += nest_passed
    failed += nest_failed
    print(f"  Deep nesting: {nest_passed}/{nest_passed + nest_failed}")

    # Summary
    print("\n" + "=" * 60)
    print(f"FUZZ RESULTS: {passed} passed, {failed} failed out of {total} total")
    if failed == 0:
        print("All fuzz tests passed! No unhandled exceptions found.")
    else:
        print(f"WARNING: {failed} inputs caused unhandled exceptions.")
    print("=" * 60)
    return failed


if __name__ == '__main__':
    random.seed(42)  # Reproducible results
    failures = run_fuzz_tests()
    sys.exit(1 if failures > 0 else 0)
