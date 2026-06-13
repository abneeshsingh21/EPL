"""
EPL — English Programming Language v9.0 (enterprise hardening release)
A production-ready independent programming language with English syntax.

v9.0 highlights — security & robustness sweep:
- SQL identifier validation across db_update/db_delete/db_count/db_table_info
  and the QueryBuilder / database_real CRUD helpers (defense-in-depth).
- exec_async no longer uses shell=True; accepts argv lists or shlex-parsed
  strings, sandbox-blocked alongside kill_process and env_delete.
- AI cloud config moved out of the package directory to a per-user XDG path
  (~/.config/epl/ai_config.json or %APPDATA%\\epl\\), chmod 0600, Gemini key
  sent via x-goog-api-key header instead of URL.
- Generators raise EPLRuntimeError on yield-timeout (was: silent stale value);
  per-yield timeout configurable via EPL_GENERATOR_TIMEOUT.
- `epl watch` no longer hard-caps each run at 60s; --timeout=<seconds|none>.
- `epl serve` defaults --host to 127.0.0.1 and warns on 0.0.0.0.
- main.py error reporting standardized via _cli_error_report/_cli_error_exit
  helpers (EPL_DEBUG=1 / --debug for full tracebacks).

Targets: Bytecode VM (default), Interpreter, LLVM Native, JavaScript, Node.js,
         Kotlin/Android, MicroPython/IoT, Desktop (Compose), Web (JS/WASM/Kotlin-JS)
Features: Web Framework, GUI, Package Manager, ORM, Debugger, LSP, Testing,
          AI Assistant, C FFI, Desktop Apps, Mobile Apps, Web SPAs
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__version__ = '9.5.0'
__author__ = 'Abneesh Singh'
__email__ = 'singhabneesh250@gmail.com'
__license__ = 'Apache 2.0'
__copyright__ = 'Copyright (c) 2024–2026 Abneesh Singh'
__repo__ = 'https://github.com/abneeshsingh21/EPL'

if TYPE_CHECKING:
    from epl.environment import Environment
    from epl.errors import EPLError
    from epl.interpreter import Interpreter
    from epl.lexer import Lexer
    from epl.parser import Parser

_LAZY_EXPORTS = {
    'Lexer': ('epl.lexer', 'Lexer'),
    'Parser': ('epl.parser', 'Parser'),
    'Interpreter': ('epl.interpreter', 'Interpreter'),
    'Environment': ('epl.environment', 'Environment'),
    'EPLError': ('epl.errors', 'EPLError'),
}

__all__ = [
    '__version__',
    '__author__',
    'Lexer',
    'Parser',
    'Interpreter',
    'Environment',
    'EPLError',
]


def __getattr__(name: str) -> Any:
    """Keep package import lightweight while preserving the public API."""
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'epl' has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
