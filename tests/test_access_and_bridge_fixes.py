"""Regression tests for the access-node / bridge / dot-notation bug-fix batch.

Covers a code-audit report of four confirmed defects:

* #1 — the type checker did not visit the object of ``PropertyAccess`` /
  ``IndexAccess`` and had no case for ``MethodCall`` / ``SliceAccess`` (nor for
  ``FunctionCall`` arguments), so a variable used ONLY via ``.prop`` / ``[i]`` /
  ``.method()`` / ``[a:b]`` / ``f(x)`` was falsely reported as W002 "unused".
* #2 — hard keywords (``json``, ``text``, ``list``, ``create`` …) could not be
  used as member names after a dot, so ``resp.json()`` / ``element.text`` crashed.
* #3 — a hard keyword auto-aliased from ``Use python "json"`` could not be typed
  at expression start (``json.dumps(...)``), making the import unusable.
* #4 — ``wrap_python_result`` force-listified ANY non-string ``__iter__`` object,
  destroying rich objects (e.g. a ``requests.Response``, which streams its body)
  and stripping attributes like ``.status_code`` / ``.headers``.
* #5b — a self-referential redeclaration (``counter = counter + 1``, which
  reparses as ``VarDeclaration``) reset the ``used`` flag AFTER inferring the
  RHS, wiping the read and producing a false W002.
"""

import pytest
from epl.interpreter import EPLDict
from epl.lexer import Lexer
from epl.parser import Parser
from epl.python_bridge import PythonModule, wrap_python_result
from epl.type_checker import TypeChecker


def _codes(src):
    checker = TypeChecker()
    checker.check(Parser(Lexer(src).tokenize()).parse())
    return [getattr(w, 'code', None) for w in checker.warnings]


def _parses(src):
    Parser(Lexer(src).tokenize()).parse()
    return True


def _wrap(value):
    return wrap_python_result(value, epl_dict_type=EPLDict, python_module_type=PythonModule)


# ─── #1: type checker visits access-node objects ────────────


@pytest.mark.parametrize(
    'src',
    [
        'Create data = [10, 20, 30]\nCreate first = data[0]\nPrint first\n',  # IndexAccess
        'Create name = "hello world"\nCreate part = name[0:3]\nPrint part\n',  # SliceAccess
        'Create user = load_user()\nCreate s = user.status\nPrint s\n',  # PropertyAccess
        'Create items = [1, 2, 3]\nCreate n = items.count()\nPrint n\n',  # MethodCall
        'Create x = 5\nPrint some_unknown(x)\n',  # FunctionCall argument
    ],
)
def test_access_use_is_not_false_unused(src):
    assert 'W002' not in _codes(src)


def test_genuinely_unused_still_warns():
    # The fix must not silence real dead variables.
    assert 'W002' in _codes('Create dead = 5\nPrint 1\n')


# ─── #5b: self-referential redeclaration keeps read ─────────


def test_self_referential_accumulate_is_used():
    # `counter = counter + 1` reparses as a redeclaration; the RHS read counts.
    assert 'W002' not in _codes('Create counter = 0\ncounter = counter + 1\nPrint counter\n')
    assert 'W002' not in _codes('Create counter = 0\ncounter = counter + 1\n')


def test_fresh_redeclaration_without_read_still_warns():
    assert 'W002' in _codes('Create x = 5\nCreate x = 9\n')


# ─── #2: hard keywords as member names after a dot ──────────


@pytest.mark.parametrize(
    'src',
    [
        'Create r = [1, 2, 3]\nCreate d = r.json()\nPrint d\n',
        'Create r = [1, 2, 3]\nCreate d = r.text\nPrint d\n',
        'Create r = [1, 2, 3]\nCreate d = r.list()\nPrint d\n',
        'Create r = [1, 2, 3]\nCreate d = r.create()\nPrint d\n',
        'Create r = [1, 2, 3]\nr.json()\n',  # statement position
    ],
)
def test_hard_keyword_member_names_parse(src):
    assert _parses(src)


def test_soft_and_ident_member_names_still_parse():
    assert _parses('Create r = [1, 2, 3]\nCreate d = r.save()\nPrint d\n')
    assert _parses('Create r = [1, 2, 3]\nCreate d = r.map()\nPrint d\n')


def test_sentence_period_before_keyword_statement_still_parses():
    # The adjacency rule must NOT consume a sentence-ending period as dot access.
    assert _parses('Create total = 5\nPrint total\n')
    assert _parses('Send json myData\n')


# ─── #3: auto-aliased hard-keyword module usable at expr start ─


def test_hard_keyword_module_usable_at_expression_start():
    assert _parses('Use python "json"\nCreate s = json.dumps(5)\nPrint s\n')


# ─── #4: rich Python objects survive the bridge ─────────────


class _FakeResponse:
    """Stand-in for a requests.Response: iterable (streams body) yet attribute-rich."""

    status_code = 200
    headers = {'content-type': 'application/json'}

    def __iter__(self):
        return iter([b'chunk1', b'chunk2'])


def test_rich_iterable_object_is_not_flattened_to_list():
    wrapped = _wrap(_FakeResponse())
    assert isinstance(wrapped, PythonModule)
    assert wrapped.get_attr('status_code') == 200


@pytest.mark.parametrize(
    'value,expected',
    [
        (range(3), [0, 1, 2]),
        (frozenset({1, 2, 3}), [1, 2, 3]),
        (iter([7, 8, 9]), [7, 8, 9]),
        ({'a': 1, 'b': 2}.keys(), ['a', 'b']),
    ],
)
def test_pure_iterables_still_become_lists(value, expected):
    result = _wrap(value)
    assert sorted(result) == sorted(expected)


def test_generator_still_becomes_list():
    assert _wrap(x for x in range(3)) == [0, 1, 2]
