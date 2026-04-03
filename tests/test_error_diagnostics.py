import pytest

from epl.errors import NameError as EPLNameError, set_source_context
from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser
from epl.vm import BytecodeCompiler, VM, VMError


def _parse(source: str):
    set_source_context(source, "<test>")
    return Parser(Lexer(source).tokenize()).parse()


def test_error_context_shows_two_lines_of_context():
    source = "\n".join([
        'Print "header"',
        'Function sample',
        '    Print missing',
        'End',
        'Print "footer"',
    ])
    set_source_context(source, "<test>")
    error = EPLNameError('Variable "missing" has not been created yet.', line=3, column=11)

    rendered = str(error)

    assert "1 |" in rendered
    assert "2 |" in rendered
    assert "3 |" in rendered
    assert "4 |" in rendered
    assert "5 |" in rendered
    assert "^" in rendered


def test_interpreter_runtime_error_includes_call_stack():
    source = "\n".join([
        "Function inner",
        "    Print missing",
        "End",
        "Function outer",
        "    call inner",
        "End",
        "call outer",
    ])
    program = _parse(source)

    with pytest.raises(EPLNameError) as exc_info:
        Interpreter().execute(program)

    rendered = str(exc_info.value)
    assert "Call stack:" in rendered
    assert "outer (line" in rendered
    assert "-> inner (line" in rendered


def test_vm_runtime_error_includes_call_stack():
    source = "\n".join([
        "Function inner takes n",
        "    Return 1 / 0",
        "End",
        "Function outer",
        "    Return call inner with 1",
        "End",
        "Print call outer",
    ])
    program = _parse(source)
    compiled = BytecodeCompiler().compile(program)

    with pytest.raises(VMError) as exc_info:
        VM().execute(compiled)

    rendered = str(exc_info.value)
    assert "Call stack:" in rendered
    assert "main (line" in rendered
    assert "outer (line" in rendered
    assert "-> inner (line" in rendered
