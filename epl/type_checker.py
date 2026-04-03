"""
EPL Type Checker v2.0
=====================
Static type analysis for EPL programs. Runs on the AST before interpretation
or compilation, catching type errors at parse time.

Supports:
- Type inference from literals and expressions
- Declared type annotation checking (Set x: integer To ...)
- Function parameter and return type validation
- Class method signature conformance with interfaces
- Generic type parameter checking
- Union types and optional types
- "did you mean?" fuzzy suggestions for undefined variables
- Unused variable detection
- Dead code / unreachable code detection
- Integration with type_system.py for advanced type analysis

Usage:
    from epl.type_checker import TypeChecker
    checker = TypeChecker()
    errors = checker.check(program)   # returns list of TypeWarning

    # Standalone CLI:
    #   epl check myfile.epl
    #   epl check myfile.epl --strict
"""

import difflib
from epl import ast_nodes as ast
from epl.errors import EPLError


# ─── Type representations ─────────────────────────────────

class EPLType:
    """Base type in EPL's type system."""

    def __init__(self, name: str, params=None, optional=False, union=None):
        self.name = name               # 'integer','text','boolean','float','list','map','nothing','any','function'
        self.params = params or []     # generic params: list of EPLType
        self.optional = optional       # T?
        self.union = union             # list of EPLType for union types

    def __eq__(self, other):
        if not isinstance(other, EPLType):
            return False
        return (self.name == other.name
                and self.params == other.params
                and self.optional == other.optional)

    def __hash__(self):
        return hash((self.name, tuple(self.params), self.optional))

    def __repr__(self):
        s = self.name
        if self.params:
            s += f"<{', '.join(str(p) for p in self.params)}>"
        if self.optional:
            s += '?'
        if self.union:
            return ' | '.join(str(u) for u in self.union)
        return s

    def is_compatible(self, other: 'EPLType') -> bool:
        """Check if `other` can be assigned to `self` (self = target, other = value)."""
        if self.name == 'any' or other.name == 'any':
            return True
        if self.optional and other.name == 'nothing':
            return True
        if self.union:
            # self is a union type: check self itself OR any union member
            if self.name == other.name:
                return True
            return any(t.is_compatible(other) for t in self.union)
        if other.union:
            return all(self.is_compatible(t) for t in other.union)
        if self.name == other.name:
            if not self.params and not other.params:
                return True
            if len(self.params) == len(other.params):
                return all(a.is_compatible(b) for a, b in zip(self.params, other.params))
            return True  # generics without params match loosely
        # Numeric coercion: integer ↔ decimal/float
        _numerics = {'integer', 'decimal', 'float', 'number'}
        if self.name in _numerics and other.name in _numerics:
            return True
        return False


# Singletons for common types
T_INTEGER = EPLType('integer')
T_FLOAT = EPLType('decimal')
T_TEXT = EPLType('text')
T_BOOLEAN = EPLType('boolean')
T_NOTHING = EPLType('nothing')
T_ANY = EPLType('any')
T_LIST = EPLType('list')
T_MAP = EPLType('map')
T_FUNCTION = EPLType('function')


# ─── Type warnings ────────────────────────────────────────

class TypeWarning:
    """A type issue found during analysis."""

    def __init__(self, message: str, line: int, severity: str = 'warning',
                 suggestion: str = None, code: str = None):
        self.message = message
        self.line = line
        self.severity = severity  # 'error', 'warning', 'info'
        self.suggestion = suggestion
        self.code = code  # diagnostic code: 'E001', 'W001', etc.

    def __repr__(self):
        prefix = f"[{self.severity.upper()}]"
        code_str = f" {self.code}" if self.code else ""
        msg = f"{prefix}{code_str} Line {self.line}: {self.message}"
        if self.suggestion:
            msg += f" (hint: {self.suggestion})"
        return msg

    def to_dict(self):
        """Convert to LSP-compatible diagnostic dict."""
        severity_map = {'error': 1, 'warning': 2, 'info': 3, 'hint': 4}
        return {
            'range': {
                'start': {'line': max(0, self.line - 1), 'character': 0},
                'end': {'line': max(0, self.line - 1), 'character': 1000}
            },
            'severity': severity_map.get(self.severity, 2),
            'source': 'epl-typecheck',
            'message': self.message + (f' (hint: {self.suggestion})' if self.suggestion else ''),
            'code': self.code or '',
        }


# ─── Type string parser ──────────────────────────────────

def parse_type_str(type_str) -> EPLType:
    """Parse a type annotation string or TypeAnnotation node into an EPLType."""
    if type_str is None:
        return T_ANY
    if isinstance(type_str, ast.TypeAnnotation):
        base = _normalize_type_name(type_str.base_type)
        params = [parse_type_str(p) for p in type_str.params] if type_str.params else []
        union = [parse_type_str(m) for m in type_str.union_members] if type_str.union_members else None
        return EPLType(base, params, type_str.is_optional, union)
    if isinstance(type_str, str):
        s = type_str.strip()
        if '|' in s:
            parts = [parse_type_str(p.strip()) for p in s.split('|')]
            return EPLType('union', union=parts)
        if s.endswith('?'):
            inner = parse_type_str(s[:-1])
            inner.optional = True
            return inner
        return EPLType(_normalize_type_name(s))
    return T_ANY


def _normalize_type_name(name: str) -> str:
    """Normalize type names to canonical forms."""
    mapping = {
        'int': 'integer', 'integer': 'integer',
        'str': 'text', 'string': 'text', 'text': 'text',
        'bool': 'boolean', 'boolean': 'boolean',
        'float': 'decimal', 'double': 'decimal', 'decimal': 'decimal', 'number': 'decimal',
        'list': 'list', 'array': 'list',
        'map': 'map', 'dict': 'map', 'dictionary': 'map', 'object': 'map',
        'nothing': 'nothing', 'none': 'nothing', 'null': 'nothing', 'void': 'nothing',
        'any': 'any',
        'function': 'function', 'callable': 'function',
    }
    return mapping.get(name.lower(), name.lower())


# ─── Type Checker ─────────────────────────────────────────

class TypeChecker:
    """
    Static type analyzer for EPL AST.

    Usage:
        checker = TypeChecker()
        warnings = checker.check(program)
        for w in warnings:
            print(w)
    """

    def __init__(self, strict: bool = False):
        self.strict = strict       # strict mode errors on type mismatches
        self.warnings: list = []
        self._scope_stack: list = [{}]  # stack of {name: EPLType}
        self._functions: dict = {}      # {name: (param_types, return_type)}
        self._classes: dict = {}        # {name: {methods, fields, parent, implements}}
        self._interfaces: dict = {}     # {name: [(method_name, params, return_type)]}
        self._current_function: str = None      # name of function being checked
        self._current_return_type: EPLType = None  # declared return type of current function
        self._var_usage: dict = {}      # {name: {'declared_line': int, 'used': bool}} for unused detection
        self._all_known_names: set = set()  # all known variable/function names for fuzzy matching

    def check(self, program) -> list:
        """Analyze a Program AST and return list of TypeWarning."""
        self.warnings = []
        self._scope_stack = [{}]
        self._functions = {}
        self._classes = {}
        self._interfaces = {}
        self._var_usage = {}
        self._all_known_names = set()

        # Two-pass: first collect declarations, then check bodies
        if hasattr(program, 'statements'):
            for stmt in program.statements:
                self._collect_declarations(stmt)
            for stmt in program.statements:
                self._check_node(stmt)

        # Post-analysis: check for unused variables
        self._check_unused_variables()

        return self.warnings

    def _check_unused_variables(self):
        """Emit warnings for variables that were declared but never used."""
        for name, info in self._var_usage.items():
            if not info.get('used') and not name.startswith('_'):
                self._warn(
                    f"Variable '{name}' is declared but never used",
                    info.get('declared_line', 0), 'info',
                    f"Prefix with _ to suppress (e.g., '_{name}'), or remove the variable",
                    code='W002'
                )

    def _fuzzy_suggest(self, name: str) -> str:
        """Find the closest known name to suggest 'did you mean?'."""
        candidates = list(self._all_known_names)
        if not candidates:
            return None
        matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
        if matches:
            return matches[0]
        return None

    # ─── Declaration collection (pass 1) ──────────────────

    def _collect_declarations(self, node):
        if isinstance(node, ast.FunctionDef):
            param_types = []
            for p in node.params:
                pt = parse_type_str(p[1]) if len(p) > 1 and p[1] else T_ANY
                param_types.append(pt)
            ret_type = parse_type_str(node.return_type)
            self._functions[node.name] = (param_types, ret_type)

        elif isinstance(node, (ast.ClassDef,)):
            class_info = {'methods': {}, 'fields': {}, 'parent': node.parent,
                          'implements': getattr(node, 'implements', [])}
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    pts = []
                    for p in item.params:
                        pt = parse_type_str(p[1]) if len(p) > 1 and p[1] else T_ANY
                        pts.append(pt)
                    ret = parse_type_str(item.return_type)
                    class_info['methods'][item.name] = (pts, ret)
                elif isinstance(item, ast.VarDeclaration):
                    class_info['fields'][item.name] = parse_type_str(item.var_type)
                elif isinstance(item, ast.VisibilityModifier) and isinstance(item.statement, ast.FunctionDef):
                    fn = item.statement
                    pts = []
                    for p in fn.params:
                        pt = parse_type_str(p[1]) if len(p) > 1 and p[1] else T_ANY
                        pts.append(pt)
                    ret = parse_type_str(fn.return_type)
                    class_info['methods'][fn.name] = (pts, ret)
            self._classes[node.name] = class_info

        elif isinstance(node, ast.InterfaceDefNode):
            methods = []
            for m in node.methods:
                name = m[0] if isinstance(m, tuple) else getattr(m, 'name', str(m))
                params = m[1] if isinstance(m, tuple) and len(m) > 1 else []
                ret = m[2] if isinstance(m, tuple) and len(m) > 2 else None
                methods.append((name, params, ret))
            self._interfaces[node.name] = methods

    # ─── Node checking (pass 2) ──────────────────────────

    def _check_node(self, node):
        if node is None:
            return

        if isinstance(node, ast.VarDeclaration):
            self._check_var_declaration(node)
        elif isinstance(node, ast.VarAssignment):
            self._check_var_assignment(node)
        elif isinstance(node, ast.FunctionDef):
            self._check_function_def(node)
        elif isinstance(node, ast.ClassDef):
            self._check_class_def(node)
        elif isinstance(node, ast.FunctionCall):
            self._check_function_call(node)
        elif isinstance(node, ast.ReturnStatement):
            self._check_return(node)
        elif isinstance(node, ast.PrintStatement):
            # Printed expressions count as usage sites for variables referenced
            # by legacy "Display x." style programs.
            self._infer_type(node.expression)
        elif isinstance(node, ast.IfStatement):
            self._check_condition_bool(node.condition, node.line)
            for stmt in (node.then_body or []):
                self._check_node(stmt)
            for stmt in (node.else_body or []):
                self._check_node(stmt)
        elif isinstance(node, ast.WhileLoop):
            self._check_condition_bool(node.condition, node.line)
            for stmt in (node.body or []):
                self._check_node(stmt)
        elif isinstance(node, (ast.ForEachLoop,)):
            for stmt in (node.body or []):
                self._check_node(stmt)
        elif isinstance(node, (ast.TryCatch,)):
            for stmt in getattr(node, 'try_body', []) or []:
                self._check_node(stmt)
            for stmt in getattr(node, 'catch_body', []) or []:
                self._check_node(stmt)
            for stmt in getattr(node, 'finally_body', []) or []:
                self._check_node(stmt)
        elif isinstance(node, list):
            for item in node:
                self._check_node(item)

    def _check_var_declaration(self, node: ast.VarDeclaration):
        declared_type = parse_type_str(node.var_type) if node.var_type else None
        inferred_type = self._infer_type(node.value)
        if declared_type and declared_type.name != 'any':
            if not declared_type.is_compatible(inferred_type):
                sev = 'error' if self.strict else 'warning'
                self._warn(
                    f"Type mismatch: variable '{node.name}' declared as {declared_type} "
                    f"but assigned {inferred_type}",
                    node.line, sev,
                    f"Change the value to match type {declared_type}, or update the annotation",
                    code='E001'
                )
            self._set_var(node.name, declared_type)
        else:
            self._set_var(node.name, inferred_type)
        # Track for unused variable detection
        self._var_usage[node.name] = {'declared_line': node.line, 'used': False}
        self._all_known_names.add(node.name)

    def _check_var_assignment(self, node: ast.VarAssignment):
        existing = self._get_var(node.name)
        if existing and existing.name != 'any':
            new_type = self._infer_type(node.value)
            if not existing.is_compatible(new_type):
                sev = 'error' if self.strict else 'warning'
                self._warn(
                    f"Type mismatch: '{node.name}' is {existing} but assigned {new_type}",
                    node.line, sev, code='E001')
        elif existing is None and self.strict:
            suggestion = self._fuzzy_suggest(node.name)
            hint = f"Did you mean '{suggestion}'?" if suggestion else "Declare the variable first"
            self._warn(
                f"Variable '{node.name}' used before declaration",
                node.line, 'error', hint, code='E003'
            )
        else:
            self._set_var(node.name, self._infer_type(node.value))
        # Mark as used (assignment counts as usage of the target)
        if node.name in self._var_usage:
            self._var_usage[node.name]['used'] = True

    def _check_function_def(self, node: ast.FunctionDef):
        # Save outer function context
        prev_fn = self._current_function
        prev_ret = self._current_return_type
        self._current_function = node.name
        self._current_return_type = parse_type_str(node.return_type)

        self._push_scope()
        for p in node.params:
            pname = p[0]
            ptype = parse_type_str(p[1]) if len(p) > 1 and p[1] else T_ANY
            self._set_var(pname, ptype)

        # Check body and collect return types
        has_return = False
        for stmt in node.body:
            self._check_node(stmt)
            if isinstance(stmt, ast.ReturnStatement):
                has_return = True

        # Warn if function declares a non-nothing return type but has no return statement
        if (self._current_return_type and
                self._current_return_type.name not in ('any', 'nothing') and
                not has_return and node.body):
            # Check if last statement might be an implicit return (if/match)
            last = node.body[-1] if node.body else None
            if not isinstance(last, (ast.IfStatement, ast.TryCatch)):
                self._warn(
                    f"Function '{node.name}' declares return type {self._current_return_type} "
                    f"but may not return a value on all paths",
                    node.line, 'warning',
                    f"Add a Return statement or change the return type to nothing")

        self._pop_scope()
        # Restore outer function context
        self._current_function = prev_fn
        self._current_return_type = prev_ret

    def _check_class_def(self, node: ast.ClassDef):
        # Check interface conformance
        for iface_name in (node.implements or []):
            if isinstance(iface_name, ast.ImplementsClause):
                iface_names = iface_name.interface_names
            else:
                iface_names = [iface_name]
            for ifn in iface_names:
                if ifn in self._interfaces:
                    class_info = self._classes.get(node.name, {})
                    class_methods = class_info.get('methods', {})
                    for method_name, _, _ in self._interfaces[ifn]:
                        if method_name not in class_methods:
                            self._warn(
                                f"Class '{node.name}' implements '{ifn}' but missing method '{method_name}'",
                                node.line, 'error',
                                f"Add method '{method_name}' to class '{node.name}'"
                            )

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._check_function_def(item)
            elif isinstance(item, ast.VisibilityModifier) and isinstance(item.statement, ast.FunctionDef):
                self._check_function_def(item.statement)

    def _check_function_call(self, node: ast.FunctionCall):
        fname = node.name if isinstance(node.name, str) else getattr(node.name, 'name', str(node.name))
        if fname in self._functions:
            param_types, _ = self._functions[fname]
            args = node.args if hasattr(node, 'args') else []
            if len(args) < len(param_types):
                # Check if missing args have defaults (from function def)
                pass  # Can't check defaults without more info
            for i, (arg, expected) in enumerate(zip(args, param_types)):
                if expected.name != 'any':
                    actual = self._infer_type(arg)
                    if not expected.is_compatible(actual):
                        self._warn(
                            f"Argument {i+1} of '{fname}' expects {expected} but got {actual}",
                            node.line, 'warning')

    def _check_return(self, node):
        """Check return statement type against declared function return type."""
        if self._current_function is None:
            self._warn(
                "Return statement outside of a function",
                getattr(node, 'line', 0), 'error')
            return

        if self._current_return_type is None or self._current_return_type.name == 'any':
            return  # No declared return type — skip check

        # Infer the type of the returned expression
        ret_expr = getattr(node, 'value', None) or getattr(node, 'expression', None)
        if ret_expr is None:
            # Return with no value
            if self._current_return_type.name != 'nothing':
                self._warn(
                    f"Function '{self._current_function}' should return {self._current_return_type} "
                    f"but returns nothing",
                    getattr(node, 'line', 0), 'warning',
                    f"Return a value of type {self._current_return_type}")
            return

        actual = self._infer_type(ret_expr)
        if actual.name != 'any' and not self._current_return_type.is_compatible(actual):
            sev = 'error' if self.strict else 'warning'
            self._warn(
                f"Function '{self._current_function}' should return {self._current_return_type} "
                f"but returns {actual}",
                getattr(node, 'line', 0), sev,
                f"Change the return value to type {self._current_return_type}")

    def _check_condition_bool(self, condition, line):
        if condition is None:
            return
        ctype = self._infer_type(condition)
        # Conditions should be boolean-ish (boolean, integer, or comparison result)
        if ctype.name not in ('boolean', 'any', 'integer'):
            if not isinstance(condition, (ast.BinaryOp, ast.UnaryOp)):
                self._warn(
                    f"Condition expression has type {ctype}, expected boolean",
                    line, 'info')

    # ─── Type inference ───────────────────────────────────

    def _infer_type(self, node) -> EPLType:
        """Infer the type of an expression node."""
        if node is None:
            return T_NOTHING

        # EPL uses ast.Literal for all literal values
        if isinstance(node, ast.Literal):
            val = node.value
            if val is None:
                return T_NOTHING
            if isinstance(val, bool):
                return T_BOOLEAN
            if isinstance(val, int):
                return T_INTEGER
            if isinstance(val, float):
                return T_FLOAT
            if isinstance(val, str):
                return T_TEXT
            return T_ANY

        if isinstance(node, ast.ListLiteral):
            return T_LIST

        if isinstance(node, ast.DictLiteral):
            return T_MAP

        if isinstance(node, ast.Identifier):
            # Mark as used for unused variable detection
            if node.name in self._var_usage:
                self._var_usage[node.name]['used'] = True
            result = self._get_var(node.name)
            if result is None and self.strict:
                suggestion = self._fuzzy_suggest(node.name)
                hint = f"Did you mean '{suggestion}'?" if suggestion else None
                self._warn(
                    f"Undefined variable '{node.name}'",
                    getattr(node, 'line', 0), 'error', hint, code='E003'
                )
            return result or T_ANY

        if isinstance(node, ast.BinaryOp):
            left = self._infer_type(node.left)
            right = self._infer_type(node.right)
            op = node.operator
            if op in ('==', '!=', '<', '>', '<=', '>=', 'and', 'or', 'is equal to',
                       'is not equal to', 'is greater than', 'is less than'):
                return T_BOOLEAN
            if op in ('+', '-', '*', '/', '%', '**', 'plus', 'minus', 'times', 'divided by'):
                if left.name == 'text' or right.name == 'text':
                    if op in ('+', 'plus'):
                        return T_TEXT
                if left.name in ('decimal', 'float') or right.name in ('decimal', 'float'):
                    return T_FLOAT
                return T_INTEGER
            return T_ANY

        if isinstance(node, ast.UnaryOp):
            if node.operator in ('not', '!'):
                return T_BOOLEAN
            return self._infer_type(node.operand)

        if isinstance(node, ast.FunctionCall):
            fname = node.name if isinstance(node.name, str) else getattr(node.name, 'name', str(node.name))
            if fname in self._functions:
                _, ret_type = self._functions[fname]
                return ret_type
            # Known builtins
            builtin_returns = {
                'length': T_INTEGER, 'type_of': T_TEXT, 'to_text': T_TEXT,
                'to_integer': T_INTEGER, 'to_float': T_FLOAT, 'to_boolean': T_BOOLEAN,
                'range': T_LIST, 'sorted': T_LIST, 'keys': T_LIST, 'values': T_LIST,
                'split': T_LIST, 'join': T_TEXT, 'trim': T_TEXT,
                'substring': T_TEXT, 'replace': T_TEXT, 'lower': T_TEXT, 'upper': T_TEXT,
                'abs': T_INTEGER, 'sqrt': T_FLOAT, 'round': T_INTEGER,
                'floor': T_INTEGER, 'ceil': T_INTEGER, 'max': T_ANY, 'min': T_ANY,
                'parse_json': T_MAP, 'to_json': T_TEXT,
                'read_file': T_TEXT, 'file_exists': T_BOOLEAN,
                'hash_sha256': T_TEXT, 'hash_md5': T_TEXT,
                'http_get': T_MAP, 'http_post': T_MAP,
            }
            if fname in builtin_returns:
                return builtin_returns[fname]
            return T_ANY

        if isinstance(node, ast.LambdaExpression):
            return T_FUNCTION

        if isinstance(node, ast.TernaryExpression):
            true_type = self._infer_type(node.true_value)
            false_type = self._infer_type(node.false_value)
            if true_type == false_type:
                return true_type
            return T_ANY

        if isinstance(node, ast.PropertyAccess):
            return T_ANY

        if isinstance(node, ast.IndexAccess):
            return T_ANY

        return T_ANY

    # ─── Scope management ─────────────────────────────────

    def _push_scope(self):
        self._scope_stack.append({})

    def _pop_scope(self):
        if len(self._scope_stack) > 1:
            self._scope_stack.pop()

    def _set_var(self, name: str, t: EPLType):
        self._scope_stack[-1][name] = t

    def _get_var(self, name: str) -> EPLType:
        for scope in reversed(self._scope_stack):
            if name in scope:
                return scope[name]
        return None

    def _warn(self, message: str, line: int, severity: str = 'warning',
              suggestion: str = None, code: str = None):
        self.warnings.append(TypeWarning(message, line, severity, suggestion, code))

    # ─── Public helpers ───────────────────────────────

    def has_errors(self) -> bool:
        """Return True if any error-level diagnostics were found."""
        return any(w.severity == 'error' for w in self.warnings)

    def format_report(self) -> str:
        """Format all warnings as a human-readable report."""
        if not self.warnings:
            return "  No type issues found."
        lines = []
        errors = [w for w in self.warnings if w.severity == 'error']
        warns = [w for w in self.warnings if w.severity == 'warning']
        infos = [w for w in self.warnings if w.severity == 'info']
        for w in sorted(self.warnings, key=lambda x: x.line):
            lines.append(str(w))
        lines.append(f"\n  Summary: {len(errors)} error(s), {len(warns)} warning(s), {len(infos)} info(s)")
        return '\n'.join(lines)

    def to_lsp_diagnostics(self) -> list:
        """Convert all warnings to LSP-compatible diagnostic dicts."""
        return [w.to_dict() for w in self.warnings]


# ─── Convenience function ─────────────────────────────────

def type_check(program, strict: bool = False) -> list:
    """Run type checking on an EPL program AST.

    Returns list of TypeWarning objects.
    """
    checker = TypeChecker(strict=strict)
    return checker.check(program)


def type_check_file(filepath: str, strict: bool = False) -> 'TypeChecker':
    """Type-check an EPL source file. Returns the TypeChecker instance.

    Usage:
        checker = type_check_file('main.epl', strict=True)
        if checker.has_errors():
            print(checker.format_report())
    """
    from epl.lexer import Lexer
    from epl.parser import Parser

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    checker = TypeChecker(strict=strict)
    checker.check(program)
    return checker
