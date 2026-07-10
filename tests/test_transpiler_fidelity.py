"""Transpiler fidelity harness — EPL interpreter output MUST equal transpiled-Python output.

The transpiler's whole promise is "write EPL, own portable production code." That
promise is only real if the generated Python *behaves* the same as EPL, not merely
parses. Historically the transpiler was syntax-faithful but semantics-incomplete:
`+` was emitted raw (so EPL's `"n: " + 3` auto-coercion became a Python TypeError),
booleans/None printed as `True`/`None` instead of EPL's `true`/`nothing`, and Maps
lost dot-access. Those gaps shipped silently because nothing compared the two engines.

This harness closes that hole permanently: every `.epl` file in `fidelity_corpus/` is
executed two ways —
  1. through the EPL interpreter (`epl run`), the reference semantics, and
  2. by transpiling to Python and running that Python —
and their stdout must match byte-for-byte. A new transpiler regression can no longer
hide; it fails a test.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fidelity_corpus')

sys.path.insert(0, REPO_ROOT)


def _corpus_files():
    if not os.path.isdir(CORPUS_DIR):
        return []
    return sorted(f for f in os.listdir(CORPUS_DIR) if f.endswith('.epl'))


def _run_epl_interpreter(epl_path):
    """Reference output: run the .epl file through the EPL interpreter."""
    proc = subprocess.run(
        [sys.executable, '-m', 'epl', 'run', epl_path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    return proc.returncode, proc.stdout


def _transpile_and_run(epl_path, tmp_path):
    """Candidate output: transpile the .epl to Python, then execute that Python."""
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.python_transpiler import transpile_to_python

    with open(epl_path, encoding='utf-8') as fh:
        source = fh.read()
    program = Parser(Lexer(source).tokenize()).parse()
    py_source = transpile_to_python(program)

    py_path = os.path.join(str(tmp_path), 'transpiled.py')
    with open(py_path, 'w', encoding='utf-8') as fh:
        fh.write(py_source)

    proc = subprocess.run(
        [sys.executable, py_path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    return proc.returncode, proc.stdout, py_source


@pytest.mark.parametrize('corpus_file', _corpus_files())
def test_transpiled_python_matches_interpreter(corpus_file, tmp_path):
    epl_path = os.path.join(CORPUS_DIR, corpus_file)

    interp_rc, interp_out = _run_epl_interpreter(epl_path)
    assert interp_rc == 0, (
        f'{corpus_file}: interpreter itself failed (rc={interp_rc}); '
        f'fix the corpus program.\n--- interpreter stdout ---\n{interp_out}'
    )

    trans_rc, trans_out, py_source = _transpile_and_run(epl_path, tmp_path)

    assert trans_rc == 0, (
        f'{corpus_file}: transpiled Python crashed (rc={trans_rc}).\n'
        f'--- generated Python ---\n{py_source}\n'
        f'--- expected (interpreter) stdout ---\n{interp_out}'
    )
    assert trans_out == interp_out, (
        f'{corpus_file}: transpiled Python output diverged from interpreter.\n'
        f'--- generated Python ---\n{py_source}\n'
        f'--- interpreter stdout ---\n{interp_out!r}\n'
        f'--- transpiled stdout ---\n{trans_out!r}'
    )


def test_corpus_is_not_empty():
    """Guard against the corpus dir silently disappearing (which would make the
    parametrized suite pass vacuously)."""
    assert len(_corpus_files()) >= 17, (
        f'Fidelity corpus should have >=17 programs, found {len(_corpus_files())}. '
        'Did the corpus dir get moved or emptied?'
    )


# ── Fail-loud contract ────────────────────────────────────────────────
#
# A production transpiler must be correct-or-loud: it either emits Python that
# behaves like the interpreter, or it refuses with a clear error. It must NEVER
# emit code that is syntactically valid but silently drops/mistranslates a
# construct. These tests enforce that guarantee, which the old transpiler
# violated by writing `# Unsupported: X` comments and `None  # Unsupported`
# expressions into otherwise-passing output.


def _transpile_source(epl_source):
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.python_transpiler import transpile_to_python

    program = Parser(Lexer(epl_source).tokenize()).parse()
    return transpile_to_python(program)


def test_corpus_output_has_no_silent_unsupported_markers():
    """No generated program may contain an 'Unsupported' escape hatch — those
    are the silent-wrong-code markers the fail-loud refactor eliminated."""
    for corpus_file in _corpus_files():
        epl_path = os.path.join(CORPUS_DIR, corpus_file)
        with open(epl_path, encoding='utf-8') as fh:
            py = _transpile_source(fh.read())
        assert 'Unsupported' not in py, (
            f'{corpus_file}: generated Python contains an "Unsupported" marker — '
            'the transpiler silently dropped a construct instead of failing loud.\n'
            f'{py}'
        )


def test_unknown_expression_node_raises_transpile_error():
    """An unrecognized expression node must raise TranspileError, not emit
    `None  # Unsupported` (which compiles and computes the wrong answer)."""
    from epl.python_transpiler import PythonTranspiler, TranspileError

    class _Alien:  # not an AST node the transpiler knows
        pass

    with pytest.raises(TranspileError):
        PythonTranspiler()._expr(_Alien())


def test_unknown_statement_node_raises_transpile_error():
    """An unrecognized statement node must raise TranspileError, not emit a
    `# Unsupported` comment that drops the statement."""
    from epl.python_transpiler import PythonTranspiler, TranspileError

    class _Alien:
        pass

    with pytest.raises(TranspileError):
        PythonTranspiler()._emit_stmt(_Alien())
