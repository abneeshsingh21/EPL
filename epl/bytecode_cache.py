"""
EPL Bytecode Cache (.eplc files)
Serializes parsed AST to disk for faster subsequent loads.

Cache files live in a per-user cache directory (NOT next to the source), so
they never clutter a user's project or VS Code explorer and are never at risk
of being committed. Each source file gets its own subdirectory keyed by the
hash of its absolute path, and the human-readable filename is preserved inside
it (e.g. <cache_root>/<path-hash>/hello.eplc). Set EPL_CACHE_DIR to relocate
the cache, or EPL_NO_CACHE=1 to disable caching entirely.

File format:
  - 4 bytes: magic b'EPLC'
  - 2 bytes: format version (uint16 LE)
  - 32 bytes: SHA-256 hash of source code
  - remainder: pickled AST (Protocol 5)

SECURITY: Uses a restricted unpickler that only allows EPL AST node classes
and Python builtins. This prevents arbitrary code execution from crafted
.eplc files (CVE-style pickle deserialization attack).
"""

import hashlib
import io
import os
import pickle
import struct
from pathlib import Path

from epl import _debug_log

_MAGIC = b'EPLC'
_FORMAT_VERSION = 2  # Bumped: v2 uses safe unpickler
_HEADER_SIZE = 4 + 2 + 32  # magic + version + sha256

# Modules allowed during deserialization — ONLY EPL AST nodes and builtins
_SAFE_MODULES = frozenset(
    {
        'epl.ast_nodes',
        'builtins',
        'collections',
    }
)


class _SafeUnpickler(pickle.Unpickler):
    """Restricted unpickler that blocks arbitrary class instantiation.

    Only allows classes from whitelisted modules (EPL AST nodes and Python
    builtins). This prevents Remote Code Execution from malicious .eplc files.
    """

    def find_class(self, module: str, name: str):
        if module not in _SAFE_MODULES:
            raise pickle.UnpicklingError(
                f'SECURITY: Blocked deserialization of {module}.{name}. '
                f'Only EPL AST nodes are allowed in .eplc files. '
                f'This file may be corrupted or malicious.'
            )
        return super().find_class(module, name)


def _source_hash(source: str) -> bytes:
    """Compute SHA-256 of source text."""
    return hashlib.sha256(source.encode('utf-8')).digest()


def save(program, source: str, path) -> None:
    """Serialize a parsed AST (Program node) to an .eplc file.

    Args:
        program: The ast.Program node from the parser.
        source: The original source code (used for cache invalidation).
        path: File path to write (str or Path).
    """
    path = Path(path)
    header = _MAGIC + struct.pack('<H', _FORMAT_VERSION) + _source_hash(source)
    ast_data = pickle.dumps(program, protocol=5)
    # The cache lives in a per-user directory, so the target subdirectory may
    # not exist yet — create it before writing.
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file + rename so a crash mid-write never produces a corrupt .eplc
    tmp = path.with_suffix('.eplc.tmp')
    try:
        tmp.write_bytes(header + ast_data)
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def load(source: str, path):
    """Load a cached AST from an .eplc file.

    Returns the Program node if the cache is valid (magic, version, and source
    hash all match), otherwise returns None.

    Uses a restricted unpickler to prevent arbitrary code execution.

    Args:
        source: The current source code for hash verification.
        path: Path to the .eplc file (str or Path).
    """
    path = Path(path)
    if not path.exists():
        return None

    data = path.read_bytes()
    if len(data) < _HEADER_SIZE:
        return None

    # Validate magic
    if data[:4] != _MAGIC:
        return None

    # Validate format version
    version = struct.unpack('<H', data[4:6])[0]
    if version != _FORMAT_VERSION:
        return None

    # Validate source hash
    stored_hash = data[6:38]
    if stored_hash != _source_hash(source):
        return None

    try:
        # SECURITY: Use restricted unpickler instead of pickle.loads()
        return _SafeUnpickler(io.BytesIO(data[38:])).load()
    except pickle.UnpicklingError:
        # Security violation or corrupted cache — silently reject
        return None
    except Exception:
        _debug_log.suppressed('bytecode_cache:119')
        return None


def _cache_root() -> Path:
    """Return the per-user root directory for EPL caches.

    Honors EPL_CACHE_DIR; otherwise uses the platform-conventional cache
    location (%LOCALAPPDATA% on Windows, $XDG_CACHE_HOME or ~/.cache elsewhere).
    """
    override = os.environ.get('EPL_CACHE_DIR')
    if override:
        return Path(override)
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
        return Path(base) / 'eplang' / 'cache'
    base = os.environ.get('XDG_CACHE_HOME') or os.path.expanduser('~/.cache')
    return Path(base) / 'eplang'


def cache_path_for(source_path):
    """Return the per-user .eplc cache path for a given .epl source path.

    The cache is centralized (never written next to the source), so it never
    clutters the user's project. Each source file maps to its own subdirectory
    keyed by the hash of its absolute path — this avoids collisions between
    same-named files in different directories while preserving the readable
    filename inside. Returns None when caching is disabled via EPL_NO_CACHE.
    """
    if os.environ.get('EPL_NO_CACHE', '').strip().lower() in ('1', 'true', 'yes', 'on'):
        return None
    src = Path(source_path)
    abs_source = os.path.abspath(str(src))
    # Case-fold the key on case-insensitive platforms so the same file resolves
    # to one cache entry regardless of how its path was typed.
    key_source = abs_source.lower() if os.name == 'nt' else abs_source
    path_hash = hashlib.sha256(key_source.encode('utf-8')).hexdigest()[:16]
    return _cache_root() / path_hash / (src.stem + '.eplc')
