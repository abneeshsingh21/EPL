"""Unit coverage for the EPL static type system.

`test_strict_type.py` drives the `TypeChecker` end-to-end; this module pins
the primitives it is built on — type construction and stringification,
`EPLType` equality/hashing, the `is_assignable` subtyping table,
`infer_type_from_value`, `TypeScope` lookups, and `PRIMITIVE_MAP` aliases —
plus a few checker-level contracts.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.type_system import (
    PRIMITIVE_MAP,
    T_ANY,
    T_BOOLEAN,
    T_DECIMAL,
    T_INTEGER,
    T_NEVER,
    T_NOTHING,
    T_TEXT,
    EPLType,
    TypeChecker,
    TypeKind,
    TypeScope,
    infer_type_from_value,
    is_assignable,
    make_list_type,
    make_map_type,
    make_optional_type,
    make_union_type,
)


def _check(code, strict=False):
    checker = TypeChecker(strict=strict)
    diags = checker.check(Parser(Lexer(code).tokenize()).parse())
    return checker, diags


# ── str() / repr of types ────────────────────────────────
STR_CASES = [
    ('primitive', lambda: str(T_INTEGER) == 'integer'),
    ('list', lambda: str(make_list_type(T_INTEGER)) == 'List<integer>'),
    ('map', lambda: str(make_map_type(T_TEXT, T_ANY)) == 'Map<text, any>'),
    ('optional', lambda: str(make_optional_type(T_INTEGER)) == 'integer?'),
    ('nested_list', lambda: str(make_list_type(make_list_type(T_TEXT))) == 'List<List<text>>'),
]


# ── Equality / hashing (compare on kind+name+params only) ─
EQ_CASES = [
    ('structural_eq', lambda: EPLType(TypeKind.PRIMITIVE, 'integer') == T_INTEGER),
    ('name_differs', lambda: EPLType(TypeKind.PRIMITIVE, 'text') != T_INTEGER),
    ('params_differ', lambda: make_list_type(T_INTEGER) != make_list_type(T_TEXT)),
    ('hashable', lambda: len({T_INTEGER, EPLType(TypeKind.PRIMITIVE, 'integer'), T_TEXT}) == 2),
]


# ── is_assignable(target, source) subtyping table ─────────
ASSIGNABLE_CASES = [
    ('identity', lambda: is_assignable(T_INTEGER, T_INTEGER) is True),
    ('int_to_decimal', lambda: is_assignable(T_DECIMAL, T_INTEGER) is True),
    ('decimal_not_to_int', lambda: is_assignable(T_INTEGER, T_DECIMAL) is False),
    ('int_not_to_text', lambda: is_assignable(T_INTEGER, T_TEXT) is False),
    ('any_target', lambda: is_assignable(T_ANY, T_TEXT) is True),
    ('any_source', lambda: is_assignable(T_TEXT, T_ANY) is True),
    ('never_source', lambda: is_assignable(T_INTEGER, T_NEVER) is True),
    ('none_target', lambda: is_assignable(None, T_TEXT) is True),
    ('none_source', lambda: is_assignable(T_TEXT, None) is True),
    (
        'optional_accepts_inner',
        lambda: is_assignable(make_optional_type(T_INTEGER), T_INTEGER) is True,
    ),
    (
        'optional_accepts_nothing',
        lambda: is_assignable(make_optional_type(T_INTEGER), T_NOTHING) is True,
    ),
]


# ── infer_type_from_value (bool checked before int) ───────
INFER_CASES = [
    ('bool', lambda: infer_type_from_value(True) == T_BOOLEAN),
    ('int', lambda: infer_type_from_value(5) == T_INTEGER),
    ('decimal', lambda: infer_type_from_value(1.5) == T_DECIMAL),
    ('text', lambda: infer_type_from_value('x') == T_TEXT),
    ('nothing', lambda: infer_type_from_value(None) == T_NOTHING),
    ('homogeneous_list', lambda: str(infer_type_from_value([1, 2, 3])) == 'List<integer>'),
    ('mixed_list_is_any', lambda: str(infer_type_from_value([1, 'x'])) == 'List<any>'),
]


# ── make_union_type flattening / collapse ─────────────────
UNION_CASES = [
    ('single_member_collapses', lambda: make_union_type(T_INTEGER, T_INTEGER) == T_INTEGER),
    ('two_members_is_union', lambda: make_union_type(T_INTEGER, T_TEXT).kind == TypeKind.UNION),
]


# ── PRIMITIVE_MAP aliases ────────────────────────────────
PRIMITIVE_MAP_CASES = [
    ('int_alias', lambda: PRIMITIVE_MAP.get('int') == T_INTEGER),
    ('string_alias', lambda: PRIMITIVE_MAP.get('string') == T_TEXT),
    ('str_alias', lambda: PRIMITIVE_MAP.get('str') == T_TEXT),
    ('float_alias', lambda: PRIMITIVE_MAP.get('float') == T_DECIMAL),
    ('bool_alias', lambda: PRIMITIVE_MAP.get('bool') == T_BOOLEAN),
]


@pytest.mark.parametrize(('name', 'check_fn'), STR_CASES, ids=[n for n, _ in STR_CASES])
def test_type_str(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), EQ_CASES, ids=[n for n, _ in EQ_CASES])
def test_type_equality(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(
    ('name', 'check_fn'), ASSIGNABLE_CASES, ids=[n for n, _ in ASSIGNABLE_CASES]
)
def test_is_assignable(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), INFER_CASES, ids=[n for n, _ in INFER_CASES])
def test_infer_type_from_value(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), UNION_CASES, ids=[n for n, _ in UNION_CASES])
def test_union(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(
    ('name', 'check_fn'), PRIMITIVE_MAP_CASES, ids=[n for n, _ in PRIMITIVE_MAP_CASES]
)
def test_primitive_map(name, check_fn):
    assert check_fn(), name


def test_type_scope_define_and_lookup():
    scope = TypeScope(name='global')
    scope.define_var('x', T_INTEGER)
    assert scope.lookup_var('x') == T_INTEGER
    assert scope.lookup_var('missing') is None


def test_type_scope_child_walks_parent():
    parent = TypeScope(name='global')
    parent.define_var('outer', T_TEXT)
    child = parent.child('local')
    assert child.lookup_var('outer') == T_TEXT


def test_type_scope_resolve_type_name():
    scope = TypeScope(name='global')
    assert scope.resolve_type_name('int') == T_INTEGER
    assert scope.resolve_type_name('does_not_exist') is None


def test_checker_returns_list_and_valid_code_has_no_errors():
    checker, diags = _check('create x as 10\nset x to 20\nprint x')
    assert isinstance(diags, list)
    assert not checker.has_errors()


def test_checker_flags_assignment_mismatch():
    checker, diags = _check('create integer x as 10\nset x to "hello"')
    assert checker.has_errors()
    assert any('assign' in d.message.lower() for d in diags)
