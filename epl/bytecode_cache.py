"""
EPL Bytecode Cache (.eplc files)
Serializes parsed AST to disk for faster subsequent loads.

Cache files live in a per-user cache directory (NOT next to the source), so
they never clutter a user's project or VS Code explorer and are never at risk
of being committed. Each source file gets its own subdirectory keyed by the
hash of its absolute path, and the human-readable filename is preserved inside
it (e.g. <cache_root>/<path-hash>/hello.eplc). Set EPL_CACHE_DIR to relocate
the cache, or EPL_NO_CACHE=1 to disable caching entirely.

File format (v3):
  - 4 bytes:  magic b'EPLC'
  - 2 bytes:  format version (uint16 LE)
  - 32 bytes: SHA-256 hash of source code (staleness / source binding)
  - 32 bytes: HMAC-SHA256(cache_key, source_hash || pickled_AST) (authenticity)
  - remainder: pickled AST (Protocol 5)

SECURITY: two independent defenses against the classic pickle-deserialization
RCE (a crafted .eplc that executes code on load):

  1. A restricted unpickler that only resolves classes actually defined in
     ``epl.ast_nodes``. It never resolves ``builtins`` (eval/exec/getattr/...)
     or any other module, so there is no callable a REDUCE opcode could invoke.

  2. An HMAC keyed by a per-user secret (mode 0600, in the cache root). A file
     written by anyone who does not hold the key fails verification and is
     rejected. The SHA-256 header is only a staleness check — it is NOT an
     authenticity control (the source is attacker-readable), so the HMAC is
     what actually stops foreign-written or substituted cache files.
"""

import hashlib
import hmac
import io
import os
import pickle
import struct
from pathlib import Path

from epl import _debug_log

_MAGIC = b'EPLC'
_FORMAT_VERSION = 3  # v3: AST-only unpickler + HMAC authenticity
_HMAC_SIZE = 32
_HEADER_SIZE = 4 + 2 + 32 + _HMAC_SIZE  # magic + version + sha256 + hmac
_KEY_FILENAME = '.eplc_key'


def _known_ast_nodes() -> frozenset:
    """The set of class names legitimately defined in ``epl.ast_nodes``.

    Built once by reflection so new AST node types are covered automatically
    without touching this allowlist. Only genuine classes whose ``__module__``
    is ``epl.ast_nodes`` are included — nothing else may be deserialized.
    """
    try:
        from epl import ast_nodes
    except Exception:
        return frozenset()
    return frozenset(
        name
        for name, obj in vars(ast_nodes).items()
        if isinstance(obj, type) and getattr(obj, '__module__', None) == 'epl.ast_nodes'
    )


_KNOWN_AST_NODES = _known_ast_nodes()


class _SafeUnpickler(pickle.Unpickler):
    """Restricted unpickler that blocks arbitrary class instantiation.

    Resolves ONLY classes defined in ``epl.ast_nodes``. Every other module —
    ``builtins`` included — is denied, so a crafted stream has no callable to
    drive a REDUCE-based code-execution gadget.
    """

    def find_class(self, module: str, name: str):
        if module != 'epl.ast_nodes' or name not in _KNOWN_AST_NODES:
            raise pickle.UnpicklingError(
                f'SECURITY: Blocked deserialization of {module}.{name}. '
                f'Only EPL AST node classes are allowed in .eplc files. '
                f'This file may be corrupted or malicious.'
            )
        return super().find_class(module, name)


def _cache_key():
    """Return the per-user HMAC key, creating it on first use.

    The key is 32 random bytes stored mode-0600 in the cache root. If it cannot
    be created or read (e.g. a read-only cache dir), returns None and the caller
    degrades to *no caching* — never to an unauthenticated cache.
    """
    try:
        root = _cache_root()
        root.mkdir(parents=True, exist_ok=True)
        key_path = root / _KEY_FILENAME
        if key_path.exists():
            data = key_path.read_bytes()
            if len(data) >= 32:
                return data[:32]
        # Create a fresh key with restrictive permissions.
        key = os.urandom(32)
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        try:
            os.chmod(str(key_path), 0o600)
        except OSError:
            pass
        return key
    except Exception:
        _debug_log.suppressed('bytecode_cache:_cache_key')
        return None


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
    key = _cache_key()
    if key is None:
        # No authenticity key available — degrade to no-cache rather than
        # writing a file we could not later trust.
        return
    path = Path(path)
    src_hash = _source_hash(source)
    ast_data = pickle.dumps(program, protocol=5)
    mac = hmac.new(key, src_hash + ast_data, hashlib.sha256).digest()
    header = _MAGIC + struct.pack('<H', _FORMAT_VERSION) + src_hash + mac
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

    # Validate source hash (staleness / source binding)
    stored_hash = data[6:38]
    if stored_hash != _source_hash(source):
        return None

    # Validate HMAC (authenticity) — reject any file not produced with our key.
    key = _cache_key()
    if key is None:
        return None
    stored_mac = data[38:70]
    payload = data[70:]
    expected_mac = hmac.new(key, stored_hash + payload, hashlib.sha256).digest()
    if not hmac.compare_digest(stored_mac, expected_mac):
        return None

    try:
        # SECURITY: Use restricted unpickler instead of pickle.loads()
        return _SafeUnpickler(io.BytesIO(payload)).load()
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
