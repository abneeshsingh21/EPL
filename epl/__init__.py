"""
EPL - English Programming Language v7.0
A production-ready independent programming language with English syntax.

Phase 6: Mobile & Desktop (Build Apps with UIs)
- 6a Desktop GUI: Compose Multiplatform Desktop apps with native packaging (MSI/DMG/DEB/RPM)
- 6b Android: Enhanced Jetpack Compose + Views, Room DB, Retrofit, Navigation, APK build
- 6c Web Apps: Browser-ready SPAs via JS transpilation, WASM+JS glue, Kotlin/JS, PWA support

Targets: Bytecode VM (default), Interpreter, LLVM Native, JavaScript, Node.js,
         Kotlin/Android, MicroPython/IoT, Desktop (Compose), Web (JS/WASM/Kotlin-JS)
Features: Web Framework, GUI, Package Manager, ORM, Debugger, LSP, Testing,
          AI Assistant, C FFI, Desktop Apps, Mobile Apps, Web SPAs
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__version__ = "7.4.0"
__author__  = "Abneesh Singh"
__email__   = "singhabneesh250@gmail.com"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2024–2026 Abneesh Singh"

if TYPE_CHECKING:
    from epl.environment import Environment
    from epl.errors import EPLError
    from epl.interpreter import Interpreter
    from epl.lexer import Lexer
    from epl.parser import Parser

_LAZY_EXPORTS = {
    "Lexer": ("epl.lexer", "Lexer"),
    "Parser": ("epl.parser", "Parser"),
    "Interpreter": ("epl.interpreter", "Interpreter"),
    "Environment": ("epl.environment", "Environment"),
    "EPLError": ("epl.errors", "EPLError"),
}

__all__ = [
    "__version__",
    "__author__",
    "Lexer",
    "Parser",
    "Interpreter",
    "Environment",
    "EPLError",
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
