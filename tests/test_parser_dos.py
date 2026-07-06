"""Parser denial-of-service regression tests (M1).

Deeply nested hostile input must produce a clean ParserError, never an
uncaught RecursionError that crashes the worker (playground / MCP / LSP).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import ParserError
from epl.lexer import Lexer
from epl.parser import Parser


@pytest.mark.parametrize('depth', [150, 300, 1000, 5000])
def test_deep_nesting_raises_clean_parser_error(depth):
    src = 'Print ' + '(' * depth + '1' + ')' * depth
    tokens = Lexer(src).tokenize()
    with pytest.raises(ParserError):
        Parser(tokens).parse()  # must NOT raise RecursionError


@pytest.mark.parametrize('depth', [300, 2000])
def test_recovery_path_also_guarded(depth):
    src = 'Print ' + '(' * depth + '1' + ')' * depth
    tokens = Lexer(src).tokenize()
    # parse_with_recovery must not crash; it returns collected errors.
    _program, errors = Parser(tokens).parse_with_recovery()
    assert errors, 'expected a nesting error, got none'


def test_moderate_nesting_still_parses():
    src = 'Print ' + '(' * 20 + '1' + ')' * 20
    tokens = Lexer(src).tokenize()
    # Should parse without error (well under MAX_DEPTH).
    Parser(tokens).parse()
