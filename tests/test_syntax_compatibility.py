"""Compatibility tests for syntax forms used by modern templates and official packages."""

from __future__ import annotations

import unittest

from epl.lexer import Lexer
from epl.parser import Parser
from epl import ast_nodes as ast


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


class TestSyntaxCompatibility(unittest.TestCase):
    def test_comment_alias_parses(self):
        _parse('Comment "hello"\nSay "ok"\n')

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

        self.assertEqual(page.elements[0].tag, "store_list")
        self.assertEqual(page.elements[0].attributes["collection"], "tasks")
        self.assertEqual(page.elements[0].attributes["delete_action"], "/delete")

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

        self.assertEqual(page.elements[0].tag, "text")
        self.assertEqual(page.elements[0].content, "Creative UI")


if __name__ == "__main__":
    unittest.main()
