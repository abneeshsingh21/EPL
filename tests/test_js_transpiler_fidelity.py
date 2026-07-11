"""JS transpiler fidelity harness — EPL interpreter output MUST equal transpiled-JS output.

The JS target's promise is "write EPL, ship it to the browser / Node." That promise
is only real if the generated JavaScript *behaves* the same as EPL, not merely runs.
Historically the JS transpiler was syntax-faithful but semantics-incomplete: `+` was
emitted raw (so `[1, 2] + [3, 4]` became the string "1,23,4" instead of a concatenated
list, and `"row: " + aList` produced "[object Object]"), Map iteration crashed
(`for..of` over a plain object), `type_of` leaked JS `typeof` names (`object` for a
list, not `list`), `reversed("abc")` returned a char array instead of "cba", and Map
methods / property accessors threw. On a 17-program corpus only 7 matched the
interpreter. Those gaps shipped silently because nothing compared the two engines.

This harness closes that hole: every `.epl` file in `fidelity_corpus/` is executed two
ways —
  1. through the EPL interpreter (`epl run`), the reference semantics, and
  2. by transpiling to Node.js JavaScript and running that with `node` —
and their stdout must match byte-for-byte. A new JS transpiler regression can no
longer hide; it fails a test.

Node is required to actually execute the JS. When `node` is unavailable (some CI
images), the execution tests skip rather than fail — but the transpile-time
fail-loud guarantees below still run everywhere.
"""

import os
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fidelity_corpus')

sys.path.insert(0, REPO_ROOT)

_NODE = shutil.which('node')
_requires_node = pytest.mark.skipif(
    _NODE is None, reason='node.js not available to run generated JS'
)


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


def _transpile_to_js(epl_path):
    from epl.js_transpiler import JSTranspiler
    from epl.lexer import Lexer
    from epl.parser import Parser

    with open(epl_path, encoding='utf-8') as fh:
        source = fh.read()
    program = Parser(Lexer(source).tokenize()).parse()
    return JSTranspiler(target='node', module_format='esm').transpile(program)


def _transpile_and_run(epl_path, tmp_path):
    """Candidate output: transpile the .epl to JS, then execute it with node."""
    js_source = _transpile_to_js(epl_path)

    # `.mjs` so Node treats it as an ES module (the transpiler emits ESM imports).
    js_path = os.path.join(str(tmp_path), 'transpiled.mjs')
    with open(js_path, 'w', encoding='utf-8') as fh:
        fh.write(js_source)

    proc = subprocess.run(
        [_NODE, js_path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    return proc.returncode, proc.stdout, js_source


@_requires_node
@pytest.mark.parametrize('corpus_file', _corpus_files())
def test_transpiled_js_matches_interpreter(corpus_file, tmp_path):
    epl_path = os.path.join(CORPUS_DIR, corpus_file)

    interp_rc, interp_out = _run_epl_interpreter(epl_path)
    assert interp_rc == 0, (
        f'{corpus_file}: interpreter itself failed (rc={interp_rc}); '
        f'fix the corpus program.\n--- interpreter stdout ---\n{interp_out}'
    )

    trans_rc, trans_out, js_source = _transpile_and_run(epl_path, tmp_path)

    assert trans_rc == 0, (
        f'{corpus_file}: transpiled JS crashed (rc={trans_rc}).\n'
        f'--- generated JS ---\n{js_source}\n'
        f'--- expected (interpreter) stdout ---\n{interp_out}'
    )
    assert trans_out == interp_out, (
        f'{corpus_file}: transpiled JS output diverged from interpreter.\n'
        f'--- generated JS ---\n{js_source}\n'
        f'--- interpreter stdout ---\n{interp_out!r}\n'
        f'--- transpiled stdout ---\n{trans_out!r}'
    )


def test_corpus_is_not_empty():
    """Guard against the corpus dir silently disappearing (which would make the
    parametrized suite pass vacuously)."""
    assert len(_corpus_files()) >= 30, (
        f'Fidelity corpus should have >=30 programs, found {len(_corpus_files())}. '
        'Did the corpus dir get moved or emptied?'
    )


# ── Fail-loud contract ────────────────────────────────────────────────
#
# The JS transpiler must be correct-or-loud: it either emits JS that behaves like
# the interpreter, or it refuses. It must NEVER emit code that runs but silently
# drops/mistranslates a construct.


def test_corpus_transpiles_without_unsupported_markers():
    """No generated program may contain an 'unsupported' escape-hatch comment —
    those mark a silently-dropped construct."""
    for corpus_file in _corpus_files():
        epl_path = os.path.join(CORPUS_DIR, corpus_file)
        js = _transpile_to_js(epl_path)
        assert 'unsupported' not in js.lower(), (
            f'{corpus_file}: generated JS contains an "unsupported" marker — '
            'the transpiler silently dropped a construct instead of handling it.\n'
            f'{js}'
        )


def _transpile_src_to_js(source):
    from epl.js_transpiler import JSTranspiler
    from epl.lexer import Lexer
    from epl.parser import Parser

    program = Parser(Lexer(source).tokenize()).parse()
    return JSTranspiler(target='node', module_format='esm').transpile(program)


def test_unmapped_builtin_raises_not_silently_emitted():
    """The core correctness gate — runs WITHOUT node, so it holds on every CI image.

    An EPL builtin that has no JS mapping (here: `aes_encrypt`, a real builtin with
    no browser/Node equivalent) must make the transpiler REFUSE at transpile time,
    not emit `aes_encrypt(...)` — a call to a nonexistent JS identifier that throws
    ReferenceError at runtime. This is the exact silent-divergence the JS target
    shipped before Phase 2, blind to node-less CI.
    """
    from epl.interpreter import BUILTINS
    from epl.python_transpiler import TranspileError

    assert 'aes_encrypt' in BUILTINS, 'test premise: aes_encrypt is a real EPL builtin'
    with pytest.raises(TranspileError, match='aes_encrypt'):
        _transpile_src_to_js('Say aes_encrypt("secret", "key")')


def test_genuine_user_function_still_emits_bare_call():
    """The fail-loud fallback must NOT swallow real user-function calls — a name
    that is not an EPL builtin stays a plain `name(args)` call."""
    js = _transpile_src_to_js(
        'Function greet takes name\n    Return "hi " + name\nEnd\nSay greet("Ada")'
    )
    assert 'greet(' in js
