"""Structured regression tests extracted from the legacy production-gaps harness."""

from __future__ import annotations

import os
import sys
import unittest

import epl.ast_nodes as ast

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import EPLError
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser

_STACK_SOURCE = """Class Stack<T>
    items = []

    Function push takes item
        Add item to items
    End

    Function peek
        Return items[length(items) - 1]
    End
End

s = new Stack()
s.push(42)
Print to_text(s.peek())"""

_PAIR_SOURCE = """Class Pair<K, V>
    key = ""
    value = ""

    Function init takes k, v
        Set key to k
        Set value to v
    End

    Function get_key
        Return key
    End

    Function get_value
        Return value
    End
End

p = new Pair("name", "EPL")
Print p.get_key()
Print p.get_value()"""

_CONTAINER_SOURCE = """Class Container<T>
    data = 0

    Function init takes val
        Set data to val
    End
End

c = new Container(99)
Print to_text(c.data)"""


def _parse_program(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _run_epl(source: str, *, safe_mode: bool = False) -> list[str]:
    interpreter = Interpreter(safe_mode=safe_mode, debug_interactive=False)
    interpreter.execute(_parse_program(source))
    return interpreter.output_lines


class TestSafeModeGuards(unittest.TestCase):
    def assertProgramErrorContains(self, expected_substring: str, source: str, **kwargs) -> None:
        with self.assertRaises(EPLError) as exc_info:
            _run_epl(source, **kwargs)

        self.assertIn(expected_substring, str(exc_info.exception).lower())

    def test_safe_mode_blocks_python_bridge(self):
        self.assertProgramErrorContains(
            'not allowed in safe mode',
            'Use python "os"\nPrint "should not reach"',
            safe_mode=True,
        )

    def test_normal_mode_allows_python_bridge(self):
        self.assertEqual(_run_epl('Use python "math"\nPrint to_text(math.factorial(5))'), ['120'])

    def test_safe_mode_allows_basic_print(self):
        self.assertEqual(_run_epl('Print "hello safe"', safe_mode=True), ['hello safe'])

    def test_safe_mode_allows_basic_math(self):
        self.assertEqual(
            _run_epl('Create x equal to 5 + 3\nPrint to_text(x)', safe_mode=True),
            ['8'],
        )

    def test_safe_mode_allows_user_defined_functions(self):
        self.assertEqual(
            _run_epl(
                """Function add takes a and b
    Return a + b
End
result = call add with 3 and 4
Print to_text(result)""",
                safe_mode=True,
            ),
            ['7'],
        )

    def test_safe_mode_allows_list_operations(self):
        self.assertEqual(
            _run_epl(
                """items = []
Add 10 to items
Add 20 to items
Print to_text(length(items))""",
                safe_mode=True,
            ),
            ['2'],
        )

    def test_safe_mode_allows_string_operations(self):
        self.assertEqual(
            _run_epl(
                """Create s equal to "Hello World"
Print to_text(length(s))
Print uppercase(s)""",
                safe_mode=True,
            ),
            ['11', 'HELLO WORLD'],
        )


class TestGenericClassSupport(unittest.TestCase):
    def test_parser_recognizes_generic_class_syntax(self):
        program = _parse_program(_STACK_SOURCE)

        self.assertIsInstance(program.statements[0], ast.GenericClassDef)

    def test_generic_class_with_single_type_parameter_executes(self):
        self.assertEqual(_run_epl(_STACK_SOURCE), ['42'])

    def test_generic_class_with_multiple_type_parameters_executes(self):
        self.assertEqual(_run_epl(_PAIR_SOURCE), ['name', 'EPL'])

    def test_generic_class_initialization_preserves_instance_data(self):
        self.assertEqual(_run_epl(_CONTAINER_SOURCE), ['99'])
