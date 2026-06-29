"""End-to-end native-build smoke test: compile an EPL program to a real
native executable and run it.

Why this exists
---------------
The LLVM/VM unit tests only exercise IR generation and the llvmlite API — none
of them ever *compiles* ``epl/runtime.c`` or *links and runs* a binary. That
blind spot let a real regression ship: ``runtime.c`` accumulated duplicate
definitions of ``epl_file_read/write/append/exists/delete`` and ``epl_time_now``
plus a conflicting ``epl_sleep_ms`` signature, so the runtime never compiled and
every ``epl build`` failed at link time with ``undefined symbol:
epl_gc_root_depth``. Parse-only and IR-only tests saw nothing wrong.

This test actually drives ``compile_file`` (the code path behind ``epl build``),
runs the resulting executable, and asserts its output — the only kind of test
that would have caught the duplicate-symbol breakage. It also pins native
counted-loop control flow (``Continue`` / negative ``step``) so the VM fixes are
mirrored on the native backend.

It is skipped when no LLVM/clang toolchain is available, so it never blocks
contributors who only run the interpreter/VM, while still running in CI images
that ship clang.
"""

import os
import subprocess

import pytest


def _find_clang():
    """Return a clang executable that can compile LLVM IR, or None.

    Only clang is probed (not gcc): the native pipeline emits textual LLVM IR
    (``.ll``), which gcc cannot consume. A gcc-only machine cannot produce a
    native binary, so the test must skip rather than fail there.
    """
    candidates = [
        'clang',
        r'C:\Program Files\LLVM\bin\clang.exe',
        r'C:\Program Files (x86)\LLVM\bin\clang.exe',
    ]
    for candidate in candidates:
        try:
            subprocess.run([candidate, '--version'], capture_output=True, timeout=15, check=True)
            return candidate
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    return None


_CLANG = _find_clang()
pytestmark = pytest.mark.skipif(
    _CLANG is None, reason='no LLVM/clang toolchain available to build a native binary'
)


def _build_and_run(source: str, tmp_path) -> str:
    """Compile ``source`` to a native exe in ``tmp_path`` and return its stdout."""
    from epl.runtime_support import compile_file

    # compile_file derives all output paths from the basename and writes them to
    # the current working directory, so run it from an isolated temp dir.
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        src_path = os.path.join(tmp_path, 'prog.epl')
        with open(src_path, 'w', encoding='utf-8') as handle:
            handle.write(source)

        # Ensure the freshly-installed clang is reachable even if it is not on
        # PATH for the test process.
        clang_dir = os.path.dirname(_CLANG)
        if clang_dir and clang_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = clang_dir + os.pathsep + os.environ.get('PATH', '')

        ok = compile_file('prog.epl', opt_level=2, static=True)
        assert ok, 'compile_file reported failure'

        exe = os.path.join(tmp_path, 'prog.exe')
        if not os.path.exists(exe):
            exe = os.path.join(tmp_path, 'prog')
        assert os.path.exists(exe), 'native executable was not produced'

        result = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (
            f'native binary exited {result.returncode} '
            f'(a non-zero/segfault code means broken codegen or a link/runtime bug)\n'
            f'stdout={result.stdout!r} stderr={result.stderr!r}'
        )
        return result.stdout.replace('\r\n', '\n')
    finally:
        os.chdir(prev)


def test_native_hello_world_runs(tmp_path):
    """The simplest program must compile, link against runtime.c, and run.

    This is the canary for the duplicate-symbol / link regression: if
    ``runtime.c`` does not compile, linking fails here.
    """
    out = _build_and_run('Print "Hello from native EPL!"\n', tmp_path)
    assert out.strip() == 'Hello from native EPL!'


def test_native_typed_function_returns_correct_value(tmp_path):
    """A fully type-annotated function must compute and print the right value."""
    src = (
        'Function add takes integer a and integer b and returns integer\n'
        '  Return a + b\n'
        'End\n'
        'Print add(2, 3)\n'
    )
    assert _build_and_run(src, tmp_path).strip() == '5'


def test_native_recursion_returns_correct_value(tmp_path):
    """Recursive calls must work natively (was a segfault before the runtime fix)."""
    src = (
        'Function fib takes integer n and returns integer\n'
        '  If n < 2 Then\n'
        '    Return n\n'
        '  End\n'
        '  Return fib(n - 1) + fib(n - 2)\n'
        'End\n'
        'Print fib(10)\n'
    )
    assert _build_and_run(src, tmp_path).strip() == '55'


def test_native_counted_loop_continue_terminates(tmp_path):
    """`Continue` in a counted loop must advance the counter (no infinite loop),
    mirroring the VM control-flow fix on the native backend."""
    src = 'For i from 1 to 6\n  If i % 3 == 0 Then\n    Continue\n  End\n  Print i\nEnd\n'
    assert _build_and_run(src, tmp_path).split() == ['1', '2', '4', '5']


def test_native_negative_step_counts_down(tmp_path):
    """A negative-step `For` loop must actually iterate downward natively."""
    src = 'For i from 5 to 1 step -1\n  Print i\nEnd\n'
    assert _build_and_run(src, tmp_path).split() == ['5', '4', '3', '2', '1']


def test_native_infers_untyped_function(tmp_path):
    """A function with NO type annotations, called only with integers, must now
    build natively (via epl.native_infer) and compute the right value — this is
    the case the bare safety gate used to refuse."""
    src = 'Function add takes a and b\n  Return a + b\nEnd\nPrint add(2, 3)\n'
    assert _build_and_run(src, tmp_path).strip() == '5'


def test_native_infers_recursive_untyped_function(tmp_path):
    """Untyped recursive fib, called with an int, builds and matches."""
    src = (
        'Function fib takes n\n'
        '  If n < 2 Then\n    Return n\n  End\n'
        '  Return fib(n - 1) + fib(n - 2)\n'
        'End\n'
        'Print fib(10)\n'
    )
    assert _build_and_run(src, tmp_path).strip() == '55'


def test_native_infers_string_int_concat(tmp_path):
    """Untyped function + string/int concatenation (matches the interpreter's
    int formatting) builds and prints correctly."""
    src = (
        'Function add takes a and b\n  Return a + b\nEnd\n'
        'Create r equal to add(5, 10)\n'
        'Print "sum = " + r\n'
    )
    assert _build_and_run(src, tmp_path).strip() == 'sum = 15'


def test_native_build_output_flag(tmp_path):
    """`epl build -o path` must write the binary to the specified path and create
    any required directories."""
    from epl.runtime_support import compile_file

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        src_path = os.path.join(tmp_path, 'prog.epl')
        with open(src_path, 'w', encoding='utf-8') as handle:
            handle.write('Print "from -o"\n')

        clang_dir = os.path.dirname(_CLANG)
        if clang_dir and clang_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = clang_dir + os.pathsep + os.environ.get('PATH', '')

        # Build into a subdir that does not exist yet.
        ok = compile_file('prog.epl', opt_level=2, static=True, output='dist/myapp')
        assert ok, 'compile_file reported failure'

        # The platform extension must be auto-appended.
        exe = os.path.join(tmp_path, 'dist', 'myapp.exe')
        if not os.path.exists(exe):
            exe = os.path.join(tmp_path, 'dist', 'myapp')
        assert os.path.exists(exe), f'output binary not found at {exe}'

        result = subprocess.run([exe], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f'binary exited {result.returncode}'
        assert result.stdout.strip() == 'from -o'
    finally:
        os.chdir(prev)
