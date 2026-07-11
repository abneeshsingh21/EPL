"""Token-level coverage for the EPL lexer and token model.

The rest of the suite exercises the lexer only as a pipeline stage
(`Parser(Lexer(src).tokenize()).parse()`); this module asserts the token
*stream* directly — numeric/string decoding, keyword-vs-identifier
resolution, operator recognition, multi-word keyword merging, comment
skipping, and lexer errors.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.errors import LexerError
from epl.lexer import Lexer
from epl.tokens import Token, TokenType


def pairs(src):
    """(type-name, value) tuples for each token, EOF included."""
    return [(t.type.name, t.value) for t in Lexer(src).tokenize()]


# ── Token model ──────────────────────────────────────────
# `Token.__eq__` compares only (type, value); line/column are ignored.
TOKEN_MODEL_CASES = [
    (
        'eq_ignores_position',
        lambda: Token(TokenType.NUMBER, 42, 1, 1) == Token(TokenType.NUMBER, 42, 9, 9),
    ),
    ('neq_on_value', lambda: Token(TokenType.NUMBER, 42, 1, 1) != Token(TokenType.NUMBER, 7, 1, 1)),
    ('neq_on_type', lambda: Token(TokenType.NUMBER, 42, 1, 1) != Token(TokenType.STRING, 42, 1, 1)),
    ('neq_non_token', lambda: (Token(TokenType.NUMBER, 42, 1, 1) == 42) is False),
    (
        'repr_has_type_and_value',
        lambda: (
            'NUMBER' in repr(Token(TokenType.NUMBER, 42, 1, 1))
            and '42' in repr(Token(TokenType.NUMBER, 42, 1, 1))
        ),
    ),
]


# ── Tokenisation ─────────────────────────────────────────
TOKENIZE_CASES = [
    # A stream is always terminated by exactly one EOF whose value is None.
    ('eof_terminates', lambda: pairs('x')[-1] == ('EOF', None)),
    ('single_eof', lambda: [t.type for t in Lexer('x y z').tokenize()].count(TokenType.EOF) == 1),
    # NUMBER values are real Python numbers, not strings.
    ('int_value', lambda: pairs('42') == [('NUMBER', 42), ('EOF', None)]),
    ('int_is_int', lambda: isinstance(Lexer('42').tokenize()[0].value, int)),
    ('float_value', lambda: pairs('3.14') == [('NUMBER', 3.14), ('EOF', None)]),
    ('float_is_float', lambda: isinstance(Lexer('3.14').tokenize()[0].value, float)),
    ('hex_literal', lambda: Lexer('0xFF').tokenize()[0].value == 255),
    ('binary_literal', lambda: Lexer('0b101').tokenize()[0].value == 5),
    ('digit_separator', lambda: Lexer('1_000').tokenize()[0].value == 1000),
    # STRING value is the decoded content (escapes resolved, quotes stripped).
    ('string_decoded', lambda: Lexer('"hi\\nthere"').tokenize()[0].value == 'hi\nthere'),
    ('string_type', lambda: Lexer('"ok"').tokenize()[0].type == TokenType.STRING),
    # Keyword resolution is case-insensitive on `.type`, original case on `.value`.
    ('keyword_type', lambda: Lexer('Create x').tokenize()[0].type == TokenType.CREATE),
    ('keyword_preserves_case', lambda: Lexer('Create x').tokenize()[0].value == 'Create'),
    ('identifier_type', lambda: Lexer('Create foo').tokenize()[1].type == TokenType.IDENTIFIER),
    ('identifier_preserves_case', lambda: Lexer('Create Foo').tokenize()[1].value == 'Foo'),
    # Operators, including two-character forms.
    ('op_plus_assign', lambda: ('OP_PLUS_ASSIGN', '+=') in pairs('foo += 2')),
    ('op_power', lambda: ('OP_POWER', '**') in pairs('2 ** 3')),
    ('op_arrow', lambda: any(t == 'ARROW' for t, _ in pairs('lambda x -> x'))),
    # Multi-word keywords merge in a post-pass; merged value is space-joined.
    (
        'multiword_merge',
        lambda: ('IS_GREATER_THAN', 'is greater than') in pairs('x is greater than 3'),
    ),
    # NEWLINE is emitted between lines; its value is the escaped literal "\n".
    ('newline_emitted', lambda: any(t == 'NEWLINE' for t, _ in pairs('foo\nbar'))),
    ('newline_value', lambda: Lexer('foo\nbar').tokenize()[1].value == '\\n'),
    # Comments produce no token at all — in all three forms the lexer accepts:
    # `#`, `Note:`, and `Note "..."` (the last carries bundled-stdlib headers).
    (
        'hash_comment_no_token',
        lambda: (
            pairs('# just a comment\n42') == [('NEWLINE', '\\n'), ('NUMBER', 42), ('EOF', None)]
        ),
    ),
    (
        'note_colon_comment_no_token',
        lambda: pairs('Note: a comment\n42') == [('NEWLINE', '\\n'), ('NUMBER', 42), ('EOF', None)],
    ),
    (
        'note_string_comment_no_token',
        lambda: pairs('Note "a header"\n42') == [('NEWLINE', '\\n'), ('NUMBER', 42), ('EOF', None)],
    ),
    # Both `\n` and `\r\n` collapse to a single NEWLINE token.
    ('crlf_is_one_newline', lambda: any(t == 'NEWLINE' for t, _ in pairs('foo\r\nbar'))),
]


# ── Positions ────────────────────────────────────────────
POSITION_CASES = [
    ('line_is_one_based', lambda: Lexer('x').tokenize()[0].line == 1),
    ('column_is_one_based', lambda: Lexer('x').tokenize()[0].column == 1),
    ('column_advances', lambda: Lexer('x y').tokenize()[1].column == 3),
    (
        'line_advances',
        lambda: (
            [t for t in Lexer('x\ny').tokenize() if t.type == TokenType.IDENTIFIER][-1].line == 2
        ),
    ),
]


# ── Errors ───────────────────────────────────────────────
ERROR_SOURCES = ['"unterminated', '@', '!']


@pytest.mark.parametrize(
    ('name', 'check_fn'), TOKEN_MODEL_CASES, ids=[n for n, _ in TOKEN_MODEL_CASES]
)
def test_token_model(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), TOKENIZE_CASES, ids=[n for n, _ in TOKENIZE_CASES])
def test_tokenize(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), POSITION_CASES, ids=[n for n, _ in POSITION_CASES])
def test_positions(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize('src', ERROR_SOURCES)
def test_lexer_errors_are_loud(src):
    with pytest.raises(LexerError):
        Lexer(src).tokenize()


def test_empty_source_is_just_eof():
    assert pairs('') == [('EOF', None)]
