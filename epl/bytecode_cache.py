"""
EPL Bytecode Cache (.eplc files)
Serializes parsed AST to disk for faster subsequent loads.

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
import pickle
import struct
from pathlib import Path

_MAGIC = b'EPLC'
_FORMAT_VERSION = 2  # Bumped: v2 uses safe unpickler
_HEADER_SIZE = 4 + 2 + 32  # magic + version + sha256

# Modules allowed during deserialization — ONLY EPL AST nodes and builtins
_SAFE_MODULES = frozenset({
    'epl.ast_nodes',
    'builtins',
    'collections',
})


class _SafeUnpickler(pickle.Unpickler):
    """Restricted unpickler that blocks arbitrary class instantiation.

    Only allows classes from whitelisted modules (EPL AST nodes and Python
    builtins). This prevents Remote Code Execution from malicious .eplc files.
    """

    def find_class(self, module: str, name: str):
        if module not in _SAFE_MODULES:
            raise pickle.UnpicklingError(
                f"SECURITY: Blocked deserialization of {module}.{name}. "
                f"Only EPL AST nodes are allowed in .eplc files. "
                f"This file may be corrupted or malicious."
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
    path.write_bytes(header + ast_data)


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
        return None


def cache_path_for(source_path) -> Path:
    """Return the .eplc cache path for a given .epl source path."""
    return Path(source_path).with_suffix('.eplc')
