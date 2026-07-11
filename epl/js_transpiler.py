"""
EPL JavaScript Transpiler (v2.0)
Converts EPL AST to JavaScript for client-side web execution
and Node.js target. Supports: variables, functions, loops, conditions,
classes, string/list methods, DOM helpers, async/await, modules,
super calls, proper constructor mapping, and target-aware output.
"""

import re
from typing import AbstractSet

from epl import ast_nodes as ast
from epl.python_transpiler import TranspileError

# Authoritative set of every name EPL treats as a builtin (core + stdlib), used
# to tell an unmapped-but-real builtin (fail loud) from a genuine user-function
# call (emit a bare call). Sourced from the interpreter so it can never drift.
_EPL_BUILTIN_NAMES: 'AbstractSet[str]'
try:  # pragma: no cover - import guard
    from epl.interpreter import BUILTINS as _EPL_BUILTIN_NAMES
except Exception:  # noqa: BLE001 - transpiler must load even if runtime import fails
    # An empty set would silently disable the fail-loud check below, so make the
    # degraded mode visible rather than shipping ReferenceError-bound output.
    import sys as _sys

    print(
        'Warning: could not import epl.interpreter.BUILTINS; the JS transpiler '
        'fail-loud check for unmapped builtins is disabled.',
        file=_sys.stderr,
    )
    _EPL_BUILTIN_NAMES = frozenset()


def _esc_js(text):
    """Escape a string for safe use inside JavaScript string literals."""
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('</', '<\\/')
    )


# EPL built-in string/list/map methods whose name or behaviour has no faithful
# 1:1 JavaScript equivalent, so they are routed through the `_epl_method` runtime
# shim below instead of emitting `obj.method(...)` directly (which would call a
# non-existent method — `greeting.count(...)`, `scores.has(...)` — and crash).
# Methods that ARE identical in JS (uppercase→toUpperCase, contains→includes, …)
# stay in the transpiler's 1:1 `method_map` and are intentionally absent here.
# Higher-order methods (map/filter/reduce/every/some/find) are excluded too —
# they take EPL callables and are handled by the existing lambda path.
_EPL_METHOD_NAMES = frozenset(
    {
        # string-only
        'count',
        'pad_left',
        'pad_right',
        'is_number',
        'is_alpha',
        'is_empty',
        'char_at',
        'to_list',
        'format',
        # list-only
        'first',
        'last',
        'unique',
        'flatten',
        'insert',
        'copy',
        # map-only — plain JS objects have none of these
        'has',
        'keys',
        'values',
        'get',
        'set',
        'entries',
        'merge',
        # shared name, divergent behaviour across receiver types
        'remove',
        'clear',
        'reverse',
    }
)


# EPL zero-arg accessors spelled as properties (no parens): `.length` on any
# string/list/map, and `.uppercase`/`.lowercase`/`.trim` on strings. JS would
# read these as a Function reference or `undefined`, so they route through the
# `_epl_prop` runtime shim. Deliberately conservative — only these four names,
# so genuine object/Map property reads (`user.name`) are untouched.
_EPL_PROPERTY_NAMES = frozenset({'length', 'uppercase', 'lowercase', 'trim'})

_EPL_PROP_RUNTIME_JS = """function _epl_prop(obj, name) {
  if (name === "length") {
    if (typeof obj === "string" || Array.isArray(obj)) return obj.length;
    if (obj && typeof obj === "object") return Object.keys(obj).length;
  }
  if (typeof obj === "string") {
    if (name === "uppercase") return obj.toUpperCase();
    if (name === "lowercase") return obj.toLowerCase();
    if (name === "trim") return obj.trim();
  }
  return obj == null ? undefined : obj[name];
}"""


# Runtime shim: faithful implementations of the divergent EPL methods, dispatched
# by the receiver's runtime type (string / array / plain-object Map). A user-class
# instance falls through to a real `obj[name](...)` call so class methods still
# work — mirroring the interpreter, which only applies these to built-in types.
_EPL_METHOD_RUNTIME_JS = """function _epl_method(obj, name, ...args) {
  if (typeof obj === "string") {
    switch (name) {
      case "count": return args[0] === undefined ? 0 : obj.split(String(args[0])).length - 1;
      case "reverse": return [...obj].reverse().join("");
      case "pad_left": return obj.padStart(args[0] || 0, args[1] !== undefined ? String(args[1])[0] : " ");
      case "pad_right": return obj.padEnd(args[0] || 0, args[1] !== undefined ? String(args[1])[0] : " ");
      case "is_number": return args.length === 0 && obj.trim() !== "" && !isNaN(Number(obj));
      case "is_alpha": return /^[A-Za-z]+$/.test(obj);
      case "is_empty": return obj.length === 0;
      case "char_at": { const i = args[0] || 0; if (i < 0 || i >= obj.length) throw new Error("Index " + i + " out of range."); return obj[i]; }
      case "to_list": return [...obj];
      case "format": { let r = obj; for (const a of args) r = r.replace("{}", String(a)); return r; }
    }
  } else if (Array.isArray(obj)) {
    switch (name) {
      case "count": return args[0] === undefined ? obj.length : obj.filter(x => x === args[0]).length;
      case "first": return obj.length ? obj[0] : null;
      case "last": return obj.length ? obj[obj.length - 1] : null;
      case "unique": { const seen = new Set(), out = []; for (const x of obj) if (!seen.has(x)) { seen.add(x); out.push(x); } return out; }
      case "flatten": { const out = []; for (const x of obj) Array.isArray(x) ? out.push(...x) : out.push(x); return out; }
      case "insert": if (args.length === 2) obj.splice(args[0], 0, args[1]); return null;
      case "copy": return [...obj];
      case "remove": { const i = obj.indexOf(args[0]); if (i !== -1) obj.splice(i, 1); return null; }
      case "clear": obj.length = 0; return null;
      case "reverse": obj.reverse(); return null;
    }
  } else if (obj && typeof obj === "object") {
    switch (name) {
      case "has": return args[0] !== undefined && Object.prototype.hasOwnProperty.call(obj, String(args[0]));
      case "keys": return Object.keys(obj);
      case "values": return Object.values(obj);
      case "entries": return Object.entries(obj).map(([k, v]) => [k, v]);
      case "get": { const k = String(args[0]); return k in obj ? obj[k] : (args[1] !== undefined ? args[1] : null); }
      case "set": if (args.length === 2) obj[String(args[0])] = args[1]; return null;
      case "merge": return Object.assign({}, obj, args[0]);
      case "remove": delete obj[String(args[0])]; return null;
      case "clear": for (const k of Object.keys(obj)) delete obj[k]; return null;
      case "copy": return Object.assign({}, obj);
    }
  }
  // User-defined class instance (or unhandled) — call the real method.
  const m = obj == null ? undefined : obj[name];
  if (typeof m === "function") return m.apply(obj, args);
  throw new Error("No method \\"" + name + "\\" on value.");
}"""


# Runtime shim: `type_of` faithful to EPL's type names (integer/decimal/text/
# boolean/list/map/nothing), NOT JS `typeof` (which returns number/object/…).
_EPL_TYPE_RUNTIME_JS = """function _epl_type(v) {
  if (v === null || v === undefined) return "nothing";
  if (typeof v === "boolean") return "boolean";
  if (typeof v === "number") return Number.isInteger(v) ? "integer" : "decimal";
  if (typeof v === "string") return "text";
  if (Array.isArray(v)) return "list";
  if (typeof v === "object") return "map";
  if (typeof v === "function") return "function";
  return "unknown";
}"""


# Runtime shim: EPL `+` overload. number+number arithmetic; list+list concat;
# text+anything / anything+text stringify the other operand to EPL display form
# (via `_epl_str`); list+non-list is a type error, matching the interpreter.
_EPL_ADD_RUNTIME_JS = """function _epl_add(a, b) {
  if (typeof a === "number" && typeof b === "number") return a + b;
  if (Array.isArray(a) && Array.isArray(b)) return [...a, ...b];
  // Exactly one operand is a list: allowed only when the other is text
  // (stringify below); otherwise it is a type error, matching the interpreter.
  if (Array.isArray(a) !== Array.isArray(b) && typeof a !== "string" && typeof b !== "string")
    throw new Error("Cannot add " + _epl_type(a) + " and " + _epl_type(b) + ".");
  if (typeof a === "string" || typeof b === "string") return _epl_str(a) + _epl_str(b);
  return a + b;
}"""


# Runtime shim: `reversed` preserving input type (string→string, list→list).
_EPL_REVERSED_RUNTIME_JS = """function _epl_reversed(v) {
  if (typeof v === "string") return [...v].reverse().join("");
  return [...v].reverse();
}"""


# Runtime shim: `is_map` — Map-object test (not a list, not null). Extracted to a
# helper so the argument is evaluated exactly once (side effects fire once).
_EPL_IS_MAP_RUNTIME_JS = """function _epl_is_map(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}"""


# Runtime shim: integer `gcd`. Mirrors the interpreter's `math.gcd(int(a), int(b))`
# — operands are truncated toward zero (`Math.trunc`) before Euclid, and the
# result is non-negative.
_EPL_GCD_RUNTIME_JS = """function _epl_gcd(a, b) {
  a = Math.abs(Math.trunc(a)); b = Math.abs(Math.trunc(b));
  while (b) { [a, b] = [b, a % b]; }
  return a;
}"""


# Runtime shim: integer `factorial`. Mirrors `math.factorial(int(n))` — the input
# is truncated toward zero and a negative argument raises (correct-or-loud: EPL
# errors on `factorial(-1)`, so the JS target must too rather than returning 1).
_EPL_FACTORIAL_RUNTIME_JS = """function _epl_factorial(n) {
  n = Math.trunc(n);
  if (n < 0) throw new Error("factorial() requires a non-negative integer");
  let r = 1;
  for (let i = 2; i <= n; i++) r *= i;
  return r;
}"""


# Runtime shims: `max`/`min` accept a single list OR varargs (mirrors the
# interpreter). A lone array argument is reduced element-wise. A fold (not
# `Math.max(...xs)`) is used so large lists can't overflow the call stack.
_EPL_MAX_RUNTIME_JS = """function _epl_max(...xs) {
  if (xs.length === 1 && Array.isArray(xs[0])) {
    xs = xs[0];
    if (xs.length === 0) throw new Error('max() called on empty list.');
  } else if (xs.length === 0) {
    throw new Error('max() requires at least 1 argument.');
  }
  let m = xs[0];
  for (let i = 1; i < xs.length; i++) if (xs[i] > m) m = xs[i];
  return m;
}"""


_EPL_MIN_RUNTIME_JS = """function _epl_min(...xs) {
  if (xs.length === 1 && Array.isArray(xs[0])) {
    xs = xs[0];
    if (xs.length === 0) throw new Error('min() called on empty list.');
  } else if (xs.length === 0) {
    throw new Error('min() requires at least 1 argument.');
  }
  let m = xs[0];
  for (let i = 1; i < xs.length; i++) if (xs[i] < m) m = xs[i];
  return m;
}"""


# Runtime shim: EPL display form for values (used by `to_text`). Mirrors the
# interpreter's `_format_value`: nothing / true / false, `[a, b]` lists, and
# `{k: v}` maps. Numbers and strings render as-is.
_EPL_STR_RUNTIME_JS = """function _epl_str(v) {
  if (v === null || v === undefined) return "nothing";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return "[" + v.map(_epl_str).join(", ") + "]";
  if (typeof v === "object") return "{" + Object.entries(v).map(([k, x]) => k + ": " + _epl_str(x)).join(", ") + "}";
  return String(v);
}"""


class JSTranspiler:
    """Transpiles EPL AST to JavaScript source code."""

    _TEMPLATE_RE = re.compile(r'\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)')

    def __init__(self, target='browser', module_format='esm'):
        """
        target: 'browser' or 'node'
        module_format: 'esm' (default) or 'cjs' (CommonJS)
        """
        self.target = target
        self.module_format = module_format
        self.indent = 0
        self.output = []
        self.in_class = None
        self.in_async = False  # True when inside async function
        self.class_properties = set()  # Property names of current class
        self.user_functions = set()
        self.async_functions = set()  # Track which functions are async
        self.esm_imports = set()  # ESM import specifiers
        self.requires = set()  # Node.js require() modules (CJS fallback)
        self.imports = []  # EPL import statements collected
        self.exported_names = set()  # Names to export
        # Names of `_epl_*` runtime helpers this program needs. Emitted once at
        # the top of the output, and only the ones actually used, so programs
        # that never touch the relevant construct stay clean.
        self._need: set[str] = set()
        # Stack of sets tracking which JS names have already been declared in the
        # current *function* scope. EPL is function-scoped and its parser emits a
        # `VarDeclaration` for BOTH first-assignment and re-assignment, so the
        # transpiler emits `let` only the first time a name is seen in a scope and
        # a plain assignment thereafter — otherwise `sum = sum + n` in a loop
        # becomes `let sum = sum + n`, a self-referential `let` that throws a TDZ
        # ReferenceError at runtime.
        self._scopes: list[set] = [set()]
        # Parallel stack of names HOISTED to the top of each function scope. EPL
        # is function-scoped, so a variable first assigned inside an `if`/loop
        # body — or a loop variable itself — stays visible after that block; JS
        # `let` is block-scoped and would not. For those names we emit a bare
        # `let a, b;` at the function top and turn every assignment (and the loop
        # header) into a plain `name = …`, preserving EPL's scoping.
        self._hoisted: list[set] = [set()]

    def transpile(self, program: ast.Program) -> str:
        self.output = []
        self.user_functions = set()
        self.async_functions = set()
        self.requires = set()
        self.imports = []
        self._need = set()
        self._scopes = [set()]
        self._hoisted = [set()]
        # Pre-scan for user-defined function names and async functions
        for stmt in program.statements:
            if isinstance(stmt, ast.FunctionDef):
                self.user_functions.add(stmt.name)
            elif isinstance(stmt, ast.AsyncFunctionDef):
                self.user_functions.add(stmt.name)
                self.async_functions.add(stmt.name)
        # Pre-scan every bound variable name so bare `$name` interpolation only
        # fires when the name is a real variable (mirroring the interpreter — a
        # `$` in front of a non-variable, e.g. inside a password literal, is
        # literal text, not a template slot).
        self._declared_vars = self._collect_bound_names(program.statements)
        # Hoist module-level block-scoped names (EPL is function-scoped, and the
        # module top level is itself a scope) before emitting any statement.
        self._begin_scope_body(program.statements)
        # Emit body
        for stmt in program.statements:
            self._emit_stmt(stmt)
        # Build final output with header
        header = []
        if self.target == 'node':
            header.append('// Generated by EPL Compiler v3.0 (Node.js target)')
            if self.module_format == 'esm':
                header.append('')
                for mod in sorted(self.esm_imports | self.requires):
                    header.append(f'import * as {mod} from "node:{mod}";')
            else:
                header.append('"use strict";')
                header.append('')
                for mod in sorted(self.requires):
                    header.append(f'const {mod} = require("{mod}");')
            if self.requires or self.esm_imports:
                header.append('')
        else:
            header.append('// Generated by EPL Compiler v3.0 (Browser target)')
            header.append('')
        footer = []
        if self.exported_names and self.module_format == 'esm':
            export_list = ', '.join(sorted(self.exported_names))
            footer.append('')
            footer.append(f'export {{ {export_list} }};')
        prelude = self._build_prelude()
        return '\n'.join(header + prelude + self.output + footer)

    def _build_prelude(self):
        """Emit the `_epl_*` runtime helpers this program actually uses.

        Kept minimal and construct-scoped: a program that never iterates a Map
        or calls a Map/string method emits no prelude at all, so simple output
        stays byte-for-byte what it was before.
        """
        parts = []
        if 'iter' in self._need:
            # `For each` faithfulness: a plain object iterates its keys (EPL Map
            # semantics); arrays and strings are already for..of-iterable and
            # pass through unchanged. null/undefined iterate as empty.
            parts.append(
                'function _epl_iter(x) {\n'
                '  if (x === null || x === undefined) return [];\n'
                '  if (Array.isArray(x) || typeof x === "string") return x;\n'
                '  if (typeof x === "object") return Object.keys(x);\n'
                '  return x;\n'
                '}'
            )
        if 'prop' in self._need:
            # EPL zero-arg property accessors (.length, .uppercase, …) computed
            # by runtime type; a plain property read for everything else.
            parts.append(_EPL_PROP_RUNTIME_JS)
        if 'method' in self._need:
            # EPL built-in string/list/map methods whose name or behaviour has no
            # 1:1 JS equivalent (.count, .has, .keys/.values on a Map, …).
            # Dispatched by runtime type so the same call is faithful whether the
            # receiver is a string, array, or Map-object.
            parts.append(_EPL_METHOD_RUNTIME_JS)
        if 'reversed' in self._need:
            # `reversed` preserves input type (string→string, list→list).
            parts.append(_EPL_REVERSED_RUNTIME_JS)
        if 'is_map' in self._need:
            # `is_map` — Map-object test, evaluating its argument exactly once.
            parts.append(_EPL_IS_MAP_RUNTIME_JS)
        if 'gcd' in self._need:
            parts.append(_EPL_GCD_RUNTIME_JS)
        if 'factorial' in self._need:
            parts.append(_EPL_FACTORIAL_RUNTIME_JS)
        if 'max' in self._need:
            parts.append(_EPL_MAX_RUNTIME_JS)
        if 'min' in self._need:
            parts.append(_EPL_MIN_RUNTIME_JS)
        # `_epl_add`'s type-error path references `_epl_type`, so pull it in.
        if 'add' in self._need:
            self._need.add('type')
        if 'type' in self._need:
            # `type_of` faithful to EPL's type names, not JS `typeof`.
            parts.append(_EPL_TYPE_RUNTIME_JS)
        if 'str' in self._need:
            # `to_text` faithful to EPL's display form (nothing/true/[a, b]/{k: v}).
            parts.append(_EPL_STR_RUNTIME_JS)
        if 'add' in self._need:
            # EPL `+` overload (number arithmetic / list concat / text coercion).
            parts.append(_EPL_ADD_RUNTIME_JS)
        if not parts:
            return []
        return ['// ── EPL runtime helpers ──', *parts, '']

    def _collect_bound_names(self, statements):
        """Field-agnostic walk collecting every bound variable name (declarations,
        assignments, loop/input vars, params). Used so bare `$name` interpolation
        only triggers for names that are actually variables."""
        names: set = set()

        def visit(node):
            if node is None:
                return
            if isinstance(node, (list, tuple)):
                for item in node:
                    visit(item)
                return
            if not isinstance(node, ast.ASTNode):
                return
            cls = type(node).__name__
            if cls in (
                'VarDeclaration',
                'VarAssignment',
                'ConstDeclaration',
                'InputStatement',
                'ForRange',
                'ForEachLoop',
            ):
                for attr in ('name', 'var_name', 'variable_name'):
                    val = getattr(node, attr, None)
                    if isinstance(val, str):
                        names.add(val)
            params = getattr(node, 'params', None)
            if isinstance(params, (list, tuple)):
                for p in params:
                    if isinstance(p, (list, tuple)) and p and isinstance(p[0], str):
                        names.add(p[0])
                    elif isinstance(getattr(p, 'name', None), str):
                        names.add(p.name)
            for value in vars(node).values():
                visit(value)

        visit(statements)
        return names

    def _line(self, text):
        self.output.append('  ' * self.indent + text)

    # ─── Statement Dispatch ─────────────────────────────

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
            self._line(f'{self._expr(node)};')
        elif isinstance(node, ast.ReturnStatement):
            self._emit_return(node)
        elif isinstance(node, ast.BreakStatement):
            self._line('break;')
        elif isinstance(node, ast.ContinueStatement):
            self._line('continue;')
        elif isinstance(node, ast.ClassDef):
            self._emit_class(node)
        elif isinstance(node, ast.MatchStatement):
            self._emit_match(node)
        elif isinstance(node, ast.TryCatch):
            self._emit_try_catch(node)
        elif isinstance(node, ast.MethodCall):
            self._line(f'{self._expr(node)};')
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
            self._emit_exit(node)
        elif isinstance(node, ast.WaitStatement):
            self._emit_wait(node)
        elif isinstance(node, ast.EnumDef):
            self._emit_enum(node)
        elif isinstance(node, ast.ImportStatement):
            self._emit_import(node)
        elif isinstance(node, ast.UseJSStatement):
            self._emit_use_js(node)
        elif isinstance(node, ast.SuperCall):
            self._emit_super_call(node)
        # v4 AST node support
        elif isinstance(node, ast.InterfaceDefNode):
            self._emit_interface(node)
        elif isinstance(node, ast.ModuleDef):
            self._emit_module(node)
        elif isinstance(node, ast.TryCatchFinally):
            self._emit_try_catch_finally(node)
        elif isinstance(node, ast.ExportStatement):
            self._emit_export(node)
        elif isinstance(node, ast.VisibilityModifier):
            self._emit_stmt(node.statement)
        elif isinstance(node, ast.StaticMethodDef):
            self._emit_static_method(node)
        elif isinstance(node, ast.AbstractMethodDef):
            pass  # abstract methods are interface-only
        elif isinstance(node, ast.YieldStatement):
            self._emit_yield(node)
        elif isinstance(node, ast.DestructureAssignment):
            self._emit_destructure(node)
        elif isinstance(node, ast.ModuleAccess):
            self._line(f'{self._expr(node)};')
        # v6.0: Style & Layout System
        elif isinstance(node, ast.StyleDef):
            self._emit_style_def(node)
        elif isinstance(node, ast.StyledElement):
            self._emit_styled_element(node)
        elif isinstance(node, ast.LayoutContainer):
            self._emit_layout_container(node)
        elif isinstance(node, ast.ComponentDef):
            self._emit_component_def(node)
        elif isinstance(node, ast.AnimateDef):
            self._emit_animate_def(node)
        elif isinstance(
            node, (ast.ResponsiveBlock, ast.TransitionDef, ast.ComponentUse, ast.KeyframeDef)
        ):
            pass  # handled at CSS generation level
        # v6.1: 3D & Canvas
        elif isinstance(node, ast.Scene3D):
            self._emit_scene_3d(node)
        elif isinstance(node, ast.DrawCommand):
            self._emit_draw_command(node)
        else:
            import sys

            print(
                f'Warning: JS transpiler skipping unsupported statement: {type(node).__name__}',
                file=sys.stderr,
            )
            self._line(f'/* unsupported: {type(node).__name__} */')

    # ─── Statements ─────────────────────────────────────

    def _need_call(self, helper: str, call: str) -> str:
        """Mark a `_epl_*` runtime helper as needed and return the call text."""
        self._need.add(helper)
        return call

    # Statement node types that open a NEW function scope. Hoisting stops at
    # their boundary — their own bodies hoist independently.
    _SCOPE_BOUNDARY = (
        'FunctionDef',
        'AsyncFunctionDef',
        'ClassDef',
        'MethodDef',
        'StaticMethodDef',
        'AbstractMethodDef',
        'ModuleDef',
        'Lambda',
        'LambdaExpression',
    )

    def _collect_hoisted_names(self, body) -> set:
        """Names that must be hoisted to the top of the current function scope.

        A name needs hoisting when JS block scoping would otherwise hide it from
        code that EPL (function-scoped) still expects to see it:
          * a variable first assigned inside a nested block (`if`/`while`/`for`/
            `try`/`match` body) but used after that block, and
          * every user loop variable — a `for (let x …)` header block-scopes `x`,
            yet EPL keeps it visible after the loop.
        Descent stops at nested function/class scopes, which hoist on their own.
        """
        hoist: set = set()

        def visit(node, depth):
            if node is None:
                return
            if isinstance(node, (list, tuple)):
                for item in node:
                    visit(item, depth)
                return
            if not isinstance(node, ast.ASTNode):
                return
            cls = type(node).__name__
            if cls in self._SCOPE_BOUNDARY:
                return  # separate function scope — do not descend
            # A declaration nested inside a block leaks past it in EPL.
            if cls == 'VarDeclaration' and depth > 0:
                nm = getattr(node, 'name', None)
                if isinstance(nm, str):
                    hoist.add(nm)
            elif cls == 'InputStatement':
                # `Ask … for x` emits `let x` inside a block (always, for the node
                # target, which wraps the readline in its own `{ }`), so hoist it
                # whenever it is nested or the wrapping block would trap it.
                vn = getattr(node, 'variable_name', None)
                if isinstance(vn, str) and (depth > 0 or self.target == 'node'):
                    hoist.add(vn)
            elif cls in ('ForRange', 'ForEachLoop'):
                vn = getattr(node, 'var_name', None)
                if isinstance(vn, str):
                    hoist.add(vn)
            for value in vars(node).values():
                visit(value, depth + 1)

        for stmt in body:
            visit(stmt, 0)
        return hoist

    def _begin_scope_body(self, body):
        """Emit the hoisted `let …;` line for the current scope and mark those
        names as already-declared so their later assignments emit plain `x = …`.

        Call after `_push_scope()`/`_seed_params()` so parameters (already bound)
        are excluded from the hoist set and never get a shadowing re-declaration.
        """
        hoist = self._collect_hoisted_names(body) - self._scopes[-1]
        self._hoisted[-1] = hoist
        if hoist:
            self._line(f'let {", ".join(sorted(hoist))};')
            self._scopes[-1] |= hoist

    def _push_scope(self):
        """Enter a new function scope for `let`-vs-reassign and hoist tracking."""
        self._scopes.append(set())
        self._hoisted.append(set())

    def _pop_scope(self):
        self._scopes.pop()
        self._hoisted.pop()

    def _declare(self, name: str) -> bool:
        """Record `name` in the current function scope. Returns True if this is
        the first time it is seen here (so the caller should emit `let`)."""
        scope = self._scopes[-1]
        if name in scope:
            return False
        scope.add(name)
        return True

    def _emit_var_decl(self, node):
        # A class property assigned as `this.x = ...` is handled by the same
        # `in_class` path as `_emit_var_assign`, so mirror it here for
        # VarDeclarations that land inside a method body.
        if self.in_class and node.name in self.class_properties:
            self._line(f'this.{node.name} = {self._expr(node.value)};')
            return
        if self._declare(node.name):
            self._line(f'let {node.name} = {self._expr(node.value)};')
        else:
            # Already declared in this scope — EPL re-assignment, not a new
            # binding. Emitting `let` again would shadow/TDZ-crash.
            self._line(f'{node.name} = {self._expr(node.value)};')

    def _emit_var_assign(self, node):
        if self.in_class and node.name in self.class_properties:
            self._line(f'this.{node.name} = {self._expr(node.value)};')
        else:
            self._line(f'{node.name} = {self._expr(node.value)};')

    def _emit_print(self, node):
        # EPL's Print/Say render through `_format_value` (nothing/true/[a, b]/
        # {k: v}), so route through `_epl_str` for faithful output. A bare string
        # or number passes through unchanged, so simple prints stay identical —
        # but a list/map/bool/nothing now matches `epl run` byte-for-byte instead
        # of leaking Node's `[ 1, 2 ]` / `null` rendering.
        self._need.add('str')
        self._line(f'console.log(_epl_str({self._expr(node.expression)}));')

    def _emit_input(self, node):
        # Record the input var so a later reassignment doesn't re-emit `let`.
        self._declare(node.variable_name)
        # If the name was hoisted to the function top (always so for the node
        # target, whose readline lives in its own `{ }` block) it is already
        # declared — assign into it, don't shadow it with a fresh `let`.
        kw = '' if node.variable_name in self._hoisted[-1] else 'let '
        if self.target == 'node':
            self.requires.add('readline')
            prompt_expr = self._expr(node.prompt) if node.prompt else '""'
            self._line('{')
            self.indent += 1
            self._line(
                'const _rl = readline.createInterface({ input: process.stdin, output: process.stdout });'
            )
            self._line(
                f'{kw}{node.variable_name} = await new Promise(resolve => _rl.question({prompt_expr}, ans => {{ _rl.close(); resolve(ans); }}));'
            )
            self.indent -= 1
            self._line('}')
        else:
            if node.prompt:
                self._line(f'{kw}{node.variable_name} = prompt({self._expr(node.prompt)});')
            else:
                self._line(f'{kw}{node.variable_name} = prompt("");')

    def _emit_if(self, node):
        self._line(f'if ({self._expr(node.condition)}) {{')
        self.indent += 1
        for s in node.then_body:
            self._emit_stmt(s)
        self.indent -= 1
        if node.else_body:
            self._line('} else {')
            self.indent += 1
            for s in node.else_body:
                self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_while(self, node):
        self._line(f'while ({self._expr(node.condition)}) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_repeat(self, node):
        # Use unique loop counter to prevent collisions in nested repeats
        if not hasattr(self, '_repeat_counter'):
            self._repeat_counter = 0
        var = f'_i{self._repeat_counter}'
        self._repeat_counter += 1
        self._line(f'for (let {var} = 0; {var} < {self._expr(node.count)}; {var}++) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_for_range(self, node):
        start = self._expr(node.start)
        end = self._expr(node.end)
        step = self._expr(node.step) if node.step else None
        # EPL keeps the loop variable live after the loop; when it has been
        # hoisted, initialise it in the header without a (re-scoping) `let`.
        decl = '' if node.var_name in self._hoisted[-1] else 'let '
        if step:
            # Detect negative step for correct comparison operator
            try:
                step_val = int(step)
                cmp = '>=' if step_val < 0 else '<='
            except (ValueError, TypeError):
                # Dynamic step: use runtime direction check
                cmp = f'({step} > 0 ? {node.var_name} <= {end} : {node.var_name} >= {end})'
                self._line(
                    f'for ({decl}{node.var_name} = {start}; {cmp}; {node.var_name} += {step}) {{'
                )
                self.indent += 1
                for s in node.body:
                    self._emit_stmt(s)
                self.indent -= 1
                self._line('}')
                return
            self._line(
                f'for ({decl}{node.var_name} = {start}; {node.var_name} {cmp} {end}; {node.var_name} += {step}) {{'
            )
        else:
            self._line(
                f'for ({decl}{node.var_name} = {start}; {node.var_name} <= {end}; {node.var_name} += 1) {{'
            )
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_for_each(self, node):
        # EPL `For each` over a Map iterates its KEYS (over a list: elements,
        # over a string: characters). A plain JS object is not iterable with
        # `for..of`, so route the iterable through `_epl_iter`, which yields
        # `Object.keys(x)` for a plain object and `x` unchanged for arrays and
        # strings (both already `for..of`-iterable, matching EPL).
        self._need.add('iter')
        # EPL keeps the loop variable visible after the loop (function scope), so
        # when it has been hoisted, drop `let` from the header — a `let` here
        # would re-scope it to the loop body and hide it from code that follows.
        decl = '' if node.var_name in self._hoisted[-1] else 'let '
        self._line(f'for ({decl}{node.var_name} of _epl_iter({self._expr(node.iterable)})) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_function(self, node):
        params = ', '.join(self._format_param(p) for p in node.params)
        # Check if function body contains yield statements → emit generator
        is_gen = self._contains_yield(node.body)
        prefix = 'function* ' if is_gen else 'function '
        self._line(f'{prefix}{node.name}({params}) {{')
        self.indent += 1
        self._push_scope()
        self._seed_params(node.params)
        self._begin_scope_body(node.body)
        for s in node.body:
            self._emit_stmt(s)
        self._pop_scope()
        self.indent -= 1
        self._line('}')

    def _contains_yield(self, stmts):
        """Check if any statement in the list contains a yield."""
        for s in stmts:
            if isinstance(s, ast.YieldStatement):
                return True
            for attr in ('body', 'then_body', 'else_body', 'try_body', 'catch_body'):
                nested = getattr(s, attr, None)
                if nested and isinstance(nested, list) and self._contains_yield(nested):
                    return True
        return False

    def _emit_async_function(self, node):
        """Emit async function with proper async keyword."""
        params = ', '.join(self._format_param(p) for p in node.params)
        self._line(f'async function {node.name}({params}) {{')
        self.indent += 1
        prev_async = self.in_async
        self.in_async = True
        self._push_scope()
        self._seed_params(node.params)
        self._begin_scope_body(node.body)
        for s in node.body:
            self._emit_stmt(s)
        self._pop_scope()
        self.in_async = prev_async
        self.indent -= 1
        self._line('}')

    def _emit_super_call(self, node):
        """Emit super(...) or super.method(...) call."""
        args = ', '.join(self._expr(a) for a in node.arguments)
        if node.method_name:
            self._line(f'super.{node.method_name}({args});')
        else:
            self._line(f'super({args});')

    def _seed_params(self, params):
        """Pre-register a function's parameters as already-declared in the new
        scope so a later `p = ...` reassignment emits a plain assignment, not a
        redundant `let` that would shadow the parameter."""
        for p in params or []:
            name = p[0] if isinstance(p, (list, tuple)) else getattr(p, 'name', p)
            if isinstance(name, str):
                self._scopes[-1].add(name)

    def _format_param(self, p):
        """Format a parameter tuple (name, type, default) to JS."""
        name = p[0] if isinstance(p, (list, tuple)) else p
        default = p[2] if isinstance(p, (list, tuple)) and len(p) > 2 and p[2] is not None else None
        if default is not None:
            return f'{name} = {self._expr(default)}'
        return name

    def _emit_return(self, node):
        if node.value:
            self._line(f'return {self._expr(node.value)};')
        else:
            self._line('return;')

    def _emit_class(self, node):
        parent = f' extends {node.parent}' if node.parent else ''
        self._line(f'class {node.name}{parent} {{')
        self.indent += 1
        # Separate properties, init method, and other methods
        props = [
            (item.name, item.value) for item in node.body if isinstance(item, ast.VarDeclaration)
        ]
        methods = [
            item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        init_method = None
        other_methods = []
        for m in methods:
            if m.name == 'init':
                init_method = m
            else:
                other_methods.append(m)
        # Track class property names for this. prefix resolution
        self.class_properties = {pn for pn, _ in props}
        # Also add any properties assigned in init body
        if init_method:
            for s in init_method.body:
                if isinstance(s, ast.VarAssignment):
                    self.class_properties.add(s.name)
                elif isinstance(s, ast.VarDeclaration):
                    self.class_properties.add(s.name)
        # Emit constructor: merge properties + init method
        if init_method:
            params = ', '.join(self._format_param(p) for p in init_method.params)
            self._line(f'constructor({params}) {{')
        else:
            self._line('constructor() {')
        self.indent += 1
        # Only auto-insert super() if parent exists AND init body doesn't have its own super call
        if node.parent and not init_method:
            self._line('super();')
        elif node.parent and init_method:
            has_super = any(isinstance(s, ast.SuperCall) for s in init_method.body)
            if not has_super:
                self._line('super();')
        for pn, pv in props:
            self._line(f'this.{pn} = {self._expr(pv)};')
        if init_method:
            self.in_class = node.name
            self._push_scope()
            self._seed_params(init_method.params)
            self._begin_scope_body(init_method.body)
            for s in init_method.body:
                self._emit_stmt(s)
            self._pop_scope()
            self.in_class = None
        self.indent -= 1
        self._line('}')
        # Emit other methods
        for m in other_methods:
            is_async = isinstance(m, ast.AsyncFunctionDef)
            params = ', '.join(self._format_param(p) for p in m.params)
            prefix = 'async ' if is_async else ''
            self._line(f'{prefix}{m.name}({params}) {{')
            self.indent += 1
            self.in_class = node.name
            prev_async = self.in_async
            if is_async:
                self.in_async = True
            self._push_scope()
            self._seed_params(m.params)
            self._begin_scope_body(m.body)
            for s in m.body:
                self._emit_stmt(s)
            self._pop_scope()
            self.in_async = prev_async
            self.in_class = None
            self.indent -= 1
            self._line('}')
        self.indent -= 1
        self._line('}')
        self.class_properties = set()  # Clear class context

    def _emit_match(self, node):
        self._line(f'switch ({self._expr(node.expression)}) {{')
        self.indent += 1
        for clause in node.when_clauses:
            for v in clause.values:
                self._line(f'case {self._expr(v)}:')
            self.indent += 1
            for s in clause.body:
                self._emit_stmt(s)
            self._line('break;')
            self.indent -= 1
        if node.default_body:
            self._line('default:')
            self.indent += 1
            for s in node.default_body:
                self._emit_stmt(s)
            self.indent -= 1
        self.indent -= 1
        self._line('}')

    def _emit_try_catch(self, node):
        self._line('try {')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        self.indent -= 1
        vn = node.error_var or '_err'
        self._line(f'}} catch ({vn}) {{')
        self.indent += 1
        for s in node.catch_body:
            self._emit_stmt(s)
        self.indent -= 1
        if hasattr(node, 'finally_body') and node.finally_body:
            self._line('} finally {')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    # ─── v4 Statements ──────────────────────────────────

    def _emit_interface(self, node):
        """Emit interface as a JSDoc comment + empty class (structural typing in JS)."""
        self._line('/** @interface */')
        self._line(f'class {node.name} {{')
        self.indent += 1
        for sig in node.methods:
            if isinstance(sig, (list, tuple)):
                name = sig[0]
                params_list = sig[1] if len(sig) > 1 else []
            else:
                name = sig.get('name', 'unknown')
                params_list = sig.get('params', [])
            params = ', '.join(
                p[0] if isinstance(p, (list, tuple)) else str(p) for p in params_list
            )
            self._line(f'{name}({params}) {{ throw new Error("Not implemented"); }}')
        self.indent -= 1
        self._line('}')

    def _emit_module(self, node):
        """Emit module as an IIFE-based namespace or ES module object."""
        self._line(f'const {node.name} = (() => {{')
        self.indent += 1
        # Collect exported names
        exports = list(node.exports) if node.exports else []
        for s in node.body:
            if isinstance(s, ast.ExportStatement):
                # ExportStatement only has .name — record it
                exports.append(s.name)
            else:
                self._emit_stmt(s)
                if isinstance(s, ast.FunctionDef):
                    exports.append(s.name)
                elif isinstance(s, ast.VarDeclaration):
                    exports.append(s.name)
        export_obj = ', '.join(dict.fromkeys(exports))  # dedupe, preserve order
        self._line(f'return {{ {export_obj} }};')
        self.indent -= 1
        self._line('})();')

    def _emit_try_catch_finally(self, node):
        self._line('try {')
        self.indent += 1
        for s in node.try_body:
            self._emit_stmt(s)
        self.indent -= 1
        for clause in node.catch_clauses:
            # clause is (error_type, error_var, body) tuple
            err_type, var_name, body = clause[0], clause[1], clause[2]
            var_name = var_name or '_err'
            self._line(f'}} catch ({var_name}) {{')
            self.indent += 1
            if err_type:
                safe_err_type = (
                    err_type.replace('\\', '\\\\')
                    .replace('"', '\\"')
                    .replace('\n', '\\n')
                    .replace('\r', '\\r')
                )
                self._line(
                    f'if (!({var_name} instanceof Error) || !{var_name}.message.includes("{safe_err_type}")) throw {var_name};'
                )
            for s in body:
                self._emit_stmt(s)
            self.indent -= 1
        if not node.catch_clauses:
            self._line('} catch (_err) {')
            self.indent += 1
            self._line('/* no catch body */')
            self.indent -= 1
        if node.finally_body:
            self._line('} finally {')
            self.indent += 1
            for s in node.finally_body:
                self._emit_stmt(s)
            self.indent -= 1
        self._line('}')

    def _emit_export(self, node):
        # ExportStatement only has .name — record it for ESM export footer
        self.exported_names.add(node.name)

    def _emit_static_method(self, node):
        params = ', '.join(self._format_param(p) for p in node.params)
        self._line(f'static {node.name}({params}) {{')
        self.indent += 1
        for s in node.body:
            self._emit_stmt(s)
        self.indent -= 1
        self._line('}')

    def _emit_yield(self, node):
        self._line(f'yield {self._expr(node.value)};')

    def _emit_destructure(self, node):
        names = ', '.join(node.names)
        self._line(f'const [{names}] = {self._expr(node.value)};')

    def _emit_prop_set(self, node):
        self._line(f'{self._expr(node.obj)}.{node.property_name} = {self._expr(node.value)};')

    def _emit_index_set(self, node):
        self._line(f'{self._expr(node.obj)}[{self._expr(node.index)}] = {self._expr(node.value)};')

    def _emit_aug_assign(self, node):
        target = (
            f'this.{node.name}'
            if (self.in_class and node.name in self.class_properties)
            else node.name
        )
        # `+=` must honour EPL's overloaded `+` (list concat, text coercion),
        # so desugar `x += v` to `x = _epl_add(x, v)` rather than emit JS `+=`
        # (which would produce "1,23,4" for lists / "[object Object]" for maps).
        if node.operator == '+=':
            self._need.add('add')
            self._need.add('str')
            self._line(f'{target} = _epl_add({target}, {self._expr(node.value)});')
        else:
            self._line(f'{target} {node.operator} {self._expr(node.value)};')

    def _emit_throw(self, node):
        self._line(f'throw new Error({self._expr(node.expression)});')

    def _emit_file_write(self, node):
        if self.target == 'node':
            if self.module_format == 'esm':
                self.esm_imports.add('fs')
            else:
                self.requires.add('fs')
            self._line(
                f'fs.writeFileSync({self._expr(node.filepath)}, {self._expr(node.content)});'
            )
        else:
            self._line('console.warn("File I/O not available in browser");')

    def _emit_file_append(self, node):
        if self.target == 'node':
            if self.module_format == 'esm':
                self.esm_imports.add('fs')
            else:
                self.requires.add('fs')
            self._line(
                f'fs.appendFileSync({self._expr(node.filepath)}, {self._expr(node.content)} + "\\n");'
            )
        else:
            self._line('console.warn("File I/O not available in browser");')

    def _emit_const(self, node):
        self._line(f'const {node.name} = {self._expr(node.value)};')

    def _emit_assert(self, node):
        self._line(f'console.assert({self._expr(node.expression)}, "Assertion failed");')

    def _emit_exit(self, node):
        if self.target == 'node':
            self._line('process.exit(0);')
        else:
            self._line('throw new Error("EPL: Program exited");')

    def _emit_wait(self, node):
        if self.in_async:
            self._line(
                f'await new Promise(r => setTimeout(r, {self._expr(node.duration)} * 1000));'
            )
        else:
            # In non-async context, use setTimeout wrapper (await is illegal)
            self._line(
                f'setTimeout(() => {{ /* wait {self._expr(node.duration)}s */ }}, {self._expr(node.duration)} * 1000);'
            )

    def _emit_enum(self, node):
        self._line(f'const {node.name} = Object.freeze({{')
        self.indent += 1
        for i, m in enumerate(node.members):
            self._line(f'{m}: {i},')
        self.indent -= 1
        self._line('});')

    def _emit_import(self, node):
        filepath = node.filepath
        # Strip .epl extension for JS module name
        mod_name = (
            filepath.replace('.epl', '')
            .replace('/', '_')
            .replace('\\', '_')
            .replace('\\\\', '_')
            .replace('.', '_')
            .replace('-', '_')
        )
        if mod_name and mod_name[0].isdigit():
            mod_name = '_' + mod_name
        js_path = './' + filepath.replace('.epl', '.js')
        if self.module_format == 'esm' or self.target == 'browser':
            self._line(f'import * as {mod_name} from "{js_path}";')
        else:
            self._line(f'const {mod_name} = require("{js_path}");')

    def _emit_use_js(self, node):
        """Emit native JS import for Use javascript/typescript statements."""
        import json as _json

        alias = node.alias or node.library.split('/')[-1].replace('-', '_')
        alias = re.sub(r'[^a-zA-Z0-9_$]', '_', alias)
        if alias and alias[0].isdigit():
            alias = '_' + alias
        safe_lib = _json.dumps(node.library)
        if self.module_format == 'esm' or self.target == 'browser':
            self._line(f'import * as {alias} from {safe_lib};')
        else:
            self._line(f'const {alias} = require({safe_lib});')

    # ─── Expression Rendering ───────────────────────────

    def _expr(self, node) -> str:
        if node is None:
            return 'null'
        if isinstance(node, ast.Literal):
            return self._expr_literal(node)
        if isinstance(node, ast.Identifier):
            if self.in_class and node.name in self.class_properties:
                return f'this.{node.name}'
            return node.name
        if isinstance(node, ast.BinaryOp):
            return self._expr_binary(node)
        if isinstance(node, ast.UnaryOp):
            return self._expr_unary(node)
        if isinstance(node, ast.FunctionCall):
            return self._expr_call(node)
        if isinstance(node, ast.PropertyAccess):
            # EPL exposes a few zero-arg accessors as *properties* (no parens):
            # `.length` (string/list/map), and `.uppercase`/`.lowercase`/`.trim`
            # on strings. In JS `s.trim` is a Function reference and `map.length`
            # is undefined, so route these known names through `_epl_prop`, which
            # computes the value by runtime type and falls back to a plain
            # property read for everything else (Map keys, instance fields).
            if node.property_name in _EPL_PROPERTY_NAMES:
                self._need.add('prop')
                return f'_epl_prop({self._expr(node.obj)}, "{node.property_name}")'
            return f'{self._expr(node.obj)}.{node.property_name}'
        if isinstance(node, ast.MethodCall):
            return self._expr_method(node)
        if isinstance(node, ast.IndexAccess):
            return f'{self._expr(node.obj)}[{self._expr(node.index)}]'
        if isinstance(node, ast.SliceAccess):
            return self._expr_slice(node)
        if isinstance(node, ast.ListLiteral):
            return f'[{", ".join(self._expr(e) for e in node.elements)}]'
        if isinstance(node, ast.DictLiteral):
            return self._expr_dict(node)
        if isinstance(node, ast.NewInstance):
            return f'new {node.class_name}({", ".join(self._expr(a) for a in node.arguments)})'
        if isinstance(node, ast.LambdaExpression):
            return f'({", ".join(p[0] if isinstance(p, (list, tuple)) else p for p in node.params)}) => {self._expr(node.body)}'
        if isinstance(node, ast.TernaryExpression):
            return f'({self._expr(node.condition)} ? {self._expr(node.true_expr)} : {self._expr(node.false_expr)})'
        if isinstance(node, ast.AwaitExpression):
            return f'await {self._expr(node.expression)}'
        if isinstance(node, ast.SuperCall):
            args = ', '.join(self._expr(a) for a in node.arguments)
            if node.method_name:
                return f'super.{node.method_name}({args})'
            return f'super({args})'
        if isinstance(node, ast.FileRead):
            if self.target == 'node':
                if self.module_format == 'esm':
                    self.esm_imports.add('fs')
                else:
                    self.requires.add('fs')
                return f'fs.readFileSync({self._expr(node.filepath)}, "utf-8")'
            return 'null /* File I/O not available in browser */'
        if isinstance(node, ast.ModuleAccess):
            return f'{node.module_name}.{node.member_name}'
        if isinstance(node, ast.SpreadExpression) if hasattr(ast, 'SpreadExpression') else False:
            return f'...{self._expr(node.expression)}'
        if isinstance(node, ast.ChainedComparison) if hasattr(ast, 'ChainedComparison') else False:
            parts = []
            for i in range(len(node.operators)):
                l = self._expr(node.operands[i])
                r = self._expr(node.operands[i + 1])
                op = node.operators[i]
                op_map = {'==': '===', '!=': '!=='}
                js_op = op_map.get(op, op)
                parts.append(f'({l} {js_op} {r})')
            return ' && '.join(parts)
        import sys

        print(
            f'Warning: JS transpiler skipping unsupported expression: {type(node).__name__}',
            file=sys.stderr,
        )
        return f'null /* unsupported expr: {type(node).__name__} */'

    def _expr_literal(self, node):
        if isinstance(node.value, bool):
            return 'true' if node.value else 'false'
        if isinstance(node.value, str):
            return self._js_string(node.value)
        if node.value is None:
            return 'null'
        return str(node.value)

    @staticmethod
    def _esc_template_literal(text: str) -> str:
        """Escape literal text for safe inclusion in a JS template literal."""
        return text.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    def _js_string(self, s):
        """Convert an EPL string to a JS string literal.
        If it contains $var or ${expr} interpolation, emit a JS template literal.
        Otherwise emit a properly escaped double-quoted string."""
        if self._TEMPLATE_RE.search(s):
            # Build a JS template literal segment by segment: literal text is
            # escaped, and each interpolation slot is TRANSPILED as a real EPL
            # expression (not copied raw). Copying raw broke builtins —
            # `${length(items)}` leaked as `length(items)`, undefined in JS —
            # whereas transpiling turns it into `items.length`.
            out = []
            pos = 0
            for m in self._TEMPLATE_RE.finditer(s):
                out.append(self._esc_template_literal(s[pos : m.start()]))
                expr_braced = m.group(1)  # ${expr}
                expr_bare = m.group(2)  # $var
                if expr_braced is not None:
                    out.append('${' + self._transpile_embedded_expr(expr_braced) + '}')
                elif expr_bare in getattr(self, '_declared_vars', set()):
                    # Bare `$name` interpolates only when `name` is a real
                    # variable, mirroring the interpreter. A `$` before a
                    # non-variable (e.g. inside a password `aB3$xK9`) is literal
                    # text, so it is escaped and left as-is below.
                    out.append('${' + expr_bare + '}')
                else:
                    out.append(self._esc_template_literal(m.group(0)))
                pos = m.end()
            out.append(self._esc_template_literal(s[pos:]))
            return '`' + ''.join(out) + '`'
        # Regular string — escape special chars
        escaped = (
            s.replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('\n', '\\n')
            .replace('\r', '\\r')
            .replace('\t', '\\t')
        )
        return f'"{escaped}"'

    def _transpile_embedded_expr(self, expr_src: str) -> str:
        """Transpile a single interpolated `${...}` slot's EPL expression.

        Falls back to the trimmed source if it cannot be parsed as an expression,
        keeping simple `${name}` slots working even for grammar the expression
        parser does not accept standalone."""
        expr_src = expr_src.strip()
        try:
            from epl.lexer import Lexer as _Lexer
            from epl.parser import Parser as _Parser

            node = _Parser(_Lexer(expr_src).tokenize())._parse_expression()
            return self._expr(node)
        except Exception:
            return expr_src

    def _expr_binary(self, node):
        left = self._expr(node.left)
        right = self._expr(node.right)
        op = node.operator
        op_map = {
            'and': '&&',
            'or': '||',
            '==': '===',
            '!=': '!==',
            '**': '**',
            '//': 'Math.floor(/',
        }
        if op == '//':
            return f'Math.floor({left} / {right})'
        if op == '+':
            # EPL `+` is overloaded: number+number arithmetic, list+list concat,
            # and text+anything / anything+text stringify the other operand to
            # EPL display form. Raw JS `+` gets the string/number cases right by
            # luck but mishandles lists ("1,23,4") and maps ("[object Object]"),
            # so route through `_epl_add` for a faithful result.
            self._need.add('add')
            self._need.add('str')
            return f'_epl_add({left}, {right})'
        js_op = op_map.get(op, op)
        return f'({left} {js_op} {right})'

    def _expr_unary(self, node):
        if node.operator == 'not':
            return f'!{self._expr(node.operand)}'
        return f'{node.operator}{self._expr(node.operand)}'

    def _expr_call(self, node):
        args = ', '.join(self._expr(a) for a in node.arguments)
        # User-defined functions take priority over builtin mappings
        if node.name in self.user_functions:
            return f'{node.name}({args})'
        builtin_map = {
            'length': lambda: f'{self._expr(node.arguments[0])}.length' if node.arguments else '0',
            'to_integer': lambda: f'parseInt({args})',
            'to_text': lambda: self._need_call('str', f'_epl_str({args})'),
            'to_number': lambda: f'Number({args})',
            'to_decimal': lambda: f'parseFloat({args})',
            'uppercase': lambda: f'{self._expr(node.arguments[0])}.toUpperCase()',
            'lowercase': lambda: f'{self._expr(node.arguments[0])}.toLowerCase()',
            'type_of': lambda: self._need_call('type', f'_epl_type({args})'),
            'absolute': lambda: f'Math.abs({args})',
            'round': lambda: f'Math.round({args})',
            'floor': lambda: f'Math.floor({args})',
            'ceil': lambda: f'Math.ceil({args})',
            'sqrt': lambda: f'Math.sqrt({args})',
            'power': lambda: f'Math.pow({args})',
            # EPL max/min accept either a single list (`max([1,2,3])`) or varargs
            # (`max(1,2,3)`); `Math.max([..])` is NaN, so route through a helper.
            'max': lambda: self._need_call('max', f'_epl_max({args})'),
            'min': lambda: self._need_call('min', f'_epl_min({args})'),
            'log': lambda: f'Math.log({args})',
            'sin': lambda: f'Math.sin({args})',
            'cos': lambda: f'Math.cos({args})',
            'random': lambda: 'Math.random()',
            'sorted': lambda: (
                f'[...{self._expr(node.arguments[0])}].sort((a, b) => typeof a === "number" ? a - b : String(a).localeCompare(String(b)))'
            ),
            # EPL `reversed` preserves the input type: a reversed STRING is a
            # string ("abc"→"cba"), a reversed list is a list. Route through a
            # runtime helper so the string case doesn't leak a char array.
            'reversed': lambda: self._need_call(
                'reversed', f'_epl_reversed({self._expr(node.arguments[0])})'
            ),
            'range': lambda: self._js_range(node.arguments),
            'sum': lambda: f'{self._expr(node.arguments[0])}.reduce((a, b) => a + b, 0)',
            'char_code': lambda: f'{self._expr(node.arguments[0])}.charCodeAt(0)',
            'from_char_code': lambda: f'String.fromCharCode({args})',
            # Stdlib: DateTime
            'now': lambda: 'new Date().toISOString()',
            'today': lambda: 'new Date().toISOString().slice(0, 10)',
            'sleep': lambda: (
                f'await new Promise(r => setTimeout(r, {self._expr(node.arguments[0])} * 1000))'
                if self.in_async
                else '/* sync sleep not supported */ void 0'
            ),
            'year': lambda: f'new Date({self._expr(node.arguments[0])}).getFullYear()',
            'month': lambda: f'(new Date({self._expr(node.arguments[0])}).getMonth() + 1)',
            'day': lambda: f'new Date({self._expr(node.arguments[0])}).getDate()',
            'hour': lambda: f'new Date({self._expr(node.arguments[0])}).getHours()',
            'minute': lambda: f'new Date({self._expr(node.arguments[0])}).getMinutes()',
            'second': lambda: f'new Date({self._expr(node.arguments[0])}).getSeconds()',
            'day_of_week': lambda: f'new Date({self._expr(node.arguments[0])}).getDay()',
            # Stdlib: Crypto / encoding
            'uuid': lambda: 'crypto.randomUUID()',
            'uuid4': lambda: 'crypto.randomUUID()',
            'base64_encode': lambda: f'btoa({args})',
            'base64_decode': lambda: f'atob({args})',
            # Stdlib: Regex
            'regex_test': lambda: (
                f'new RegExp({self._expr(node.arguments[0])}).test({self._expr(node.arguments[1])})'
            ),
            'regex_match': lambda: (
                f'{self._expr(node.arguments[1])}.match(new RegExp({self._expr(node.arguments[0])}))'
            ),
            'regex_find_all': lambda: (
                f'[...{self._expr(node.arguments[1])}.matchAll(new RegExp({self._expr(node.arguments[0])}, "g"))]'
            ),
            'regex_replace': lambda: (
                f'{self._expr(node.arguments[2])}.replace(new RegExp({self._expr(node.arguments[0])}, "g"), {self._expr(node.arguments[1])})'
            ),
            'regex_split': lambda: (
                f'{self._expr(node.arguments[1])}.split(new RegExp({self._expr(node.arguments[0])}))'
            ),
            # Stdlib: Advanced Math
            'pi': lambda: 'Math.PI',
            'euler': lambda: 'Math.E',
            'atan': lambda: f'Math.atan({args})',
            'atan2': lambda: f'Math.atan2({args})',
            'asin': lambda: f'Math.asin({args})',
            'acos': lambda: f'Math.acos({args})',
            'tan': lambda: f'Math.tan({args})',
            'degrees': lambda: f'({self._expr(node.arguments[0])} * 180 / Math.PI)',
            'radians': lambda: f'({self._expr(node.arguments[0])} * Math.PI / 180)',
            'sign': lambda: f'Math.sign({args})',
            'clamp': lambda: (
                f'Math.max({self._expr(node.arguments[1])}, Math.min({self._expr(node.arguments[2])}, {self._expr(node.arguments[0])}))'
            ),
            'is_finite': lambda: f'Number.isFinite({args})',
            'is_nan': lambda: f'Number.isNaN({args})',
            'lerp': lambda: (
                f'({self._expr(node.arguments[0])} + ({self._expr(node.arguments[1])} - {self._expr(node.arguments[0])}) * {self._expr(node.arguments[2])})'
            ),
            # Stdlib: Collections
            'zip_lists': lambda: (
                f'{self._expr(node.arguments[0])}.map((v, i) => [v, {self._expr(node.arguments[1])}[i]])'
            ),
            'enumerate_list': lambda: f'{self._expr(node.arguments[0])}.map((v, i) => [i, v])',
            # Stdlib: OS / System
            'platform': lambda: (
                '(typeof process !== "undefined" ? process.platform : navigator.platform)'
            ),
            'args': lambda: '(typeof process !== "undefined" ? process.argv.slice(2) : [])',
            'env_get': lambda: f'(typeof process !== "undefined" ? process.env[{args}] || "" : "")',
            'print_error': lambda: f'console.error({args})',
            'exit_code': lambda: (
                f'process.exit({args})'
                if self.target == 'node'
                else f'(() => {{ throw new Error("EPL exit: " + {args}); }})()'
            ),
            # Stdlib: URL
            'url_encode': lambda: f'encodeURIComponent({args})',
            'url_decode': lambda: f'decodeURIComponent({args})',
            # Stdlib: Strings
            'format': lambda: self._js_format(node.arguments),
            # Stdlib: Networking (Node.js)
            'http_get': lambda: self._js_http_get(node.arguments),
            'http_post': lambda: self._js_http_post(node.arguments),
            'json_parse': lambda: f'JSON.parse({args})',
            'json_stringify': lambda: f'JSON.stringify({args})',
            # Stdlib: Timers
            'set_timeout': lambda: (
                f'setTimeout({self._expr(node.arguments[0])}, {self._expr(node.arguments[1])} * 1000)'
            ),
            'set_interval': lambda: (
                f'setInterval({self._expr(node.arguments[0])}, {self._expr(node.arguments[1])} * 1000)'
            ),
            'clear_timeout': lambda: f'clearTimeout({args})',
            'clear_interval': lambda: f'clearInterval({args})',
            # Stdlib: Type checking
            'is_number': lambda: f'(typeof {args} === "number")',
            'is_string': lambda: f'(typeof {args} === "string")',
            'is_text': lambda: f'(typeof {args} === "string")',
            'is_list': lambda: f'Array.isArray({args})',
            'is_null': lambda: f'({args} === null || {args} === undefined)',
            'is_boolean': lambda: f'(typeof {args} === "boolean")',
            'is_map': lambda: self._need_call('is_map', f'_epl_is_map({args})'),
            # Aliases of already-mapped builtins.
            'abs': lambda: f'Math.abs({args})',
            'to_string': lambda: self._need_call('str', f'_epl_str({args})'),
            # `trim` coerces to text first (interpreter: str(x).strip()), so a
            # non-text argument like `trim(123)` stays valid.
            'trim': lambda: self._need_call('str', f'_epl_str({args}).trim()'),
            # Float-returning math (JS single number type; whole-float display
            # ambiguity is the same accepted gap as the existing sqrt/log/sin).
            'exp': lambda: f'Math.exp({args})',
            'log10': lambda: f'Math.log10({args})',
            'log2': lambda: f'Math.log2({args})',
            'hypot': lambda: f'Math.hypot({args})',
            # Integer-returning math — display-unambiguous, routed through helpers.
            'gcd': lambda: self._need_call('gcd', f'_epl_gcd({args})'),
            'factorial': lambda: self._need_call('factorial', f'_epl_factorial({args})'),
            # `contains(hay, needle)` is a pure string-coercion substring test in
            # the interpreter (`str(needle) in str(hay)`), NOT typed membership —
            # e.g. `contains([12], 2)` is true because "2" is in "[12]".
            'contains': lambda: self._need_call(
                'str',
                f'_epl_str({self._expr(node.arguments[0])}).includes('
                f'_epl_str({self._expr(node.arguments[1])}))',
            ),
            'keys': lambda: f'Object.keys({args})',
            'values': lambda: f'Object.values({args})',
            'has_key': lambda: (
                f'Object.prototype.hasOwnProperty.call({self._expr(node.arguments[0])}, '
                f'{self._expr(node.arguments[1])})'
            ),
        }
        if node.name in builtin_map:
            return builtin_map[node.name]()
        # Correct-or-loud: a name that IS a real EPL builtin but has no JS mapping
        # would otherwise emit `name(args)` — a call to a nonexistent JS identifier
        # that throws ReferenceError at runtime. Refuse at transpile time instead.
        if node.name in _EPL_BUILTIN_NAMES:
            raise TranspileError(
                f'Builtin {node.name!r} is not yet supported by the JavaScript '
                'target. It has no faithful JS mapping, so emitting a call would '
                'produce code that fails at runtime. Use the Python target, or '
                'avoid this builtin in code you transpile to JS.'
            )
        return f'{node.name}({args})'

    def _js_format(self, arguments):
        """Generate JS for EPL format(template, ...args) → string interpolation."""
        if len(arguments) < 1:
            return '""'
        tmpl = self._expr(arguments[0])
        if len(arguments) == 1:
            return tmpl
        # Replace {} placeholders with template literal expressions
        parts = [self._expr(a) for a in arguments[1:]]
        # Use string replace chain
        result = tmpl
        for p in parts:
            result = f'{result}.replace("{{}}", String({p}))'
        return result

    def _js_http_get(self, arguments):
        """Generate JS fetch GET call."""
        url = self._expr(arguments[0])
        if self.in_async:
            return f'await fetch({url}).then(r => r.text())'
        return f'fetch({url}).then(r => r.text())'

    def _js_http_post(self, arguments):
        """Generate JS fetch POST call."""
        url = self._expr(arguments[0])
        body = self._expr(arguments[1]) if len(arguments) > 1 else '""'
        fetch_call = f'fetch({url}, {{method: "POST", headers: {{"Content-Type": "application/json"}}, body: JSON.stringify({body})}})'
        if self.in_async:
            return f'await {fetch_call}.then(r => r.text())'
        return f'{fetch_call}.then(r => r.text())'

    def _js_range(self, arguments):
        """Generate correct JS for range(n), range(start, end), range(start, end, step)."""
        if len(arguments) == 1:
            n = self._expr(arguments[0])
            return f'Array.from({{length: {n}}}, (_, i) => i)'
        elif len(arguments) == 2:
            start = self._expr(arguments[0])
            end = self._expr(arguments[1])
            return f'Array.from({{length: {end} - {start}}}, (_, i) => {start} + i)'
        elif len(arguments) >= 3:
            start = self._expr(arguments[0])
            end = self._expr(arguments[1])
            step = self._expr(arguments[2])
            return f'Array.from({{length: Math.ceil(({end} - {start}) / {step})}}, (_, i) => {start} + i * {step})'
        return '[]'

    def _expr_method(self, node):
        obj = self._expr(node.obj)
        args = ', '.join(self._expr(a) for a in node.arguments)
        # Divergent EPL methods (no faithful JS equivalent) route through the
        # runtime shim; checked before the 1:1 map so EPL semantics win. The
        # shim's user-class fallback keeps class methods working.
        if node.method_name in _EPL_METHOD_NAMES:
            self._need.add('method')
            head = f'_epl_method({obj}, "{node.method_name}"'
            return f'{head}, {args})' if args else f'{head})'
        method_map = {
            'add': 'push',
            'push': 'push',
            'remove': 'splice',
            'upper': 'toUpperCase',
            'uppercase': 'toUpperCase',
            'lower': 'toLowerCase',
            'lowercase': 'toLowerCase',
            'trim': 'trim',
            'contains': 'includes',
            'replace': 'replace',
            'starts_with': 'startsWith',
            'ends_with': 'endsWith',
            'split': 'split',
            'reverse': 'reverse',
            'sort': 'sort',
            'substring': 'substring',
            'index_of': 'indexOf',
            'join': 'join',
            'find': 'find',
            'repeat': 'repeat',
            'char_at': 'charAt',
            'to_list': 'split',
        }
        m = node.method_name
        if m == 'remove':
            return f'{obj}.splice({obj}.indexOf({args}), 1)'
        if m == 'length':
            return f'{obj}.length'
        if m == 'sort':
            # Use numeric-aware comparator
            return f'{obj}.sort((a, b) => typeof a === "number" ? a - b : String(a).localeCompare(String(b)))'
        js_m = method_map.get(m, m)
        return f'{obj}.{js_m}({args})'

    def _expr_slice(self, node):
        obj = self._expr(node.obj)
        start = self._expr(node.start) if node.start else '0'
        end = self._expr(node.end) if node.end else ''
        if end:
            return f'{obj}.slice({start}, {end})'
        return f'{obj}.slice({start})'

    def _expr_dict(self, node):
        parts = []
        for k, v in node.pairs:
            val = self._expr(v)
            # If key is a valid JS identifier, emit unquoted; otherwise quote it
            if isinstance(k, str) and re.match(r'^[a-zA-Z_$][a-zA-Z0-9_$]*$', k):
                parts.append(f'{k}: {val}')
            else:
                parts.append(f'{self._js_string(str(k)) if isinstance(k, str) else k}: {val}')
        joined = ', '.join(parts)
        return '{' + joined + '}'

    # ─── v6.0: Style & Layout Emit Methods ────────────────

    def _emit_style_def(self, node):
        """Emit CSS injection via JavaScript."""
        props = []
        for p in node.properties:
            val = p.value if isinstance(p.value, str) else str(p.value)
            props.append(f'  {p.property_name}: {val};')
        css_text = '\\n'.join(props)
        self._line(f'// Style: .{node.name}')
        self._line('(function() {')
        self._line('  const s = document.createElement("style");')
        self._line(f'  s.textContent = ".{node.name} {{\\n{css_text}\\n}}";')
        self._line('  document.head.appendChild(s);')
        self._line('})();')

    def _emit_styled_element(self, node):
        """Emit DOM element creation for styled elements."""
        tag = node.tag if node.tag != 'container' else 'div'
        var = f'_el_{id(node)}'
        self._line(f'const {var} = document.createElement("{tag}");')
        classes = list(node.styles) + list(node.class_names)
        if node.attributes.get('data-animate'):
            classes.append(f'animate-{node.attributes["data-animate"]}')
        if classes:
            self._line(f'{var}.className = "{" ".join(classes)}";')
        if 'id' in node.attributes:
            self._line(f'{var}.id = "{node.attributes["id"]}";')
        self._line(f'document.body.appendChild({var});')
        for child in node.children:
            self._emit_stmt(child)

    def _emit_layout_container(self, node):
        """Emit flex/grid container via DOM."""
        var = f'_layout_{id(node)}'
        self._line(f'const {var} = document.createElement("div");')
        style_parts = []
        if node.layout_type == 'flex':
            style_parts.append('display: flex')
            if 'direction' in node.properties:
                style_parts.append(f'flex-direction: {node.properties["direction"]}')
            if 'gap' in node.properties:
                style_parts.append(f'gap: {node.properties["gap"]}')
            if 'align' in node.properties:
                style_parts.append(f'align-items: {node.properties["align"]}')
        elif node.layout_type == 'grid':
            style_parts.append('display: grid')
            if 'columns' in node.properties:
                cols = node.properties['columns']
                try:
                    style_parts.append(f'grid-template-columns: repeat({int(cols)}, 1fr)')
                except (ValueError, TypeError):
                    style_parts.append(f'grid-template-columns: {cols}')
            if 'gap' in node.properties:
                style_parts.append(f'gap: {node.properties["gap"]}')
        if style_parts:
            self._line(f'{var}.style.cssText = "{"; ".join(style_parts)}";')
        self._line(f'document.body.appendChild({var});')
        for child in node.children:
            self._emit_stmt(child)

    def _emit_component_def(self, node):
        """Emit component as a JavaScript function."""
        params = ', '.join(p[0] if isinstance(p, tuple) else p for p in node.params)
        self._line(f'function {node.name}({params}) {{')
        self.indent += 1
        for stmt in node.body:
            self._emit_stmt(stmt)
        self.indent -= 1
        self._line('}')

    def _emit_animate_def(self, node):
        """Emit CSS @keyframes via JavaScript."""
        keyframe_parts = []
        for kf in node.keyframes:
            props = []
            for p in kf.properties:
                val = p.value if isinstance(p.value, str) else str(p.value)
                props.append(f'    {p.property_name}: {val};')
            keyframe_parts.append(f'  {kf.percentage}% {{\\n' + '\\n'.join(props) + '\\n  }')
        kf_css = '\\n'.join(keyframe_parts)
        duration = node.duration or '1s'
        easing = node.easing or 'ease'
        iteration = node.iteration or '1'
        self._line(f'// Animation: {node.name}')
        self._line('(function() {')
        self._line('  const s = document.createElement("style");')
        self._line(
            f'  s.textContent = "@keyframes {node.name} {{\\n{kf_css}\\n}}'
            f'\\n.animate-{node.name} {{ animation: {node.name} {duration} {easing} {iteration}; }}";'
        )
        self._line('  document.head.appendChild(s);')
        self._line('})();')

    # ─── v6.1: 3D & Canvas Emit Methods ────────────────────

    def _emit_scene_3d(self, node):
        """Emit Three.js scene initialization as IIFE."""
        name = node.name
        w, h = node.width, node.height

        self._line(f'// 3D Scene: {name}')
        self._line('(function() {')
        self._line('  const container = document.createElement("div");')
        self._line(f'  container.id = "scene-{name}";')
        self._line(f'  container.style.width = "{w}px";')
        self._line(f'  container.style.height = "{h}px";')
        self._line('  document.body.appendChild(container);')
        self._line('  const scene = new THREE.Scene();')

        cam_code = f'  const camera = new THREE.PerspectiveCamera(75, {w}/{h}, 0.1, 1000);'
        cam_pos = '  camera.position.set(0, 5, 10);'
        cam_look = '  camera.lookAt(0, 0, 0);'

        for child in node.body:
            if isinstance(child, ast.CameraSetup):
                px, py, pz = child.position
                lx, ly, lz = child.look_at
                cam_code = f'  const camera = new THREE.PerspectiveCamera({child.fov}, {w}/{h}, 0.1, 1000);'
                cam_pos = f'  camera.position.set({px}, {py}, {pz});'
                cam_look = f'  camera.lookAt({lx}, {ly}, {lz});'

        self._line(cam_code)
        self._line(cam_pos)
        self._line(cam_look)
        self._line('  const renderer = new THREE.WebGLRenderer({antialias: true});')
        self._line(f'  renderer.setSize({w}, {h});')
        self._line('  container.appendChild(renderer.domElement);')

        for child in node.body:
            if isinstance(child, ast.LightSetup):
                lt = child.light_type
                color = _esc_js(child.color)
                intensity = child.intensity
                if lt == 'ambient':
                    self._line(f'  scene.add(new THREE.AmbientLight("{color}", {intensity}));')
                elif lt == 'directional':
                    pos = child.position or [5, 10, 5]
                    self._line(
                        f'  {{ const l = new THREE.DirectionalLight("{color}", {intensity});'
                    )
                    self._line(
                        f'    l.position.set({pos[0]}, {pos[1]}, {pos[2]}); scene.add(l); }}'
                    )
                elif lt == 'point':
                    pos = child.position or [0, 5, 0]
                    self._line(f'  {{ const l = new THREE.PointLight("{color}", {intensity});')
                    self._line(
                        f'    l.position.set({pos[0]}, {pos[1]}, {pos[2]}); scene.add(l); }}'
                    )
            elif isinstance(child, ast.MeshAdd):
                geo_map = {
                    'cube': 'BoxGeometry(1,1,1)',
                    'sphere': 'SphereGeometry(1,32,32)',
                    'plane': 'PlaneGeometry(1,1)',
                    'cylinder': 'CylinderGeometry(0.5,0.5,1,32)',
                    'cone': 'ConeGeometry(0.5,1,32)',
                    'torus': 'TorusGeometry(1,0.4,16,100)',
                }
                geo = geo_map.get(child.shape, 'BoxGeometry(1,1,1)')
                color = _esc_js(child.color or '#667eea')
                px, py, pz = child.position
                sx, sy, sz = child.scale
                rx, ry, rz = child.rotation
                self._line(f'  {{ const g = new THREE.{geo};')
                self._line(f'    const m = new THREE.MeshStandardMaterial({{color: "{color}"}});')
                self._line('    const mesh = new THREE.Mesh(g, m);')
                self._line(f'    mesh.position.set({px}, {py}, {pz});')
                self._line(f'    mesh.scale.set({sx}, {sy}, {sz});')
                self._line(
                    f'    mesh.rotation.set({rx}*Math.PI/180, {ry}*Math.PI/180, {rz}*Math.PI/180);'
                )
                self._line('    scene.add(mesh); }')

        self._line(
            '  function animate() { requestAnimationFrame(animate); renderer.render(scene, camera); }'
        )
        self._line('  animate();')
        self._line('})();')

    def _emit_draw_command(self, node):
        """Emit Canvas 2D drawing code as IIFE."""
        shape = node.shape
        props = node.properties

        self._line(f'// Canvas Draw: {shape}')
        self._line('(function() {')
        self._line('  const canvas = document.createElement("canvas");')
        self._line('  canvas.width = 800; canvas.height = 600;')
        self._line('  document.body.appendChild(canvas);')
        self._line('  const ctx = canvas.getContext("2d");')

        if shape == 'rect':
            x, y = props.get('x', 0), props.get('y', 0)
            w, h = props.get('width', 100), props.get('height', 50)
            fill = _esc_js(props.get('fill', '#000'))
            self._line(f'  ctx.fillStyle = "{fill}";')
            self._line(f'  ctx.fillRect({x}, {y}, {w}, {h});')
            if 'stroke' in props:
                self._line(f'  ctx.strokeStyle = "{_esc_js(props["stroke"])}";')
                self._line(f'  ctx.strokeRect({x}, {y}, {w}, {h});')
        elif shape == 'circle':
            x, y = props.get('x', 50), props.get('y', 50)
            r = props.get('radius', 25)
            fill = _esc_js(props.get('fill', '#000'))
            self._line('  ctx.beginPath();')
            self._line(f'  ctx.arc({x}, {y}, {r}, 0, Math.PI * 2);')
            self._line(f'  ctx.fillStyle = "{fill}"; ctx.fill();')
            if 'stroke' in props:
                self._line(f'  ctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.stroke();')
        elif shape == 'line':
            x1, y1 = props.get('x1', 0), props.get('y1', 0)
            x2, y2 = props.get('x2', 100), props.get('y2', 100)
            stroke = _esc_js(props.get('stroke', '#000'))
            lw = props.get('width', 1)
            self._line('  ctx.beginPath();')
            self._line(f'  ctx.moveTo({x1}, {y1}); ctx.lineTo({x2}, {y2});')
            self._line(f'  ctx.strokeStyle = "{stroke}"; ctx.lineWidth = {lw}; ctx.stroke();')
        elif shape == 'text':
            x, y = props.get('x', 10), props.get('y', 30)
            content = _esc_js(props.get('content', ''))
            font = _esc_js(props.get('font', '16px Arial'))
            fill = _esc_js(props.get('fill', '#000'))
            self._line(f'  ctx.font = "{font}";')
            self._line(f'  ctx.fillStyle = "{fill}";')
            self._line(f'  ctx.fillText("{content}", {x}, {y});')
        elif shape == 'path':
            points = _esc_js(props.get('points', ''))
            fill = _esc_js(props.get('fill', 'transparent'))
            self._line(f'  const p = new Path2D("{points}");')
            self._line(f'  ctx.fillStyle = "{fill}"; ctx.fill(p);')
            if 'stroke' in props:
                self._line(f'  ctx.strokeStyle = "{_esc_js(props["stroke"])}"; ctx.stroke(p);')

        self._line('})();')


def transpile_to_js(program: ast.Program) -> str:
    """Convenience function to transpile EPL AST to browser JavaScript."""
    return JSTranspiler(target='browser').transpile(program)


def transpile_to_node(program: ast.Program, module_format='esm') -> str:
    """Transpile EPL AST to Node.js JavaScript.
    module_format: 'esm' (default, import/export) or 'cjs' (CommonJS require)."""
    return JSTranspiler(target='node', module_format=module_format).transpile(program)
