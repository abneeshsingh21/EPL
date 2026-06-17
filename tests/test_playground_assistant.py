"""Regression coverage for the playground assistant and syntax-aware copilot."""

import re
from pathlib import Path

from epl.copilot import _convert_set_to_create, analyze_code, assist_request
from epl.lexer import Lexer
from epl.parser import Parser
from epl.playground import (
    _PLAYGROUND_HTML,
    _assist_playground,
    _get_syntax_reference,
    _safe_error,
)
from epl.syntax_reference import get_syntax_sections


def _assert_parses(source: str) -> None:
    Parser(Lexer(source).tokenize()).parse()


def test_syntax_reference_exposes_authoritative_sections():
    payload = _get_syntax_reference()
    section_ids = {section['id'] for section in payload['sections']}

    assert 'Authoritative EPL syntax reference' in payload['text']
    assert {'variables', 'functions', 'web'} <= section_ids


def test_syntax_reference_examples_are_parseable():
    for section in get_syntax_sections():
        for example in section['examples']:
            _assert_parses(example)


def test_analyze_code_reports_parser_diagnostics():
    analysis = analyze_code('If True Then\n    Say "ok"\nElsee\n    Say "bad"\nEnd\n')

    assert analysis['syntax_ok'] is False
    assert analysis['diagnostics']
    assert any(diag['level'] == 'error' for diag in analysis['diagnostics'])


def test_assist_request_generates_parseable_chatbot_starter():
    result = assist_request('build a chatbot api assistant', mode='generate')

    assert result['mode'] == 'generate'
    assert result['syntax_ok'] is True
    assert 'Route "/api/chat" responds with' in result['code']
    assert any(section['id'] == 'web' for section in result['syntax_sections'])
    _assert_parses(result['code'])


def test_assist_request_repairs_common_else_syntax():
    broken = 'If True Then\n    Say "A"\nElse\n    Say "B"\nEnd\n'

    result = assist_request('fix this code', current_code=broken, mode='fix')

    assert result['mode'] == 'fix'
    assert result['syntax_ok'] is True
    assert 'Otherwise' in result['code']
    _assert_parses(result['code'])


def test_convert_set_to_create_rewrites_initialization():
    src = 'set counter to 0\nrepeat 3 times\n    set counter to counter + 1\nend\n'
    converted, notes = _convert_set_to_create(src)

    assert 'Create counter = 0' in converted
    assert 'Create counter = counter + 1' in converted
    assert not re.search(r'^\s*set\b', converted, re.IGNORECASE | re.MULTILINE)
    assert notes  # a human-readable repair note is recorded


def test_convert_set_to_create_preserves_value_starting_with_to():
    # The value `to_integer(guess)` must survive — only the first ` to ` delimits.
    converted, _ = _convert_set_to_create('set guess to to_integer(guess)\n')
    assert 'Create guess = to_integer(guess)' in converted


def test_generated_loop_code_defines_variables_with_create():
    # Regression: the assistant used to emit `set X to` which crashes at runtime
    # with a NameError because EPL's `set` only reassigns existing variables.
    result = assist_request('loops counting with a counter', mode='generate')

    assert result['syntax_ok'] is True
    assert not re.search(r'^\s*set\b', result['code'], re.IGNORECASE | re.MULTILINE)
    _assert_parses(result['code'])


def test_safe_error_explains_interactive_input():
    message = _safe_error(EOFError('EOF when reading a line'))
    assert 'interactive input' in message
    assert message != 'Internal error'


def test_playground_assistant_uses_syntax_aware_generation():
    result = _assist_playground('creative frontend landing page', mode='generate')

    assert result['syntax_ok'] is True
    assert 'Create WebApp called' in result['code']
    assert result['syntax_sections']
    _assert_parses(result['code'])


def test_playground_html_exposes_assistant_ui():
    assert '/api/assist' in _PLAYGROUND_HTML
    assert 'EPL syntax' in _PLAYGROUND_HTML
    assert 'Apply to editor' in _PLAYGROUND_HTML
    assert 'syntaxGuide' in _PLAYGROUND_HTML


def test_docs_playground_routes_only_to_explicit_ai_providers():
    html = Path('docs/playground.html').read_text(encoding='utf-8')

    assert 'value="groq"' in html
    assert 'value="gemini"' in html
    assert 'requestGroqAssistant' in html
    assert 'requestGeminiAssistant' in html
    assert 'requestProxyAssistant' in html
    assert 'text.pollinations.ai' not in html


def test_docs_playground_matches_current_runtime_contract():
    html = Path('docs/playground.html').read_text(encoding='utf-8')

    assert 'v7.4.4' not in html
    assert 'epl.type_system' not in html
    assert 'mode: "epl"' in html


def test_docs_landing_page_advertises_current_playground_version():
    html = Path('docs/index.html').read_text(encoding='utf-8')

    assert (
        'EPL v7.7.0 IS LIVE!' in html
        or 'EPL v7.8.0 IS LIVE!' in html
        or 'EPL v7.5.2 IS LIVE!' in html
    )
    assert 'EPL v7.4.4 IS LIVE!' not in html
