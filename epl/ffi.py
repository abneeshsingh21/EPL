"""
EPL C FFI Module (Phase 5.4)
============================
Provides Foreign Function Interface to call C libraries directly from EPL.

Uses Python's ctypes under the hood for safe, portable C interop.

SECURITY: FFI is powerful and potentially dangerous. When running untrusted
code, set EPL_FFI_SANDBOX=1 to block all FFI calls. Use EPL_FFI_ALLOWLIST
to restrict which libraries can be loaded (comma-separated).

EPL usage:
    Set lib to ffi_open("libm.so")          Note: or .dll / .dylib
    Set result to ffi_call(lib, "sqrt", "double", [3.14], ["double"])
    Say result
    ffi_close(lib)

Supported types: "int", "long", "float", "double", "char_p" (string),
                 "void", "bool", "uint", "short", "byte", "size_t", "pointer"
"""

import ctypes
import ctypes.util
import os
import sys
import atexit

# ─── Security: FFI Sandbox ────────────────────────────────

# When True, ALL FFI calls are blocked (for running untrusted code)
_SAFE_MODE = os.environ.get('EPL_FFI_SANDBOX', '').strip() in ('1', 'true', 'yes')

# Optional allowlist of library names/paths (comma-separated env var)
_allowlist_raw = os.environ.get('EPL_FFI_ALLOWLIST', '').strip()
_LIBRARY_ALLOWLIST = frozenset(
    lib.strip() for lib in _allowlist_raw.split(',') if lib.strip()
) if _allowlist_raw else None  # None = no restriction (allowlist disabled)


def set_safe_mode(enabled: bool):
    """Enable or disable FFI sandbox mode at runtime."""
    global _SAFE_MODE
    _SAFE_MODE = enabled


def _check_sandbox(action: str = "FFI operation"):
    """Raise error if FFI sandbox is active."""
    if _SAFE_MODE:
        raise PermissionError(
            f"SECURITY: {action} blocked — FFI sandbox is active. "
            f"Unset EPL_FFI_SANDBOX or call ffi.set_safe_mode(False) to allow FFI."
        )


def _check_allowlist(library_path: str):
    """Raise error if library is not in the allowlist (when enabled)."""
    if _LIBRARY_ALLOWLIST is not None:
        # Check both the raw path and the basename
        basename = os.path.basename(library_path)
        if library_path not in _LIBRARY_ALLOWLIST and basename not in _LIBRARY_ALLOWLIST:
            raise PermissionError(
                f"SECURITY: Loading library '{library_path}' is not allowed. "
                f"Allowed libraries: {', '.join(sorted(_LIBRARY_ALLOWLIST))}. "
                f"Update EPL_FFI_ALLOWLIST to add it."
            )


# ─── Type mappings ────────────────────────────────────────

_TYPE_MAP = {
    'int':      ctypes.c_int,
    'uint':     ctypes.c_uint,
    'long':     ctypes.c_long,
    'ulong':    ctypes.c_ulong,
    'short':    ctypes.c_short,
    'ushort':   ctypes.c_ushort,
    'byte':     ctypes.c_byte,
    'ubyte':    ctypes.c_ubyte,
    'float':    ctypes.c_float,
    'double':   ctypes.c_double,
    'char_p':   ctypes.c_char_p,
    'wchar_p':  ctypes.c_wchar_p,
    'bool':     ctypes.c_bool,
    'void':     None,
    'pointer':  ctypes.c_void_p,
    'size_t':   ctypes.c_size_t,
    'int8':     ctypes.c_int8,
    'int16':    ctypes.c_int16,
    'int32':    ctypes.c_int32,
    'int64':    ctypes.c_int64,
    'uint8':    ctypes.c_uint8,
    'uint16':   ctypes.c_uint16,
    'uint32':   ctypes.c_uint32,
    'uint64':   ctypes.c_uint64,
}


def _resolve_type(type_name):
    """Resolve a type name string to a ctypes type."""
    if type_name is None or type_name == 'void':
        return None
    t = _TYPE_MAP.get(type_name)
    if t is None:
        raise ValueError(f"Unknown FFI type: {type_name!r}. "
                         f"Supported: {', '.join(sorted(_TYPE_MAP.keys()))}")
    return t


def _convert_arg(value, type_name):
    """Convert an EPL value to the appropriate ctypes argument."""
    ctype = _resolve_type(type_name)
    if ctype is None:
        return value
    if type_name == 'char_p':
        if isinstance(value, str):
            return value.encode('utf-8')
        return value
    if type_name == 'wchar_p':
        return str(value)
    # Validate numeric ranges for integer types
    if type_name in ('uint', 'uint8', 'uint16', 'uint32', 'uint64', 'ubyte', 'ushort', 'ulong', 'size_t'):
        if isinstance(value, (int, float)) and value < 0:
            raise ValueError(f"Negative value {value} for unsigned type '{type_name}'")
    return ctype(value).value


def _convert_result(raw_result, ret_type):
    """Convert a ctypes result back to an EPL-friendly value."""
    if ret_type is None or ret_type == 'void':
        return None
    if isinstance(raw_result, bytes):
        return raw_result.decode('utf-8')
    if isinstance(raw_result, ctypes.c_char_p):
        v = raw_result.value
        return v.decode('utf-8') if isinstance(v, bytes) else v
    return raw_result


# ─── Library handle wrapper ───────────────────────────────

class FFILibrary:
    """Wraps a loaded shared library for use from EPL."""

    def __init__(self, handle, path):
        self._handle = handle
        self._path = path
        self._cache = {}

    def __del__(self):
        """Release handle on garbage collection."""
        if self._handle is not None:
            self.close()

    def call(self, func_name, ret_type, args, arg_types):
        """Call a C function. Returns the result converted to Python/EPL types."""
        # Validate inputs
        if not isinstance(func_name, str):
            raise TypeError(f"Function name must be a string, got {type(func_name).__name__}")

        if len(args) != len(arg_types):
            raise ValueError(f"Argument count ({len(args)}) doesn't match "
                             f"type count ({len(arg_types)})")

        # Get or cache the function
        key = (func_name, ret_type, tuple(arg_types))
        if key not in self._cache:
            try:
                func = getattr(self._handle, func_name)
            except AttributeError:
                raise AttributeError(f"Function '{func_name}' not found in {self._path}")
            func.restype = _resolve_type(ret_type)
            func.argtypes = [_resolve_type(t) for t in arg_types]
            self._cache[key] = func

        cfunc = self._cache[key]

        # Convert arguments
        converted = [_convert_arg(a, t) for a, t in zip(args, arg_types)]

        # Call
        result = cfunc(*converted)
        return _convert_result(result, ret_type)

    def close(self):
        """Release the library handle."""
        self._handle = None
        self._cache.clear()

    def __repr__(self):
        return f'<FFILibrary {self._path!r}>'


# ─── Public API (called from EPL builtins) ────────────────

_open_libraries = {}


def _cleanup_libraries():
    """Close all open libraries at interpreter shutdown."""
    for lib in list(_open_libraries.values()):
        try:
            lib.close()
        except Exception:
            pass
    _open_libraries.clear()


atexit.register(_cleanup_libraries)


def ffi_open(library_path):
    """
    Open a shared library.
    Accepts: full path, library name (auto-resolves), or standard names like "c", "m".
    Returns an FFILibrary handle.

    Blocked when FFI sandbox is active (EPL_FFI_SANDBOX=1).
    Restricted by allowlist when EPL_FFI_ALLOWLIST is set.
    """
    _check_sandbox(f"Loading library '{library_path}'")
    _check_allowlist(library_path)

    # Try to find the library
    resolved = None

    # Direct path
    if os.path.isfile(library_path):
        resolved = library_path
    else:
        # Try ctypes.util.find_library (handles platform differences)
        found = ctypes.util.find_library(library_path)
        if found:
            resolved = found

    if resolved is None:
        # Try loading directly — CDLL will search system paths
        resolved = library_path

    try:
        handle = ctypes.CDLL(resolved)
    except OSError as e:
        raise OSError(f"Cannot load library '{library_path}': {e}")

    lib = FFILibrary(handle, resolved)
    _open_libraries[id(lib)] = lib
    return lib


def ffi_call(lib, func_name, ret_type='void', args=None, arg_types=None):
    """
    Call a function in a loaded library.

    Parameters:
        lib       - FFILibrary from ffi_open()
        func_name - Name of the C function
        ret_type  - Return type string (e.g., "double", "int", "void")
        args      - List of argument values
        arg_types - List of argument type strings
    """
    _check_sandbox(f"Calling FFI function '{func_name}'")
    if not isinstance(lib, FFILibrary):
        raise TypeError("First argument must be an FFI library handle from ffi_open()")
    if args is None:
        args = []
    if arg_types is None:
        arg_types = []
    return lib.call(func_name, ret_type, args, arg_types)


def ffi_close(lib):
    """Close a library handle."""
    if isinstance(lib, FFILibrary):
        lid = id(lib)
        lib.close()
        _open_libraries.pop(lid, None)


def ffi_find(name):
    """Find a library by name (returns the resolved path or None)."""
    return ctypes.util.find_library(name)


def ffi_types():
    """Return list of supported FFI type names."""
    return sorted(_TYPE_MAP.keys())


# ─── Registration helper (for interpreter integration) ────

def register_ffi_builtins():
    """
    Return the public EPL FFI builtins.

    Keep this mapping limited to the language-level builtin surface. Runtime
    administration helpers like ``ffi_sandbox`` stay import-only so older
    callers that validate the public builtin contract continue to see the
    historical five-entry mapping.
    """
    return {
        'ffi_open':  ffi_open,
        'ffi_call':  ffi_call,
        'ffi_close': ffi_close,
        'ffi_find':  ffi_find,
        'ffi_types': ffi_types,
    }
