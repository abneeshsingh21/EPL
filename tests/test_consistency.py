"""Pytest coverage for interpreter/VM runtime parity contracts.

The suite tracks three buckets:
- cases that must match across both runtimes
- documented behavior divergences, recorded as strict xfails
- documented backend capability gaps, also recorded as strict xfails

An unexpected XPASS means the runtimes were brought back into parity and the case
should be promoted into the main parity bucket.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.errors import EPLError
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser
from epl.vm import compile_and_run


def _run_interpreter(source: str) -> tuple[str, object]:
    """Run a source snippet via the tree-walking interpreter."""
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        interpreter = Interpreter()
        interpreter.execute(program)
        return ('ok', interpreter.output_lines)
    except EPLError as exc:
        return ('error', str(exc))
    except Exception as exc:
        return ('crash', f'{type(exc).__name__}: {exc}')


def _run_vm(source: str) -> tuple[str, object]:
    """Run a source snippet via the bytecode VM."""
    try:
        result = compile_and_run(source)
        return ('ok', result.get('output', []))
    except EPLError as exc:
        return ('error', str(exc))
    except Exception as exc:
        return ('crash', f'{type(exc).__name__}: {exc}')


BACKEND_RUNNERS = {
    'interpreter': _run_interpreter,
    'vm': _run_vm,
}

PARITY_CASES = [
    ('integer arithmetic', 'Print 2 + 3\nPrint 10 - 4\nPrint 3 * 7\nPrint 10 / 2'),
    ('float arithmetic', 'Print 3.14 + 2.86\nPrint 10.0 / 3.0'),
    ('negative numbers', 'Print -5\nPrint -3 + 8\nPrint -2 * -3'),
    ('modulo', 'Print 10 % 3\nPrint 7 % 2'),
    ('power', 'Print 2 ** 10\nPrint 3 ** 3'),
    ('floor division', 'Print 7 // 2\nPrint 10 // 3'),
    ('mixed int/float', 'Print 5 + 3.0\nPrint 10 / 3.0'),
    ('operator precedence', 'Print 2 + 3 * 4\nPrint (2 + 3) * 4'),
    ('variable create and print', 'Create x equal to 42\nPrint x'),
    ('variable reassign', 'Create x equal to 10\nSet x to 20\nPrint x'),
    ('multiple variables', 'left = 1\nright = 2\ntotal = left + right\nPrint total'),
    (
        'augmented assign',
        'x = 10\nIncrease x by 5\nPrint x\nDecrease x by 3\nPrint x\nSet x to x * 2\nPrint x',
    ),
    ('string print', 'Print "hello world"'),
    ('string concatenation', 'greeting = "hello"\nsuffix = " world"\nPrint greeting + suffix'),
    ('string length', 'Print length("hello")'),
    ('string methods', 'Print uppercase("hello")\nPrint lowercase("HELLO")'),
    ('boolean values', 'Print true\nPrint false'),
    (
        'boolean logic',
        'Print true and true\nPrint true and false\nPrint false or true\nPrint not true',
    ),
    ('comparisons', 'Print 5 > 3\nPrint 3 > 5\nPrint 5 == 5\nPrint 5 != 3'),
    ('if true', 'If true\n  Print "yes"\nEnd'),
    ('if false', 'If false\n  Print "no"\nEnd'),
    ('if else', 'If false Then\n  Print "no"\nOtherwise\n  Print "yes"\nEnd'),
    (
        'if elif else',
        """x = 15
If x > 20 Then
  Print "big"
Otherwise If x > 10 Then
  Print "medium"
Otherwise
  Print "small"
End""",
    ),
    ('nested if', 'If true\n  If true\n    Print "nested"\n  End\nEnd'),
    ('while loop', 'Create i equal to 0\nWhile i < 5\n  Print i\n  Set i to i + 1\nEnd'),
    ('for each list', 'For each item in [10, 20, 30]\n  Print item\nEnd'),
    ('for each string', 'For each ch in "abc"\n  Print ch\nEnd'),
    (
        'loop with break',
        'Create i equal to 0\nWhile true\n  If i == 3\n    Break\n  End\n  Print i\n  Set i to i + 1\nEnd',
    ),
    ('simple function', 'Function greet()\n  Print "hello"\nEnd\nCall greet()'),
    ('function with params', 'Function add(a, b)\n  Return a + b\nEnd\nPrint add(3, 4)'),
    ('function with return', 'Function double(x)\n  Return x * 2\nEnd\nPrint double(5)'),
    ('list creation', 'items = [1, 2, 3]\nPrint items'),
    ('list length', 'Print length([1, 2, 3, 4])'),
    ('list append', 'items = [1, 2]\nitems.add(3)\nPrint items'),
    ('list remove', 'items = [1, 2, 3]\nitems.remove(2)\nPrint items'),
    ('empty list', 'items = []\nPrint length(items)'),
    (
        'map creation',
        'profile = Map with name = "Ada" and score = 42\nPrint profile.name\nPrint profile.score',
    ),
    ('to_text', 'Print to_text(42)\nPrint to_text(3.14)'),
    ('min max', 'Print min(3, 7)\nPrint max(3, 7)'),
    (
        'type of',
        'Print type_of(42)\nPrint type_of("hello")\nPrint type_of(true)\nPrint type_of(3.14)',
    ),
    ('to_number', 'Print to_number("42")\nPrint to_number("3.14")'),
    ('abs function', 'Print abs(-5)\nPrint abs(5)'),
    ('string contains', 'Print contains("hello world", "world")\nPrint contains("hello", "xyz")'),
    ('string trim', 'Print trim("  hello  ")'),
    ('string indexing', 'Create s equal to "abc"\nPrint s[0]\nPrint s[1]\nPrint s[2]'),
    (
        'loop with continue',
        'For each i in [1, 2, 3, 4, 5]\n  If i == 3\n    Continue\n  End\n  Print i\nEnd',
    ),
    (
        'recursive function',
        """Function factorial(n)
  If n <= 1
    Return 1
  End
  Return n * factorial(n - 1)
End
Print factorial(5)""",
    ),
    (
        'fibonacci',
        """Function fib(n)
  If n <= 1
    Return n
  End
  Return fib(n - 1) + fib(n - 2)
End
Print fib(0)
Print fib(1)
Print fib(5)
Print fib(10)""",
    ),
    (
        'fizzbuzz',
        """For each i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
  If i % 15 == 0 Then
    Print "FizzBuzz"
  Otherwise If i % 3 == 0 Then
    Print "Fizz"
  Otherwise If i % 5 == 0 Then
    Print "Buzz"
  Otherwise
    Print i
  End
End""",
    ),
    (
        'list comprehension style',
        """result = []
For each i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
  If i % 2 == 0 Then
    Add i to result
  End
End
Print result""",
    ),
    (
        'try catch',
        """Try
  Create x equal to 10 / 0
Catch error
  Print "caught error"
End""",
    ),
    (
        'simple class',
        """Class Dog
  name = "Rex"

  Function speak takes nothing
    Return "Woof!"
  End
End

Create myDog equal to new Dog()
Print myDog.name
Print myDog.speak()""",
    ),
    (
        'Set list index',
        'Create xs equal to [10, 20, 30]\nSet xs[1] to 99\nPrint xs[0]\nPrint xs[1]\nPrint xs[2]',
    ),
    (
        'Set map key',
        'Create m equal to Map with a = "1"\nSet m["b"] to "2"\nPrint m["a"]\nPrint m["b"]',
    ),
    (
        'Set map property',
        'Create p equal to Map with name = "old"\nSet p.name to "new"\nPrint p["name"]',
    ),
    (
        'Set index equals shorthand index',
        # Both spellings must reach the same node and produce the same result.
        'Create arr equal to [1, 2, 3]\narr[0] = 100\nSet arr[2] to 300\n'
        'Print arr[0]\nPrint arr[1]\nPrint arr[2]',
    ),
    (
        # `When 1 or 2 or 3` must match each alternative, not fold to `1`.
        'Match multi-value numeric When',
        'Create x equal to 2\nMatch x\n'
        '  When 1 or 2 or 3\n    Print "small"\n'
        '  When 4 or 5\n    Print "medium"\n'
        '  Otherwise\n    Print "other"\nEnd',
    ),
    (
        'Match multi-value string When',
        'Create d equal to "Wed"\nMatch d\n'
        '  When "Mon" or "Tue" or "Wed"\n    Print "weekday"\n'
        '  Otherwise\n    Print "weekend"\nEnd',
    ),
    (
        'Match falls through to Otherwise',
        'Create x equal to 99\nMatch x\n'
        '  When 1 or 2\n    Print "low"\n'
        '  Otherwise\n    Print "high"\nEnd',
    ),
    (
        # `Default` and `Otherwise` are interchangeable catch-alls.
        'Match Default keyword',
        'Create x equal to 7\nMatch x\n'
        '  When 1\n    Print "one"\n'
        '  Default\n    Print "other"\nEnd',
    ),
]

# All previously-documented VM divergences (continue, recursion, fizzbuzz,
# list-mutation, fibonacci) now pass parity in PARITY_CASES — v9.1.0 fix.

KNOWN_BACKEND_GAP_CASES: list = []


@pytest.fixture
def parity_runner():
    """Run the same EPL source through both supported runtime backends."""

    def _run(source: str) -> dict[str, tuple[str, object]]:
        return {
            backend_name: backend_runner(source)
            for backend_name, backend_runner in BACKEND_RUNNERS.items()
        }

    return _run


def _normalize_output(lines: object) -> list[str]:
    """Normalize output so numeric formatting differences do not hide parity."""
    normalized = []
    for line in lines:
        text = str(line).strip()
        try:
            value = float(text)
        except (TypeError, ValueError, OverflowError):
            normalized.append(text)
            continue
        if value.is_integer():
            normalized.append(str(int(value)))
        else:
            normalized.append(text)
    return normalized


def _format_result(result: tuple[str, object]) -> str:
    status, payload = result
    if status == 'ok':
        return f'{status}: {_normalize_output(payload)}'
    return f'{status}: {payload}'


def _assert_runtime_parity(name: str, results: dict[str, tuple[str, object]]) -> None:
    interpreter_result = results['interpreter']
    vm_result = results['vm']

    interpreter_status, interpreter_payload = interpreter_result
    vm_status, vm_payload = vm_result

    assert interpreter_status == vm_status, (
        f'{name}: status mismatch; '
        f'interpreter={_format_result(interpreter_result)}; '
        f'vm={_format_result(vm_result)}'
    )
    assert interpreter_status == 'ok', (
        f'{name}: expected both backends to complete successfully; '
        f'interpreter={_format_result(interpreter_result)}; '
        f'vm={_format_result(vm_result)}'
    )
    assert _normalize_output(interpreter_payload) == _normalize_output(vm_payload), (
        f'{name}: output mismatch; '
        f'interpreter={_format_result(interpreter_result)}; '
        f'vm={_format_result(vm_result)}'
    )


@pytest.mark.parametrize(('name', 'source'), PARITY_CASES, ids=[name for name, _ in PARITY_CASES])
def test_runtime_parity_cases(name: str, source: str, parity_runner) -> None:
    _assert_runtime_parity(name, parity_runner(source))


@pytest.mark.parametrize(('name', 'source'), KNOWN_BACKEND_GAP_CASES)
def test_runtime_parity_known_backend_gaps(name: str, source: str, parity_runner) -> None:
    _assert_runtime_parity(name, parity_runner(source))


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__]))
