"""Conservative monomorphic type inference for the native (`epl build`) backend.

Why this exists
---------------
The LLVM backend has no type inference: an untyped parameter defaults to ``i8*``
(string), so idiomatic dynamic EPL — ``Function add takes a and b`` / ``Return a
+ b`` called with integers — miscompiles (an ``i64`` passed where an ``i8*`` is
expected becomes a bogus pointer, then segfaults). The safety gate
(`runtime_support._native_unsafe_functions`) therefore *refuses* to build any
function with an untyped parameter or untyped value-return.

This module recovers a large, safe slice of those programs. It runs a
whole-program **monomorphic** inference: each untyped function's parameter and
return types are inferred from its call sites and body. A function is *resolved*
only when every parameter and the return collapse to a single concrete native
type with no conflict across call sites.

Soundness over coverage
------------------------
The integration is **purely additive**: it only ever runs on a program the
safety gate would otherwise refuse, and admits it only when the *entire* program
(top level + every function body) type-checks to concrete native types with no
unknown or divergent operation. The type rules mirror the backend exactly, and
anything uncertain — int division (native truncates, the interpreter does not),
``**`` (native is always float), string/float or string/bool concatenation
(build-fail or formatted differently), an unmodeled builtin, a foreach element of
unknown type — yields ``UNKNOWN`` and makes the program fall back to refusal.
So admitting can only turn a *refused* program into a *correct* native binary; it
can never turn a passing program into a worse one, nor admit a crash.
"""

from __future__ import annotations

from epl import ast_nodes as ast
from epl.native_names import NATIVE_BUILTIN_NAMES
from epl.native_names import NATIVE_SHADOWED_NAMES as _RESERVED_RUNTIME_NAMES

# Concrete native types (EPL type-name strings, matching _infer_param_type).
INT = 'int'
FLOAT = 'float'
STRING = 'string'
BOOL = 'bool'
LIST = 'list'
MAP = 'map'
VOID = 'void'

# Sentinels distinct from any concrete type.
UNKNOWN = None  # could not be determined → forces refusal
CONFLICT = '<conflict>'  # call sites disagree → unresolved

_NUMERIC = (INT, FLOAT)

# ``_RESERVED_RUNTIME_NAMES`` (imported above as NATIVE_SHADOWED_NAMES): user
# function names the native backend cannot build as a distinct, correctly
# dispatched function — either they shadow a builtin (the compiler dispatches the
# builtin first, so the user function never runs natively though the interpreter
# runs it) or they collide with a runtime ``epl_<name>`` symbol (duplicate-symbol
# build failure). Admitting either diverges from the interpreter, so inference
# declines them and the program is refused cleanly.

# Builtins with a statically-known, native-matching result type. Anything not
# here is treated as UNKNOWN (conservative → refuse).
_BUILTIN_RET = {
    'length': INT,
    'to_integer': INT,
    'to_text': STRING,
    'to_string': STRING,
    'uppercase': STRING,
    'lowercase': STRING,
    'trim': STRING,
}


class NativeAnalysis:
    """Result of :func:`analyze`.

    ``admit`` — build natively with the inferred signatures.
    ``func_sigs`` — ``{function_name: ([param_epl_type, ...], return_epl_type)}``
    for resolved functions; consumed by the compiler to type untyped params.
    ``reasons`` — ``[(qualified_name, line, reason)]`` when not admitted.
    """

    def __init__(self, admit, func_sigs, reasons):
        self.admit = admit
        self.func_sigs = func_sigs
        self.reasons = reasons


def _unwrap(node):
    return node.statement if isinstance(node, ast.VisibilityModifier) else node


def _literal_type(value):
    if isinstance(value, bool):
        return BOOL
    if isinstance(value, int):
        return INT
    if isinstance(value, float):
        return FLOAT
    if isinstance(value, str):
        return STRING
    return UNKNOWN


class _Inferencer:
    def __init__(self, program):
        self.program = program
        self.funcs = {}  # name -> FunctionDef (top-level only; modules handled separately)
        self.sig = {}  # name -> {'params': [type], 'ret': type|None, 'returns_value': bool}
        self.callsites = []  # (caller_name_or_None, FunctionCall)
        self.global_env = {}

    # ── collection ─────────────────────────────────────────
    def _collect(self):
        for stmt in getattr(self.program, 'statements', []) or []:
            stmt = _unwrap(stmt)
            if isinstance(stmt, ast.FunctionDef):
                self.funcs[stmt.name] = stmt
        for name, fn in self.funcs.items():
            explicit = []
            for p in fn.params:
                if isinstance(p, ast.RestParameter):
                    explicit.append(UNKNOWN)  # rest params unsupported → stays unknown
                else:
                    explicit.append(_normalize_type(p[1]) if p[1] else UNKNOWN)
            returns_value = _returns_value(fn.body)
            ret = _normalize_type(fn.return_type) if fn.return_type else UNKNOWN
            self.sig[name] = {
                'params': explicit,
                # Which params were given no source annotation (so inference must
                # supply them, and a conflict among call sites must block admit).
                'inferred_param': [t is UNKNOWN for t in explicit],
                'ret': ret,
                'returns_value': returns_value,
                # Whether the *source* left something to infer — recorded before
                # inference fills `params`/`ret`, so the admit check can tell a
                # genuinely-resolved function from one inference couldn't pin.
                'needs': any(t is UNKNOWN for t in explicit) or (returns_value and ret is UNKNOWN),
            }
        # Gather every call site, tagged with the function it appears inside.
        for stmt in getattr(self.program, 'statements', []) or []:
            self._gather_calls(_unwrap(stmt), None)

    def _gather_calls(self, node, caller):
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, ast.FunctionDef):
            caller = node.name if node.name in self.funcs else caller
            for s in node.body or []:
                self._gather_calls(s, caller)
            return
        if isinstance(node, ast.FunctionCall) and node.name in self.funcs:
            self.callsites.append((caller, node))
        if hasattr(node, '__dict__'):
            for v in vars(node).values():
                if isinstance(v, (list, tuple)):
                    for item in v:
                        self._gather_calls(item, caller)
                elif hasattr(v, '__dict__'):
                    self._gather_calls(v, caller)

    # ── environments ───────────────────────────────────────
    def _build_global_env(self):
        env = {}
        for stmt in getattr(self.program, 'statements', []) or []:
            self._walk_bindings(_unwrap(stmt), env)
        self.global_env = env

    def _local_env(self, fn_name):
        """Param + local-variable types inside ``fn_name`` under current sigs."""
        fn = self.funcs[fn_name]
        env = {}
        sig = self.sig[fn_name]
        for i, p in enumerate(fn.params):
            if isinstance(p, ast.RestParameter):
                continue
            t = sig['params'][i]
            if t not in (UNKNOWN, CONFLICT):
                env[p[0]] = t
        for s in fn.body or []:
            self._walk_bindings(s, env)
        return env

    def _walk_bindings(self, node, env):
        """Apply this statement's variable binding and recurse into the bodies of
        control-flow statements, so locals declared inside loops/ifs are visible.
        Nested function defs are not descended into (their scope is their own)."""
        if node is None or isinstance(node, ast.FunctionDef):
            return
        self._apply_binding(node, env)
        for attr in ('then_body', 'else_body', 'body', 'try_body', 'catch_body', 'finally_body'):
            sub = getattr(node, attr, None)
            if isinstance(sub, list):
                for s in sub:
                    self._walk_bindings(s, env)

    def _apply_binding(self, node, env):
        """Record the type of variables a statement introduces (best effort)."""
        if isinstance(node, ast.VarDeclaration):
            t = _normalize_type(node.var_type) if node.var_type else self.infer(node.value, env)
            env[node.name] = t
        elif isinstance(node, ast.VarAssignment):
            # Only set if consistent; a conflicting reassignment marks it unknown.
            t = self.infer(node.value, env)
            if node.name in env and env[node.name] != t:
                env[node.name] = UNKNOWN
            else:
                env[node.name] = t
        elif isinstance(node, ast.ForRange):
            env[node.var_name] = INT

    # ── expression inference ───────────────────────────────
    def infer(self, node, env):
        if node is None:
            return UNKNOWN
        if isinstance(node, ast.Literal):
            return _literal_type(node.value)
        if isinstance(node, ast.Identifier):
            return env.get(node.name, UNKNOWN)
        if isinstance(node, ast.ListLiteral):
            return LIST
        if isinstance(node, ast.DictLiteral):
            return MAP
        if isinstance(node, ast.UnaryOp):
            if node.operator == 'not':
                return BOOL
            if node.operator == '-':
                t = self.infer(node.operand, env)
                return t if t in _NUMERIC else UNKNOWN
            return UNKNOWN
        if isinstance(node, ast.BinaryOp):
            return self._infer_binary(node, env)
        if isinstance(node, ast.TernaryExpression):
            a = self.infer(node.true_expr, env)
            b = self.infer(node.false_expr, env)
            return a if a == b and a not in (UNKNOWN, CONFLICT) else UNKNOWN
        if isinstance(node, ast.FunctionCall):
            return self._infer_call(node, env)
        if isinstance(node, (ast.MethodCall, ast.PropertyAccess)):
            name = getattr(node, 'method_name', None) or getattr(node, 'property_name', None)
            return _BUILTIN_RET.get(name, UNKNOWN)
        return UNKNOWN

    def _infer_binary(self, node, env):
        op = node.operator
        lt = self.infer(node.left, env)
        rt = self.infer(node.right, env)
        if lt in (UNKNOWN, CONFLICT) or rt in (UNKNOWN, CONFLICT):
            return UNKNOWN
        # Comparisons / logic → bool.
        if op in ('<', '>', '<=', '>=', '==', '!='):
            return BOOL
        if op in ('and', 'or'):
            return BOOL if lt == BOOL and rt == BOOL else UNKNOWN
        if op == '+':
            if lt == STRING and rt == STRING:
                return STRING
            # string + int matches the backend (int_to_str); string + float/bool
            # does not, so only INT is allowed alongside a string.
            if lt == STRING and rt == INT:
                return STRING
            if lt == INT and rt == STRING:
                return STRING
            if lt == LIST and rt == LIST:
                return LIST
            if lt in _NUMERIC and rt in _NUMERIC:
                return FLOAT if FLOAT in (lt, rt) else INT
            return UNKNOWN
        if op in ('-', '*', '%'):
            if lt in _NUMERIC and rt in _NUMERIC:
                if op == '%' and (lt == FLOAT or rt == FLOAT):
                    return UNKNOWN  # float modulo: avoid divergence
                return FLOAT if FLOAT in (lt, rt) else INT
            return UNKNOWN
        if op == '/':
            # Native int/int truncates (sdiv) but the interpreter yields a float
            # for non-divisible operands → only admit float division.
            if FLOAT in (lt, rt) and lt in _NUMERIC and rt in _NUMERIC:
                return FLOAT
            return UNKNOWN
        # '**', '//', 'raised', bit ops, etc. → not proven equivalent.
        return UNKNOWN

    def _infer_call(self, node, env):
        # Only names the native compiler actually dispatches as builtins count in
        # *call* position. ``_BUILTIN_RET`` also holds method/property-only names
        # (e.g. ``to_string``, ``trim``) that the backend does NOT treat as
        # function-call builtins, so gating on NATIVE_BUILTIN_NAMES keeps call
        # inference aligned with the compiler's real dispatch contract.
        if node.name in _BUILTIN_RET and node.name in NATIVE_BUILTIN_NAMES:
            return _BUILTIN_RET[node.name]
        if node.name in self.sig:
            s = self.sig[node.name]
            return s['ret'] if s['returns_value'] else VOID
        return UNKNOWN

    # ── fixpoint ───────────────────────────────────────────
    def _iterate_once(self):
        changed = False
        self._build_global_env()
        # Gather the concrete argument type seen at every call site for each
        # inferred parameter; a parameter that sees two different concrete types
        # is polymorphic at the call boundary → CONFLICT (unresolvable here).
        constraints = {name: {} for name in self.funcs}  # name -> {param_idx: set(types)}
        for caller, call in self.callsites:
            env = self.global_env if caller is None else self._local_env(caller)
            s = self.sig[call.name]
            for i, arg in enumerate(call.arguments):
                if i >= len(s['params']) or not s['inferred_param'][i]:
                    continue  # out of range, or an explicitly-annotated param
                t = self.infer(arg, env)
                if t not in (UNKNOWN, CONFLICT):
                    constraints[call.name].setdefault(i, set()).add(t)
        for name, per_param in constraints.items():
            s = self.sig[name]
            for i, types in per_param.items():
                new = CONFLICT if len(types) > 1 else next(iter(types))
                if s['params'][i] != new:
                    s['params'][i] = new
                    changed = True
        # Infer return types from return expressions.
        for name, fn in self.funcs.items():
            s = self.sig[name]
            if not s['returns_value'] or s['ret'] != UNKNOWN:
                continue
            env = self._local_env(name)
            rtypes = set()
            for rexpr in _return_exprs(fn.body):
                rtypes.add(self.infer(rexpr, env))
            rtypes.discard(UNKNOWN)
            if len(rtypes) == 1:
                s['ret'] = rtypes.pop()
                changed = True
        return changed

    def run(self):
        self._collect()
        for _ in range(64):  # converges well within this bound for real programs
            if not self._iterate_once():
                break
        return self._finalize()

    # ── finalize / whole-program safety check ──────────────
    def _finalize(self):
        resolved = {}
        for name, fn in self.funcs.items():
            s = self.sig[name]
            params = s['params']
            ret = s['ret']
            ok_params = all(t not in (UNKNOWN, CONFLICT) for t in params if t is not None) and all(
                t is not None for t in params
            )
            ok_ret = (not s['returns_value']) or ret not in (UNKNOWN, CONFLICT)
            if ok_params and ok_ret and name not in _RESERVED_RUNTIME_NAMES:
                resolved[name] = (list(params), ret if s['returns_value'] else VOID)

        # Whole-program proof: every statement must type-check to concrete native
        # types with no UNKNOWN anywhere (top level + every resolved function).
        checker = _SafetyChecker(self)
        admit = checker.program_is_native_safe(resolved)
        return NativeAnalysis(admit, resolved if admit else {}, checker.reasons)


class _SafetyChecker:
    """Conservative whole-program walk: refuses on any expression that does not
    infer to a concrete native type, or any statement form the backend can't
    lower safely. Sound by construction — uncertainty means refuse."""

    def __init__(self, inf):
        self.inf = inf
        self.reasons = []

    def program_is_native_safe(self, resolved):
        # Every function the source left untyped must end up resolved (a single
        # concrete monomorphic signature, not reserved-name-blocked, not in
        # conflict). `needs` is recorded from the *source*, so a function whose
        # types inference could not pin still blocks admission here.
        for name, fn in self.inf.funcs.items():
            if name in _RESERVED_RUNTIME_NAMES:
                # Shadows a native builtin or collides with a runtime symbol. This
                # must block admission regardless of annotation: a *fully typed*
                # `Function power ...` is never in `resolved` either, yet without
                # this the compiler would still hit the duplicate-symbol /
                # builtin-shadowing divergence this pass exists to refuse.
                self.reasons.append(
                    (
                        name,
                        getattr(fn, 'line', 0),
                        'name shadows a native builtin or runtime symbol',
                    )
                )
            elif self.inf.sig[name]['needs'] and name not in resolved:
                self.reasons.append(
                    (name, getattr(fn, 'line', 0), 'parameter/return types could not be inferred')
                )
        if self.reasons:
            return False

        # Walk top-level statements and every function body; any UNKNOWN expr or
        # unsupported statement fails the proof.
        for stmt in getattr(self.inf.program, 'statements', []) or []:
            self._check_stmt(_unwrap(stmt), self.inf.global_env, None)
        for name, fn in self.inf.funcs.items():
            self._check_body(fn.body, self.inf._local_env(name), name)
        return not self.reasons

    def _fail(self, node, msg):
        self.reasons.append(('<program>', getattr(node, 'line', 0), msg))

    def _check_body(self, body, env, fn):
        for s in body or []:
            self._check_stmt(s, env, fn)

    def _check_stmt(self, node, env, fn):
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        # Nested function defs are checked via their own local env elsewhere.
        if isinstance(node, ast.FunctionDef):
            return
        if isinstance(node, (ast.PrintStatement,)):
            self._require(node.expression, env, node)
        elif isinstance(node, ast.VarDeclaration):
            if node.value is not None:
                self._require(node.value, env, node)
        elif isinstance(node, ast.VarAssignment):
            self._require(node.value, env, node)
        elif isinstance(node, ast.ReturnStatement):
            if node.value is not None:
                self._require(node.value, env, node)
        elif isinstance(node, ast.IfStatement):
            self._require(node.condition, env, node)
            self._check_body(node.then_body, env, fn)
            self._check_body(node.else_body, env, fn)
        elif isinstance(node, ast.WhileLoop):
            self._require(node.condition, env, node)
            self._check_body(node.body, env, fn)
        elif isinstance(node, ast.RepeatLoop):
            self._require(node.count, env, node)
            self._check_body(node.body, env, fn)
        elif isinstance(node, ast.ForRange):
            # Loop var is int; bounds/step must be numeric. `_require` alone would
            # accept a concrete-but-non-numeric type (e.g. a string bound), which
            # the native counted loop cannot lower — so require numeric explicitly.
            self._require_numeric(node.start, env, node)
            self._require_numeric(node.end, env, node)
            if getattr(node, 'step', None) is not None:
                self._require_numeric(node.step, env, node)
            self._check_body(node.body, {**env, node.var_name: INT}, fn)
        elif isinstance(node, ast.FunctionCall):
            self._check_call(node, env)
        else:
            # Any statement form not explicitly modeled (classes, async, web,
            # file I/O, foreach over unknown element types, etc.) is not proven
            # safe under inference → refuse.
            self._fail(
                node, f'unsupported construct for inferred native build: {type(node).__name__}'
            )

    def _check_call(self, node, env):
        # Validate the callee, not just its arguments: a standalone
        # `Call missing(1)` has concrete args but no target the backend can emit.
        # A callee is admissible only if it is a user function in the program or a
        # builtin the native compiler dispatches.
        if node.name not in self.inf.funcs and node.name not in NATIVE_BUILTIN_NAMES:
            self._fail(node, f'call to unknown function "{node.name}"')
            return
        for arg in node.arguments:
            self._require(arg, env, node)

    def _require(self, expr, env, node):
        t = self.inf.infer(expr, env)
        if t in (UNKNOWN, CONFLICT):
            self._fail(node, 'expression type could not be proven native-safe')

    def _require_numeric(self, expr, env, node):
        t = self.inf.infer(expr, env)
        if t not in _NUMERIC:
            self._fail(node, 'expression must be numeric for a native counted loop')


def _normalize_type(t):
    if t is None:
        return UNKNOWN
    t = str(t).lower()
    if t in ('integer', 'int', 'number'):
        return INT
    if t in ('decimal', 'float', 'double'):
        return FLOAT
    if t in ('text', 'string', 'str'):
        return STRING
    if t in ('boolean', 'bool'):
        return BOOL
    if t in ('list', 'array'):
        return LIST
    if t in ('map', 'dict', 'dictionary'):
        return MAP
    return UNKNOWN


def _returns_value(body):
    for _ in _return_exprs(body):
        return True
    return False


def _return_exprs(body):
    """Yield the value expression of every value-returning Return in ``body``,
    skipping nested function definitions (their returns are their own)."""
    stack = list(body or [])
    while stack:
        node = stack.pop()
        if node is None or isinstance(node, (str, int, float, bool)):
            continue
        if isinstance(node, ast.FunctionDef):
            continue
        if isinstance(node, ast.ReturnStatement):
            if getattr(node, 'value', None) is not None:
                yield node.value
            continue
        if hasattr(node, '__dict__'):
            for v in vars(node).values():
                if isinstance(v, (list, tuple)):
                    stack.extend(v)
                elif hasattr(v, '__dict__'):
                    stack.append(v)


def analyze(program) -> NativeAnalysis:
    """Run conservative monomorphic inference over ``program``."""
    return _Inferencer(program).run()
