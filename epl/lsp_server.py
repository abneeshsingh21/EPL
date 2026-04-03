"""
EPL Language Server Protocol (LSP) Implementation v2.0 — Production Ready
Provides IDE features: diagnostics (errors/warnings), code completion,
hover information, go-to-definition, document symbols, formatting,
references, rename, code actions, and signature help.

Usage:
    python -m epl.lsp_server          # stdio transport (for VS Code extension)
    python -m epl.lsp_server --tcp    # TCP transport on port 2087

Protocol: JSON-RPC 2.0 over stdio or TCP
Spec: https://microsoft.github.io/language-server-protocol/
"""

import json
import sys
import re
import os
import threading
import traceback
from typing import Dict, List, Optional, Tuple, Any

# ─── EPL Imports ────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from epl.lexer import Lexer
from epl.parser import Parser
from epl import ast_nodes as ast
from epl.tokens import TokenType


# ═══════════════════════════════════════════════════════════
# EPL Language Intelligence
# ═══════════════════════════════════════════════════════════

class EPLAnalyzer:
    """Analyzes EPL source code for IDE features."""

    # Built-in functions with signatures and docs
    BUILTINS = {
        # I/O
        'Display': {'sig': 'Display expression', 'doc': 'Print a value to the console.'},
        'Print': {'sig': 'Print expression', 'doc': 'Print a value to the console.'},
        'Input': {'sig': 'Input variable_name with "prompt"', 'doc': 'Read user input.'},
        # Math
        'absolute': {'sig': 'absolute(n) -> number', 'doc': 'Returns the absolute value of n.'},
        'round': {'sig': 'round(n) -> integer', 'doc': 'Rounds n to the nearest integer.'},
        'floor': {'sig': 'floor(n) -> integer', 'doc': 'Rounds n down.'},
        'ceil': {'sig': 'ceil(n) -> integer', 'doc': 'Rounds n up.'},
        'sqrt': {'sig': 'sqrt(n) -> number', 'doc': 'Square root of n.'},
        'power': {'sig': 'power(base, exp) -> number', 'doc': 'Returns base raised to exp.'},
        'max': {'sig': 'max(a, b) -> number', 'doc': 'Returns the larger value.'},
        'min': {'sig': 'min(a, b) -> number', 'doc': 'Returns the smaller value.'},
        'log': {'sig': 'log(n) -> number', 'doc': 'Natural logarithm of n.'},
        'sin': {'sig': 'sin(n) -> number', 'doc': 'Sine of n (radians).'},
        'cos': {'sig': 'cos(n) -> number', 'doc': 'Cosine of n (radians).'},
        'tan': {'sig': 'tan(n) -> number', 'doc': 'Tangent of n (radians).'},
        'random': {'sig': 'random() -> number', 'doc': 'Random float between 0 and 1.'},
        'random_int': {'sig': 'random_int(min, max) -> integer', 'doc': 'Random integer in range.'},
        'pi': {'sig': 'pi() -> number', 'doc': 'Returns 3.14159265358979...'},
        'euler': {'sig': 'euler() -> number', 'doc': 'Returns Euler\'s number e.'},
        'sign': {'sig': 'sign(n) -> integer', 'doc': 'Returns -1, 0, or 1.'},
        'clamp': {'sig': 'clamp(value, min, max) -> number', 'doc': 'Clamp value within range.'},
        'lerp': {'sig': 'lerp(a, b, t) -> number', 'doc': 'Linear interpolation.'},
        # String
        'length': {'sig': 'length(value) -> integer', 'doc': 'Length of string/list.'},
        'uppercase': {'sig': 'uppercase(s) -> string', 'doc': 'Convert string to uppercase.'},
        'lowercase': {'sig': 'lowercase(s) -> string', 'doc': 'Convert string to lowercase.'},
        'to_text': {'sig': 'to_text(value) -> string', 'doc': 'Convert value to string.'},
        'to_integer': {'sig': 'to_integer(value) -> integer', 'doc': 'Convert value to integer.'},
        'to_decimal': {'sig': 'to_decimal(value) -> decimal', 'doc': 'Convert value to decimal.'},
        'type_of': {'sig': 'type_of(value) -> string', 'doc': 'Get the type name.'},
        'char_code': {'sig': 'char_code(s) -> integer', 'doc': 'Get ASCII code of first character.'},
        'from_char_code': {'sig': 'from_char_code(n) -> string', 'doc': 'Character from ASCII code.'},
        'format': {'sig': 'format(template, ...args) -> string', 'doc': 'Format string with {} placeholders.'},
        # Collections
        'range': {'sig': 'range(n) or range(start, end, step) -> list', 'doc': 'Generate a range of numbers.'},
        'sorted': {'sig': 'sorted(list) -> list', 'doc': 'Return a sorted copy.'},
        'reversed': {'sig': 'reversed(list) -> list', 'doc': 'Return a reversed copy.'},
        'sum': {'sig': 'sum(list) -> number', 'doc': 'Sum all elements.'},
        'zip_lists': {'sig': 'zip_lists(a, b) -> list', 'doc': 'Combine two lists into pairs.'},
        'enumerate_list': {'sig': 'enumerate_list(list) -> list', 'doc': 'Pairs of [index, value].'},
        'keys': {'sig': 'keys(map) -> list', 'doc': 'Get map keys.'},
        'values': {'sig': 'values(map) -> list', 'doc': 'Get map values.'},
        # DateTime
        'now': {'sig': 'now() -> string', 'doc': 'Current datetime as ISO string.'},
        'today': {'sig': 'today() -> string', 'doc': 'Current date as YYYY-MM-DD.'},
        'timestamp': {'sig': 'timestamp() -> number', 'doc': 'Unix timestamp in seconds.'},
        'sleep': {'sig': 'sleep(seconds)', 'doc': 'Pause execution.'},
        # Crypto
        'uuid': {'sig': 'uuid() -> string', 'doc': 'Generate a UUID v4.'},
        'hash_sha256': {'sig': 'hash_sha256(s) -> string', 'doc': 'SHA-256 hash.'},
        'hash_md5': {'sig': 'hash_md5(s) -> string', 'doc': 'MD5 hash.'},
        'base64_encode': {'sig': 'base64_encode(s) -> string', 'doc': 'Encode to Base64.'},
        'base64_decode': {'sig': 'base64_decode(s) -> string', 'doc': 'Decode from Base64.'},
        # Regex
        'regex_test': {'sig': 'regex_test(pattern, text) -> boolean', 'doc': 'Test if pattern matches.'},
        'regex_match': {'sig': 'regex_match(pattern, text) -> list', 'doc': 'Find first match.'},
        'regex_find_all': {'sig': 'regex_find_all(pattern, text) -> list', 'doc': 'Find all matches.'},
        'regex_replace': {'sig': 'regex_replace(pattern, replacement, text) -> string', 'doc': 'Replace matches.'},
        # File I/O
        'file_exists': {'sig': 'file_exists(path) -> boolean', 'doc': 'Check if file exists.'},
        'read_lines': {'sig': 'read_lines(path) -> list', 'doc': 'Read file lines.'},
        'write_lines': {'sig': 'write_lines(path, lines)', 'doc': 'Write lines to file.'},
        # JSON
        'json_parse': {'sig': 'json_parse(text) -> value', 'doc': 'Parse JSON string.'},
        'json_stringify': {'sig': 'json_stringify(value) -> string', 'doc': 'Convert to JSON.'},
        # Networking
        'http_get': {'sig': 'http_get(url) -> string', 'doc': 'HTTP GET request.'},
        'http_post': {'sig': 'http_post(url, body) -> string', 'doc': 'HTTP POST request.'},
    }

    # EPL keywords for completion
    KEYWORDS = [
        'Set', 'to', 'Create', 'equal', 'Display', 'Print', 'Input', 'with',
        'If', 'then', 'Else', 'End', 'While', 'For', 'from', 'to', 'step',
        'each', 'in', 'Repeat', 'times', 'Function', 'takes', 'and', 'Return',
        'Class', 'extends', 'new', 'Call', 'Try', 'Catch', 'Throw',
        'Match', 'When', 'Default', 'Break', 'Continue', 'Exit',
        'Constant', 'Enum', 'as', 'Import', 'Export', 'Assert',
        'Async', 'Await', 'Super', 'Write', 'Read', 'Append', 'file',
        'Wait', 'seconds', 'true', 'false', 'null', 'nothing',
        'or', 'not', 'is', 'Lambda', 'Web', 'Start', 'Route', 'Port',
    ]

    # Method completions for common types
    STRING_METHODS = ['upper', 'lower', 'trim', 'split', 'contains', 'replace',
                      'starts_with', 'ends_with', 'substring', 'index_of',
                      'repeat', 'char_at', 'to_list', 'length']
    LIST_METHODS = ['add', 'remove', 'push', 'pop', 'length', 'sort', 'reverse',
                    'contains', 'index_of', 'join', 'find', 'slice']
    MAP_METHODS = ['keys', 'values', 'has_key', 'remove', 'length', 'entries']

    def __init__(self):
        self.documents: Dict[str, str] = {}
        self.symbols: Dict[str, List[dict]] = {}  # uri -> symbol list
        self.diagnostics: Dict[str, List[dict]] = {}  # uri -> diagnostic list

    def update_document(self, uri: str, text: str):
        """Update document content and re-analyze."""
        self.set_document_text(uri, text)
        try:
            symbols, diagnostics = self.analyze_text(text)
        except Exception as exc:
            symbols = self._regex_extract_symbols(text)
            diagnostics = self.make_internal_diagnostics(text, f'Analysis failed: {exc}')
        self.apply_document_analysis(uri, text, symbols, diagnostics)

    def set_document_text(self, uri: str, text: str):
        """Store the latest document text, even when analysis is deferred."""
        self.documents[uri] = text

    def analyze_text(self, text: str) -> Tuple[List[dict], List[dict]]:
        """Analyze source text and return symbols plus diagnostics."""
        return self._extract_symbols(text), self._get_diagnostics(text)

    def apply_document_analysis(
        self,
        uri: str,
        text: str,
        symbols: List[dict],
        diagnostics: List[dict],
    ):
        """Commit analysis results for a document."""
        self.documents[uri] = text
        self.symbols[uri] = symbols
        self.diagnostics[uri] = diagnostics

    def make_internal_diagnostics(self, source: str, message: str, source_name: str = 'epl-lsp') -> List[dict]:
        """Build a safe diagnostic payload for internal analysis failures."""
        line = self._extract_line_from_error(message, source)
        return [{
            'range': {
                'start': {'line': max(0, line - 1), 'character': 0},
                'end': {'line': max(0, line - 1), 'character': 1000}
            },
            'severity': 1,
            'source': source_name,
            'message': message,
        }]

    def _get_diagnostics(self, source: str) -> List[dict]:
        """Parse source and return diagnostics (errors/warnings/type checks)."""
        diagnostics = []
        program = None
        try:
            tokens = Lexer(source).tokenize()
            try:
                program = Parser(tokens).parse()
            except Exception as e:
                msg = str(e)
                line = self._extract_line_from_error(msg, source)
                diagnostics.append({
                    'range': {
                        'start': {'line': max(0, line - 1), 'character': 0},
                        'end': {'line': max(0, line - 1), 'character': 1000}
                    },
                    'severity': 1,  # Error
                    'source': 'epl',
                    'message': msg
                })
        except Exception as e:
            msg = str(e)
            line = self._extract_line_from_error(msg, source)
            diagnostics.append({
                'range': {
                    'start': {'line': max(0, line - 1), 'character': 0},
                    'end': {'line': max(0, line - 1), 'character': 1000}
                },
                'severity': 1,  # Error
                'source': 'epl',
                'message': msg
            })

        # Type checking pass (runs on successfully parsed AST)
        if program is not None:
            try:
                from epl.type_checker import TypeChecker
                checker = TypeChecker(strict=False)
                checker.check(program)
                diagnostics.extend(checker.to_lsp_diagnostics())
            except Exception:
                pass  # type checker failures should not break the LSP

        # Warnings: check for common issues
        diagnostics.extend(self._lint_warnings(source))
        return diagnostics

    def _lint_warnings(self, source: str) -> List[dict]:
        """Basic lint warnings."""
        warnings = []
        lines = source.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Warn about unreachable code after Return
            if stripped.startswith('Return ') and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.startswith('End') and not next_line.startswith('#'):
                    warnings.append({
                        'range': {
                            'start': {'line': i + 1, 'character': 0},
                            'end': {'line': i + 1, 'character': len(lines[i + 1])}
                        },
                        'severity': 2,  # Warning
                        'source': 'epl-lint',
                        'message': 'Unreachable code after Return statement.'
                    })
            # Warn about empty loops
            if stripped.startswith('While ') or stripped.startswith('For '):
                if i + 1 < len(lines) and lines[i + 1].strip() in ('End', 'End.'):
                    warnings.append({
                        'range': {
                            'start': {'line': i, 'character': 0},
                            'end': {'line': i, 'character': len(line)}
                        },
                        'severity': 2,
                        'source': 'epl-lint',
                        'message': 'Empty loop body.'
                    })
            # Warn about very long lines
            if len(line) > 120:
                warnings.append({
                    'range': {
                        'start': {'line': i, 'character': 120},
                        'end': {'line': i, 'character': len(line)}
                    },
                    'severity': 3,  # Information
                    'source': 'epl-lint',
                    'message': f'Line exceeds 120 characters ({len(line)}).'
                })
        return warnings

    def _extract_line_from_error(self, msg: str, source: str) -> int:
        """Extract line number from error message."""
        m = re.search(r'line\s+(\d+)', msg, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 1

    def _extract_symbols(self, source: str) -> List[dict]:
        """Extract document symbols (functions, classes, variables) from source."""
        symbols = []
        try:
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
            for stmt in program.statements:
                self._collect_symbols(stmt, symbols, source)
        except Exception:
            # Fallback: regex-based symbol extraction
            symbols = self._regex_extract_symbols(source)
        return symbols

    def _collect_symbols(self, node, symbols, source, container=None):
        """Recursively collect symbols from AST."""
        if isinstance(node, ast.FunctionDef):
            params = ', '.join(p[0] if isinstance(p, (list, tuple)) else p for p in node.params)
            symbols.append({
                'name': node.name,
                'kind': 12,  # Function
                'detail': f'Function {node.name}({params})',
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
            })
        elif isinstance(node, ast.AsyncFunctionDef):
            params = ', '.join(p[0] if isinstance(p, (list, tuple)) else p for p in node.params)
            symbols.append({
                'name': node.name,
                'kind': 12,  # Function
                'detail': f'Async Function {node.name}({params})',
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
            })
        elif isinstance(node, ast.ClassDef):
            cls_sym = {
                'name': node.name,
                'kind': 5,  # Class
                'detail': f'Class {node.name}' + (f' extends {node.parent}' if node.parent else ''),
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
                'children': [],
            }
            for child in node.body:
                self._collect_symbols(child, cls_sym['children'], source, container=node.name)
            symbols.append(cls_sym)
        elif isinstance(node, ast.VarDeclaration):
            symbols.append({
                'name': node.name,
                'kind': 13,  # Variable
                'detail': f'Variable {node.name}',
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
            })
        elif isinstance(node, ast.ConstDeclaration):
            symbols.append({
                'name': node.name,
                'kind': 14,  # Constant
                'detail': f'Constant {node.name}',
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
            })
        elif isinstance(node, ast.EnumDef):
            symbols.append({
                'name': node.name,
                'kind': 10,  # Enum
                'detail': f'Enum {node.name}',
                'range': self._node_range(node, source),
                'selectionRange': self._node_range(node, source),
            })

    def _node_range(self, node, source):
        """Get LSP range for a node."""
        line = getattr(node, 'line', 1)
        return {
            'start': {'line': max(0, line - 1), 'character': 0},
            'end': {'line': max(0, line - 1), 'character': 1000}
        }

    def _regex_extract_symbols(self, source: str) -> List[dict]:
        """Fallback regex-based symbol extraction when parser fails."""
        symbols = []
        for i, line in enumerate(source.split('\n')):
            stripped = line.strip()
            # Function
            m = re.match(r'(?:Async\s+)?Function\s+(\w+)', stripped)
            if m:
                symbols.append({
                    'name': m.group(1), 'kind': 12,
                    'detail': f'Function {m.group(1)}',
                    'range': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                    'selectionRange': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                })
            # Class
            m = re.match(r'Class\s+(\w+)', stripped)
            if m:
                symbols.append({
                    'name': m.group(1), 'kind': 5,
                    'detail': f'Class {m.group(1)}',
                    'range': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                    'selectionRange': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                })
            # Variable
            m = re.match(r'(?:Set|Create)\s+(\w+)', stripped)
            if m:
                symbols.append({
                    'name': m.group(1), 'kind': 13,
                    'detail': f'Variable {m.group(1)}',
                    'range': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                    'selectionRange': {'start': {'line': i, 'character': 0}, 'end': {'line': i, 'character': len(line)}},
                })
        return symbols

    def get_completions(self, uri: str, line: int, character: int) -> List[dict]:
        """Get completion items at the given position."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        if line >= len(lines):
            return []

        current_line = lines[line]
        prefix = current_line[:character].strip()
        word = self._get_word_at(current_line, character)

        completions = []

        # After a dot -> method completions
        if '.' in prefix:
            parts = prefix.rsplit('.', 1)
            obj_name = parts[0].split()[-1] if parts[0] else ''
            # Determine type of object for method suggestions
            for method in self.STRING_METHODS + self.LIST_METHODS:
                completions.append({
                    'label': method,
                    'kind': 2,  # Method
                    'detail': f'.{method}()',
                    'insertText': f'{method}($0)',
                    'insertTextFormat': 2,  # Snippet
                })
        else:
            # Keywords
            for kw in self.KEYWORDS:
                if not word or kw.lower().startswith(word.lower()):
                    completions.append({
                        'label': kw,
                        'kind': 14,  # Keyword
                        'detail': 'keyword',
                    })
            # Builtins
            for name, info in self.BUILTINS.items():
                if not word or name.lower().startswith(word.lower()):
                    completions.append({
                        'label': name,
                        'kind': 3,  # Function
                        'detail': info['sig'],
                        'documentation': info['doc'],
                        'insertText': f'{name}($0)',
                        'insertTextFormat': 2,
                    })
            # User-defined symbols from current document
            for sym in self.symbols.get(uri, []):
                if not word or sym['name'].lower().startswith(word.lower()):
                    kind_map = {5: 7, 12: 3, 13: 6, 14: 21, 10: 13}
                    completions.append({
                        'label': sym['name'],
                        'kind': kind_map.get(sym['kind'], 1),
                        'detail': sym.get('detail', ''),
                    })

        return completions

    def get_hover(self, uri: str, line: int, character: int) -> Optional[dict]:
        """Get hover info at position."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        if line >= len(lines):
            return None

        word = self._get_word_at(lines[line], character)
        if not word:
            return None

        # Check builtins
        if word in self.BUILTINS:
            info = self.BUILTINS[word]
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f'```epl\n{info["sig"]}\n```\n\n{info["doc"]}'
                }
            }

        # Check document symbols
        for sym in self.symbols.get(uri, []):
            if sym['name'] == word:
                return {
                    'contents': {
                        'kind': 'markdown',
                        'value': f'```epl\n{sym["detail"]}\n```'
                    }
                }

        # Check keywords
        if word in self.KEYWORDS:
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f'**{word}** — EPL keyword'
                }
            }

        return None

    def get_definition(self, uri: str, line: int, character: int) -> Optional[dict]:
        """Get go-to-definition location."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        if line >= len(lines):
            return None
        word = self._get_word_at(lines[line], character)
        if not word:
            return None
        for sym in self.symbols.get(uri, []):
            if sym['name'] == word:
                return {
                    'uri': uri,
                    'range': sym['range']
                }
            # Check children (class methods)
            for child in sym.get('children', []):
                if child['name'] == word:
                    return {
                        'uri': uri,
                        'range': child['range']
                    }
        return None

    def _get_word_at(self, line: str, character: int) -> str:
        """Get the word at a character position in a line."""
        if character > len(line):
            character = len(line)
        # Find word boundaries
        start = character
        while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_'):
            start -= 1
        end = character
        while end < len(line) and (line[end].isalnum() or line[end] == '_'):
            end += 1
        return line[start:end]

    def get_references(self, uri: str, line: int, character: int) -> List[dict]:
        """Find all references to the symbol at position."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        if line >= len(lines):
            return []
        word = self._get_word_at(lines[line], character)
        if not word:
            return []
        results = []
        for doc_uri, doc_text in self.documents.items():
            doc_lines = doc_text.split('\n')
            for i, doc_line in enumerate(doc_lines):
                col = 0
                while True:
                    idx = doc_line.find(word, col)
                    if idx == -1:
                        break
                    # Check word boundaries
                    before = doc_line[idx - 1] if idx > 0 else ' '
                    after = doc_line[idx + len(word)] if idx + len(word) < len(doc_line) else ' '
                    if not (before.isalnum() or before == '_') and not (after.isalnum() or after == '_'):
                        results.append({
                            'uri': doc_uri,
                            'range': {
                                'start': {'line': i, 'character': idx},
                                'end': {'line': i, 'character': idx + len(word)}
                            }
                        })
                    col = idx + len(word)
        return results

    def get_rename_edits(self, uri: str, line: int, character: int, new_name: str) -> dict:
        """Compute workspace edit for renaming a symbol."""
        refs = self.get_references(uri, line, character)
        if not refs:
            return {'changes': {}}
        changes = {}
        for ref in refs:
            ref_uri = ref['uri']
            changes.setdefault(ref_uri, []).append({
                'range': ref['range'],
                'newText': new_name
            })
        return {'changes': changes}

    def get_code_actions(self, uri: str, diagnostics: List[dict]) -> List[dict]:
        """Return code actions (quick fixes) for diagnostics."""
        actions = []
        for diag in diagnostics:
            msg = diag.get('message', '')
            # Quick fix: suggest Run with --strict for type errors
            if 'unreachable' in msg.lower():
                actions.append({
                    'title': 'Remove unreachable code',
                    'kind': 'quickfix',
                    'diagnostics': [diag],
                    'edit': {
                        'changes': {
                            uri: [{
                                'range': diag['range'],
                                'newText': ''
                            }]
                        }
                    }
                })
            if 'empty loop' in msg.lower():
                actions.append({
                    'title': 'Add TODO comment in empty loop',
                    'kind': 'quickfix',
                    'diagnostics': [diag],
                    'edit': {
                        'changes': {
                            uri: [{
                                'range': {
                                    'start': diag['range']['end'],
                                    'end': diag['range']['end']
                                },
                                'newText': '\n    // TODO: implement'
                            }]
                        }
                    }
                })
        return actions

    def get_signature_help(self, uri: str, line: int, character: int) -> Optional[dict]:
        """Get signature help for function calls."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        if line >= len(lines):
            return None
        current_line = lines[line][:character]
        # Find function name before the opening paren
        paren_depth = 0
        func_end = -1
        for i in range(len(current_line) - 1, -1, -1):
            if current_line[i] == ')':
                paren_depth += 1
            elif current_line[i] == '(':
                if paren_depth == 0:
                    func_end = i
                    break
                paren_depth -= 1
        if func_end < 0:
            return None
        # Extract function name
        name_end = func_end
        name_start = name_end
        while name_start > 0 and (current_line[name_start - 1].isalnum() or current_line[name_start - 1] == '_'):
            name_start -= 1
        func_name = current_line[name_start:name_end]
        if not func_name:
            return None
        # Check builtins
        if func_name in self.BUILTINS:
            info = self.BUILTINS[func_name]
            # Count commas to determine active parameter
            args_text = current_line[func_end + 1:]
            active_param = args_text.count(',')
            return {
                'signatures': [{
                    'label': info['sig'],
                    'documentation': info['doc'],
                    'parameters': [],
                }],
                'activeSignature': 0,
                'activeParameter': active_param,
            }
        # Check user symbols
        for sym in self.symbols.get(uri, []):
            if sym['name'] == func_name and sym['kind'] == 12:
                detail = sym.get('detail', '')
                args_text = current_line[func_end + 1:]
                active_param = args_text.count(',')
                return {
                    'signatures': [{
                        'label': detail,
                        'parameters': [],
                    }],
                    'activeSignature': 0,
                    'activeParameter': active_param,
                }
        return None

    def get_formatting(self, uri: str, options: dict) -> List[dict]:
        """Format the document."""
        source = self.documents.get(uri, '')
        lines = source.split('\n')
        tab_size = options.get('tabSize', 4)
        use_tabs = options.get('insertSpaces', True) is False

        formatted_lines = []
        indent = 0
        indent_char = '\t' if use_tabs else ' ' * tab_size

        for line in lines:
            stripped = line.strip()
            if not stripped:
                formatted_lines.append('')
                continue

            # Decrease indent before End
            if stripped.startswith('End') or stripped == 'Else' or stripped.startswith('Catch') or stripped.startswith('Default') or stripped.startswith('When '):
                if stripped.startswith('End'):
                    indent = max(0, indent - 1)

            formatted_lines.append(indent_char * indent + stripped)

            # Increase indent after block openers
            if any(stripped.startswith(kw) for kw in [
                'If ', 'While ', 'For ', 'Repeat ', 'Function ', 'Async Function ',
                'Class ', 'Try', 'Match '
            ]):
                indent += 1
            elif stripped in ('Else', 'Else.') or stripped.startswith('Catch') or stripped.startswith('Default') or stripped.startswith('When '):
                indent += 1

        # Build a single edit replacing entire document
        formatted_text = '\n'.join(formatted_lines)
        if formatted_text == source:
            return []
        return [{
            'range': {
                'start': {'line': 0, 'character': 0},
                'end': {'line': len(lines), 'character': 0}
            },
            'newText': formatted_text
        }]


# ═══════════════════════════════════════════════════════════
# JSON-RPC Transport Layer
# ═══════════════════════════════════════════════════════════

class JSONRPC:
    """JSON-RPC 2.0 message handling over stdio/TCP."""

    def __init__(self, reader=None, writer=None):
        self.reader = reader or sys.stdin.buffer
        self.writer = writer or sys.stdout.buffer
        self._lock = threading.Lock()

    def read_message(self) -> Optional[dict]:
        """Read a JSON-RPC message with Content-Length header."""
        try:
            headers = {}
            while True:
                line = self.reader.readline()
                if not line:
                    return None
                line = line.decode('utf-8').strip()
                if not line:
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            content_length = int(headers.get('content-length', 0))
            if content_length == 0:
                return None

            body = self.reader.read(content_length)
            return json.loads(body.decode('utf-8'))
        except Exception:
            return None

    def write_message(self, msg: dict):
        """Write a JSON-RPC message with Content-Length header."""
        body = json.dumps(msg).encode('utf-8')
        header = f'Content-Length: {len(body)}\r\n\r\n'.encode('utf-8')
        with self._lock:
            self.writer.write(header + body)
            self.writer.flush()


# ═══════════════════════════════════════════════════════════
# EPL Language Server
# ═══════════════════════════════════════════════════════════

class EPLLanguageServer:
    """LSP server for EPL language."""

    def __init__(
        self,
        transport: JSONRPC,
        change_debounce_seconds: Optional[float] = None,
        analysis_timeout_seconds: Optional[float] = None,
    ):
        self.transport = transport
        self.analyzer = EPLAnalyzer()
        self.running = True
        self.initialized = False
        self.shutdown_requested = False
        self.change_debounce_seconds = (
            float(os.environ.get('EPL_LSP_DEBOUNCE_SECONDS', '0.05'))
            if change_debounce_seconds is None else change_debounce_seconds
        )
        self.analysis_timeout_seconds = (
            float(os.environ.get('EPL_LSP_ANALYSIS_TIMEOUT_SECONDS', '1.0'))
            if analysis_timeout_seconds is None else analysis_timeout_seconds
        )
        self._analysis_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_document_updates: Dict[str, str] = {}
        self._debounce_timers: Dict[str, threading.Timer] = {}

    def run(self):
        """Main server loop."""
        while self.running:
            msg = self.transport.read_message()
            if msg is None:
                break
            try:
                self._handle_message(msg)
            except Exception as e:
                traceback.print_exc(file=sys.stderr)
                if 'id' in msg:
                    self._send_error(msg['id'], -32603, str(e))

    def _handle_message(self, msg: dict):
        """Route JSON-RPC message to handler."""
        method = msg.get('method', '')
        params = msg.get('params', {})
        msg_id = msg.get('id')

        handlers = {
            'initialize': self._on_initialize,
            'initialized': self._on_initialized,
            'shutdown': self._on_shutdown,
            'exit': self._on_exit,
            'textDocument/didOpen': self._on_did_open,
            'textDocument/didChange': self._on_did_change,
            'textDocument/didClose': self._on_did_close,
            'textDocument/didSave': self._on_did_save,
            'textDocument/completion': self._on_completion,
            'textDocument/hover': self._on_hover,
            'textDocument/definition': self._on_definition,
            'textDocument/references': self._on_references,
            'textDocument/rename': self._on_rename,
            'textDocument/codeAction': self._on_code_action,
            'textDocument/signatureHelp': self._on_signature_help,
            'textDocument/documentSymbol': self._on_document_symbol,
            'textDocument/formatting': self._on_formatting,
        }

        handler = handlers.get(method)
        if handler:
            result = handler(params)
            if msg_id is not None:
                self._send_response(msg_id, result)
        elif msg_id is not None:
            # Unknown request method
            self._send_error(msg_id, -32601, f'Method not found: {method}')

    # ─── LSP Lifecycle ──────────────────────────────

    def _on_initialize(self, params: dict) -> dict:
        self.initialized = True
        return {
            'capabilities': {
                'textDocumentSync': {
                    'openClose': True,
                    'change': 1,  # Full content sync
                    'save': {'includeText': True}
                },
                'completionProvider': {
                    'triggerCharacters': ['.', '(', '"'],
                    'resolveProvider': False
                },
                'hoverProvider': True,
                'definitionProvider': True,
                'referencesProvider': True,
                'renameProvider': True,
                'codeActionProvider': True,
                'signatureHelpProvider': {
                    'triggerCharacters': ['(', ','],
                },
                'documentSymbolProvider': True,
                'documentFormattingProvider': True,
            },
            'serverInfo': {
                'name': 'EPL Language Server',
                'version': '2.0.0'
            }
        }

    def _on_initialized(self, params: dict):
        return None

    def _on_shutdown(self, params: dict):
        self.shutdown_requested = True
        return None

    def _on_exit(self, params: dict):
        self.running = False
        sys.exit(0 if self.shutdown_requested else 1)

    # ─── Document Sync ──────────────────────────────

    def _on_did_open(self, params: dict):
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        text = td.get('text', '')
        self._queue_document_update(uri, text, immediate=True)

    def _on_did_change(self, params: dict):
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        changes = params.get('contentChanges', [])
        if changes:
            text = changes[-1].get('text', '')
            self._queue_document_update(uri, text)

    def _on_did_close(self, params: dict):
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._cancel_pending_update(uri)
        # Clear diagnostics on close
        self.analyzer.documents.pop(uri, None)
        self.analyzer.symbols.pop(uri, None)
        self.analyzer.diagnostics.pop(uri, None)
        self._notify('textDocument/publishDiagnostics', {
            'uri': uri, 'diagnostics': []
        })

    def _on_did_save(self, params: dict):
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        text = params.get('text')
        if text:
            self._queue_document_update(uri, text, immediate=True)
        else:
            self._ensure_document_analyzed(uri)
            self._publish_diagnostics(uri)

    # ─── LSP Features ──────────────────────────────

    def _on_completion(self, params: dict) -> dict:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        items = self.analyzer.get_completions(uri, pos.get('line', 0), pos.get('character', 0))
        return {'isIncomplete': False, 'items': items}

    def _on_hover(self, params: dict) -> Optional[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        return self.analyzer.get_hover(uri, pos.get('line', 0), pos.get('character', 0))

    def _on_definition(self, params: dict) -> Optional[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        return self.analyzer.get_definition(uri, pos.get('line', 0), pos.get('character', 0))

    def _on_document_symbol(self, params: dict) -> List[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        return self.analyzer.symbols.get(uri, [])

    def _on_formatting(self, params: dict) -> List[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        options = params.get('options', {})
        return self.analyzer.get_formatting(uri, options)

    def _on_references(self, params: dict) -> List[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        return self.analyzer.get_references(uri, pos.get('line', 0), pos.get('character', 0))

    def _on_rename(self, params: dict) -> dict:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        new_name = params.get('newName', '')
        return self.analyzer.get_rename_edits(uri, pos.get('line', 0), pos.get('character', 0), new_name)

    def _on_code_action(self, params: dict) -> List[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        context = params.get('context', {})
        diagnostics = context.get('diagnostics', [])
        return self.analyzer.get_code_actions(uri, diagnostics)

    def _on_signature_help(self, params: dict) -> Optional[dict]:
        td = params.get('textDocument', {})
        uri = td.get('uri', '')
        self._ensure_document_analyzed(uri)
        pos = params.get('position', {})
        return self.analyzer.get_signature_help(uri, pos.get('line', 0), pos.get('character', 0))

    # ─── Helpers ────────────────────────────────────

    def _cancel_pending_update(self, uri: str):
        with self._pending_lock:
            timer = self._debounce_timers.pop(uri, None)
            self._pending_document_updates.pop(uri, None)
        if timer is not None:
            timer.cancel()

    def _queue_document_update(self, uri: str, text: str, immediate: bool = False):
        self.analyzer.set_document_text(uri, text)
        if immediate or self.change_debounce_seconds <= 0:
            self._cancel_pending_update(uri)
            if self._analyze_document(uri, text):
                self._publish_diagnostics(uri)
            return

        with self._pending_lock:
            self._pending_document_updates[uri] = text
            timer = self._debounce_timers.pop(uri, None)
            if timer is not None:
                timer.cancel()
            timer = threading.Timer(self.change_debounce_seconds, self._flush_document_update, args=(uri,))
            timer.daemon = True
            self._debounce_timers[uri] = timer
            timer.start()

    def _flush_document_update(self, uri: str):
        with self._pending_lock:
            text = self._pending_document_updates.pop(uri, None)
            self._debounce_timers.pop(uri, None)
        if text is None:
            return
        if self._analyze_document(uri, text):
            self._publish_diagnostics(uri)

    def _ensure_document_analyzed(self, uri: str):
        with self._pending_lock:
            text = self._pending_document_updates.pop(uri, None)
            timer = self._debounce_timers.pop(uri, None)
        if timer is not None:
            timer.cancel()
        if text is not None:
            self._analyze_document(uri, text)

    def _analyze_document(self, uri: str, text: str) -> bool:
        with self._analysis_lock:
            symbols, diagnostics = self._compute_analysis(text)
            if self.analyzer.documents.get(uri) != text:
                return False
            self.analyzer.apply_document_analysis(uri, text, symbols, diagnostics)
            return True

    def _compute_analysis(self, text: str) -> Tuple[List[dict], List[dict]]:
        result: Dict[str, Tuple[List[dict], List[dict]]] = {}
        error: Dict[str, Exception] = {}

        def worker():
            try:
                result['value'] = self.analyzer.analyze_text(text)
            except Exception as exc:
                error['value'] = exc

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        timeout = self.analysis_timeout_seconds if self.analysis_timeout_seconds and self.analysis_timeout_seconds > 0 else None
        thread.join(timeout)

        if thread.is_alive():
            symbols = self.analyzer._regex_extract_symbols(text)
            diagnostics = self.analyzer.make_internal_diagnostics(
                text,
                f'Analysis timed out after {self.analysis_timeout_seconds:.2f}s. Retry after the file settles.',
                source_name='epl-lsp-timeout',
            )
            return symbols, diagnostics

        if 'value' in error:
            symbols = self.analyzer._regex_extract_symbols(text)
            diagnostics = self.analyzer.make_internal_diagnostics(
                text,
                f'Analysis failed: {error["value"]}',
            )
            return symbols, diagnostics

        return result.get('value', ([], []))

    def _publish_diagnostics(self, uri: str):
        """Send diagnostics to client."""
        diagnostics = self.analyzer.diagnostics.get(uri, [])
        self._notify('textDocument/publishDiagnostics', {
            'uri': uri,
            'diagnostics': diagnostics
        })

    def _send_response(self, msg_id, result):
        self.transport.write_message({
            'jsonrpc': '2.0',
            'id': msg_id,
            'result': result
        })

    def _send_error(self, msg_id, code, message):
        self.transport.write_message({
            'jsonrpc': '2.0',
            'id': msg_id,
            'error': {'code': code, 'message': message}
        })

    def _notify(self, method, params):
        self.transport.write_message({
            'jsonrpc': '2.0',
            'method': method,
            'params': params
        })


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='EPL Language Server')
    parser.add_argument('--tcp', action='store_true', help='Use TCP transport on port 2087')
    parser.add_argument('--port', type=int, default=2087, help='TCP port (default: 2087)')
    args = parser.parse_args()

    if args.tcp:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', args.port))
        sock.listen(1)
        print(f'EPL Language Server listening on port {args.port}...', file=sys.stderr)
        conn, addr = sock.accept()
        print(f'Client connected from {addr}', file=sys.stderr)
        reader = conn.makefile('rb')
        writer = conn.makefile('wb')
        transport = JSONRPC(reader, writer)
    else:
        transport = JSONRPC()

    server = EPLLanguageServer(transport)
    server.run()


if __name__ == '__main__':
    main()
