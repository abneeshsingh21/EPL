"""Structured regression coverage for the remaining high-signal production-gap contracts."""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.package_manager import _get_builtin_source
from epl.parser import Parser

_FLOAT_CAPTURE_SOURCE = """pi = 3.14
double_pi = lambda -> pi * 2
Print to_text(double_pi())"""

_TRY_CATCH_FINALLY_SOURCE = """Try
    Throw "something went wrong"
Catch error
    Print error
Finally
    Print "cleanup"
End"""

_TRY_SUCCESS_FINALLY_SOURCE = """Try
    Print "no error"
Catch error
    Print "caught"
Finally
    Print "finally"
End"""


HAS_LLVM = importlib.util.find_spec('llvmlite') is not None

_LLVM_SMOKE_SOURCE = """Create x equal to 42
Print to_text(x)"""


def _parse_program(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def _run_epl(source: str) -> list[str]:
    interpreter = Interpreter(debug_interactive=False)
    interpreter.execute(_parse_program(source))
    return interpreter.output_lines


def _builtin_source(name: str) -> str:
    source = _get_builtin_source(name)
    if not source:
        raise AssertionError(f'Expected bundled source for {name}')
    return source


class TestInterpreterEdgeContracts(unittest.TestCase):
    def test_lambda_closure_captures_float_value(self):
        self.assertEqual(_run_epl(_FLOAT_CAPTURE_SOURCE), ['6.28'])

    def test_try_catch_finally_reports_error_then_cleanup(self):
        output = _run_epl(_TRY_CATCH_FINALLY_SOURCE)

        self.assertGreaterEqual(len(output), 2)
        self.assertIn('something went wrong', output[0].lower())
        self.assertIn('runtime error', output[0].lower())
        self.assertEqual(output[-1], 'cleanup')

    def test_try_catch_finally_skips_catch_when_no_error(self):
        self.assertEqual(_run_epl(_TRY_SUCCESS_FINALLY_SOURCE), ['no error', 'finally'])


@unittest.skipUnless(HAS_LLVM, 'llvmlite not available')
class TestCompilerContracts(unittest.TestCase):
    def test_compiler_sets_nonempty_module_data_layout(self):
        from epl.compiler import Compiler

        compiler = Compiler(opt_level=3)
        compiler.compile(_parse_program(_LLVM_SMOKE_SOURCE))

        self.assertTrue(compiler.module.data_layout)
        self.assertIn('target datalayout = "', str(compiler.module))

    def test_compiler_o3_emits_nonempty_object_bytes(self):
        from epl.compiler import Compiler

        compiler = Compiler(opt_level=3)
        compiler.compile(_parse_program(_LLVM_SMOKE_SOURCE))

        obj = compiler.compile_to_object()

        self.assertIsInstance(obj, (bytes, bytearray))
        self.assertGreater(len(obj), 0)


class TestBuiltinPackageSourceContracts(unittest.TestCase):
    def test_epl_db_source_uses_parameterized_insert_helpers(self):
        source = _builtin_source('epl-db')

        self.assertIn('InsertParams', source)
        self.assertIn('ExecuteParams', source)

    def test_epl_db_source_uses_parameter_placeholders(self):
        source = _builtin_source('epl-db')

        self.assertIn('?', source)
        self.assertIn('ExecuteParams(db, sql, params)', source)

    def test_epl_db_select_where_requires_params(self):
        source = _builtin_source('epl-db')

        self.assertIn('SelectWhere(db, table, condition, params)', source)

    def test_epl_auth_source_uses_base64_token_encoding(self):
        source = _builtin_source('epl-auth')

        self.assertIn('base64', source)
        self.assertIn('urlsafe_b64encode', source)

    def test_epl_auth_source_decodes_base64_tokens(self):
        source = _builtin_source('epl-auth')

        self.assertIn('urlsafe_b64decode', source)

    def test_epl_auth_source_uses_integer_timestamp(self):
        source = _builtin_source('epl-auth')

        self.assertIn('int(time::time())', source)
