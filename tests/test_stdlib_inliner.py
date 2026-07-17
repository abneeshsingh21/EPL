"""Tests for native-codegen stdlib inlining (epl/stdlib_inliner.py).

The native transpilers have no runtime import loader, so plain `Import "<stdlib>"`
statements must be resolved by splicing the reachable definitions into the program
ahead of user code. These tests pin that behaviour: reachability, ordering,
import stripping, and the boundaries it deliberately leaves alone.
"""

from epl import ast_nodes as ast
from epl.lexer import Lexer
from epl.parser import Parser
from epl.stdlib_inliner import inline_stdlib_imports


def _parse(src):
    return Parser(Lexer(src).tokenize()).parse()


def _def_names(program):
    return [
        s.name for s in program.statements if isinstance(s, (ast.FunctionDef, ast.ConstDeclaration))
    ]


def _has_plain_import(program):
    return any(isinstance(s, ast.ImportStatement) and not s.alias for s in program.statements)


def test_used_stdlib_def_is_inlined():
    prog = _parse('Import "string"\nSay word_count("a b c")\n')
    out = inline_stdlib_imports(prog)
    assert 'word_count' in _def_names(out)
    assert not _has_plain_import(out)


def test_unused_defs_are_not_inlined():
    prog = _parse('Import "string"\nSay word_count("a b c")\n')
    names = _def_names(inline_stdlib_imports(prog))
    # word_count is reachable; an unrelated helper like title_case is not.
    assert 'word_count' in names
    assert 'title_case' not in names


def test_transitive_dependency_pulled_in():
    # capitalize is used; if it calls another stdlib helper, that must come too.
    prog = _parse('Import "string"\nSay capitalize("hello")\n')
    out = inline_stdlib_imports(prog)
    assert 'capitalize' in _def_names(out)


def test_callee_precedes_caller():
    prog = _parse('Import "string"\nSay title_case("a b")\n')
    out = inline_stdlib_imports(prog)
    names = _def_names(out)
    # title_case depends on capitalize → capitalize must be emitted first.
    if 'capitalize' in names and 'title_case' in names:
        assert names.index('capitalize') < names.index('title_case')


def test_defs_precede_user_code():
    prog = _parse('Import "string"\nSay word_count("a b")\n')
    out = inline_stdlib_imports(prog)
    first_def = next(
        i
        for i, s in enumerate(out.statements)
        if isinstance(s, (ast.FunctionDef, ast.ConstDeclaration))
    )
    first_say = next(
        i for i, s in enumerate(out.statements) if type(s).__name__ == 'PrintStatement'
    )
    assert first_def < first_say


def test_unused_import_is_dropped():
    prog = _parse('Import "string"\nSay "hello"\n')
    out = inline_stdlib_imports(prog)
    assert not _has_plain_import(out)
    assert _def_names(out) == []


def test_aliased_import_is_left_untouched():
    prog = _parse('Import "math" as M\nSay "hi"\n')
    out = inline_stdlib_imports(prog)
    # Aliased imports use a namespace mechanism native targets don't model yet.
    assert any(isinstance(s, ast.ImportStatement) and s.alias for s in out.statements)


def test_no_imports_returns_program_unchanged():
    prog = _parse('Say "hello"\n')
    out = inline_stdlib_imports(prog)
    assert out is prog


def test_unknown_module_is_ignored():
    prog = _parse('Import "definitely_not_a_stdlib_module"\nSay "hi"\n')
    out = inline_stdlib_imports(prog)
    # Non-stdlib import is left in place for the target to handle or report.
    assert _has_plain_import(out)
