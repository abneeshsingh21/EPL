"""
Tests for the EPL JavaScript/TypeScript Bridge (v2)

Tests cover:
  1. Parser — Use javascript/typescript parsing
  2. AST — UseJSStatement node creation
  3. Tokens — JAVASCRIPT keyword token
  4. Bridge Serialization — Round-trip EPL ↔ JSON
  5. JS Transpiler — ESM/CJS emission
  6. Error Explainer — JS-specific diagnostics
  7. Integration — Real Node.js bridge operations
  8. JSModule — Class behavior
"""

import os
import re
import shutil
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl import ast_nodes as ast
from epl.tokens import KEYWORDS, TokenType


# ═══════════════════════════════════════════════════════════
#  1. Parser Tests
# ═══════════════════════════════════════════════════════════


class TestParserJS(unittest.TestCase):
    """Test that Use javascript/typescript statements are parsed correctly."""

    def _parse(self, source: str):
        from epl.lexer import Lexer
        from epl.parser import Parser

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()

    def test_use_javascript_basic(self):
        prog = self._parse('Use javascript "path"\n')
        self.assertEqual(len(prog.statements), 1)
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.UseJSStatement)
        self.assertEqual(stmt.library, 'path')
        self.assertEqual(stmt.alias, 'path')
        self.assertFalse(stmt.is_typescript)

    def test_use_javascript_with_alias(self):
        prog = self._parse('Use javascript "axios" as http\n')
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.UseJSStatement)
        self.assertEqual(stmt.library, 'axios')
        self.assertEqual(stmt.alias, 'http')

    def test_use_typescript_basic(self):
        prog = self._parse('Use typescript "lodash"\n')
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.UseJSStatement)
        self.assertEqual(stmt.library, 'lodash')
        self.assertTrue(stmt.is_typescript)

    def test_use_javascript_scoped_package(self):
        prog = self._parse('Use javascript "@scope/my-lib"\n')
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.UseJSStatement)
        self.assertEqual(stmt.library, '@scope/my-lib')
        self.assertEqual(stmt.alias, 'my_lib')

    def test_use_python_backward_compat(self):
        """Ensure Use python still works correctly."""
        prog = self._parse('Use python "os"\n')
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.UseStatement)
        self.assertEqual(stmt.library, 'os')

    def test_use_epl_import_backward_compat(self):
        """Ensure Use 'file.epl' still works correctly."""
        prog = self._parse('Use "utils.epl"\n')
        stmt = prog.statements[0]
        self.assertIsInstance(stmt, ast.ImportStatement)

    def test_use_javascript_auto_alias_dash(self):
        """Dashes in package names are converted to underscores in auto-alias."""
        prog = self._parse('Use javascript "my-package"\n')
        stmt = prog.statements[0]
        self.assertEqual(stmt.alias, 'my_package')


# ═══════════════════════════════════════════════════════════
#  2. AST Node Tests
# ═══════════════════════════════════════════════════════════


class TestASTNode(unittest.TestCase):
    def test_use_js_statement_creation(self):
        node = ast.UseJSStatement('axios', 'http', False, 5)
        self.assertEqual(node.library, 'axios')
        self.assertEqual(node.alias, 'http')
        self.assertFalse(node.is_typescript)
        self.assertEqual(node.line, 5)

    def test_use_js_statement_typescript_flag(self):
        node = ast.UseJSStatement('lodash', 'lodash', True, 10)
        self.assertTrue(node.is_typescript)

    def test_use_js_statement_defaults(self):
        node = ast.UseJSStatement('path')
        self.assertIsNone(node.alias)
        self.assertFalse(node.is_typescript)
        self.assertEqual(node.line, 0)


# ═══════════════════════════════════════════════════════════
#  3. Token Tests
# ═══════════════════════════════════════════════════════════


class TestTokens(unittest.TestCase):
    def test_javascript_keyword_exists(self):
        self.assertIn('javascript', KEYWORDS)
        self.assertEqual(KEYWORDS['javascript'], TokenType.JAVASCRIPT)

    def test_javascript_token_type_exists(self):
        self.assertIsNotNone(TokenType.JAVASCRIPT)

    def test_typescript_not_keyword(self):
        """TypeScript should NOT be a keyword — handled as an identifier by the parser."""
        self.assertNotIn('typescript', KEYWORDS)


# ═══════════════════════════════════════════════════════════
#  4. Bridge Serialization Tests
# ═══════════════════════════════════════════════════════════


class TestBridgeSerialization(unittest.TestCase):
    """Test the NodeBridge serialize/deserialize round-trip."""

    def setUp(self):
        from epl.js_bridge import NodeBridge
        self.bridge = NodeBridge()  # Don't start the process

    def test_serialize_none(self):
        result = self.bridge._serialize_arg(None)
        self.assertEqual(result, {'type': 'null', 'value': None})

    def test_serialize_bool(self):
        result = self.bridge._serialize_arg(True)
        self.assertEqual(result, {'type': 'boolean', 'value': True})

    def test_serialize_int(self):
        result = self.bridge._serialize_arg(42)
        self.assertEqual(result, {'type': 'number', 'value': 42})

    def test_serialize_float(self):
        result = self.bridge._serialize_arg(3.14)
        self.assertEqual(result, {'type': 'number', 'value': 3.14})

    def test_serialize_string(self):
        result = self.bridge._serialize_arg('hello')
        self.assertEqual(result, {'type': 'string', 'value': 'hello'})

    def test_serialize_list(self):
        result = self.bridge._serialize_arg([1, 'two', True])
        self.assertEqual(result['type'], 'array')
        self.assertEqual(len(result['value']), 3)

    def test_deserialize_handle(self):
        from epl.js_bridge import JSModuleHandle
        result = self.bridge._deserialize_result({
            'type': 'handle',
            'handle': 'h42',
            'typeName': 'Function',
        })
        self.assertIsInstance(result, JSModuleHandle)
        self.assertEqual(result.handle, 'h42')
        self.assertEqual(result.type_name, 'Function')


# ═══════════════════════════════════════════════════════════
#  5. JS Transpiler Tests
# ═══════════════════════════════════════════════════════════


class TestJSTranspiler(unittest.TestCase):
    def _transpile(self, source, module_format='cjs', target='node'):
        from epl.js_transpiler import JSTranspiler
        from epl.lexer import Lexer
        from epl.parser import Parser

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        transpiler = JSTranspiler(target=target, module_format=module_format)
        return transpiler.transpile(program)

    def test_use_js_cjs(self):
        js_code = self._transpile('Use javascript "path"\n', 'cjs')
        self.assertIn('require("path")', js_code)
        self.assertIn('const path', js_code)

    def test_use_js_esm(self):
        js_code = self._transpile('Use javascript "axios" as http\n', 'esm', 'browser')
        self.assertIn('import * as http from "axios"', js_code)

    def test_use_js_node_esm(self):
        js_code = self._transpile('Use javascript "lodash"\n', 'cjs')
        self.assertIn('const lodash = require("lodash")', js_code)


# ═══════════════════════════════════════════════════════════
#  6. Error Explainer Tests
# ═══════════════════════════════════════════════════════════


class TestErrorExplainer(unittest.TestCase):
    def _make_error(self, message):
        """Create a simple mock error object for the explainer."""
        class MockError:
            pass
        err = MockError()
        err.message = message
        err.line = 1
        return err

    def test_node_not_installed_pattern(self):
        from epl.error_explainer import explain
        err = self._make_error('Node.js is not installed or not found in PATH.')
        result = explain(err)
        self.assertIn('Node.js', result.what_went_wrong)

    def test_module_not_found_pattern(self):
        from epl.error_explainer import explain
        err = self._make_error('Cannot load module "fancy-lib": MODULE_NOT_FOUND')
        result = explain(err)
        self.assertIn('fancy-lib', result.what_went_wrong)

    def test_pipe_broken_pattern(self):
        from epl.error_explainer import explain
        err = self._make_error('JS bridge pipe broken: connection reset')
        result = explain(err)
        self.assertIn('crashed', result.what_went_wrong)


# ═══════════════════════════════════════════════════════════
#  7. Integration Tests (require Node.js)
# ═══════════════════════════════════════════════════════════


@unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
class TestIntegration(unittest.TestCase):
    """Integration tests that require a running Node.js process."""

    def setUp(self):
        from epl.js_bridge import NodeBridge
        NodeBridge.reset()

    def tearDown(self):
        from epl.js_bridge import NodeBridge
        NodeBridge.reset()

    def test_require_path_module(self):
        from epl.js_bridge import NodeBridge
        bridge = NodeBridge.get_instance()
        handle = bridge.require('path')
        self.assertIsInstance(handle, str)
        self.assertTrue(handle.startswith('h'))

    def test_call_path_join(self):
        from epl.js_bridge import NodeBridge
        bridge = NodeBridge.get_instance()
        handle = bridge.require('path')
        result = bridge.call(handle, 'join', ['/home', 'user', 'file.txt'])
        self.assertIsInstance(result, str)
        self.assertIn('file.txt', result)

    def test_call_path_basename(self):
        from epl.js_bridge import NodeBridge
        bridge = NodeBridge.get_instance()
        handle = bridge.require('path')
        result = bridge.call(handle, 'basename', ['/home/user/file.txt'])
        self.assertEqual(result, 'file.txt')

    def test_get_property(self):
        from epl.js_bridge import NodeBridge
        bridge = NodeBridge.get_instance()
        handle = bridge.require('path')
        sep = bridge.get_prop(handle, 'sep')
        self.assertIsInstance(sep, str)
        self.assertIn(sep, ['/', '\\'])

    def test_require_os_module(self):
        from epl.js_bridge import NodeBridge
        bridge = NodeBridge.get_instance()
        handle = bridge.require('os')
        result = bridge.call(handle, 'platform', [])
        self.assertIsInstance(result, str)
        self.assertIn(result, ['win32', 'linux', 'darwin', 'freebsd', 'sunos'])

    def test_error_invalid_module(self):
        from epl.js_bridge import NodeBridge, NodeBridgeError
        bridge = NodeBridge.get_instance()
        with self.assertRaises(NodeBridgeError):
            bridge.require('this_module_definitely_does_not_exist_xyz123')


# ═══════════════════════════════════════════════════════════
#  8. JSModule Class Tests
# ═══════════════════════════════════════════════════════════


class TestJSModuleClass(unittest.TestCase):
    def test_jsmodule_repr(self):
        from epl.interpreter import JSModule
        mod = JSModule(None, 'h1', 'lodash')
        self.assertEqual(repr(mod), '<js module lodash>')

    def test_jsmodule_name(self):
        from epl.interpreter import JSModule
        mod = JSModule(None, 'h2', 'path')
        self.assertEqual(mod.name, 'path')
        self.assertEqual(mod.handle, 'h2')


if __name__ == '__main__':
    unittest.main(verbosity=2)
