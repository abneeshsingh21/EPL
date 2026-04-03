"""Pytest coverage for v0.5 parser/interpreter changes."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser


def parse(src):
    lexer = Lexer(src)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def test_store_statement_parses():
    statement = parse('Store form "task" in "tasks"').statements[0]
    assert statement.__class__.__name__ == "StoreStatement"
    assert statement.collection == "tasks"
    assert statement.field_name == "task"


def test_delete_statement_parses():
    statement = parse('Delete from "tasks" at 0').statements[0]
    assert statement.__class__.__name__ == "DeleteStatement"
    assert statement.collection == "tasks"


def test_fetch_statement_parses():
    statement = parse('Fetch "tasks"').statements[0]
    assert statement.__class__.__name__ == "FetchStatement"
    assert statement.collection == "tasks"


def test_redirect_statement_parses():
    statement = parse('Redirect to "/home"').statements[0]
    assert statement.__class__.__name__ == "SendResponse"
    assert statement.response_type == "redirect"


def test_new_statement_types_execute_without_crashing():
    interpreter = Interpreter()
    sources = [
        'Store form "task" in "tasks"',
        'Delete from "tasks" at 0',
        'Fetch "tasks"',
        'Redirect to "/home"',
    ]
    for source in sources:
        program = parse(source)
        interpreter.execute(program)


def test_todo_example_parses():
    with open("examples/todo.epl", encoding="utf-8") as handle:
        program = parse(handle.read())

    assert len(program.statements) > 0
    assert any(hasattr(statement, "app_name") or hasattr(statement, "path") for statement in program.statements)
