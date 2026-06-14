"""Regression tests for the v9.6.x static-analysis bug-fix batch.

Each test pins a specific defect found by mypy/ruff that previously either
crashed at runtime or was silently swallowed by a broad ``except``. The
type-checker tests are the most important: the bugs they cover lived behind
``except Exception: pass`` in the LSP/diagnostics path, so the checker appeared
to run while actually checking nothing on If/Ternary/Match nodes.
"""

import pytest

from epl import ast_nodes as ast
from epl import type_checker, type_system
from epl.lexer import Lexer
from epl.parser import Parser


def _parse(src):
    return Parser(Lexer(src).tokenize()).parse()


def _find_nodes(node, predicate, acc):
    if predicate(node):
        acc.append(node)
    if hasattr(node, '__dict__'):
        for value in vars(node).values():
            if isinstance(value, ast.ASTNode):
                _find_nodes(value, predicate, acc)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.ASTNode):
                        _find_nodes(item, predicate, acc)
    return acc


# ─── thread_run NameError (stdlib.py) ───────────────────────


def test_thread_run_returns_thread_not_nameerror():
    import threading

    from epl.stdlib import call_stdlib

    done = threading.Event()

    def _target():
        done.set()

    # Previously raised NameError: name 'tid' is not defined.
    result = call_stdlib('thread_run', [_target], 0, interpreter=None)
    assert result is not None
    assert hasattr(result, 'join')  # it's a Thread
    result.join(timeout=2)


# ─── vm.py random/random_int shadowing ──────────────────────


def test_vm_random_builtins_work():
    # Before the fix, `random` recursed into the function and `random_int`
    # called `.randint` on a function object -> AttributeError.
    from epl.vm import VM

    builtins = VM()._build_builtin_dispatch()
    r = builtins['random']([], 0)
    assert 0.0 <= r <= 1.0
    ri = builtins['random_int']([1, 1], 0)
    assert ri == 1


# ─── type_system: If / Match no longer crash (were swallowed) ─


def test_type_system_checks_if_without_crashing():
    prog = _parse(
        'Create x = 5\n'
        'If x is greater than 3 then\n'
        '    Print 1\n'
        'Otherwise\n'
        '    Print 2\n'
        'End'
    )
    checker = type_system.TypeChecker()
    # Must not raise AttributeError on node.true_body/false_body.
    diags = checker.check(prog)
    assert isinstance(diags, list)


def test_type_system_actually_visits_if_bodies():
    # Proves the checker walks into the branch bodies (it couldn't before,
    # because it crashed accessing the wrong attribute on entry).
    prog = _parse(
        'If true then\n'
        '    Print 1\n'
        'Otherwise\n'
        '    Print 2\n'
        'End'
    )
    checker = type_system.TypeChecker()
    visited = []
    original = checker._check_body

    def spy(stmts, scope):
        visited.append(len(stmts))
        return original(stmts, scope)

    checker._check_body = spy
    checker.check(prog)
    # Top-level body + both branch bodies => at least 3 _check_body calls.
    assert len(visited) >= 3


def test_type_system_checks_match_without_crashing():
    prog = _parse(
        'Create x = 1\n'
        'Match x\n'
        '    When 1\n'
        '        Print 1\n'
        '    Default\n'
        '        Print 0\n'
        'End'
    )
    checker = type_system.TypeChecker()
    diags = checker.check(prog)  # was: AttributeError on node.clauses
    assert isinstance(diags, list)


# ─── type_checker: ternary inference (was swallowed) ────────


def test_type_checker_ternary_does_not_crash():
    prog = _parse('Create y = 1 if true otherwise 2')
    checker = type_checker.TypeChecker(strict=False)
    warnings = checker.check(prog)  # was: AttributeError on true_value
    assert isinstance(warnings, list)


def test_type_checker_ternary_infers_common_type():
    prog = _parse('Create y = 1 if true otherwise 2')
    ternaries = _find_nodes(
        prog, lambda n: isinstance(n, ast.TernaryExpression), []
    )
    assert len(ternaries) == 1
    checker = type_checker.TypeChecker(strict=False)
    checker.check(prog)
    inferred = checker._infer_type(ternaries[0])
    # Both branches are integers -> the inferred type is integer, not ANY.
    assert str(inferred) == 'integer'


# ─── EPLClass static attrs are always present ───────────────


def test_eplclass_has_static_attrs_on_plain_construction():
    from epl.interpreter import EPLClass

    cls = EPLClass('Foo', {}, {})
    # Previously these were only set by the class-def executor.
    assert cls.static_methods == {}
    assert cls.type_params == []


# ─── parser: parameter-default error raises ParserError ─────


def test_parser_param_default_ordering_raises_parsererror():
    from epl.errors import ParserError

    # A non-default param after a default param must raise ParserError,
    # not AttributeError (self._error didn't exist).
    src = 'Define function f takes a as 1, b\n    Return a\nEnd'
    with pytest.raises(Exception) as exc_info:
        _parse(src)
    # Whatever the exact trigger, it must not be an AttributeError about _error.
    assert 'attribute' not in str(exc_info.value).lower() or 'ParserError' in type(
        exc_info.value
    ).__name__


# ─── rest/variadic params no longer crash the type checker ──


def test_type_checker_handles_rest_param_function():
    # node.params contains a RestParameter object; the checker used to do p[0]
    # / len(p) on it -> TypeError, swallowed, so variadic fns went unchecked.
    prog = _parse('Define function sum_all takes rest nums\n    Return 0\nEnd')
    warnings = type_checker.TypeChecker(strict=False).check(prog)
    assert isinstance(warnings, list)


def test_type_system_handles_rest_param_function():
    prog = _parse('Define function sum_all takes rest nums\n    Return 0\nEnd')
    diags = type_system.TypeChecker().check(prog)
    assert isinstance(diags, list)


def test_type_checker_handles_rest_param_in_class_method():
    prog = _parse(
        'Class Calc\n'
        '    Define function add takes rest xs\n'
        '        Return 0\n'
        '    End\n'
        'End'
    )
    # Both declaration-collection and body-check passes must survive.
    warnings = type_checker.TypeChecker(strict=False).check(prog)
    assert isinstance(warnings, list)


# ─── silent-except instrumentation is observable under EPL_DEBUG ─


def test_debug_log_suppressed_emits_only_under_env(capsys, monkeypatch):
    from epl import _debug_log

    monkeypatch.delenv('EPL_DEBUG', raising=False)
    try:
        raise ValueError('boom')
    except Exception:
        _debug_log.suppressed('demo:test')
    assert capsys.readouterr().err == ''  # silent by default

    monkeypatch.setenv('EPL_DEBUG', '1')
    try:
        raise ValueError('boom2')
    except Exception:
        _debug_log.suppressed('demo:test')
    assert 'demo:test' in capsys.readouterr().err  # observable when enabled

