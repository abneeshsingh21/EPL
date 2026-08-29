"""
EPL 64-bit IEEE 754 NaN-Boxing Value Engine (v1.0)
==================================================
Encodes all EPL runtime values (integers, floats, booleans, nothing/null,
pointers/references) inside a single 64-bit word using IEEE 754 NaN-boxing.

Layout of 64-bit Value:
  Standard Double: Any 64-bit IEEE 754 float where exponent != 0x7FF (or quiet NaN).
  Quiet NaN prefix: 0x7FF8_0000_0000_0000 (Sign = 0, Exp = 0x7FF, Quiet bit = 1)

Tagged Types (stored within lower 48/32 bits of quiet NaN):
  - Tag Bits (bits 48-50):
      0x1: INT (32-bit signed integer in bits 0-31)
      0x2: BOOL (0 = false, 1 = true)
      0x3: NONE / NOTHING
      0x4: HEAP OBJECT (48-bit pointer / object table index)
      0x5: STRING REFERENCE (48-bit pointer / string table index)
      0x6: LIST REFERENCE
      0x7: MAP REFERENCE

Memory Savings:
  - Reduces tagged value from 16-24 bytes struct to 8 bytes (64-bit integer / double).
  - Enables SIMD registers, cache line density, and zero-allocation primitive passing.
"""

from __future__ import annotations

import struct
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple, Union


# ─── Bitmask Constants ───────────────────────────────────────

# QNAN mask (Sign = 0, Exp = 11111111111b, Quiet bit = 1)
QNAN_MASK: int = 0x7FF8_0000_0000_0000

# Tag definitions in bits 48..51
TAG_INT: int = 0x7FF8_0001_0000_0000
TAG_BOOL: int = 0x7FF8_0002_0000_0000
TAG_NONE: int = 0x7FF8_0003_0000_0000
TAG_OBJECT: int = 0x7FF8_0004_0000_0000
TAG_STRING: int = 0x7FF8_0005_0000_0000
TAG_LIST: int = 0x7FF8_0006_0000_0000
TAG_MAP: int = 0x7FF8_0007_0000_0000

TAG_MASK: int = 0xFFFF_FFFF_0000_0000
PAYLOAD_MASK: int = 0x0000_0000_FFFF_FFFF
SIGN_MASK_32: int = 0x8000_0000


class ValueType(IntEnum):
    FLOAT = 0
    INT = 1
    BOOL = 2
    NONE = 3
    OBJECT = 4
    STRING = 5
    LIST = 6
    MAP = 7


class NaNBoxEngine:
    """
    Core NaN-boxing encoder/decoder and heap reference table manager.
    """

    def __init__(self):
        # Heap object table for mapping 32-bit integer IDs to Python objects
        self._heap_table: List[Any] = [None]  # Index 0 is reserved
        self._obj_to_id: Dict[int, int] = {}

    def clear(self) -> None:
        self._heap_table = [None]
        self._obj_to_id.clear()

    # ─── Encoding Methods ────────────────────────────────────

    @staticmethod
    def encode_float(f: float) -> int:
        """Encode a 64-bit IEEE 754 float into a 64-bit integer word."""
        bits = struct.unpack('<Q', struct.pack('<d', float(f)))[0]
        # Canonicalize NaNs to prevent collision with tagged types
        if (bits & 0x7FF0_0000_0000_0000) == 0x7FF0_0000_0000_0000:
            return 0x7FF8_0000_0000_0000  # Canonical quiet NaN
        return bits

    @staticmethod
    def encode_int(i: int) -> int:
        """Encode a signed 32-bit integer into a tagged NaN."""
        u32 = i & PAYLOAD_MASK
        return TAG_INT | u32

    @staticmethod
    def encode_bool(b: bool) -> int:
        """Encode a boolean (True=1, False=0) into a tagged NaN."""
        return TAG_BOOL | (1 if b else 0)

    @staticmethod
    def encode_none() -> int:
        """Encode nothing/null into a tagged NaN."""
        return TAG_NONE

    def encode_heap_obj(self, obj: Any, tag: int = TAG_OBJECT) -> int:
        """Allocate or lookup heap table ID and return tagged pointer."""
        obj_id = id(obj)
        if obj_id in self._obj_to_id:
            idx = self._obj_to_id[obj_id]
        else:
            idx = len(self._heap_table)
            self._heap_table.append(obj)
            self._obj_to_id[obj_id] = idx
        return tag | (idx & PAYLOAD_MASK)

    def encode(self, val: Any) -> int:
        """Encode any Python / EPL runtime value into a 64-bit NaN-boxed word."""
        if val is None:
            return self.encode_none()
        if isinstance(val, bool):
            return self.encode_bool(val)
        if isinstance(val, int) and -2147483648 <= val <= 2147483647:
            return self.encode_int(val)
        if isinstance(val, (int, float)):
            return self.encode_float(float(val))
        if isinstance(val, str):
            return self.encode_heap_obj(val, TAG_STRING)
        if isinstance(val, list):
            return self.encode_heap_obj(val, TAG_LIST)
        if isinstance(val, dict):
            return self.encode_heap_obj(val, TAG_MAP)
        return self.encode_heap_obj(val, TAG_OBJECT)

    # ─── Type Inspection Methods ─────────────────────────────

    @staticmethod
    def get_type(word: int) -> ValueType:
        if (word & 0x7FF8_0000_0000_0000) != 0x7FF8_0000_0000_0000:
            return ValueType.FLOAT

        tag = word & TAG_MASK
        if tag == TAG_INT:
            return ValueType.INT
        if tag == TAG_BOOL:
            return ValueType.BOOL
        if tag == TAG_NONE:
            return ValueType.NONE
        if tag == TAG_STRING:
            return ValueType.STRING
        if tag == TAG_LIST:
            return ValueType.LIST
        if tag == TAG_MAP:
            return ValueType.MAP
        if tag == TAG_OBJECT:
            return ValueType.OBJECT
        return ValueType.FLOAT

    @staticmethod
    def is_float(word: int) -> bool:
        return (word & 0x7FF8_0000_0000_0000) != 0x7FF8_0000_0000_0000

    @staticmethod
    def is_int(word: int) -> bool:
        return (word & TAG_MASK) == TAG_INT

    @staticmethod
    def is_bool(word: int) -> bool:
        return (word & TAG_MASK) == TAG_BOOL

    @staticmethod
    def is_none(word: int) -> bool:
        return (word & TAG_MASK) == TAG_NONE

    @staticmethod
    def is_string(word: int) -> bool:
        return (word & TAG_MASK) == TAG_STRING

    @staticmethod
    def is_list(word: int) -> bool:
        return (word & TAG_MASK) == TAG_LIST

    @staticmethod
    def is_map(word: int) -> bool:
        return (word & TAG_MASK) == TAG_MAP

    # ─── Decoding Methods ────────────────────────────────────

    @staticmethod
    def decode_float(word: int) -> float:
        return struct.unpack('<d', struct.pack('<Q', word))[0]

    @staticmethod
    def decode_int(word: int) -> int:
        u32 = word & PAYLOAD_MASK
        if u32 & SIGN_MASK_32:
            return u32 - 0x1_0000_0000
        return u32

    @staticmethod
    def decode_bool(word: int) -> bool:
        return (word & 1) == 1

    def decode_heap_obj(self, word: int) -> Any:
        idx = word & PAYLOAD_MASK
        if 0 < idx < len(self._heap_table):
            return self._heap_table[idx]
        return None

    def decode(self, word: int) -> Any:
        """Decode a 64-bit NaN-boxed word back into its Python / EPL value."""
        if (word & 0x7FF8_0000_0000_0000) != 0x7FF8_0000_0000_0000:
            return self.decode_float(word)

        tag = word & TAG_MASK
        if tag == TAG_INT:
            return self.decode_int(word)
        if tag == TAG_BOOL:
            return self.decode_bool(word)
        if tag == TAG_NONE:
            return None
        if tag in (TAG_STRING, TAG_LIST, TAG_MAP, TAG_OBJECT):
            return self.decode_heap_obj(word)
        return self.decode_float(word)


# Global default engine instance for zero-allocation calls
_DEFAULT_ENGINE = NaNBoxEngine()


def val_encode(v: Any) -> int:
    return _DEFAULT_ENGINE.encode(v)


def val_decode(w: int) -> Any:
    return _DEFAULT_ENGINE.decode(w)
