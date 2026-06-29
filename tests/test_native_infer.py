"""Conservative monomorphic type inference for the native backend
(``epl.native_infer``).

These tests pin the *analysis* — what it resolves and, crucially, what it
refuses — and need no clang toolchain (they never build a binary). The
end-to-end "inferred program builds and matches the interpreter" checks live in
``test_native_build.py`` (clang-gated).

The contract is soundness over coverage: inference may only turn a *refused*
program into a correctly-typed one. Anything uncertain must fall back to
refusal, so every "refuses" test below is a safety guarantee.
"""

import pytest
from epl.lexer import Lexer
from epl.native_infer import analyze
from epl.parser import Parser


def _analyze(src: str):
    return analyze(Parser(Lexer(src).tokenize()).parse())


def test_reserved_runtime_names_stay_in_sync_with_compiler():
    """The hand-maintained RESERVED_RUNTIME_NAMES must cover every plain-word
    ``epl_<name>`` symbol the compiler actually declares, or a colliding user
    function would slip through to a duplicate-symbol build failure. Skipped when
    llvmlite is unavailable (the compiler can't be instantiated)."""
    # Skip ONLY when llvmlite itself is missing — a blanket `except ImportError`
    # would also swallow a genuine regression in epl.compiler's import and turn
    # this drift guard into a false green.
    pytest.importorskip('llvmlite')
    from epl.compiler import Compiler
    from epl.native_names import RESERVED_RUNTIME_NAMES

    compiler = Compiler()
    declared = {
        g.name[4:]
        for g in compiler.module.global_values
        if g.name.startswith('epl_') and g.name[4:].isidentifier() and '_' not in g.name[4:]
    }
    missing = declared - RESERVED_RUNTIME_NAMES
    assert not missing, f'RESERVED_RUNTIME_NAMES is missing runtime symbols: {sorted(missing)}'


# ── resolves the safe monomorphic cases ───────────────────────────────────


def test_infers_int_function_from_call_site():
    a = _analyze('Function add takes a and b\n  Return a + b\nEnd\nPrint add(2, 3)\n')
    assert a.admit
    assert a.func_sigs['add'] == (['int', 'int'], 'int')


def test_infers_recursive_int_function():
    src = (
        'Function fib takes n\n'
        '  If n < 2 Then\n    Return n\n  End\n'
        '  Return fib(n - 1) + fib(n - 2)\n'
        'End\n'
        'Print fib(10)\n'
    )
    a = _analyze(src)
    assert a.admit
    assert a.func_sigs['fib'] == (['int'], 'int')


def test_infers_string_param_and_void_return():
    src = 'Function greet takes name\n  Print "Hi " + name\nEnd\nCall greet with "Abneesh"\n'
    a = _analyze(src)
    assert a.admit
    assert a.func_sigs['greet'] == (['string'], 'void')


def test_string_plus_int_concat_is_admitted():
    # The backend converts int -> string for concatenation, matching the
    # interpreter, so this is a safe admit.
    src = (
        'Function add takes a and b\n  Return a + b\nEnd\n'
        'Create r equal to add(5, 10)\n'
        'Print "sum = " + r\n'
    )
    assert _analyze(src).admit


# ── refuses everything it cannot prove (soundness) ─────────────────────────


def test_conflicting_call_sites_refused():
    # Called with an int and a string -> no single monomorphic type -> refuse.
    src = 'Function id takes x\n  Return x\nEnd\nPrint id(1)\nPrint id("hi")\n'
    a = _analyze(src)
    assert not a.admit
    assert a.func_sigs == {}


def test_int_division_refused():
    # Native int division truncates (sdiv) while the interpreter yields a float
    # for non-divisible operands — admitting it would diverge, so refuse.
    src = 'Function half takes a and b\n  Return a / b\nEnd\nPrint half(3, 2)\n'
    assert not _analyze(src).admit


def test_power_operator_refused():
    # '**' is always float in the backend; not proven equivalent -> refuse.
    src = 'Function sq takes n\n  Return n ** 2\nEnd\nPrint sq(4)\n'
    assert not _analyze(src).admit


def test_string_plus_float_refused():
    # string + float build-fails / formats differently in the backend.
    src = (
        'Function f takes a and b\n  Return a + b\nEnd\n'
        'Create r equal to f(1.5, 2.5)\n'
        'Print "v" + r\n'
    )
    assert not _analyze(src).admit


def test_library_without_call_sites_refused():
    # No call sites -> parameter types cannot be constrained -> refuse.
    src = 'Function add takes a and b\n  Return a + b\nEnd\n'
    assert not _analyze(src).admit


def test_runtime_name_collision_refused():
    # A user function named `power` mangles to `epl_power`, colliding with the
    # runtime intrinsic; admitting it would build-fail, so decline it.
    src = 'Function power takes a and b\n  Return a + b\nEnd\nPrint power(2, 3)\n'
    a = _analyze(src)
    assert not a.admit
    assert 'power' not in a.func_sigs


def test_builtin_shadowing_function_refused():
    # `sum` is a native builtin the compiler dispatches before user functions, so
    # natively the user `sum` never runs (returns the builtin's result) while the
    # interpreter runs the user function — divergent, so inference must refuse.
    src = 'Function sum takes a and b\n  Return a + b\nEnd\nPrint sum(3, 4)\n'
    a = _analyze(src)
    assert not a.admit
    assert 'sum' not in a.func_sigs


def test_fully_typed_shadowing_function_refused():
    # Even with EXPLICIT annotations, a user function named `power` shadows a
    # runtime/builtin symbol — the compiler would hit a duplicate-symbol /
    # builtin-shadowing divergence. `needs` is false here, so this only refuses
    # because shadowed names are a hard reject regardless of annotation.
    src = (
        'Function power takes integer a and integer b and returns integer\n'
        '  Return a + b\n'
        'End\n'
        'Print power(2, 3)\n'
    )
    a = _analyze(src)
    assert not a.admit
    assert 'power' not in a.func_sigs


def test_for_range_non_numeric_bound_refused():
    # A counted loop whose bound is a (concrete) string is not lowerable by the
    # native backend; it must refuse rather than admit on "concrete != unknown".
    src = 'For i from 1 to "ten"\n  Print i\nEnd\n'
    assert not _analyze(src).admit


def test_unsupported_construct_refused():
    # A foreach over a list of unknown element type is not modeled -> refuse.
    src = (
        'Function total takes items\n'
        '  Create s equal to 0\n'
        '  For each x in items\n    Set s to s + x\n  End\n'
        '  Return s\n'
        'End\n'
        'Print total([1, 2, 3])\n'
    )
    assert not _analyze(src).admit
