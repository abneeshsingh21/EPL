"""Structured regression tests for interpreter resource-limit enforcement."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import EPLError
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser

_INFINITE_LOOP_SOURCE = """Create i equal to 0
While true
    Set i to i + 1
End"""

_SUM_SOURCE = """Create total equal to 0
For i from 1 to 10
    Set total to total + i
End
Print to_text(total)"""

_LARGE_OUTPUT_SOURCE = """For i from 1 to 200
    Print to_text(i)
End"""

_SMALL_OUTPUT_SOURCE = """For i from 1 to 5
    Print to_text(i)
End"""


def _parse_program(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def _run_epl(
    source: str,
    *,
    safe_mode: bool = False,
    max_instructions: int = 0,
    execution_timeout: float = 0,
    max_output_lines: int = 0,
    max_loop_iterations: int | None = None,
) -> list[str]:
    interpreter = Interpreter(
        safe_mode=safe_mode,
        max_instructions=max_instructions,
        execution_timeout=execution_timeout,
        max_output_lines=max_output_lines,
        debug_interactive=False,
    )
    if max_loop_iterations is not None:
        interpreter.MAX_LOOP_ITERATIONS = max_loop_iterations
    interpreter.execute(_parse_program(source))
    return interpreter.output_lines


class TestRuntimeLimits(unittest.TestCase):
    def assertProgramErrorContains(self, expected_substring: str, source: str, **kwargs) -> None:
        with self.assertRaises(EPLError) as exc_info:
            _run_epl(source, **kwargs)

        self.assertIn(expected_substring, str(exc_info.exception).lower())

    def test_instruction_limit_rejects_infinite_loop(self):
        self.assertProgramErrorContains(
            'execution limit exceeded',
            _INFINITE_LOOP_SOURCE,
            max_instructions=1000,
        )

    def test_instruction_limit_allows_bounded_program(self):
        self.assertEqual(_run_epl(_SUM_SOURCE, max_instructions=50_000), ['55'])

    def test_output_line_limit_rejects_excessive_output(self):
        self.assertProgramErrorContains(
            'output limit exceeded',
            _LARGE_OUTPUT_SOURCE,
            max_output_lines=50,
        )

    def test_output_line_limit_allows_small_output(self):
        self.assertEqual(
            _run_epl(_SMALL_OUTPUT_SOURCE, max_output_lines=100),
            ['1', '2', '3', '4', '5'],
        )

    def test_execution_timeout_rejects_nonterminating_program(self):
        with mock.patch('epl.interpreter._time.time', side_effect=[0.0] + [1.0] * 4096):
            self.assertProgramErrorContains(
                'execution timeout',
                _INFINITE_LOOP_SOURCE,
                execution_timeout=0.01,
            )

    def test_safe_mode_enables_default_instruction_and_output_caps(self):
        unrestricted = Interpreter(debug_interactive=False)
        self.assertEqual(unrestricted._max_instructions, 0)
        self.assertEqual(unrestricted._max_output_lines, 0)

        restricted = Interpreter(safe_mode=True, debug_interactive=False)
        self.assertEqual(restricted._max_instructions, restricted.MAX_INSTRUCTIONS)
        self.assertEqual(restricted._max_output_lines, restricted.MAX_OUTPUT_LINES)
        self.assertEqual(restricted._execution_timeout, restricted.EXECUTION_TIMEOUT)

    def test_safe_mode_infinite_loop_hits_loop_guard(self):
        self.assertProgramErrorContains(
            'maximum iterations',
            _INFINITE_LOOP_SOURCE,
            safe_mode=True,
            max_loop_iterations=128,
        )
