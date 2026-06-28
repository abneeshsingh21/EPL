"""Compatibility tests for syntax forms used by modern templates and official packages."""

from __future__ import annotations

import unittest

from epl import ast_nodes as ast
from epl.lexer import Lexer
from epl.parser import Parser


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


class TestSyntaxCompatibility(unittest.TestCase):
    def test_comment_alias_parses(self):
        _parse('Comment "hello"\nSay "ok"\n')

    def test_bare_map_is_empty_map_literal(self):
        """`Map` with no `with` is the empty-map literal (no other way to write one)."""
        program = _parse('Create m equal to Map\n')
        decl = program.statements[0]
        self.assertIsInstance(decl.value, ast.DictLiteral)
        self.assertEqual(decl.value.pairs, [])

    def test_bare_map_in_argument_position(self):
        _parse('Create t equal to create_token(Map, "secret", 24)\n')

    def test_map_with_still_parses(self):
        program = _parse('Create m equal to Map with a = 1 and b = 2\n')
        self.assertEqual(len(program.statements[0].value.pairs), 2)

    def test_window_usable_as_identifier(self):
        """`window` (a GUI block keyword) works as a function/param name in context."""
        _parse('Function f takes numbers, window\n    Return window\nEnd\n')
        _parse('Create r equal to window([1, 2, 3], 3)\n')

    def test_constant_usable_as_function_name(self):
        """`constant` (the K-combinator) works as a function name."""
        _parse('Define Function constant Takes value\n    Return value\nEnd\n')

    def test_constant_declaration_still_works(self):
        program = _parse('Constant PI = 3.14\n')
        self.assertEqual(program.statements[0].name, 'PI')

    def test_add_to_subscript_target_parses(self):
        _parse('Add 5 to graph["a"]\n')

    def test_add_to_property_target_parses(self):
        _parse('Add 5 to obj.items\n')

    def test_function_with_alias_parses(self):
        _parse('Function greet with name\n    Return name\nEnd\n')

    def test_function_parenthesized_params_parse(self):
        _parse('Function add(a, b)\n    Return a + b\nEnd\n')

    def test_call_parenthesized_args_parse(self):
        _parse('Call greet("EPL")\n')

    def test_call_method_parenthesized_args_parse(self):
        _parse('Call user.render_card("EPL")\n')

    def test_call_module_parenthesized_args_parse(self):
        _parse('Call Web::render("home")\n')

    def test_page_store_list_alias_parses(self):
        program = _parse(
            'Create WebApp called todoApp\n'
            'Route "/" shows\n'
            '    Page "Home"\n'
            '        Say items from "tasks" delete "/delete"\n'
            '    End\n'
            'End\n'
        )

        route = next(node for node in program.statements if isinstance(node, ast.Route))
        page = next(stmt for stmt in route.body if isinstance(stmt, ast.PageDef))

        self.assertEqual(page.elements[0].tag, 'store_list')
        self.assertEqual(page.elements[0].attributes['collection'], 'tasks')
        self.assertEqual(page.elements[0].attributes['delete_action'], '/delete')

    def test_page_say_string_alias_parses_as_text(self):
        program = _parse(
            'Create WebApp called frontendApp\n'
            'Route "/" shows\n'
            '    Page "Landing"\n'
            '        Say "Creative UI"\n'
            '    End\n'
            'End\n'
        )

        route = next(node for node in program.statements if isinstance(node, ast.Route))
        page = next(stmt for stmt in route.body if isinstance(stmt, ast.PageDef))

        self.assertEqual(page.elements[0].tag, 'text')
        self.assertEqual(page.elements[0].content, 'Creative UI')


if __name__ == '__main__':
    unittest.main()
