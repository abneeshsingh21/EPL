"""Runtime smoke test: every run-to-completion example must EXECUTE, not just parse.

Parsing alone let corruption ship. An automated "AUTO-FIX" pass (v7.4.0, commit
e35d948) deleted essential lines from 17 example files — variable declarations,
function signatures — leaving programs that *parsed* cleanly but crashed at
runtime ("Variable X has not been created yet"). The parse-only guard
(``test_examples_parse.py``) never noticed, so the breakage shipped for many
releases. This test actually RUNS each run-to-completion example via ``epl run``
and asserts a clean exit, which is the only thing that would have caught it.

Examples that legitimately cannot "run to completion" are excluded by category,
each with a reason:

* ``_SERVERS``      — start a web server / run forever; covered by the parse test.
* ``_INTERACTIVE``  — block on stdin; cannot run unattended.
* ``_NEEDS_NODE``   — require a Node.js runtime for the JavaScript bridge.
* ``_TEST_DSL``     — use the ``Test "…" … End Test`` assertion DSL, not ``epl run``.
* ``_KNOWN_BROKEN`` — real, still-open engine bugs (see each entry). These are
  xfailed (not skipped) so they stay visible; when a bug is fixed, delete its
  entry and the example becomes enforced. ``strict=False`` means an
  accidental fix surfaces as XPASS rather than breaking CI.

Anything NOT in a list above is expected to run with exit code 0. New examples
are therefore covered by default (fail-closed).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / 'examples'

# Long-running web servers — they never exit, so there is nothing to "complete".
# Their source is still guarded by test_examples_parse.py.
_SERVERS = {
    'portfolio.epl',
    'todo.epl',
    'todo_api.epl',
    'webapp.epl',
}

# Block on stdin (input/ask/prompt); cannot run unattended in CI.
_INTERACTIVE = {
    'calculator.epl',
}

# Require a Node.js runtime for the JS/TS bridge (`Use javascript "…"`).
_NEEDS_NODE = {
    'js_bridge_demo.epl',
}

# Use the `Test "…" … End Test` assertion DSL, which is exercised by its own
# runner, not by `epl run`.
_TEST_DSL = {
    'test_strings.epl',
}

# Real, still-open engine bugs. Keep the reason specific so the next person knows
# exactly what to fix; delete the entry when the bug is closed.
_KNOWN_BROKEN = {
    'lambdas.epl': 'context-dependent parse: a bare ternary assignment parses '
    'alone but fails after earlier lambda assignments in the same file',
    'slicing.epl': 'omitted-bound step slices [::2] / [::-1] are unsupported '
    '(explicit [start:stop:step] works)',
    'text_editor.epl': 'bare `name = call(...)` assignment does not parse; only '
    '`Create`/`Set` handle a function-call RHS',
    'database_app.epl': 'db_create_table raises a runtime error under the interpreter SQLite path',
}


def _run_to_completion_examples():
    excluded = _SERVERS | _INTERACTIVE | _NEEDS_NODE | _TEST_DSL | set(_KNOWN_BROKEN)
    return sorted(p for p in _EXAMPLES_DIR.glob('*.epl') if p.name not in excluded)


def _run_example(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-m', 'epl', 'run', str(path)],
        cwd=str(_REPO_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_examples_directory_present():
    assert _EXAMPLES_DIR.is_dir(), f'missing {_EXAMPLES_DIR}'
    assert _run_to_completion_examples(), 'no run-to-completion examples found'


def test_known_broken_entries_exist():
    """Guard against stale xfail entries. A removed/renamed example would also
    make ``epl run`` exit non-zero, so ``test_known_broken_examples`` would keep
    xfailing it forever and quietly hide that it's gone. Fail loudly instead."""
    missing = sorted(n for n in _KNOWN_BROKEN if not (_EXAMPLES_DIR / n).is_file())
    assert not missing, f'stale _KNOWN_BROKEN entries (file no longer exists): {missing}'


@pytest.mark.parametrize('example', _run_to_completion_examples(), ids=lambda p: p.name)
def test_example_runs_clean(example: Path):
    result = _run_example(example)
    assert result.returncode == 0, (
        f'{example.name} exited {result.returncode}\n'
        f'--- stdout ---\n{result.stdout[-1500:]}\n'
        f'--- stderr ---\n{result.stderr[-1500:]}'
    )


@pytest.mark.parametrize(
    'name',
    [
        pytest.param(n, marks=pytest.mark.xfail(reason=r, strict=False))
        for n, r in sorted(_KNOWN_BROKEN.items())
    ],
)
def test_known_broken_examples(name):
    """Track open engine bugs as xfail so a fix surfaces (XPASS) instead of
    silently rotting. Delete the `_KNOWN_BROKEN` entry once the bug is fixed and
    this example will become enforced by ``test_example_runs_clean``."""
    result = _run_example(_EXAMPLES_DIR / name)
    assert result.returncode == 0
