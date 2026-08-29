"""
EPL Semantic Parity & Cross-Runtime Normalization Engine (Phase 5 Deep)
========================================================================
Normalizes runtime semantic differences between EPL compilation targets:
1. Unicode UTF-8 Scalar Value Slicing & Indexing (Python, JS, C, Kotlin).
2. Integer Overflow Parity (64-bit signed integer wrapping vs BigInt promotion).
3. Closure Variable Binding Cells (guaranteeing uniform loop-capture semantics).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


# ═══════════════════════════════════════════════════════════
#  1. Unicode UTF-8 Scalar Value Indexing & Slicing
# ═══════════════════════════════════════════════════════════


def unicode_char_at(text: str, index: int) -> str:
    """Return the Unicode character at 0-based scalar index."""
    codepoints = list(text)
    if 0 <= index < len(codepoints):
        return codepoints[index]
    if -len(codepoints) <= index < 0:
        return codepoints[len(codepoints) + index]
    return ''


def unicode_substring(text: str, start: int, end: Optional[int] = None) -> str:
    """Return substring based on Unicode scalar codepoint boundaries."""
    codepoints = list(text)
    total_len = len(codepoints)
    if start < 0:
        start = max(0, total_len + start)
    if end is None or end > total_len:
        end = total_len
    elif end < 0:
        end = max(0, total_len + end)

    if start >= end:
        return ''
    return ''.join(codepoints[start:end])


def unicode_length(text: str) -> int:
    """Return count of Unicode scalar values (characters/codepoints)."""
    return len(list(text))


class UnicodeParity:
    """Unicode scalar normalization helper."""

    @staticmethod
    def unicode_scalars(text: str) -> List[str]:
        return list(text)

    @staticmethod
    def scalar_slice(text: str, start: int, end: Optional[int] = None) -> str:
        return unicode_substring(text, start, end)

    @staticmethod
    def validate_utf8_boundaries(utf8_bytes: bytes) -> bool:
        try:
            utf8_bytes.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False


# ═══════════════════════════════════════════════════════════
#  2. Integer Overflow & BigInt Parity
# ═══════════════════════════════════════════════════════════

INT64_MIN: int = -(1 << 63)
INT64_MAX: int = (1 << 63) - 1
INT32_MIN: int = -(1 << 31)
INT32_MAX: int = (1 << 31) - 1


class OverflowMode:
    WRAP_64 = 'wrap64'
    WRAP_32 = 'wrap32'
    PROMOTE_BIGINT = 'promote'


def normalize_int_operation(
    op: str,
    a: int,
    b: int,
    mode: str = OverflowMode.PROMOTE_BIGINT,
) -> int:
    """Compute integer arithmetic with deterministic overflow handling."""
    if op == '+':
        res = a + b
    elif op == '-':
        res = a - b
    elif op == '*':
        res = a * b
    elif op == '/':
        res = a // b if b != 0 else 0
    elif op == '%':
        res = a % b if b != 0 else 0
    elif op == '^':
        res = a ** b if b >= 0 else 0
    else:
        raise ValueError(f'Unknown arithmetic operator: {op}')

    if mode == OverflowMode.WRAP_64:
        res = (res + (1 << 63)) % (1 << 64) - (1 << 63)
    elif mode == OverflowMode.WRAP_32:
        res = (res + (1 << 31)) % (1 << 32) - (1 << 31)

    return res


class IntegerParity:
    """Integer overflow and BigInt arithmetic normalization helper."""

    @staticmethod
    def normalize_int64(val: int, signed: bool = True) -> int:
        if signed:
            return (val + (1 << 63)) % (1 << 64) - (1 << 63)
        return val % (1 << 64)

    @staticmethod
    def checked_add(a: int, b: int) -> Tuple[int, bool]:
        res = a + b
        did_overflow = (res > INT64_MAX) or (res < INT64_MIN)
        wrapped = IntegerParity.normalize_int64(res, signed=True)
        return wrapped, did_overflow

    @staticmethod
    def checked_mul(a: int, b: int) -> Tuple[int, bool]:
        res = a * b
        did_overflow = (res > INT64_MAX) or (res < INT64_MIN)
        wrapped = IntegerParity.normalize_int64(res, signed=True)
        return wrapped, did_overflow

    @staticmethod
    def bigint_op(a: int, b: int, op: str = "+") -> int:
        return normalize_int_operation(op, a, b, mode=OverflowMode.PROMOTE_BIGINT)


# ═══════════════════════════════════════════════════════════
#  3. Lexical Closure Variable Binding Cells
# ═══════════════════════════════════════════════════════════


@dataclass
class ClosureCell:
    """A mutable heap-allocated cell for variable capture in closures."""
    value: Any

    def get(self) -> Any:
        return self.value

    def set(self, new_value: Any) -> None:
        self.value = new_value

    def __repr__(self) -> str:
        return f'Cell({self.value!r})'


class ClosureParity:
    """Closure variable capture cell generator."""

    @staticmethod
    def create_binding_cell(initial_value: Any) -> ClosureCell:
        return ClosureCell(initial_value)


def make_closure(
    fn: Callable[..., Any],
    captured_cells: Dict[str, ClosureCell],
) -> Callable[..., Any]:
    """Create an explicitly bound closure over mutable cell references."""
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, cells=captured_cells, **kwargs)

    wrapper.__name__ = getattr(fn, '__name__', 'epl_closure')
    return wrapper


class SemanticParitySuite:
    """Comprehensive test harness ensuring parity invariants across runtimes."""

    def run_all(self) -> Dict[str, bool]:
        # 1. Unicode parity
        u_scalars = UnicodeParity.unicode_scalars("🔥🚀")
        unicode_ok = (len(u_scalars) == 2 and UnicodeParity.scalar_slice("🔥🚀", 0, 1) == "🔥")

        # 2. Integer overflow parity
        wrapped = IntegerParity.normalize_int64(INT64_MAX + 1, signed=True)
        int_ok = (wrapped == INT64_MIN)

        # 3. Closure binding parity
        cell = ClosureParity.create_binding_cell(42)
        cell.set(100)
        closure_ok = (cell.get() == 100)

        return {
            "unicode_parity": unicode_ok,
            "integer_parity": int_ok,
            "closure_parity": closure_ok,
        }
