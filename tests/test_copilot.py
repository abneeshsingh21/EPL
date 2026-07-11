"""Coverage for the offline EPL copilot (template code generator + analyzer).

The copilot is fully offline — regex pattern matching against a fixed template
table, then lex/parse/type-check. No network or API keys. `analyze_code`,
`generate_from_description`, `assist_request`, and `_convert_set_to_create` are
pure and hermetically testable; the web/interactive entry points are not
exercised here. `test_playground_assistant.py` covers `analyze_code`/`assist`
diagnostics — this module adds the generation-contract and matcher coverage.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.copilot import (
    _convert_set_to_create,
    analyze_code,
    assist_request,
    generate_from_description,
)
from epl.lexer import Lexer
from epl.parser import Parser


def _reparses(code):
    """The central contract: generated EPL must lex and parse."""
    try:
        Parser(Lexer(code).tokenize()).parse()
        return True
    except Exception:
        return False


# Prompts that hit a known template, and a substring each must contain.
GENERATE_CASES = [
    ('hello world', 'Hello, World!'),
    ('calculator with add subtract', 'function add takes a and b'),
    ('fibonacci 10', 'function fibonacci takes n'),
    ('reverse a string', 'function reverseString takes s'),
    ('fizzbuzz', 'FizzBuzz'),
]


@pytest.mark.parametrize(('prompt', 'needle'), GENERATE_CASES, ids=[p for p, _ in GENERATE_CASES])
def test_generate_matches_template(prompt, needle):
    assert needle in generate_from_description(prompt)


@pytest.mark.parametrize(
    'prompt', [p for p, _ in GENERATE_CASES] + ['quantum teleportation simulation']
)
def test_generated_code_reparses(prompt):
    # Every generated program — matched template or fallback — must be valid EPL.
    assert _reparses(generate_from_description(prompt))


def test_analyze_empty_input_is_clean():
    result = analyze_code('   ')
    assert result['ok'] is True
    assert result['syntax_ok'] is True
    assert result['statement_count'] == 0
    assert result['diagnostics'] == []


def test_analyze_flags_syntax_error():
    result = analyze_code('If True Then\n    Say "ok"\nElsee\n    Say "bad"\nEnd\n')
    assert result['syntax_ok'] is False
    assert any(d['level'] == 'error' for d in result['diagnostics'])


def test_analyze_does_not_execute_code():
    # A program that would loop/exit if run must still just be analyzed.
    result = analyze_code('While True\n    Say "spin"\nEnd\n')
    assert 'diagnostics' in result and 'statement_count' in result


def test_assist_generate_mode():
    result = assist_request('build a chatbot', mode='generate')
    assert result['mode'] == 'generate'
    assert result['syntax_ok'] is True
    assert _reparses(result['code'])


def test_assist_fix_mode_repairs_else():
    broken = 'If True Then\n    Say "A"\nElse\n    Say "B"\nEnd\n'
    result = assist_request('fix this', current_code=broken, mode='fix')
    assert result['mode'] == 'fix'
    assert 'Otherwise' in result['code']


def test_convert_set_to_create_initialization():
    code, notes = _convert_set_to_create('set counter to 0\n')
    assert 'Create counter = 0' in code
    assert len(notes) > 0


def test_convert_set_to_create_preserves_value_starting_with_to():
    # Only the first ' to ' delimits; a value like `to_integer(...)` is kept.
    code, _ = _convert_set_to_create('set guess to to_integer(guess)\n')
    assert 'Create guess = to_integer(guess)' in code
