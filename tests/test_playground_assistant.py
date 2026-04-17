"""Regression coverage for the playground assistant and syntax-aware copilot."""

from epl.copilot import analyze_code, assist_request
from epl.lexer import Lexer
from epl.parser import Parser
from epl.playground import _PLAYGROUND_HTML, _assist_playground, _get_syntax_reference


def _assert_parses(source: str) -> None:
    Parser(Lexer(source).tokenize()).parse()


def test_syntax_reference_exposes_authoritative_sections():
    payload = _get_syntax_reference()
    section_ids = {section["id"] for section in payload["sections"]}

    assert "Authoritative EPL syntax reference" in payload["text"]
    assert {"variables", "functions", "web"} <= section_ids


def test_analyze_code_reports_parser_diagnostics():
    analysis = analyze_code('If True Then\n    Say "ok"\nElse\n    Say "bad"\nEnd\n')

    assert analysis["syntax_ok"] is False
    assert analysis["diagnostics"]
    assert any(diag["level"] == "error" for diag in analysis["diagnostics"])


def test_assist_request_generates_parseable_chatbot_starter():
    result = assist_request("build a chatbot api assistant", mode="generate")

    assert result["mode"] == "generate"
    assert result["syntax_ok"] is True
    assert 'Route "/api/chat" responds with' in result["code"]
    assert any(section["id"] == "web" for section in result["syntax_sections"])
    _assert_parses(result["code"])


def test_assist_request_repairs_common_else_syntax():
    broken = 'If True Then\n    Say "A"\nElse\n    Say "B"\nEnd\n'

    result = assist_request("fix this code", current_code=broken, mode="fix")

    assert result["mode"] == "fix"
    assert result["syntax_ok"] is True
    assert "Otherwise" in result["code"]
    _assert_parses(result["code"])


def test_playground_assistant_uses_syntax_aware_generation():
    result = _assist_playground("creative frontend landing page", mode="generate")

    assert result["syntax_ok"] is True
    assert "Create WebApp called" in result["code"]
    assert result["syntax_sections"]
    _assert_parses(result["code"])


def test_playground_html_exposes_assistant_ui():
    assert "/api/assist" in _PLAYGROUND_HTML
    assert "Real EPL Syntax" in _PLAYGROUND_HTML
    assert "Apply To Editor" in _PLAYGROUND_HTML

