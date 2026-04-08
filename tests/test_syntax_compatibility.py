"""Compatibility tests for syntax forms used by modern templates and official packages."""

from __future__ import annotations

import unittest

from epl.lexer import Lexer
from epl.parser import Parser


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


if __name__ == "__main__":
    unittest.main()
