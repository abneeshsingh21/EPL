"""
EPL Error Explainer v1.0
Provides rich, structured error explanations with optional AI enhancement.

Analyses EPLError instances using pattern matching to identify common mistakes
(typos, Python/JS syntax habits, missing blocks, type mismatches) and produces
clear, actionable fix suggestions. Optionally calls the AI backend for deeper
analysis when the --ai-errors flag is active.

Usage (internal):
    from epl.error_explainer import explain, format_explanation
    exp = explain(error, source=source_code, ai=False)
    print(format_explanation(exp))
"""

import difflib
import logging
import re
from dataclasses import dataclass
from typing import Optional

_log = logging.getLogger(__name__)


# ─── Structured Result ───────────────────────────────────


@dataclass
class ErrorExplanation:
    """Structured error explanation produced by the explainer."""

    error_type: str  # e.g. "NameError"
    error_code: str  # e.g. "E0500"
    message: str  # Original error message
    line: Optional[int]  # Line number where the error occurred
    source_line: str  # The actual source code at that line

    # Pattern-based analysis
    what_went_wrong: str  # Plain English description of the problem
    how_to_fix: str  # Concrete fix suggestion
    corrected_code: str  # Suggested corrected source line (may be empty)

    # Optional AI analysis
    ai_explanation: str = ''  # AI-generated deep explanation (empty if AI disabled)

    # Metadata
    category: str = ''  # "syntax", "runtime", "type", "name", "io", "index"
    confidence: float = 1.0  # How confident the pattern match is (0.0-1.0)


# ─── EPL Stdlib Functions (for "did you mean?" on functions) ──

_COMMON_STDLIB_FUNCTIONS = [
    'length',
    'to_text',
    'to_integer',
    'to_decimal',
    'to_number',
    'uppercase',
    'lowercase',
    'trim',
    'split',
    'join',
    'replace',
    'contains',
    'starts_with',
    'ends_with',
    'index_of',
    'sorted',
    'reversed',
    'range',
    'type_of',
    'absolute',
    'round',
    'round_number',
    'floor',
    'ceil',
    'sqrt',
    'square_root',
    'power',
    'max',
    'min',
    'maximum',
    'minimum',
    'random',
    'random_number',
    'random_integer',
    'sum',
    'keys',
    'values',
    'items',
    'has_key',
    'get',
    'push',
    'pop',
    'remove',
    'remove_at',
    'insert',
    'format',
    'char_code',
    'from_char_code',
    'now',
    'today',
    'sleep',
    'year',
    'month',
    'day',
    'uuid',
    'uuid4',
    'base64_encode',
    'base64_decode',
    'regex_test',
    'regex_match',
    'regex_find_all',
    'regex_replace',
    'json_parse',
    'json_stringify',
    'http_get',
    'http_post',
    'url_encode',
    'url_decode',
    'print_error',
    'exit_code',
    'platform',
    'args',
    'env_get',
    'is_number',
    'is_string',
    'is_list',
    'is_null',
    'map',
    'filter',
    'enumerate',
    'zip',
    'sin',
    'cos',
    'tan',
    'asin',
    'acos',
    'atan',
    'atan2',
    'log',
    'sign',
    'clamp',
    'lerp',
    'pi',
    'euler',
    'degrees',
    'radians',
    'is_finite',
    'is_nan',
    'zip_lists',
    'enumerate_list',
    'file_read',
    'file_write',
    'file_append',
    'file_exists',
    'open',
    'query',
    'execute',
    'create_table',
]


# ─── Python/JS → EPL Keyword Map ─────────────────────────

_FOREIGN_KEYWORD_MAP = {
    # Python keywords → EPL equivalents
    'def': 'Function <name> Takes <params> ... End',
    'print': 'Say / Display / Show / Print (capitalized)',
    'elif': 'Otherwise If',
    'else': 'Otherwise',
    'while': 'While <condition> ... End',
    'for': 'For Each / For...from...to / Repeat N times',
    'return': 'Return <value>',
    'class': 'Class <Name> ... End',
    'import': 'Import "module"',
    'true': 'True / Yes',
    'false': 'False / No',
    'none': 'Nothing',
    'null': 'Nothing',
    'try': 'Try ... Catch error ... End',
    'except': 'Catch <error>',
    'raise': 'Throw <message>',
    'pass': '(EPL does not need pass — just leave the block empty or add a Note)',
    'assert': 'Assert <expression>',
    'lambda': 'lambda <params> -> <expression>',
    'with': '(EPL uses Try/Catch for resource management)',
    'yield': 'Yields <value>',
    'async': 'Async Function <name> ... End',
    'await': 'Await <expression>',
    # JavaScript keywords → EPL equivalents
    'var': 'Create <name> equal to <value>',
    'let': 'Create <name> equal to <value>',
    'const': 'Constant <name> = <value>',
    'function': 'Function <name> Takes <params> ... End',
    'console': 'Say / Display / Print',
    'if': 'If <condition> Then ... End',
    'switch': 'Match <value> When ... Default ... End',
    'case': 'When <value>',
    'default': 'Default',
    'new': 'New <ClassName>(<args>)',
    'this': 'self (inside a class method)',
    'throw': 'Throw <message>',
    'catch': 'Catch <error>',
    'typeof': 'type_of(<value>)',
    'undefined': 'Nothing',
}


# ─── EPL Keywords (excluded from "did you mean?" candidates) ──

_EPL_KEYWORDS = {
    'create',
    'set',
    'to',
    'equal',
    'say',
    'print',
    'display',
    'show',
    'if',
    'then',
    'otherwise',
    'end',
    'while',
    'repeat',
    'times',
    'for',
    'each',
    'in',
    'from',
    'step',
    'function',
    'define',
    'takes',
    'return',
    'class',
    'extends',
    'implements',
    'new',
    'try',
    'catch',
    'finally',
    'throw',
    'assert',
    'import',
    'use',
    'true',
    'false',
    'yes',
    'no',
    'nothing',
    'and',
    'or',
    'not',
    'match',
    'when',
    'default',
    'break',
    'continue',
    'constant',
    'module',
    'export',
    'interface',
    'abstract',
    'override',
    'static',
    'public',
    'private',
    'protected',
    'async',
    'await',
    'yields',
    'ask',
    'input',
    'read',
    'write',
    'append',
    'file',
}


# ─── Pattern Explainer Functions ─────────────────────────


def _explain_undefined_var(match, source_line, source_lines):
    """Generate explanation for undefined variable errors."""
    name = match.group(1)
    all_names = set()
    for line in source_lines:
        for m in re.finditer(r'\b([a-zA-Z_]\w*)\b', line):
            all_names.add(m.group(1))
    candidates = [n for n in all_names if n.lower() not in _EPL_KEYWORDS and n != name]
    similar = difflib.get_close_matches(name, candidates, n=3, cutoff=0.6)
    if similar:
        best = similar[0]
        corrected = source_line.replace(name, best) if source_line else ''
        return (
            f"Variable '{name}' has not been declared. Did you mean '{best}'?",
            f"Replace '{name}' with '{best}', or declare it first with: Create {name} equal to <value>",
            corrected,
        )
    return (
        f"Variable '{name}' has not been declared in this scope.",
        f'Declare it before using it: Create {name} equal to <value>',
        f'Create {name} equal to <value>' if not source_line else '',
    )


def _explain_undefined_func(match, source_line, source_lines):
    """Generate explanation for undefined function errors."""
    name = match.group(1)
    similar = difflib.get_close_matches(name, _COMMON_STDLIB_FUNCTIONS, n=3, cutoff=0.65)
    if similar:
        suggestion_list = ', '.join(similar)
        return (
            f"Function '{name}' does not exist.",
            f'Did you mean: {suggestion_list}?',
            source_line.replace(name, similar[0]) if source_line else '',
        )
    return (
        f"Function '{name}' is not defined. It is not a built-in function and was not declared.",
        f'Define it first:\n      Function {name} Takes <params>\n          ...\n      End',
        '',
    )


def _explain_unexpected_token(match, source_line, source_lines):
    """Generate explanation for unexpected token errors."""
    token = match.group(1)
    lower_token = token.lower()
    if lower_token in _FOREIGN_KEYWORD_MAP:
        epl_equiv = _FOREIGN_KEYWORD_MAP[lower_token]
        return (
            f"'{token}' is not valid EPL syntax — it looks like Python or JavaScript.",
            f'EPL equivalent: {epl_equiv}',
            '',
        )
    return (
        f"The parser did not expect '{token}' at this position.",
        'Check for typos, missing keywords, or mismatched block delimiters (End).',
        '',
    )


def _explain_missing_end(match, source_line, source_lines):
    """Generate explanation for missing End block errors."""
    open_blocks = []
    block_starters = [
        (r'^\s*(?:define\s+)?function\s+', 'Function'),
        (r'^\s*if\s+', 'If'),
        (r'^\s*while\s+', 'While'),
        (r'^\s*repeat\s+', 'Repeat'),
        (r'^\s*for\s+each\s+', 'For Each'),
        (r'^\s*for\s+', 'For'),
        (r'^\s*class\s+', 'Class'),
        (r'^\s*try\b', 'Try'),
        (r'^\s*match\s+', 'Match'),
        (r'^\s*async\s+function\s+', 'Async Function'),
        (r'^\s*module\s+', 'Module'),
        (r'^\s*interface\s+', 'Interface'),
    ]
    for i, line in enumerate(source_lines):
        stripped = line.strip().lower()
        if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('note:'):
            continue
        for pattern, block_type in block_starters:
            if re.match(pattern, stripped):
                open_blocks.append((block_type, i + 1))
                break
        if re.match(r'end\b', stripped):
            if open_blocks:
                open_blocks.pop()
    if open_blocks:
        block_type, block_line = open_blocks[-1]
        return (
            f"The '{block_type}' block starting on line {block_line} was never closed.",
            f"Add 'End' to close the '{block_type}' block.",
            'End',
        )
    return (
        "A block (If, Function, While, Class, Try, etc.) is missing its closing 'End'.",
        "Add 'End' at the end of the unclosed block.",
        'End',
    )


def _explain_type_mismatch(match, source_line, source_lines):
    return (
        'You are trying to combine or compare values of incompatible types (e.g., text and numbers).',
        'Convert types explicitly: to_text(number) or to_integer(text).',
        '',
    )


def _explain_index_out_of_range(match, source_line, source_lines):
    return (
        'You are trying to access a position in a list that does not exist.',
        'Check the list size with length(list) before accessing by index. '
        'Remember: EPL list indices start at 0.',
        '',
    )


def _explain_divide_by_zero(match, source_line, source_lines):
    return (
        'You are dividing a number by zero, which is mathematically undefined.',
        'Add a check before dividing:\n'
        '      If divisor != 0 Then\n'
        '          Create result equal to value / divisor\n'
        '      End',
        '',
    )


def _explain_key_not_found(match, source_line, source_lines):
    return (
        'You are trying to access a key in a Map that does not exist.',
        'Use has_key(map, key) to check before accessing, or use get(map, key, default_value).',
        '',
    )


def _explain_not_callable(match, source_line, source_lines):
    return (
        'You are trying to call something that is not a function — it might be a variable or a value.',
        'Make sure the name refers to a function, not a variable. Check spelling.',
        '',
    )


def _explain_max_recursion(match, source_line, source_lines):
    return (
        'A function is calling itself (or another function that calls it back) too many times without stopping.',
        'Add a base case — a condition where the function returns without calling itself:\n'
        '      Function countdown Takes n\n'
        '          If n <= 0 Then\n'
        '              Say "Done!"\n'
        '              Return\n'
        '          End\n'
        '          Say n\n'
        '          Call countdown(n - 1)\n'
        '      End',
        '',
    )


def _explain_import_error(match, source_line, source_lines):
    return (
        'The module or file you are trying to import could not be found.',
        'Check the path and spelling. Usage: Import "module_name" or Import "path/to/file.epl"',
        '',
    )


def _explain_constant_reassign(match, source_line, source_lines):
    name = match.group(1) if match.lastindex else 'the constant'
    return (
        f"You are trying to change '{name}', but it was declared as a constant.",
        'Constants cannot be changed after creation. Use a regular variable instead:\n'
        f'      Create {name} equal to <value>',
        '',
    )


def _explain_function_not_defined(match, source_line, source_lines):
    name = match.group(1)
    similar = difflib.get_close_matches(name, _COMMON_STDLIB_FUNCTIONS, n=3, cutoff=0.65)
    if similar:
        return (
            f"Function '{name}' has not been defined.",
            f'Did you mean: {", ".join(similar)}?',
            '',
        )
    return (
        f"Function '{name}' is not defined anywhere in your code.",
        f'Define it first:\n      Function {name} Takes <params>\n          ...\n      End',
        '',
    )


def _explain_class_not_found(match, source_line, source_lines):
    name = match.group(1)
    return (
        f"Class '{name}' has not been defined.",
        f'Make sure the class is defined before you try to use it:\n'
        f'      Class {name}\n          ...\n      End',
        '',
    )


def _explain_not_a_class(match, source_line, source_lines):
    name = match.group(1)
    return (
        f"'{name}' exists but it is not a class — you cannot use it as a parent class or instantiate it.",
        f"Check that '{name}' was defined with 'Class {name} ... End', not as a variable or function.",
        '',
    )


def _explain_wrong_arg_count(match, source_line, source_lines):
    func_name = match.group(1) if match.lastindex else 'the function'
    return (
        f"You called '{func_name}' with the wrong number of arguments.",
        'Check the function definition to see how many parameters it expects.',
        '',
    )


def _explain_list_index_type(match, source_line, source_lines):
    return (
        'List indices must be integers, but you provided a different type.',
        'Use to_integer(value) if your index is stored as text or decimal.',
        '',
    )


def _explain_cannot_call(match, source_line, source_lines):
    type_name = match.group(1) if match.lastindex else 'this value'
    return (
        f'You are trying to call {type_name} as if it were a function, but it is not callable.',
        'Make sure the name refers to a defined Function, not a variable.',
        '',
    )


def _explain_for_each_type(match, source_line, source_lines):
    return (
        "'For Each' can only iterate over lists, text, maps, or generators.",
        'Make sure the collection variable is a list, text, or map before iterating.',
        '',
    )


def _explain_cannot_convert(match, source_line, source_lines):
    return (
        'The value could not be converted to the target type.',
        'Make sure the value is in the correct format before converting:\n'
        '      to_integer("42") works, but to_integer("hello") does not.',
        '',
    )


def _explain_property_not_found(match, source_line, source_lines):
    prop = match.group(1) if match.lastindex else 'the property'
    return (
        f"The property '{prop}' does not exist on this object.",
        f"Check the spelling of '{prop}' and make sure the object has this property defined.",
        '',
    )


def _explain_repeat_count(match, source_line, source_lines):
    return (
        'The repeat count must be a positive integer.',
        'Use a whole number: Repeat 5 times ... End',
        '',
    )


# ─── Pattern Registry ────────────────────────────────────

_PATTERNS = [
    # NameError patterns
    {
        'match': r"undefined variable ['\"]?(\w+)['\"]?",
        'category': 'name',
        'explain': _explain_undefined_var,
    },
    {
        'match': r"variable ['\"]?(\w+)['\"]? has not been (?:created|declared|defined)",
        'category': 'name',
        'explain': _explain_undefined_var,
    },
    {
        'match': r"undefined function ['\"]?(\w+)['\"]?",
        'category': 'name',
        'explain': _explain_undefined_func,
    },
    {'match': r'not callable', 'category': 'name', 'explain': _explain_not_callable},
    # ParserError patterns
    {'match': r'expected ["\']?end["\']?', 'category': 'syntax', 'explain': _explain_missing_end},
    {
        'match': r"unexpected token ['\"]?(\w+)['\"]?",
        'category': 'syntax',
        'explain': _explain_unexpected_token,
    },
    # TypeError patterns
    {
        'match': r'cannot (add|subtract|multiply|combine|concatenate).*(?:string|text).*(?:integer|number|float|decimal)',
        'category': 'type',
        'explain': _explain_type_mismatch,
    },
    {'match': r'type mismatch', 'category': 'type', 'explain': _explain_type_mismatch},
    {'match': r'cannot compare', 'category': 'type', 'explain': _explain_type_mismatch},
    # RuntimeError patterns
    {
        'match': r'divide by zero|division by zero',
        'category': 'runtime',
        'explain': _explain_divide_by_zero,
    },
    {
        'match': r'index out of range|index.*bounds',
        'category': 'index',
        'explain': _explain_index_out_of_range,
    },
    {
        'match': r'key not found|key.*does not exist',
        'category': 'runtime',
        'explain': _explain_key_not_found,
    },
    {
        'match': r'maximum recursion|stack overflow',
        'category': 'runtime',
        'explain': _explain_max_recursion,
    },
    # ImportError patterns
    {
        'match': r'cannot find|module not found|import.*failed',
        'category': 'import',
        'explain': _explain_import_error,
    },
    # EPL-native patterns
    {
        'match': r'function ["\']?(\w+)["\']? has not been defined',
        'category': 'name',
        'explain': _explain_function_not_defined,
    },
    {
        'match': r'(?:parent )?class ["\']?(\w+)["\']? not found',
        'category': 'name',
        'explain': _explain_class_not_found,
    },
    {
        'match': r'["\']?(\w+)["\']? is not a class',
        'category': 'type',
        'explain': _explain_not_a_class,
    },
    {
        'match': r'cannot change constant ["\']?(\w+)["\']?',
        'category': 'runtime',
        'explain': _explain_constant_reassign,
    },
    {
        'match': r'(\w+)\(\) takes \d+ argument',
        'category': 'runtime',
        'explain': _explain_wrong_arg_count,
    },
    {
        'match': r'(?:list|text) index must be integer',
        'category': 'type',
        'explain': _explain_list_index_type,
    },
    {'match': r'cannot call (\w+)', 'category': 'type', 'explain': _explain_cannot_call},
    {'match': r'for each requires', 'category': 'type', 'explain': _explain_for_each_type},
    {'match': r'repeat count', 'category': 'type', 'explain': _explain_repeat_count},
    {
        'match': r'cannot convert to (?:integer|decimal)',
        'category': 'runtime',
        'explain': _explain_cannot_convert,
    },
    {
        'match': r'has no property ["\']?(\w+)["\']?',
        'category': 'type',
        'explain': _explain_property_not_found,
    },
    {
        'match': r'cannot (?:add|subtract|negate|slice|index into)',
        'category': 'type',
        'explain': _explain_type_mismatch,
    },
    # Beginner mistakes (foreign language syntax)
    {
        'match': r'unexpected.*print\b',
        'category': 'syntax',
        'explain': lambda m, src, lines: (
            "EPL does not use 'print()' — it uses English keywords for output.",
            'Replace \'print(...)\' with: Say "your message"',
            re.sub(r'print\s*\(\s*', 'Say ', src).rstrip(')') if src else 'Say "Hello"',
        ),
    },
    {
        'match': r'unexpected.*\bdef\b',
        'category': 'syntax',
        'explain': lambda m, src, lines: (
            "EPL does not use 'def' to define functions — it uses English syntax.",
            'Use: Function <name> Takes <params> ... End',
            '',
        ),
    },
    {
        'match': r'unexpected.*\bfor\b',
        'category': 'syntax',
        'explain': lambda m, src, lines: (
            "EPL uses English-style loops instead of C/Python-style 'for'.",
            "Use: 'For Each item In list', 'For i from 1 to 10', or 'Repeat 5 times'",
            '',
        ),
    },
    # JavaScript/TypeScript Bridge errors
    {
        'match': r'node\.js is not installed',
        'category': 'runtime',
        'explain': lambda m, src, lines: (
            "The JavaScript bridge requires Node.js, which is not installed on this system.",
            "Install Node.js from https://nodejs.org/ and ensure 'node' is in your PATH.",
            '',
        ),
    },
    {
        'match': r'cannot load module ["\']?([\w@/.-]+)["\']?',
        'category': 'runtime',
        'explain': lambda m, src, lines: (
            f'The npm package "{m.group(1)}" could not be loaded by Node.js.',
            f'Install it with: epl jsinstall {m.group(1)}',
            '',
        ),
    },
    {
        'match': r'js bridge (?:pipe broken|process terminated)',
        'category': 'runtime',
        'explain': lambda m, src, lines: (
            "The Node.js bridge subprocess crashed or was terminated unexpectedly.",
            "Check your Node.js installation and ensure no other process is interfering. "
            "Try running the program again.",
            '',
        ),
    },
]


# ─── Main Entry Point ────────────────────────────────────


def explain(error, source: str = None, ai: bool = False) -> ErrorExplanation:
    """Generate a structured explanation for an EPL error.

    Args:
        error: An EPLError instance (or any exception with .message and .line)
        source: Full source code string (optional — falls back to thread-local context)
        ai: Whether to include AI-generated explanation (requires Ollama or cloud API)

    Returns:
        ErrorExplanation with all analysis results
    """
    from epl.errors import _get_source_lines

    if source:
        source_lines = source.splitlines()
    else:
        source_lines = _get_source_lines() or []

    error_line = getattr(error, 'line', None)
    source_at_line = ''
    if error_line and source_lines and 0 < error_line <= len(source_lines):
        source_at_line = source_lines[error_line - 1].strip()

    error_msg = getattr(error, 'message', str(error))
    error_type = type(error).__name__
    error_code = error._error_code() if hasattr(error, '_error_code') else 'E0000'

    what_went_wrong = 'An error occurred in your EPL code.'
    how_to_fix = 'Review the error message and source line above for clues.'
    corrected_code = ''
    category = 'runtime'
    confidence = 0.3

    msg_lower = error_msg.lower()
    for pattern in _PATTERNS:
        match = re.search(pattern['match'], msg_lower)
        if match:
            try:
                what_went_wrong, how_to_fix, corrected_code = pattern['explain'](
                    match, source_at_line, source_lines
                )
                category = pattern['category']
                confidence = 0.9
            except Exception as exc:
                _log.debug('Pattern explainer failed: %s', exc)
            break

    result = ErrorExplanation(
        error_type=error_type,
        error_code=error_code,
        message=error_msg,
        line=error_line,
        source_line=source_at_line,
        what_went_wrong=what_went_wrong,
        how_to_fix=how_to_fix,
        corrected_code=corrected_code,
        category=category,
        confidence=confidence,
    )

    if ai:
        result.ai_explanation = _get_ai_explanation(error, source)

    return result


# ─── AI Integration ──────────────────────────────────────


def _get_ai_explanation(error, source: str = None) -> str:
    """Get AI-powered explanation using the configured AI backend.

    Uses Ollama (local) or cloud provider (Gemini/Groq) if available.
    Returns empty string if no AI backend is reachable.
    """
    try:
        from epl.ai import _use_cloud, explain_error, is_available

        if not (is_available() or _use_cloud()):
            return ''

        error_msg = getattr(error, 'message', str(error))
        return explain_error(error_msg, source_code=source) or ''
    except Exception:
        return ''


# ─── Rich Terminal Formatting ─────────────────────────────


def format_explanation(exp: ErrorExplanation, color: bool = True) -> str:
    """Format an ErrorExplanation for terminal display."""
    if color:
        try:
            from epl.errors import _bold, _cyan, _dim, _green, _red, _yellow
        except ImportError:
            color = False

    if not color:
        _bold = _red = _green = _cyan = _dim = _yellow = lambda s: s

    bar = '\u2501' * 52

    lines = []
    lines.append('')
    lines.append(f'  {_cyan(bar)}')
    lines.append(f'  {_bold("Error Explanation")}')
    lines.append(f'  {_cyan(bar)}')
    lines.append('')
    lines.append(f'  {_bold("What went wrong:")}')

    for part in exp.what_went_wrong.split('\n'):
        lines.append(f'    {part}')

    lines.append('')
    lines.append(f'  {_bold("How to fix:")}')
    for part in exp.how_to_fix.split('\n'):
        lines.append(f'    {_green(part)}')

    if exp.corrected_code:
        lines.append('')
        lines.append(f'  {_bold("Suggested code:")}')
        for part in exp.corrected_code.split('\n'):
            lines.append(f'    {_green(part)}')

    if exp.ai_explanation:
        lines.append('')
        lines.append(f'  {_bold("AI Analysis:")}')
        for ai_line in exp.ai_explanation.split('\n'):
            lines.append(f'    {ai_line}')

    lines.append(f'  {_cyan(bar)}')
    lines.append('')

    return '\n'.join(lines)
