"""
EPL Error System v5.0
Provides clear, English-language error messages with helpful suggestions.
Includes full exception hierarchy, custom exceptions, and finally support.
Production-grade: ANSI colors, source context, error codes, "did you mean?" suggestions.
Structured JSON output for tool integration.
"""

import json
import os
import sys
import difflib


# ─── ANSI Color Support ─────────────────────────────────
def _supports_color():
    """Check if the terminal supports ANSI color codes."""
    if os.environ.get('NO_COLOR') or os.environ.get('EPL_NO_COLOR'):
        return False
    if os.environ.get('FORCE_COLOR') or os.environ.get('EPL_FORCE_COLOR'):
        return True
    if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
        return True
    return False

_COLOR = _supports_color()

def _red(s):    return f"\033[31m{s}\033[0m" if _COLOR else s
def _bold(s):   return f"\033[1m{s}\033[0m" if _COLOR else s
def _dim(s):    return f"\033[2m{s}\033[0m" if _COLOR else s
def _yellow(s): return f"\033[33m{s}\033[0m" if _COLOR else s
def _cyan(s):   return f"\033[36m{s}\033[0m" if _COLOR else s
def _green(s):  return f"\033[32m{s}\033[0m" if _COLOR else s


# ─── Error Codes ─────────────────────────────────────────
ERROR_CODES = {
    'LexerError':       'E0100',
    'ParserError':      'E0200',
    'RuntimeError':     'E0300',
    'TypeError':        'E0400',
    'NameError':        'E0500',
    'ValueError':       'E0600',
    'IndexError':       'E0700',
    'KeyError':         'E0800',
    'IOError':          'E0900',
    'NetworkError':     'E1000',
    'TimeoutError':     'E1100',
    'OverflowError':    'E1200',
    'ImportError':      'E1300',
    'AttributeError':   'E1400',
    'AssertionError': 'E1500',
    'ConcurrencyError': 'E1600',
    'EPLError':         'E0000',
}


# ─── Suggestion hints for common mistakes ────────────────
_HINTS = {
    'unexpected token': 'Check for missing periods at end of statements, or reserved keywords used as variable names.',
    'expected a variable name': 'Some words are reserved (e.g., "a", "text", "port", "debug", "match"). Try a different variable name.',
    'undefined variable': 'Make sure you declared the variable with "Create X equal to ..." or "Remember X as ..." first.',
    'undefined function': 'Check spelling. Built-in functions include: length(), print(), sqrt(), sorted(), range(), etc.',
    'not callable': 'You are trying to call something that is not a function. Not every name is a function.',
    'divide by zero': 'Division by zero is not allowed. Check the denominator value.',
    'index out of range': 'The index is beyond the list boundaries. Use length() to check list size.',
    'expected "end"': 'Every block (If, While, For, Function, Class, Try, Interface, Module) must be closed with "End".',
    'type mismatch': 'You cannot mix incompatible types. Use to_text() or to_integer() to convert.',
    'cannot assign': 'Type-checked variables can only hold values of their declared type.',
    'expected "->"': 'Lambda syntax uses "->": lambda x -> x + 1',
    'expected "="': 'Constants use "=": Constant PI = 3.14',
    'interface': 'Interfaces define method signatures. Classes use "implements" to adopt them.',
    'module': 'Modules group related code. Access with Module::function() or Import "module".',
    'finally': 'Finally blocks always run, even if an error occurs. Use for cleanup.',
    'key not found': 'The key does not exist in the map. Use has_key() to check first.',
    'file not found': 'The file path does not exist. Check spelling and ensure the file is accessible.',
    'permission denied': 'Insufficient permissions. Check file or resource permissions.',
    'connection': 'Network error. Check connectivity and the endpoint address.',
    'timeout': 'The operation timed out. Consider increasing timeout or checking the server.',
    'overflow': 'Numeric value too large. Check for infinite loops or unbounded calculations.',
    'import': 'Cannot find the module. Check spelling and ensure it is installed.',
    'maximum recursion': 'Function calls itself too deeply. Add a base case to stop recursion.',
    'stack overflow': 'Too many nested function calls. Check for infinite recursion.',
    'pycryptodome': 'AES encryption requires pycryptodome. Run: pip install pycryptodome',
    'cryptography': 'Encryption requires a crypto library. Run: pip install pycryptodome',
    'psycopg2': 'PostgreSQL support requires psycopg2. Run: pip install psycopg2-binary',
    'mysql': 'MySQL support requires mysql-connector. Run: pip install mysql-connector-python',
    'gunicorn': 'Production server requires gunicorn. Run: pip install gunicorn (Linux/macOS)',
    'waitress': 'Production server requires waitress. Run: pip install waitress',
    'already defined': 'A variable or function with this name already exists in this scope.',
    'not iterable': 'Only lists, maps, strings, and ranges can be iterated with ForEach.',
    'argument': 'Check the number and types of arguments passed to this function.',
    'abstract': 'Abstract methods must be implemented in subclasses.',
    'constructor': 'Check the constructor (Begin/Init) for the correct number of parameters.',
    'property': 'This object does not have the property you are trying to access.',
    'read only': 'This value is a constant and cannot be modified.',
    'method not found': 'This object does not have the method you are trying to call. Check spelling.',
    'syntax error': 'Check your code for missing keywords, mismatched brackets, or typos.',
    'invalid number': 'This string cannot be converted to a number. Check for non-numeric characters.',
    'empty': 'The collection is empty. Check with length() before accessing elements.',
}


def _get_hint(message: str) -> str:
    """Find a relevant hint for the error message."""
    lower = message.lower()
    for pattern, hint in _HINTS.items():
        if pattern in lower:
            return f"\n  {_dim('Hint:')} {hint}"
    return ""


def _did_you_mean(name: str, candidates: list, max_suggestions: int = 3, cutoff: float = 0.6) -> str:
    """Suggest similar names using difflib (edit-distance based)."""
    if not candidates or not name:
        return ""
    matches = difflib.get_close_matches(name, candidates, n=max_suggestions, cutoff=cutoff)
    if not matches:
        return ""
    if len(matches) == 1:
        return f"\n  {_dim('Did you mean:')} {_green(matches[0])}?"
    suggestions = ", ".join(_green(m) for m in matches)
    return f"\n  {_dim('Did you mean one of:')} {suggestions}?"


# ─── Source Context ──────────────────────────────────────

# Thread-local source reference — each thread gets its own context
# Prevents corruption when serving concurrent web requests
import threading
_source_ctx = threading.local()


def set_source_context(source: str, filename: str = "<input>"):
    """Store source lines for error context display. Called by the runner.
    Thread-safe: each thread maintains its own source context.
    """
    _source_ctx.lines = source.splitlines()
    _source_ctx.filename = filename


def _get_source_lines():
    """Get source lines for the current thread."""
    return getattr(_source_ctx, 'lines', [])


def _get_source_filename():
    """Get source filename for the current thread."""
    return getattr(_source_ctx, 'filename', '<input>')

def _format_source_context(line: int, column: int = None, context_lines: int = 2) -> str:
    """Format a source code snippet showing the error location."""
    source_lines = _get_source_lines()
    if not source_lines or line is None or line < 1:
        return ""
    idx = line - 1
    parts = []
    start = max(0, idx - max(0, context_lines))
    end = min(len(source_lines), idx + max(0, context_lines) + 1)

    for current_idx in range(start, end):
        current_line = source_lines[current_idx]
        current_num = str(current_idx + 1).rjust(4)
        if current_idx == idx:
            parts.append(f"  {_red(current_num + ' |')} {current_line}")
            if column is not None and column >= 1:
                caret_column = min(max(1, column), max(1, len(current_line)))
                padding = ' ' * (caret_column - 1)
                parts.append(f"  {' ' * 4} {_red('|')} {_red(padding + '^')}")
            else:
                parts.append(f"  {' ' * 4} {_red('|')} {_red('^' * max(1, len(current_line)))}")
        else:
            parts.append(f"  {_dim(current_num + ' |')} {current_line}")
    if parts:
        return "\n" + "\n".join(parts)
    return ""


# ═══════════════════════════════════════════════════════════
#  Base Error
# ═══════════════════════════════════════════════════════════

class EPLError(Exception):
    """Base class for all EPL errors."""

    def __init__(self, message: str, line: int = None, column: int = None, filename: str = None):
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename or _get_source_filename()
        self._traceback_frames = []
        self._suggestions = ""  # "did you mean?" text
        super().__init__(self.format_message())

    def _error_code(self) -> str:
        return ERROR_CODES.get(type(self).__name__, 'E0000')

    @property
    def user_message(self) -> str:
        """Plain message suitable for user try/catch (no ANSI, no source context)."""
        label = type(self).__name__.replace('Error', ' Error')
        # Map class names to EPL-friendly names
        labels = {
            'LexerError': 'EPL Lexer Error',
            'ParserError': 'EPL Parser Error',
            'RuntimeError': 'EPL Runtime Error',
            'TypeError': 'EPL Type Error',
            'NameError': 'EPL Name Error',
            'ValueError': 'EPL Value Error',
            'IndexError': 'EPL Index Error',
            'KeyError': 'EPL Key Error',
            'IOError': 'EPL IO Error',
            'NetworkError': 'EPL Network Error',
            'TimeoutError': 'EPL Timeout Error',
            'OverflowError': 'EPL Overflow Error',
            'ImportError': 'EPL Import Error',
            'AttributeError': 'EPL Attribute Error',
            'AssertionError': 'EPL Assertion Error',
            'ConcurrencyError': 'EPL Concurrency Error',
        }
        label = labels.get(type(self).__name__, f'EPL {label}')
        loc = f" on line {self.line}" if self.line is not None else ""
        return f"{label}{loc}: {self.message}"

    def format_message(self) -> str:
        return self._format_standard_message('EPL Error', include_suggestions=True, include_traceback=True)

    def __str__(self) -> str:
        # Re-render lazily so added frames/suggestions are visible after construction.
        return self.format_message()

    def _format_standard_message(
        self,
        label: str,
        *,
        include_suggestions: bool = False,
        include_traceback: bool = False,
        include_hint: bool = True,
    ) -> str:
        hint = _get_hint(self.message)
        loc = f" on line {self.line}" if self.line is not None else ""
        code = f"[{self._error_code()}] "
        ctx = _format_source_context(self.line, self.column)
        suffix = []
        if include_suggestions and self._suggestions:
            suffix.append(self._suggestions)
        if include_hint and hint:
            suffix.append(hint)
        if ctx:
            suffix.append(ctx)
        if include_traceback:
            tb = self._format_traceback()
            if tb:
                suffix.append(tb)
        return f"{_red(_bold(f'{code}{label}'))}{loc}: {self.message}{''.join(suffix)}"

    def add_frame(self, func_name: str, line: int):
        """Add a stack frame for traceback display."""
        self._traceback_frames.append((func_name, line))
        self.args = (self.format_message(),)

    def _format_traceback(self) -> str:
        if not self._traceback_frames:
            return ""
        ordered_frames = list(reversed(self._traceback_frames))
        lines = [f"\n\n  {_dim('Call stack:')}"]
        for idx, (fname, fline) in enumerate(ordered_frames):
            marker = '-> ' if idx == len(ordered_frames) - 1 else '   '
            loc = f" (line {fline})" if fline else ""
            lines.append(f"    {marker}{_cyan(fname)}{_dim(loc)}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return structured error data as a dictionary (no ANSI)."""
        d = {
            "error_code": self._error_code(),
            "type": type(self).__name__,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "filename": self.filename,
        }
        if self._traceback_frames:
            d["traceback"] = [
                {"function": fname, "line": fline}
                for fname, fline in self._traceback_frames
            ]
        hint = _get_hint(self.message)
        if hint:
            # Strip ANSI and formatting prefix
            clean = hint.strip()
            if clean.startswith("Hint:"):
                clean = clean[5:].strip()
            d["hint"] = clean
        return d

    def to_json(self) -> str:
        """Return structured error data as a JSON string."""
        return json.dumps(self.to_dict(), indent=2)


# ═══════════════════════════════════════════════════════════
#  Compilation Phase Errors
# ═══════════════════════════════════════════════════════════

class LexerError(EPLError):
    """Error during tokenization."""
    def format_message(self) -> str:
        hint = _get_hint(self.message)
        code = f"[{self._error_code()}] "
        ctx = _format_source_context(self.line, self.column)
        if self.line is not None:
            loc = f" on line {self.line}, column {self.column}" if self.column else f" on line {self.line}"
            return f"{_red(_bold(f'{code}EPL Lexer Error'))}{loc}: {self.message}{hint}{ctx}"
        return f"{_red(_bold(f'{code}EPL Lexer Error'))}: {self.message}{hint}"


class ParserError(EPLError):
    """Error during parsing."""
    def format_message(self) -> str:
        hint = _get_hint(self.message)
        code = f"[{self._error_code()}] "
        ctx = _format_source_context(self.line, self.column)
        if self.line is not None:
            loc = f" on line {self.line}"
            if self.column:
                loc += f", column {self.column}"
            return f"{_red(_bold(f'{code}EPL Parser Error'))}{loc}: {self.message}{hint}{ctx}"
        return f"{_red(_bold(f'{code}EPL Parser Error'))}: {self.message}{hint}"


# ═══════════════════════════════════════════════════════════
#  Runtime Errors (full hierarchy)
# ═══════════════════════════════════════════════════════════

class RuntimeError(EPLError):
    """General error during execution."""
    def format_message(self) -> str:
        return self._format_standard_message(
            'EPL Runtime Error',
            include_suggestions=True,
            include_traceback=True,
        )


class TypeError(EPLError):
    """Error for type mismatches."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Type Error', include_traceback=True)


class NameError(EPLError):
    """Error for undefined variables or functions."""
    def format_message(self) -> str:
        return self._format_standard_message(
            'EPL Name Error',
            include_suggestions=True,
            include_traceback=True,
        )


class ValueError(EPLError):
    """Error for invalid values (e.g., wrong format, out of expected range)."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Value Error', include_traceback=True)


class IndexError(EPLError):
    """Error for index out of range."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Index Error', include_traceback=True)


class KeyError(EPLError):
    """Error for missing dictionary key."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Key Error', include_traceback=True)


class IOError(EPLError):
    """Error for file and I/O operations."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL IO Error', include_traceback=True)


class NetworkError(EPLError):
    """Error for network/HTTP operations."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Network Error', include_traceback=True)


class TimeoutError(EPLError):
    """Error for operations that exceed time limits."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Timeout Error', include_traceback=True, include_hint=False)


class OverflowError(EPLError):
    """Error for numeric overflow."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Overflow Error', include_traceback=True, include_hint=False)


class ImportError(EPLError):
    """Error for module import failures."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Import Error', include_traceback=True)


class AttributeError(EPLError):
    """Error for missing attributes on objects."""
    def format_message(self) -> str:
        return self._format_standard_message(
            'EPL Attribute Error',
            include_suggestions=True,
            include_traceback=True,
            include_hint=False,
        )


class AssertionError(EPLError):
    """Error for failed assertions."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Assertion Error', include_traceback=True, include_hint=False)


# Backward-compatibility alias (legacy code used 'AssertationError' spelling)
AssertionError = AssertionError


class ConcurrencyError(EPLError):
    """Error for thread/async issues (deadlocks, race conditions)."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Concurrency Error', include_traceback=True, include_hint=False)


class NotImplementedError(EPLError):
    """Error for abstract methods or unimplemented features."""
    def format_message(self) -> str:
        return self._format_standard_message('EPL Not Implemented', include_traceback=True, include_hint=False)


# ═══════════════════════════════════════════════════════════
#  User-Defined Exception Support
# ═══════════════════════════════════════════════════════════

class EPLUserException(EPLError):
    """Base for user-defined exception classes created with 'Class MyError extends Error'."""

    def __init__(self, class_name: str, message: str, data=None, line: int = None):
        self.class_name = class_name
        self.data = data or {}
        super().__init__(message, line)

    def format_message(self) -> str:
        loc = f" on line {self.line}" if self.line is not None else ""
        return f"{self.class_name}{loc}: {self.message}"


# ═══════════════════════════════════════════════════════════
#  Error name → class mapping (for Catch clauses)
# ═══════════════════════════════════════════════════════════

ERROR_CLASSES = {
    'Error': EPLError,
    'RuntimeError': RuntimeError,
    'TypeError': TypeError,
    'NameError': NameError,
    'ValueError': ValueError,
    'IndexError': IndexError,
    'KeyError': KeyError,
    'IOError': IOError,
    'NetworkError': NetworkError,
    'TimeoutError': TimeoutError,
    'OverflowError': OverflowError,
    'ImportError': ImportError,
    'AttributeError': AttributeError,
    'AssertionError': AssertionError,   # backward compat alias
    'AssertionError': AssertionError,    # canonical spelling
    'ConcurrencyError': ConcurrencyError,
    'NotImplementedError': NotImplementedError,
}
