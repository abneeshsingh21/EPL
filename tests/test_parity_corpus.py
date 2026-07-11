"""Corpus parity gate: every runnable example must behave identically on both backends.

`epl run` defaults to the bytecode VM, while the docs and most of the suite validate
against the tree-walking interpreter. A program whose *observable behaviour* (stdout +
exit status) differs between the two backends is a divergence bug. This gate walks the
real example corpus (``examples/`` + ``benchmarks/``, recursively), runs each eligible
program through BOTH backends via the actual CLI, and asserts they agree — promoting the
previously advisory ``tests/parity_check.py`` harness (which always returned 0) into an
enforced CI gate.

Ineligible programs are excluded by a documented, content-based filter. The filter is
directory-agnostic (unlike ``test_examples_run.py``'s top-level-only glob), so programs
under ``examples/apps/``, ``examples/discord_agent/``, ``benchmarks/`` … are covered too:

* servers / never-exit loops    — ``WebApp``/``Route``/``Serve``/``web_api_create``/…
* interactive (stdin-blocking)  — ``Ask``/``Prompt``/``input``/``Read line``
* socket / GUI event loops      — ``websocket``/``WebSocket``/``gui_window``
* environment-dependent bridge  — ``Use javascript`` (needs a Node.js runtime)
* the ``Test "…" End Test`` DSL  — exercised by its own runner, not ``epl run``
* nondeterministic output       — ``random``/``uuid``/… (differs run-to-run, so it
                                  cannot be diffed for backend parity)

Every other program is INCLUDED by default (fail-closed): a new compute example is
auto-covered, and a program that hangs (no natural exit) FAILS on the per-program
timeout rather than being silently skipped — the exact failure mode the advisory harness
used to swallow.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORPUS_DIRS = ('examples', 'benchmarks')

# Per-program wall-clock budget for a single backend run. Every eligible program in the
# corpus completes in well under this; exceeding it means the program hangs (a server or
# event loop that slipped the content filter), which must FAIL, not skip.
_TIMEOUT_S = 45

# Substrings that make a program unsuitable for headless, deterministic backend diffing.
# Content-based (not path-based) so the same rule covers every subdirectory and any
# future example without per-file maintenance. Grouped by why the program can't be diffed.
_SKIP_TOKENS = (
    # Servers and never-exit event loops: they don't run to completion, so there is no
    # terminal stdout/exit status to compare.
    'WebApp',
    'Route ',
    'Listen',
    'Serve',
    'serve(',
    'run_server',
    'web_api_create',
    # Interactive: block on stdin, so they can't run unattended.
    'Ask ',
    'Prompt ',
    'input(',
    'Read line',
    # Sockets / desktop GUI event loops: block like a server.
    'websocket',
    'WebSocket',
    'gui_window',
    # Environment-dependent: the JS/TS bridge needs a Node.js runtime that may be absent.
    'Use javascript',
    # The `Test "…" … End Test` assertion DSL has its own runner; it is not `epl run` code.
    'End Test',
    # Nondeterministic output: random/uuid legitimately differ between any two runs, so
    # the two backends can't be expected to emit byte-identical stdout.
    'random',
    'uuid',
    'generate_uuid',
    'random_string',
)


def _skip_reason(path: Path) -> str | None:
    """Return the first matching skip token for a program, or ``None`` if it is eligible."""
    try:
        src = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return 'unreadable'
    for tok in _SKIP_TOKENS:
        if tok in src:
            return tok.strip()
    return None


def _all_programs() -> list[Path]:
    programs: list[Path] = []
    for base in _CORPUS_DIRS:
        programs.extend((_REPO_ROOT / base).rglob('*.epl'))
    return sorted(programs)


def _eligible_programs() -> list[Path]:
    return [p for p in _all_programs() if _skip_reason(p) is None]


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _run(path: Path, interpret: bool) -> tuple[int, str, str]:
    """Run a program under one backend. Raises ``TimeoutExpired`` (→ test failure) on hang."""
    cmd = [sys.executable, '-m', 'epl', 'run']
    if interpret:
        cmd.append('--interpret')
    cmd.append(str(path))
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_corpus_present():
    """The corpus and a non-trivial eligible set must exist, or the gate is vacuous."""
    assert (_REPO_ROOT / 'examples').is_dir(), 'missing examples/ corpus'
    eligible = _eligible_programs()
    assert len(eligible) >= 30, f'suspiciously few eligible parity programs: {len(eligible)}'


@pytest.mark.parametrize('program', _eligible_programs(), ids=_rel)
def test_backend_parity(program: Path):
    """Interpreter and VM must both run the program to completion (exit 0) with
    byte-identical stdout. A hang trips ``_TIMEOUT_S`` and fails as a ``TimeoutExpired``."""
    try:
        vm_rc, vm_out, vm_err = _run(program, interpret=False)
        in_rc, in_out, in_err = _run(program, interpret=True)
    except subprocess.TimeoutExpired as exc:
        pytest.fail(
            f'{_rel(program)} did not complete within {_TIMEOUT_S}s '
            f'(command: {" ".join(map(str, exc.cmd))}) — a hanging program must be added '
            f'to the documented skip filter, not left to time out.'
        )

    assert in_rc == 0, (
        f'{_rel(program)} exited {in_rc} under the interpreter\n'
        f'--- interpreter stderr ---\n{in_err[-1500:]}'
    )
    assert vm_rc == 0, (
        f'{_rel(program)} exited {vm_rc} under the VM\n--- VM stderr ---\n{vm_err[-1500:]}'
    )
    assert vm_out == in_out, (
        f'BACKEND DIVERGENCE: {_rel(program)} produced different stdout\n'
        f'--- interpreter stdout ---\n{in_out[-1500:]}\n'
        f'--- VM stdout ---\n{vm_out[-1500:]}'
    )
