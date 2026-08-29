"""
EPL Monomorphic & Polymorphic Inline Caching (MIC / PIC) Engine (v1.0)
======================================================================
Optimizes dynamic method dispatch and property access in the EPL Virtual Machine
and Interpreter by eliminating repeated dictionary / vtable lookups at call sites.

Inline Cache Lifecycle:
  1. UNINITIALIZED: Call site has not yet recorded receiver types.
  2. MONOMORPHIC: Single receiver type seen. Direct fast-path call.
  3. POLYMORPHIC: 2 to 4 distinct receiver types seen. Small array scan.
  4. MEGAMORPHIC: > 4 receiver types seen. Falls back to global dictionary lookup.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


class CacheState(Enum):
    UNINITIALIZED = auto()
    MONOMORPHIC = auto()
    POLYMORPHIC = auto()
    MEGAMORPHIC = auto()


class MethodCallSite:
    """
    Inline Cache for a single method invocation site in bytecode or AST.
    """

    MAX_POLYMORPHIC_ENTRIES = 4

    def __init__(self, method_name: str, site_id: int = 0):
        self.method_name = method_name
        self.site_id = site_id
        self.state: CacheState = CacheState.UNINITIALIZED
        # Monomorphic cache slots
        self._mono_type: Optional[type] = None
        self._mono_method: Optional[Callable] = None
        # Polymorphic cache list: [(type, method), ...]
        self._poly_entries: List[Tuple[type, Callable]] = []
        # Metrics
        self.hit_count: int = 0
        self.miss_count: int = 0

    def _invoke(self, method: Callable, receiver: Any, args: list) -> Any:
        if hasattr(method, '__self__') and getattr(method, '__self__', None) is not None:
            return method(*args)
        try:
            return method(receiver, *args)
        except TypeError:
            return method(*args)

    def resolve_and_call(
        self, receiver: Any, args: list, fallback_lookup: Callable[[Any, str], Callable]
    ) -> Any:
        """Fast-path dispatch with inline caching."""
        rec_type = type(receiver)

        # ── 1. Monomorphic Fast Path ──
        if self.state == CacheState.MONOMORPHIC:
            if rec_type is self._mono_type:
                self.hit_count += 1
                return self._invoke(self._mono_method, receiver, args)
            # Cache miss: upgrade to polymorphic
            self.miss_count += 1
            method = fallback_lookup(receiver, self.method_name)
            self._poly_entries = [(self._mono_type, self._mono_method), (rec_type, method)]
            self._mono_type = None
            self._mono_method = None
            self.state = CacheState.POLYMORPHIC
            return self._invoke(method, receiver, args)

        # ── 2. Polymorphic Fast Path ──
        if self.state == CacheState.POLYMORPHIC:
            for cached_type, cached_method in self._poly_entries:
                if rec_type is cached_type:
                    self.hit_count += 1
                    return self._invoke(cached_method, receiver, args)

            # Polymorphic miss
            self.miss_count += 1
            method = fallback_lookup(receiver, self.method_name)
            if len(self._poly_entries) < self.MAX_POLYMORPHIC_ENTRIES:
                self._poly_entries.append((rec_type, method))
            else:
                # Transition to Megamorphic
                self.state = CacheState.MEGAMORPHIC
                self._poly_entries.clear()
            return self._invoke(method, receiver, args)

        # ── 3. Uninitialized Path ──
        if self.state == CacheState.UNINITIALIZED:
            method = fallback_lookup(receiver, self.method_name)
            self._mono_type = rec_type
            self._mono_method = method
            self.state = CacheState.MONOMORPHIC
            self.hit_count += 1
            return self._invoke(method, receiver, args)

        # ── 4. Megamorphic Fallback ──
        self.miss_count += 1
        method = fallback_lookup(receiver, self.method_name)
        return self._invoke(method, receiver, args)


class PropertyAccessSite:
    """
    Inline Cache for property / field reads.
    """

    def __init__(self, property_name: str):
        self.property_name = property_name
        self.state: CacheState = CacheState.UNINITIALIZED
        self._mono_type: Optional[type] = None
        self._mono_getter: Optional[Callable] = None
        self._poly_entries: List[Tuple[type, Callable]] = []
        self.hit_count: int = 0
        self.miss_count: int = 0

    def get_property(
        self, receiver: Any, fallback_getter: Callable[[Any, str], Any]
    ) -> Any:
        rec_type = type(receiver)

        if self.state == CacheState.MONOMORPHIC:
            if rec_type is self._mono_type:
                self.hit_count += 1
                return self._mono_getter(receiver)
            self.miss_count += 1
            val = fallback_getter(receiver, self.property_name)
            self._poly_entries = [
                (self._mono_type, self._mono_getter),
                (rec_type, lambda r: fallback_getter(r, self.property_name)),
            ]
            self.state = CacheState.POLYMORPHIC
            return val

        if self.state == CacheState.POLYMORPHIC:
            for c_type, c_getter in self._poly_entries:
                if rec_type is c_type:
                    self.hit_count += 1
                    return c_getter(receiver)
            self.miss_count += 1
            if len(self._poly_entries) < 4:
                self._poly_entries.append(
                    (rec_type, lambda r: fallback_getter(r, self.property_name))
                )
            else:
                self.state = CacheState.MEGAMORPHIC
                self._poly_entries.clear()
            return fallback_getter(receiver, self.property_name)

        if self.state == CacheState.UNINITIALIZED:
            val = fallback_getter(receiver, self.property_name)
            self._mono_type = rec_type
            self._mono_getter = lambda r: fallback_getter(r, self.property_name)
            self.state = CacheState.MONOMORPHIC
            self.hit_count += 1
            return val

        self.miss_count += 1
        return fallback_getter(receiver, self.property_name)
