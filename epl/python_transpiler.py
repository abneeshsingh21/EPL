"""
EPL-to-Python Transpiler
========================
Transpiles EPL AST to clean, idiomatic Python 3 code.
Usage:  epl export python myprogram.epl
"""

import keyword as _keyword
import re as _re
from typing import AbstractSet

from epl import ast_nodes as ast


class TranspileError(Exception):
    """Raised when EPL source cannot be faithfully transpiled to Python.

    The transpiler's contract is correct-or-loud: it either emits Python that
    behaves like `epl run`, or it refuses with this error. It must never emit
    code that is syntactically valid but semantically wrong — that is the one
    failure mode a production transpiler cannot have.
    """


# Authoritative set of every name EPL treats as a builtin (core + stdlib). The
# transpiler idiomatically maps the common ones and routes the rest through the
# real runtime; either way it needs to know which bare calls are builtins (so it
# can distinguish them from genuinely-undefined names and fail loud on the
# latter). Sourced from the interpreter so it can never drift out of sync.
_EPL_BUILTIN_NAMES: 'AbstractSet[str]'
try:  # pragma: no cover - import guard
    from epl.interpreter import BUILTINS as _EPL_BUILTIN_NAMES
except Exception:  # noqa: BLE001 - transpiler must load even if runtime import fails
    _EPL_BUILTIN_NAMES = frozenset()


# EPL built-in string/list/map methods whose names or semantics diverge from
# Python's (e.g. list `.add` is `.append`; `.join(sep)` reverses Python's
# receiver/arg; `.has` is `in`; `.substring` is slicing). These are routed
# through the `_epl_method` runtime shim for faithful behavior. Higher-order
# methods that take an EPL callable (map/filter/reduce/every/some/find) are
# deliberately excluded — they are handled by the `_EPLList` wrapper, since the
# interpreter's versions expect EPL function objects, not Python lambdas.
_EPL_HOF_METHODS = frozenset({'map', 'filter', 'reduce', 'every', 'some', 'find'})
_EPL_METHOD_NAMES = (
    frozenset(
        {
            # string
            'char_at',
            'count',
            'is_alpha',
            'is_empty',
            'is_number',
            'pad_left',
            'pad_right',
            'repeat',
            'substring',
            'to_list',
            'uppercase',
            'lowercase',
            'format',
            # list
            'add',
            'clear',
            'copy',
            'first',
            'flatten',
            'insert',
            'last',
            'remove',
            'slice',
            'unique',
            # map — keys/values return EPL lists, not Python dict views (dict_keys(...))
            'entries',
            'has',
            'merge',
            'set',
            'keys',
            'values',
            # shared: join reverses receiver/arg vs Python; reverse works on lists but
            # not strings in Python, and EPL supports both.
            'join',
            'reverse',
        }
    )
    - _EPL_HOF_METHODS
)


# Python names the transpiler emits as free references (for builtin mappings
# like length→len, to_integer→int) plus Python keywords. An EPL variable named
# any of these would shadow the emitted builtin — e.g. `len = length(x)` becomes
# `len = len(x)`, an UnboundLocalError. Bound EPL names that collide are renamed
# with a trailing underscore everywhere they appear, keeping generated code
# correct without constraining EPL identifiers.
_PY_RESERVED = frozenset(_keyword.kwlist) | frozenset(
    {
        'len',
        'int',
        'float',
        'str',
        'bool',
        'list',
        'dict',
        'set',
        'tuple',
        'round',
        'abs',
        'pow',
        'min',
        'max',
        'sum',
        'sorted',
        'reversed',
        'range',
        'enumerate',
        'zip',
        'map',
        'filter',
        'open',
        'input',
        'print',
        'type',
        'id',
        'iter',
        'next',
        'object',
        'super',
        'property',
        'format',
    }
)


# ── Public API ───────────────────────────────────────────


def transpile_to_python(program: ast.Program) -> str:
    """Transpile an EPL Program AST to Python 3 source code."""
    return PythonTranspiler().transpile(program)


# ── Transpiler ───────────────────────────────────────────


class PythonTranspiler:
    def __init__(self):
        self.indent = 0
        self.output: list[str] = []
        self.imports: set[str] = set()  # 'import X' lines
        self.from_imports: dict[str, set] = {}  # 'from X import Y'
        self.in_class = False
        self.class_properties: set[str] = set()
        self.user_functions: set[str] = set()
        # Runtime-helper usage flags. EPL's `+`, print formatting, division,
        # `.length`, and Map dot-access carry semantics plain Python does not
        # (auto-coercion, `true`/`false`/`nothing` display, int-preserving
        # division, dict attribute access). We emit a small `_epl_*` prelude —
        # but only the helpers a program actually uses, so a program that needs
        # none stays helper-free and fully idiomatic.
        self._need: set[str] = set()

    # ── Main entry ─────────────────────────────────────

    def transpile(self, program: ast.Program) -> str:
        # Pre-scan for function names
        for stmt in program.statements:
            if isinstance(stmt, ast.FunctionDef):
                self.user_functions.add(stmt.name)
            elif isinstance(stmt, ast.AsyncFunctionDef):
                self.user_functions.add(stmt.name)

        # Pre-scan to decide collection wrapping. EPL's list HOFs (`map`/
        # `filter`/`reduce`) and Map dot-access need list/dict subclasses to
        # behave like the interpreter; but wrapping every literal would clutter
        # programs that never use those features. A single field-agnostic walk
        # tells us whether the wrappers are worth emitting.
        method_names, class_names, bound_names = self._prescan(program)
        # Any EPL higher-order list method (map/filter/reduce/every/some/find)
        # needs the `_EPLList` wrapper, since Python's built-in list has none of
        # them and they take a Python lambda (so can't route through _epl_method).
        self._wrap_lists = bool(method_names & _EPL_HOF_METHODS)
        # Bound variable names, used to reproduce the interpreter's rule that a
        # bare `$var` template slot only interpolates when the variable exists.
        self._declared_vars = bound_names
        # Names that collide with a Python builtin/keyword the transpiler emits.
        # Renamed consistently (see _safe_name) so user code can freely use
        # identifiers like `len`, `list`, `type`, `sum` without shadowing.
        self._renames = {n: n + '_' for n in bound_names if n in _PY_RESERVED}
        # Dot-access on a Map is indistinguishable from a class-property access
        # at transpile time, so wrap dict literals whenever the program both
        # builds a map and accesses a property somewhere. Wrapping is always
        # semantically safe (a dict subclass); this rule just avoids the noise
        # in programs that only index maps with `["key"]`.
        self._wrap_maps = ('DictLiteral' in class_names) and ('PropertyAccess' in class_names)

        for stmt in program.statements:
            self._emit_stmt(stmt)

        header = []
        header.append('#!/usr/bin/env python3')
        header.append('"""Auto-generated from EPL source."""')
        header.append('')
        for mod in sorted(self.imports):
            header.append(mod)
        for mod, names in sorted(self.from_imports.items()):
            header.append(f'from {mod} import {", ".join(sorted(names))}')
        if self.imports or self.from_imports:
            header.append('')
        prelude = self._render_prelude()
        if prelude:
            header.append(prelude)
        header.append('')
        return '\n'.join(header) + '\n'.join(self.output) + '\n'

    def _render_prelude(self) -> str:
        """Emit only the `_epl_*` runtime helpers the program actually used.

        Each helper reproduces one EPL semantic that plain Python lacks, so
        transpiled code behaves byte-for-byte like `epl run`.
        """
        if not self._need:
            return ''
        parts = ['# ── EPL runtime helpers (semantic parity with the interpreter) ──']

        # `_epl_fmt`: EPL's display form — true/false/nothing, bracketed lists,
        # brace maps — used by print and by string `+`. Several helpers depend
        # on it, so emit it whenever any of them is needed.
        if self._need & {'fmt', 'add', 'print'}:
            parts.append(
                'def _epl_fmt(v):\n'
                '    if v is True: return "true"\n'
                '    if v is False: return "false"\n'
                '    if v is None: return "nothing"\n'
                '    if isinstance(v, list):\n'
                '        return "[" + ", ".join(_epl_fmt(x) for x in v) + "]"\n'
                '    if isinstance(v, dict):\n'
                '        return "{" + ", ".join(f"{k}: {_epl_fmt(x)}" for k, x in v.items()) + "}"\n'
                '    return str(v)'
            )
        if 'print' in self._need:
            parts.append('def _epl_print(v):\n    print(_epl_fmt(v))')
        if 'add' in self._need:
            parts.append(
                'def _epl_add(a, b):\n'
                '    if isinstance(a, str) or isinstance(b, str):\n'
                '        return _epl_fmt(a) + _epl_fmt(b)\n'
                '    return a + b'
            )
        if 'div' in self._need:
            parts.append(
                'def _epl_div(a, b):\n'
                '    if isinstance(a, int) and isinstance(b, int) and b != 0 and a % b == 0:\n'
                '        return a // b\n'
                '    return a / b'
            )
        if 'epllist' in self._need:
            # EPL's higher-order list methods take a Python lambda (not an EPL
            # function object), so they can't route through `_epl_method`. Provide
            # a `list` subclass with faithful implementations: `find` returns
            # `nothing` (None) on no match, `every`/`some` mirror all()/any().
            parts.append(
                'class _EPLList(list):\n'
                '    def map(self, fn): return _EPLList(fn(x) for x in self)\n'
                '    def filter(self, fn): return _EPLList(x for x in self if fn(x))\n'
                '    def reduce(self, fn, *init):\n'
                '        it = iter(self)\n'
                '        acc = init[0] if init else next(it)\n'
                '        for x in it: acc = fn(acc, x)\n'
                '        return acc\n'
                '    def every(self, fn): return all(bool(fn(x)) for x in self)\n'
                '    def some(self, fn): return any(bool(fn(x)) for x in self)\n'
                '    def find(self, fn):\n'
                '        for x in self:\n'
                '            if fn(x): return x\n'
                '        return None'
            )
        if 'dotdict' in self._need:
            parts.append(
                'class _EPLMap(dict):\n'
                '    def __getattr__(self, k):\n'
                '        try: return self[k]\n'
                '        except KeyError: raise AttributeError(k)\n'
                '    def __setattr__(self, k, v): self[k] = v'
            )
        if 'getattr' in self._need:
            # EPL's `obj.name` reads a Map key when obj is a mapping, else an
            # object attribute. Mirror that so Maps from any source (literals,
            # builtins, `Map with …`) support dot-access uniformly.
            parts.append(
                'def _epl_getattr(obj, name):\n'
                '    if isinstance(obj, dict):\n'
                '        try: return obj[name]\n'
                '        except KeyError: raise AttributeError(name)\n'
                '    return getattr(obj, name)'
            )
        if self._need & {'call', 'method'}:
            # A single lazily-built interpreter backs both the builtin and method
            # shims below. Building it once keeps generated programs fast.
            parts.append(
                '_epl_rt = None\n'
                'def _epl_runtime():\n'
                '    global _epl_rt\n'
                '    if _epl_rt is None:\n'
                '        from epl.interpreter import Interpreter\n'
                '        _epl_rt = Interpreter()\n'
                '    return _epl_rt'
            )
        if 'call' in self._need:
            # Route EPL's builtin long tail (file_*, db_*, http_*, regex_*,
            # crypto_*, …) through EPL's own tested runtime instead of
            # re-implementing hundreds of functions here. This keeps generated
            # code faithful by construction — it calls the exact same code path
            # `epl run` does. Values are converted at the boundary so results
            # (maps, etc.) come back in native Python shape.
            parts.append(
                'def _epl_call(name, *args):\n'
                '    rt = _epl_runtime()\n'
                '    epl_args = [rt._python_to_epl(a) for a in args]\n'
                '    return rt._epl_to_python(rt._call_builtin(name, epl_args, 0))'
            )
        if 'method' in self._need:
            # Faithful dispatch for EPL's built-in string/list/map methods
            # (.add, .has, .substring, .join, .count, .uppercase, …) whose
            # semantics or names differ from Python's. Dispatches by runtime
            # type through the interpreter's own method handlers; falls back to a
            # native attribute for user-defined objects so class methods still
            # work. dict is wrapped in EPLDict (which shares the underlying
            # mapping, so in-place mutation persists).
            parts.append(
                'def _epl_method(obj, name, *args):\n'
                '    rt = _epl_runtime()\n'
                '    a = [rt._python_to_epl(x) for x in args]\n'
                '    if isinstance(obj, str):\n'
                '        return rt._epl_to_python(rt._call_string_method(obj, name, a, 0))\n'
                '    if isinstance(obj, list):\n'
                '        return rt._epl_to_python(rt._call_list_method(obj, name, a, 0))\n'
                '    if isinstance(obj, dict):\n'
                '        from epl.interpreter import EPLDict\n'
                '        w = EPLDict()\n'
                '        w.data = obj  # share the real mapping, even when empty, so mutations persist\n'
                '        return rt._epl_to_python(rt._call_dict_method(w, name, a, 0))\n'
                '    m = getattr(obj, name)\n'
                '    return m(*args) if callable(m) else m'
            )
        return '\n\n'.join(parts) + '\n'

    def _prescan(self, program):
        """Walk the whole AST once, collecting method names called, node class
        names seen, and every bound variable name. Field-agnostic so it
        survives AST shape changes."""
        method_names: set[str] = set()
        class_names: set[str] = set()
        bound_names: set[str] = set()

        # Node types that introduce a binding, and the attribute holding the
        # bound name. Used to reproduce the interpreter's rule that a bare
        # `$var` template slot interpolates ONLY when the variable exists —
        # otherwise the `$` is literal text (e.g. inside a password string).
        name_attrs = ('name', 'var_name', 'variable_name')

        def visit(node):
            if node is None:
                return
            if isinstance(node, (list, tuple)):
                for item in node:
                    visit(item)
                return
            if isinstance(node, ast.RestParameter):
                bound_names.add(node.name)
                return
            if not isinstance(node, ast.ASTNode):
                return
            cls = type(node).__name__
            class_names.add(cls)
            if isinstance(node, ast.MethodCall):
                method_names.add(node.method_name)
            # Collect binding names (declarations, assignments, loop/input vars,
            # function params). Function/class names are intentionally excluded:
            # their call sites don't go through _safe_name, so renaming them
            # would desync definition and use. Params are still captured by the
            # dedicated `params` block below.
            if cls in (
                'VarDeclaration',
                'VarAssignment',
                'ConstDeclaration',
                'InputStatement',
                'ForRange',
                'ForEachLoop',
            ):
                for attr in name_attrs:
                    val = getattr(node, attr, None)
                    if isinstance(val, str):
                        bound_names.add(val)
            names = getattr(node, 'names', None)
            if isinstance(names, (list, tuple)):
                bound_names.update(n for n in names if isinstance(n, str))
            params = getattr(node, 'params', None)
            if isinstance(params, (list, tuple)):
                for p in params:
                    if isinstance(p, ast.RestParameter):
                        bound_names.add(p.name)
                    elif isinstance(p, str):
                        # LambdaExpression.params is a list of plain strings; record
                        # them so a reserved-name lambda param is renamed the same
                        # way its uses inside the body are (see _safe_name).
                        bound_names.add(p)
                    elif isinstance(p, (list, tuple)) and p and isinstance(p[0], str):
                        bound_names.add(p[0])
            for value in vars(node).values():
                visit(value)

        visit(program.statements)
        return method_names, class_names, bound_names

    # ── Helpers ────────────────────────────────────────

    def _safe_name(self, name: str) -> str:
        """Map an EPL variable name to a collision-free Python name.

        Only names that both are bound in this program and collide with an
        emitted Python builtin/keyword are rewritten (with a trailing `_`);
        every other identifier passes through untouched.
        """
        return self._renames.get(name, name) if hasattr(self, '_renames') else name

    def _line(self, text: str):
        self.output.append('    ' * self.indent + text)

    def _blank(self):
        self.output.append('')

    def _add_import(self, module: str):
        self.imports.add(f'import {module}')

    def _add_from_import(self, module: str, name: str):
        self.from_imports.setdefault(module, set()).add(name)

    def _py_string(self, s) -> str:
        s = str(s)
        # Check for template patterns $var or ${expr}
        tmpl = _re.search(r'\$\{[^}]+\}|\$[A-Za-z_]\w*', s)
        if tmpl:
            # Convert to an f-string. Each interpolated slot is a real EPL
            # expression, so transpile it through the normal pipeline rather
            # than embedding the raw source — otherwise builtins like
            # `${length(items)}` or `${truncate(x)}` would leak untranslated
            # and NameError at runtime.
            def _slot(expr_src: str) -> str:
                py = self._transpile_embedded_expr(expr_src)
                # Interpolated values use EPL's display form, not Python's str()
                # — so a bool shows as `true`/`false`, nothing as `nothing`, and
                # lists/maps in EPL's bracket/brace style. `_epl_fmt` is a no-op
                # on plain strings, so `${name}` is unchanged.
                self._need.add('fmt')
                return '{_epl_fmt(' + py + ')}'

            result = _re.sub(r'\$\{([^}]+)\}', lambda m: _slot(m.group(1)), s)

            def _bare(m):
                # Bare `$name` interpolates only when `name` is a variable that
                # actually exists — mirroring the interpreter. Otherwise the `$`
                # is literal text (e.g. `"aB3$xK9!mN2@"`, a password, not a
                # template), so leave it untouched.
                var = m.group(1)
                if var in getattr(self, '_declared_vars', set()):
                    return _slot(var)
                return m.group(0)

            result = _re.sub(r'\$([A-Za-z_]\w*)', _bare, result)
            esc = (
                result.replace('\\', '\\\\')
                .replace("'", "\\'")
                .replace('\n', '\\n')
                .replace('\r', '\\r')
            )
            return f"f'{esc}'"
        esc = (
            s.replace('\\', '\\\\')
            .replace("'", "\\'")
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t')
        )
        return f"'{esc}'"

    def _transpile_embedded_expr(self, expr_src: str) -> str:
        """Transpile a single interpolated `${...}` slot's EPL expression.

        Falls back to the trimmed source (a bare identifier) if it cannot be
        parsed as an expression — that keeps simple `$name` slots working even
        for grammar the expression parser doesn't accept standalone.
        """
        expr_src = expr_src.strip()
        try:
            from epl.lexer import Lexer as _Lexer
            from epl.parser import Parser as _Parser

            parser = _Parser(_Lexer(expr_src).tokenize())
            node = parser._parse_expression()
            return self._expr(node)
        except Exception:  # noqa: BLE001 - fall back to raw identifier text
            return expr_src

    # ── Statement dispatch ─────────────────────────────

    def _emit_stmt(self, node):
        if node is None:
            return
        if isinstance(node, ast.VarDeclaration):
            self._emit_var_decl(node)
        elif isinstance(node, ast.VarAssignment):
            self._emit_var_assign(node)
        elif isinstance(node, ast.PrintStatement):
            self._emit_print(node)
        elif isinstance(node, ast.InputStatement):
            self._emit_input(node)
        elif isinstance(node, ast.IfStatement):
            self._emit_if(node)
        elif isinstance(node, ast.WhileLoop):
            self._emit_while(node)
        elif isinstance(node, ast.RepeatLoop):
            self._emit_repeat(node)
        elif isinstance(node, ast.ForRange):
            self._emit_for_range(node)
        elif isinstance(node, ast.ForEachLoop):
            self._emit_for_each(node)
        elif isinstance(node, ast.AsyncFunctionDef):
            self._emit_async_function(node)
        elif isinstance(node, ast.FunctionDef):
            self._emit_function(node)
        elif isinstance(node, ast.FunctionCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.ReturnStatement):
            self._emit_return(node)
        elif isinstance(node, ast.BreakStatement):
            self._line('break')
        elif isinstance(node, ast.ContinueStatement):
            self._line('continue')
        elif isinstance(node, ast.ClassDef):
            self._emit_class(node)
        elif isinstance(node, ast.MatchStatement):
            self._emit_match(node)
        elif isinstance(node, ast.TryCatch):
            self._emit_try_catch(node)
        elif isinstance(node, ast.TryCatchFinally):
            self._emit_try_catch_finally(node)
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._expr(node)}')
        elif isinstance(node, ast.PropertySet):
            self._emit_prop_set(node)
        elif isinstance(node, ast.IndexSet):
            self._emit_index_set(node)
        elif isinstance(node, ast.AugmentedAssignment):
            self._emit_aug_assign(node)
        elif isinstance(node, ast.ThrowStatement):
            self._emit_throw(node)
        elif isinstance(node, ast.FileWrite):
            self._emit_file_write(node)
        elif isinstance(node, ast.FileAppend):
            self._emit_file_append(node)
        elif isinstance(node, ast.ConstDeclaration):
            self._emit_const(node)
        elif isinstance(node, ast.AssertStatement):
            self._emit_assert(node)
        elif isinstance(node, ast.ExitStatement):
            self._add_import('sys')
            self._line('sys.exit(0)')
        elif isinstance(node, ast.WaitStatement):
            self._emit_wait(node)
        elif isinstance(node, ast.EnumDef):
            self._emit_enum(node)
        elif isinstance(node, ast.ImportStatement):
            self._emit_import(node)
        elif isinstance(node, ast.UseStatement):
            self._emit_use(node)
        elif isinstance(node, ast.SuperCall):
            self._emit_super_call(node)
        elif isinstance(node, ast.InterfaceDefNode):
            self._emit_interface(node)
        elif isinstance(node, ast.ModuleDef):
            self._emit_module(node)
        elif isinstance(node, ast.ExportStatement):
            self._line(f'# export: {node.name}')
        elif isinstance(node, ast.VisibilityModifier):
            self._line(f'# {node.visibility}')
            self._emit_stmt(node.statement)
        elif isinstance(node, ast.StaticMethodDef):
            self._emit_static_method(node)
        elif isinstance(node, ast.YieldStatement):
            val = f' {self._expr(node.value)}' if node.value else ''
            self._line(f'yield{val}')
        elif isinstance(node, ast.DestructureAssignment):
            names = ', '.join(self._safe_name(n) for n in node.names)
            self._line(f'{names} = {self._expr(node.value)}')
        elif isinstance(node, ast.ModuleAccess):
            self._line(f'{self._expr(node)}')
        else:
            # Correct-or-loud: refuse rather than emit a silent `# Unsupported`
            # comment that drops the statement and changes program behavior.
            raise TranspileError(
                f'Cannot transpile statement of type {type(node).__name__} '
                f'(line {getattr(node, "line", "?")}). This construct is not yet '
                f'supported by the Python transpiler.'
            )

    # ── Statement emitters ─────────────────────────────

    def _emit_var_decl(self, node):
        self._line(f'{self._safe_name(node.name)} = {self._expr(node.value)}')

    def _emit_var_assign(self, node):
        if self.in_class and node.name in self.class_properties:
            self._line(f'self.{node.name} = {self._expr(node.value)}')
        else:
            self._line(f'{self._safe_name(node.name)} = {self._expr(node.value)}')

    def _emit_print(self, node):
        # EPL prints via its display formatter (true/false/nothing, bracketed
        # lists, brace maps), not Python's str(); `_epl_print` matches it.
        self._need.add('print')
        self._line(f'_epl_print({self._expr(node.expression)})')

    def _emit_input(self, node):
        # InputStatement.prompt is a bare Python string (the parser stores the
        # literal directly), not an AST node — render it as a Python string
        # literal rather than routing through _expr (which would treat the raw
        # str as an unknown node and emit an "Unsupported" marker).
        if not node.prompt:
            prompt = "''"
        elif isinstance(node.prompt, str):
            prompt = self._py_string(node.prompt)
        else:
            prompt = self._expr(node.prompt)
        self._line(f'{self._safe_name(node.variable_name)} = input({prompt})')

    def _emit_if(self, node):
        self._line(f'if {self._expr(node.condition)}:')
        self.indent += 1
        for s in node.then_body:
            self._emit_stmt(s)
        if not node.then_body:
            self._line('pass')
        self.indent -= 1
        if node.else_body:
            # Check for elif pattern (else_body is single IfStatement)
            if len(node.else_body) == 1 and isinstance(node.else_body[0], ast.IfStatement):
                self._line(f'elif {self._expr(node.else_body[0].condition)}:')
                self.indent += 1
                for s in node.else_body[0].then_body:
                    self._emit_stmt(s)
                if not node.else_body[0].then_body:
                    self._line('pass')
                self.indent -= 1
                if node.else_body[0].else_body:
                    self._emit_else(node.else_body[0].else_body)
            else:
                self._emit_else(node.else_body)

    def _emit_else(self, else_body):
        if len(else_body) == 1 and isinstance(else_body[0], ast.IfStatement):
            self._line(f'elif {self._expr(else_body[0].condition)}:')
            self.indent += 1
            for s in else_body[0].then_body:
                self._emit_stmt(s)
            if not else_body[0].then_body:
                self._line('pass')
            self.indent -= 1
            if else_body[0].else_body:
                self._emit_else(else_body[0].else_body)
        else:
            self._line('else:')
            self.indent += 1
            for s in else_body:
                self._emit_stmt(s)
            if not else_body:
                self._line('pass')
            self.indent -= 1

    def _emit_while(self, node):
        self._line(f'while {self._expr(node.condition)}:')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_repeat(self, node):
        self._line(f'for _ in range({self._expr(node.count)}):')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_for_range(self, node):
        start = self._expr(node.start)
        end = self._expr(node.end)
        # EPL ranges are inclusive on BOTH ends; Python's range() excludes the
        # stop value. To include it we nudge the stop by one step *in the
        # direction of travel* — +1 counting up, −1 counting down. A fixed `+1`
        # (the old behavior) silently dropped the last two iterations of any
        # descending loop (`from 10 to 1 step -1` stopped at 3).
        if hasattr(node, 'step') and node.step is not None:
            step = self._expr(node.step)
            # Sign-aware inclusive stop, valid whether step is a literal or an
            # expression evaluated at runtime.
            end_expr = f'({end}) + (1 if ({step}) > 0 else -1)'
            self._line(
                f'for {self._safe_name(node.var_name)} in range({start}, {end_expr}, {step}):'
            )
        else:
            self._line(f'for {self._safe_name(node.var_name)} in range({start}, ({end}) + 1):')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_for_each(self, node):
        self._line(f'for {self._safe_name(node.var_name)} in {self._expr(node.iterable)}:')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        if not node.body:
            self._line('pass')
        self.indent -= 1

    def _emit_function(self, node):
        self._blank()
        params = ', '.join(self._format_param(p) for p in node.params)
        if self.in_class:
            params = f'self, {params}' if params else 'self'
        ret = f' -> {self._py_type(node.return_type)}' if node.return_type else ''
        self._line(f'def {node.name}({params}){ret}:')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_async_function(self, node):
        self._add_import('asyncio')
        self._blank()
        params = ', '.join(self._format_param(p) for p in node.params)
        ret = f' -> {self._py_type(node.return_type)}' if node.return_type else ''
        self._line(f'async def {node.name}({params}){ret}:')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_return(self, node):
        if node.value:
            self._line(f'return {self._expr(node.value)}')
        else:
            self._line('return')

    def _emit_class(self, node):
        self._blank()
        parent = f'({node.parent})' if node.parent else ''
        self._line(f'class {node.name}{parent}:')
        self.indent += 1
        old_in_class = self.in_class
        old_props = self.class_properties.copy()
        self.in_class = True
        self.class_properties = set()

        # Separate fields from methods
        fields = []
        methods = []
        for item in node.body:
            if isinstance(item, (ast.VarDeclaration, ast.VarAssignment)):
                fields.append(item)
                self.class_properties.add(item.name)
            else:
                methods.append(item)

        # Generate __init__ from fields
        if fields:
            self._line('def __init__(self):')
            self.indent += 1
            if node.parent:
                self._line('super().__init__()')
            for f in fields:
                self._line(f'self.{f.name} = {self._expr(f.value)}')
            self.indent -= 1
            self._blank()

        for m in methods:
            self._emit_stmt(m)

        if not fields and not methods:
            self._line('pass')

        self.in_class = old_in_class
        self.class_properties = old_props
        self.indent -= 1
        self._blank()

    def _emit_match(self, node):
        expr = self._expr(node.expression)
        self._line(f'match {expr}:')
        self.indent += 1
        for clause in node.when_clauses:
            vals = ' | '.join(self._expr(v) for v in clause.values)
            self._line(f'case {vals}:')
            self.indent += 1
            for s in clause.body:
                self._emit_stmt(s)
            if not clause.body:
                self._line('pass')
            self.indent -= 1
        if node.default_body:
            self._line('case _:')
            self.indent += 1
            for s in node.default_body:
                self._emit_stmt(s)
            self.indent -= 1
        self.indent -= 1

    def _emit_try_catch(self, node):
        self._line('try:')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        if not node.try_body:
            self._line('pass')
        self.indent -= 1
        err_var = node.error_var or 'e'
        self._line(f'except Exception as {err_var}:')
        self.indent += 1
        if node.catch_body:
            for s in node.catch_body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        if hasattr(node, 'finally_body') and node.finally_body:
            self._line('finally:')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1

    def _emit_try_catch_finally(self, node):
        self._line('try:')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        if not node.try_body:
            self._line('pass')
        self.indent -= 1
        for err_type, err_var, body in node.catch_clauses:
            exc_type = err_type if err_type else 'Exception'
            var = err_var if err_var else 'e'
            self._line(f'except {exc_type} as {var}:')
            self.indent += 1
            if body:
                for s in body:
                    self._emit_stmt(s)
            else:
                self._line('pass')
            self.indent -= 1
        if node.finally_body:
            self._line('finally:')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1

    def _emit_prop_set(self, node):
        if self.in_class:
            self._line(f'self.{node.property_name} = {self._expr(node.value)}')
        else:
            self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)}')

    def _emit_index_set(self, node):
        self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)}')

    def _emit_aug_assign(self, node):
        target = (
            f'self.{node.name}'
            if self.in_class and node.name in self.class_properties
            else self._safe_name(node.name)
        )
        val = self._expr(node.value)
        # `+=` and `/=` must carry EPL's `+`/`/` semantics (string coercion,
        # int-preserving division), which Python's in-place operators do not —
        # so desugar them through the same runtime helpers as the binary forms.
        if node.operator == '+=':
            self._need.add('add')
            self._line(f'{target} = _epl_add({target}, {val})')
        elif node.operator == '/=':
            self._need.add('div')
            self._line(f'{target} = _epl_div({target}, {val})')
        else:
            self._line(f'{target} {node.operator} {val}')

    def _emit_throw(self, node):
        self._line(f'raise Exception({self._expr(node.expression)})')

    def _emit_file_write(self, node):
        self._line(f'with open({self._expr(node.filepath)}, "w") as _f:')
        self.indent += 1
        self._line(f'_f.write(str({self._expr(node.content)}))')
        self.indent -= 1

    def _emit_file_append(self, node):
        self._line(f'with open({self._expr(node.filepath)}, "a") as _f:')
        self.indent += 1
        self._line(f'_f.write(str({self._expr(node.content)}) + "\\n")')
        self.indent -= 1

    def _emit_const(self, node):
        self._line(f'{node.name.upper()} = {self._expr(node.value)}  # constant')

    def _emit_assert(self, node):
        self._line(f'assert {self._expr(node.expression)}')

    def _emit_wait(self, node):
        self._add_import('time')
        self._line(f'time.sleep({self._expr(node.duration)})')

    def _emit_enum(self, node):
        self._add_from_import('enum', 'Enum')
        self._blank()
        self._line(f'class {node.name}(Enum):')
        self.indent += 1
        for i, member in enumerate(node.members):
            self._line(f'{member} = {i}')
        if not node.members:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_import(self, node):
        mod = node.filepath.replace('.epl', '').replace('/', '.').replace('\\', '.')
        if hasattr(node, 'alias') and node.alias:
            self._line(f'import {mod} as {node.alias}')
        else:
            self._line(f'import {mod}')

    def _emit_use(self, node):
        if node.alias:
            self._line(f'import {node.library} as {node.alias}')
        else:
            self._line(f'import {node.library}')

    def _emit_super_call(self, node):
        args = ', '.join(self._expr(a) for a in node.arguments)
        if node.method_name:
            self._line(f'super().{node.method_name}({args})')
        else:
            self._line(f'super().__init__({args})')

    def _emit_interface(self, node):
        self._add_from_import('abc', 'ABC')
        self._add_from_import('abc', 'abstractmethod')
        self._blank()
        extends = f'({", ".join(node.extends)}, ABC)' if node.extends else '(ABC)'
        self._line(f'class {node.name}{extends}:')
        self.indent += 1
        if node.methods:
            for m in node.methods:
                self._line('@abstractmethod')
                params = ', '.join(['self'] + [p[0] for p in m.params])
                self._line(f'def {m.name}({params}):')
                self.indent += 1
                self._line('pass')
                self.indent -= 1
                self._blank()
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    def _emit_module(self, node):
        self._line(f'# Module: {node.name}')
        for s in node.body:
            self._emit_stmt(s)

    def _emit_static_method(self, node):
        self._line('@staticmethod')
        params = ', '.join(self._format_param(p) for p in node.params)
        self._line(f'def {node.name}({params}):')
        self.indent += 1
        if node.body:
            for s in node.body:
                self._emit_stmt(s)
        else:
            self._line('pass')
        self.indent -= 1
        self._blank()

    # ── Expression rendering ───────────────────────────

    def _expr(self, node) -> str:
        if node is None:
            return 'None'
        if isinstance(node, ast.Literal):
            return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            # EPL's `this` inside a method is Python's `self`.
            if node.name == 'this':
                return 'self'
            if self.in_class and node.name in self.class_properties:
                return f'self.{node.name}'
            return self._safe_name(node.name)
        if isinstance(node, ast.BinaryOp):
            return self._expr_binary(node)
        if isinstance(node, ast.UnaryOp):
            return self._expr_unary(node)
        if isinstance(node, ast.FunctionCall):
            return self._expr_call(node)
        if isinstance(node, ast.PropertyAccess):
            # EPL exposes `.length` on strings, lists and maps as a property;
            # Python spells it len(). Map/instance dot-access stays as-is (the
            # _EPLMap subclass resolves `.key` via __getattr__ when wrapped).
            if node.property_name == 'length':
                return f'len({self._expr(node.obj)})'
            if node.property_name in ('uppercase', 'lowercase', 'trim'):
                method = {'uppercase': 'upper', 'lowercase': 'lower', 'trim': 'strip'}[
                    node.property_name
                ]
                return f'{self._expr(node.obj)}.{method}()'
            # EPL dot-access is dual: on a Map it reads a key (`user.name`), on an
            # instance it reads an attribute. Python's `.` only does the latter,
            # so a Map returned by a builtin (json_parse, db_query) or built via
            # `Map with …` would raise AttributeError. Route through a runtime
            # helper that does key-access on dicts and attribute-access on
            # everything else — universal and faithful, no static type guess.
            self._need.add('getattr')
            return f'_epl_getattr({self._expr(node.obj)}, {self._py_string(node.property_name)})'
        if isinstance(node, ast.MethodCall):
            return self._expr_method(node)
        if isinstance(node, ast.IndexAccess):
            return f'{self._expr(node.obj)}[{self._expr(node.index)}]'
        if isinstance(node, ast.SliceAccess):
            return self._expr_slice(node)
        if isinstance(node, ast.ListLiteral):
            elems = ', '.join(self._expr(e) for e in node.elements)
            # When the program calls .map/.filter/.reduce anywhere, lists must
            # carry those methods (Python's built-in list has none). Wrap in the
            # _EPLList subclass; otherwise keep a plain, idiomatic list.
            if getattr(self, '_wrap_lists', False):
                self._need.add('epllist')
                return f'_EPLList([{elems}])'
            return f'[{elems}]'
        if isinstance(node, ast.DictLiteral):
            pairs = []
            for k, v in node.pairs:
                if isinstance(k, str):
                    pairs.append(f'{self._py_string(k)}: {self._expr(v)}')
                else:
                    pairs.append(f'{self._expr(k)}: {self._expr(v)}')
            body = '{' + ', '.join(pairs) + '}'
            # EPL Maps support dot-access (user.name). A plain dict raises
            # AttributeError, so wrap in _EPLMap when the program uses property
            # access. Indexing (map["key"]) works on both, unwrapped or not.
            if getattr(self, '_wrap_maps', False):
                self._need.add('dotdict')
                return f'_EPLMap({body})'
            return body
        if isinstance(node, ast.NewInstance):
            args = ', '.join(self._expr(a) for a in node.arguments)
            return f'{node.class_name}({args})'
        if isinstance(node, ast.LambdaExpression):
            # Render params through _safe_name so a param named e.g. `len` is
            # renamed consistently with its uses in the body (both become `len_`).
            params = ', '.join(self._safe_name(p) for p in node.params)
            return f'lambda {params}: {self._expr(node.body)}'
        if isinstance(node, ast.TernaryExpression):
            return f'({self._expr(node.true_expr)} if {self._expr(node.condition)} else {self._expr(node.false_expr)})'
        if isinstance(node, ast.AwaitExpression):
            return f'await {self._expr(node.expression)}'
        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                return f'super().{node.method_name}({args})'
            return f'super().__init__({args})'
        if isinstance(node, ast.FileRead):
            return f'open({self._expr(node.filepath)}).read()'
        if isinstance(node, ast.ModuleAccess):
            if node.arguments is not None:
                args = ', '.join(self._expr(a) for a in node.arguments)
                return f'{node.module_name}.{node.member_name}({args})'
            return f'{node.module_name}.{node.member_name}'
        if hasattr(ast, 'SpreadExpression') and isinstance(node, ast.SpreadExpression):
            return f'*{self._expr(node.expression)}'
        if hasattr(ast, 'ChainedComparison') and isinstance(node, ast.ChainedComparison):
            parts = []
            for i, op in enumerate(node.operators):
                parts.append(self._expr(node.operands[i]))
                parts.append(self._map_op(op))
            parts.append(self._expr(node.operands[-1]))
            return ' '.join(parts)
        # Correct-or-loud: an unrecognized expression node must not silently
        # become `None`, which would compile fine and compute the wrong answer.
        raise TranspileError(
            f'Cannot transpile expression of type {type(node).__name__} '
            f'(line {getattr(node, "line", "?")}). This construct is not yet '
            f'supported by the Python transpiler.'
        )

    def _expr_literal(self, node) -> str:
        v = node.value
        if v is True:
            return 'True'
        if v is False:
            return 'False'
        if v is None:
            return 'None'
        if isinstance(v, str):
            return self._py_string(v)
        return repr(v)

    def _expr_binary(self, node) -> str:
        left = self._expr(node.left)
        right = self._expr(node.right)
        op = self._map_op(node.operator)
        if op == '//':
            return f'({left} // {right})'
        if op == '**':
            return f'({left} ** {right})'
        # EPL's `+` auto-stringifies when either side is text ("n: " + 3) and
        # concatenates lists — Python's raw `+` raises TypeError on the mixed
        # case. Route through `_epl_add` to preserve the interpreter's behavior.
        if op == '+':
            self._need.add('add')
            return f'_epl_add({left}, {right})'
        # EPL's `/` yields an int when two ints divide evenly (10/2 -> 5), unlike
        # Python's always-float `/`. `_epl_div` mirrors the interpreter/VM.
        if op == '/':
            self._need.add('div')
            return f'_epl_div({left}, {right})'
        return f'({left} {op} {right})'

    def _map_op(self, op: str) -> str:
        return {
            'and': 'and',
            'or': 'or',
            'not': 'not',
            '==': '==',
            '!=': '!=',
            '<': '<',
            '>': '>',
            '<=': '<=',
            '>=': '>=',
            '+': '+',
            '-': '-',
            '*': '*',
            '/': '/',
            '//': '//',
            '%': '%',
            '**': '**',
            '&': '&',
            '|': '|',
            '^': '^',
        }.get(op, op)

    def _expr_unary(self, node) -> str:
        op = 'not ' if node.operator == 'not' else node.operator
        return f'({op}{self._expr(node.operand)})'

    def _expr_call(self, node) -> str:
        args = ', '.join(self._expr(a) for a in node.arguments)
        # Map EPL builtins to Python equivalents
        name = node.name
        # A user binding shadows a builtin of the same name in the interpreter
        # (`Set to_text to lambda …` then `to_text("x")` calls the lambda), so if
        # the name is a bound variable, dispatch to it directly — never route
        # through the builtin/`_epl_call` path below. `user_functions` are
        # excluded: those are real `Function` defs whose call sites are correct as
        # a direct call anyway, and they are not in `_declared_vars`.
        if name in getattr(self, '_declared_vars', set()):
            return f'{self._safe_name(name)}({args})'
        # Only EPL builtins whose Python equivalent is behaviorally identical
        # live here. Ones that *look* mappable but diverge — to_text (EPL
        # formats bools as true/false), type_of (EPL type names), to_number
        # (int-preserving) — are deliberately absent so they route through the
        # faithful `_epl_call` runtime shim instead.
        builtin_map = {
            'length': 'len',
            'to_integer': 'int',
            'to_decimal': 'float',
            'round_number': 'round',
            'absolute': 'abs',
            'power': 'pow',
            'square_root': 'math.sqrt',
            'minimum': 'min',
            'maximum': 'max',
            'random_number': 'random.random',
            'random_integer': 'random.randint',
            'sorted': 'sorted',
            'range': 'range',
            'enumerate': 'enumerate',
            'zip': 'zip',
            'sum': 'sum',
            'join': "', '.join",
            'upper': 'str.upper',
            'lower': 'str.lower',
            # `trim` is NOT mapped to `str.strip`: the interpreter coerces first
            # (`str(x).strip()`), so `trim(123)` is valid and yields "123". A bare
            # `str.strip(123)` would raise, so route it through the faithful
            # `_epl_call` shim instead (falls through to the builtin path below).
            'split': 'str.split',
            'replace': 'str.replace',
            'starts_with': 'str.startswith',
            'ends_with': 'str.endswith',
            'floor': 'math.floor',
            'ceil': 'math.ceil',
            'log': 'math.log',
            'sin': 'math.sin',
            'cos': 'math.cos',
        }
        # Builtins that wrap another call and must materialize to a concrete
        # value (EPL's reversed/map/filter are eager, Python's are lazy iterators).
        # Kept as explicit templates so the paren-balancing is correct by
        # construction rather than by string-suffix guessing.
        wrap_templates = {
            'map': 'list(map({a}))',
            'filter': 'list(filter({a}))',
            # EPL's range() returns a materialized list; Python's is a lazy
            # iterator that displays as `range(0, 5)`. Materialize for parity.
            'range': 'list(range({a}))',
        }
        if name in wrap_templates:
            return wrap_templates[name].format(a=args)
        if name in builtin_map:
            py_name = builtin_map[name]
            if name in ('square_root', 'floor', 'ceil', 'log', 'sin', 'cos'):
                self._add_import('math')
            if name in ('random_number', 'random_integer'):
                self._add_import('random')
            return f'{py_name}({args})'
        # EPL builtin with no idiomatic Python equivalent (the ~720-strong long
        # tail: file_*, db_*, regex_*, http_*, crypto_*, …). Rather than
        # re-implement 900 functions here — which would silently drift from the
        # interpreter — route through EPL's own tested runtime. Faithful by
        # construction. This branch is essential: emitting a bare `name(args)`
        # for these would raise NameError in Python while `epl run` succeeds —
        # the exact silent divergence this transpiler must never ship. See the
        # `_epl_call` shim in the prelude.
        if name in _EPL_BUILTIN_NAMES:
            self._need.add('call')
            return f'_epl_call({self._py_string(name)}{", " + args if args else ""})'
        # Otherwise it's a user-defined function, a variable holding a callable
        # (e.g. `double = lambda x -> x * 2`), or a genuinely-undefined name.
        # A direct call is correct for the first two; for the third, Python
        # raises NameError exactly as `epl run` raises its own "undefined"
        # error — same failure on both engines, so no silent divergence.
        return f'{name}({args})'

    def _expr_method(self, node) -> str:
        obj = self._expr(node.obj)
        args = ', '.join(self._expr(a) for a in node.arguments)
        method = node.method_name
        # EPL built-in string/list/map methods whose names/semantics differ from
        # Python's — route through the faithful runtime shim (see prelude). This
        # is checked before the idiomatic method_map so EPL semantics win; the
        # shim's native-attribute fallback keeps user-class methods working.
        if method in _EPL_METHOD_NAMES:
            self._need.add('method')
            head = f'_epl_method({obj}, {self._py_string(method)}'
            return f'{head}, {args})' if args else f'{head})'
        # Map EPL method names to Python (idiomatic 1:1 equivalents only).
        method_map = {
            'push': 'append',
            'remove_at': 'pop',
            'upper': 'upper',
            'lower': 'lower',
            'trim': 'strip',
            'split': 'split',
            'replace': 'replace',
            'starts_with': 'startswith',
            'ends_with': 'endswith',
            'contains': '__contains__',
            'index_of': 'index',
            'sort': 'sort',
            'items': 'items',
            'get': 'get',
            'has_key': '__contains__',
        }
        py_method = method_map.get(method, method)
        if args:
            return f'{obj}.{py_method}({args})'
        return f'{obj}.{py_method}()'

    def _expr_slice(self, node) -> str:
        obj = self._expr(node.obj)
        start = self._expr(node.start) if node.start else ''
        end = self._expr(node.end) if node.end else ''
        step = ''
        if hasattr(node, 'step') and node.step:
            step = f':{self._expr(node.step)}'
        return f'{obj}[{start}:{end}{step}]'

    # ── Param / type helpers ───────────────────────────

    def _format_param(self, p) -> str:
        # Rest/varargs parameter (`takes rest names`) → Python `*names`.
        if isinstance(p, ast.RestParameter):
            return f'*{self._safe_name(p.name)}'
        name = self._safe_name(p[0])
        ptype = p[1] if len(p) > 1 else None
        default = p[2] if len(p) > 2 else None
        result = name
        if ptype:
            result += f': {self._py_type(ptype)}'
        if default is not None:
            result += f' = {self._expr(default)}'
        return result

    def _py_type(self, epl_type) -> str:
        if not epl_type:
            return ''
        type_map = {
            'integer': 'int',
            'decimal': 'float',
            'text': 'str',
            'boolean': 'bool',
            'list': 'list',
            'map': 'dict',
            'any': 'Any',
            'void': 'None',
            'nothing': 'None',
            'number': 'float',
            'string': 'str',
        }
        return type_map.get(epl_type.lower(), epl_type)
