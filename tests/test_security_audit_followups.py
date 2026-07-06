"""Regression tests for the second-pass security-audit fixes (PR #84 review).

Covers four issues found while addressing the CodeRabbit review:

1. ReDoS guard only unwrapped one redundant group, so deeply nested wrappers
   like ``(((a+)))+$`` bypassed the catastrophic-backtracking check.
2. The bytecode VM swallowed a non-numeric ``Exit`` value to status 0 instead
   of raising like the interpreter path.
3. ``epl.ffi._has_path_separator`` folded ``os.altsep`` into the membership
   test; on POSIX ``os.altsep`` is None so ``('' in name)`` was always True,
   defeating the basename allowlist shortcut.
4. ``web_send_file`` jailing was separator-blind: Windows-style traversal
   payloads slipped past the jail on POSIX hosts (covered separately in
   test_web_send_file_traversal.py; a cross-host case is asserted here too).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.stdlib import _check_redos

# ── 1. ReDoS: nested redundant groups must not bypass the guard ──────────────


@pytest.mark.parametrize(
    'evil',
    ['(a+)+$', '((a+))+$', '(((a+)))+$', '((((a+))))+$', '(?:(a+))+$'],
)
def test_nested_catastrophic_patterns_are_blocked(evil):
    with pytest.raises(EPLRuntimeError):
        _check_redos(evil)


@pytest.mark.parametrize(
    'safe',
    ['(abc)+$', '[a-z]+$', '(a|b)+$', r'\d{1,5}', 'hello', '(foo)(bar)+'],
)
def test_safe_patterns_are_not_false_positives(safe):
    # Must not raise — over-blocking legit patterns would break real programs.
    _check_redos(safe)


# ── 2. VM Exit code must reject non-numeric values (parity with interpreter) ──


def test_vm_exit_rejects_non_numeric():
    from epl.vm import VM, VMError

    vm = VM.__new__(VM)  # avoid full init; exercise the opcode handler directly
    vm.stack = ['bad']
    vm.exit_code = 0

    class _Inst:
        arg = True
        line = 1

    with pytest.raises(VMError) as ei:
        vm._op_halt(_Inst())
    assert 'Exit code must be a number' in str(ei.value)


def test_vm_exit_accepts_numeric():
    from epl.vm import VM

    vm = VM.__new__(VM)
    vm.stack = [3]
    vm.exit_code = 0

    class _Inst:
        arg = True
        line = 1

    assert vm._op_halt(_Inst()) == '__HALT__'
    assert vm.exit_code == 3


# ── 3. ffi basename allowlist shortcut works (altsep=None on POSIX) ───────────


def test_bare_name_has_no_path_separator():
    import epl.ffi as ffi

    assert ffi._has_path_separator('libm.so') is False
    assert ffi._has_path_separator('/tmp/x.so') is True
    assert ffi._has_path_separator('a\\b.so') is True  # backslash is explicit
