"""The native-build safety gate: ``epl build`` must refuse to emit a binary it
cannot prove type-correct, instead of silently producing a segfaulting one.

The native backend has no type inference — untyped function parameters and
untyped value-returns default to ``i8*``/string, which miscompiles numeric code
(typically into a crash). Until a tagged-value / inference backend exists,
``compile_file`` scans for these unprovable functions and refuses with an
actionable message. These tests pin that behaviour.

The refusal happens entirely before any C compiler is invoked, so — unlike the
end-to-end build tests — these need no clang toolchain and run everywhere.
"""

import os

from epl.lexer import Lexer
from epl.parser import Parser
from epl.runtime_support import _native_unsafe_functions, compile_file


def _parse(src: str):
    return Parser(Lexer(src).tokenize()).parse()


def test_untyped_params_flagged():
    problems = _native_unsafe_functions(_parse('Function add takes a and b\n  Return a + b\nEnd\n'))
    assert len(problems) == 1
    name, _line, reason = problems[0]
    assert name == 'add'
    assert 'no type annotation' in reason


def test_value_return_without_return_type_flagged():
    # Params are typed, but the value-returning body has no return type — this
    # is the exact shape that boxed an int as a string pointer and segfaulted.
    src = 'Function add takes integer a and integer b\n  Return a + b\nEnd\n'
    problems = _native_unsafe_functions(_parse(src))
    assert len(problems) == 1
    assert 'returns a value' in problems[0][2]


def test_fully_typed_function_is_safe():
    src = 'Function add takes integer a and integer b and returns integer\n  Return a + b\nEnd\n'
    assert _native_unsafe_functions(_parse(src)) == []


def test_void_untyped_procedure_is_safe():
    # No parameters and no value return: nothing to mistype, so it must NOT be
    # flagged (over-refusing valid programs would be its own regression).
    src = 'Function greet takes nothing\n  Print "hi"\nEnd\nCall greet\n'
    assert _native_unsafe_functions(_parse(src)) == []


def test_module_function_is_checked():
    src = 'Module Math\n  Function square takes n\n    Return n * n\n  End\nEnd\n'
    problems = _native_unsafe_functions(_parse(src))
    assert problems and problems[0][0] == 'Math::square'


def test_compile_file_refuses_unsafe_program_without_emitting_binary(tmp_path, capsys):
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        src = os.path.join(tmp_path, 'prog.epl')
        # `id` is called with both an int and a string — genuinely polymorphic, so
        # monomorphic inference cannot resolve it and the build must still refuse.
        # (A simple `add(2, 3)` is now inferable and would build, so it no longer
        # exercises the refusal path.)
        with open(src, 'w', encoding='utf-8') as handle:
            handle.write('Function id takes x\n  Return x\nEnd\nPrint id(1)\nPrint id("hi")\n')

        result = compile_file('prog.epl')

        assert result is False, 'unsafe program must not report a successful build'
        # No executable (and no leftover IR/object) may be produced.
        for ext in ('.exe', '', '.ll', '.o'):
            assert not os.path.exists(os.path.join(tmp_path, 'prog' + ext)), (
                f'native build must not emit prog{ext} for an unprovable program'
            )
        out = capsys.readouterr().out
        assert 'cannot guarantee a correct binary' in out
        assert 'epl run' in out  # points the user at the path that works
    finally:
        os.chdir(prev)
