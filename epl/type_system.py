"""
EPL Type System v4.0
Production-grade static type checking with:
  - Type annotations for variables, function params/returns
  - Interface definitions with required method signatures
  - Generic types (List<T>, Map<K,V>, Optional<T>)
  - Type inference engine
  - Union types (integer | text)
  - Type aliases
  - Structural typing for interfaces
  - Compile-time type checking pass (optional, enabled with --strict)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple, Any
from enum import Enum, auto


# ═══════════════════════════════════════════════════════════
#  Type Representation
# ═══════════════════════════════════════════════════════════

class TypeKind(Enum):
    """Classification of EPL types."""
    PRIMITIVE = auto()      # integer, decimal, text, boolean, nothing
    LIST = auto()           # List<T>
    MAP = auto()            # Map<K, V>
    FUNCTION = auto()       # (params) -> return
    CLASS = auto()          # user-defined class
    INTERFACE = auto()      # interface type
    UNION = auto()          # A | B
    OPTIONAL = auto()       # T?  (sugar for T | nothing)
    GENERIC_VAR = auto()    # T, K, V — type parameter
    TUPLE = auto()          # (A, B, C)
    ANY = auto()            # any — opt out of type checking
    NEVER = auto()          # bottom type (unreachable)
    ALIAS = auto()          # type alias


@dataclass(frozen=True)
class EPLType:
    """Immutable representation of an EPL type."""
    kind: TypeKind
    name: str                                  # "integer", "List", class name, etc.
    params: Tuple['EPLType', ...] = ()         # generic parameters: List<integer> → params=(integer,)
    fields: Dict[str, 'EPLType'] = field(default_factory=dict)   # class/interface fields
    methods: Dict[str, 'FunctionType'] = field(default_factory=dict)  # class/interface methods
    union_members: Tuple['EPLType', ...] = ()  # for union types
    resolved: Optional['EPLType'] = None       # for aliases

    def __hash__(self):
        return hash((self.kind, self.name, self.params))

    def __eq__(self, other):
        if not isinstance(other, EPLType):
            return False
        return self.kind == other.kind and self.name == other.name and self.params == other.params

    def __repr__(self):
        if self.kind == TypeKind.PRIMITIVE or self.kind == TypeKind.ANY:
            return self.name
        if self.kind == TypeKind.LIST:
            inner = self.params[0] if self.params else 'any'
            return f"List<{inner}>"
        if self.kind == TypeKind.MAP:
            k = self.params[0] if len(self.params) > 0 else 'any'
            v = self.params[1] if len(self.params) > 1 else 'any'
            return f"Map<{k}, {v}>"
        if self.kind == TypeKind.OPTIONAL:
            inner = self.params[0] if self.params else 'any'
            return f"{inner}?"
        if self.kind == TypeKind.UNION:
            return ' | '.join(str(m) for m in self.union_members)
        if self.kind == TypeKind.FUNCTION:
            return f"({', '.join(str(p) for p in self.params)}) -> {self.name}"
        if self.kind == TypeKind.TUPLE:
            return f"({', '.join(str(p) for p in self.params)})"
        if self.kind == TypeKind.GENERIC_VAR:
            return self.name
        if self.kind == TypeKind.CLASS or self.kind == TypeKind.INTERFACE:
            if self.params:
                return f"{self.name}<{', '.join(str(p) for p in self.params)}>"
            return self.name
        return self.name


@dataclass(frozen=True)
class FunctionType:
    """Type signature for a function/method."""
    param_types: Tuple[EPLType, ...] = ()
    param_names: Tuple[str, ...] = ()
    return_type: EPLType = None
    is_async: bool = False
    generic_params: Tuple[str, ...] = ()   # <T, K> on the function itself

    def __repr__(self):
        params = ', '.join(f"{n}: {t}" for n, t in zip(self.param_names, self.param_types))
        ret = f" -> {self.return_type}" if self.return_type else ""
        prefix = "async " if self.is_async else ""
        generics = f"<{', '.join(self.generic_params)}>" if self.generic_params else ""
        return f"{prefix}fn{generics}({params}){ret}"


# ═══════════════════════════════════════════════════════════
#  Built-in Types
# ═══════════════════════════════════════════════════════════

# Primitives
T_INTEGER = EPLType(TypeKind.PRIMITIVE, "integer")
T_DECIMAL = EPLType(TypeKind.PRIMITIVE, "decimal")
T_TEXT    = EPLType(TypeKind.PRIMITIVE, "text")
T_BOOLEAN = EPLType(TypeKind.PRIMITIVE, "boolean")
T_NOTHING = EPLType(TypeKind.PRIMITIVE, "nothing")
T_ANY     = EPLType(TypeKind.ANY, "any")
T_NEVER   = EPLType(TypeKind.NEVER, "never")

# Number supertype
T_NUMBER = EPLType(TypeKind.UNION, "number", union_members=(T_INTEGER, T_DECIMAL))

PRIMITIVE_MAP = {
    "integer": T_INTEGER, "int": T_INTEGER,
    "decimal": T_DECIMAL, "float": T_DECIMAL, "double": T_DECIMAL,
    "text": T_TEXT, "string": T_TEXT, "str": T_TEXT,
    "boolean": T_BOOLEAN, "bool": T_BOOLEAN,
    "nothing": T_NOTHING, "void": T_NOTHING, "null": T_NOTHING, "none": T_NOTHING,
    "any": T_ANY,
    "number": T_NUMBER,
}


def make_list_type(element_type: EPLType = T_ANY) -> EPLType:
    return EPLType(TypeKind.LIST, "List", params=(element_type,))

def make_map_type(key_type: EPLType = T_TEXT, value_type: EPLType = T_ANY) -> EPLType:
    return EPLType(TypeKind.MAP, "Map", params=(key_type, value_type))

def make_optional_type(inner: EPLType) -> EPLType:
    return EPLType(TypeKind.OPTIONAL, f"{inner}?", params=(inner,))

def make_union_type(*members: EPLType) -> EPLType:
    # Flatten nested unions
    flat = []
    for m in members:
        if m.kind == TypeKind.UNION:
            flat.extend(m.union_members)
        else:
            flat.append(m)
    # Deduplicate
    seen = set()
    unique = []
    for m in flat:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    if len(unique) == 1:
        return unique[0]
    return EPLType(TypeKind.UNION, "union", union_members=tuple(unique))

def make_tuple_type(*element_types: EPLType) -> EPLType:
    return EPLType(TypeKind.TUPLE, "tuple", params=element_types)

def make_function_type(param_types, return_type, is_async=False) -> FunctionType:
    return FunctionType(
        param_types=tuple(param_types),
        return_type=return_type,
        is_async=is_async,
    )


# ═══════════════════════════════════════════════════════════
#  Interface Definition
# ═══════════════════════════════════════════════════════════

@dataclass
class InterfaceDef:
    """
    An interface definition.
    EPL syntax:
        Interface Printable
            method to_string() returns text
            method print()
        End Interface
    """
    name: str
    methods: Dict[str, FunctionType]       # method_name -> signature
    properties: Dict[str, EPLType] = field(default_factory=dict)
    extends: List[str] = field(default_factory=list)   # parent interfaces
    generic_params: List[str] = field(default_factory=list)  # <T, K>
    line: int = 0


# ═══════════════════════════════════════════════════════════
#  Type Environment (Scope-aware type tracking)
# ═══════════════════════════════════════════════════════════

class TypeScope:
    """Tracks type bindings in a scope, with parent chaining."""

    def __init__(self, parent: Optional['TypeScope'] = None, name: str = "global"):
        self.parent = parent
        self.name = name
        self.variables: Dict[str, EPLType] = {}           # var_name -> type
        self.functions: Dict[str, FunctionType] = {}      # fn_name -> signature
        self.classes: Dict[str, EPLType] = {}             # class_name -> class type
        self.interfaces: Dict[str, InterfaceDef] = {}     # interface_name -> def
        self.type_aliases: Dict[str, EPLType] = {}        # alias_name -> target type
        self.generic_vars: Dict[str, EPLType] = {}        # T -> constraint or T_ANY

    def define_var(self, name: str, typ: EPLType):
        self.variables[name] = typ

    def lookup_var(self, name: str) -> Optional[EPLType]:
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.lookup_var(name)
        return None

    def define_function(self, name: str, sig: FunctionType):
        self.functions[name] = sig

    def lookup_function(self, name: str) -> Optional[FunctionType]:
        if name in self.functions:
            return self.functions[name]
        if self.parent:
            return self.parent.lookup_function(name)
        return None

    def define_class(self, name: str, typ: EPLType):
        self.classes[name] = typ

    def lookup_class(self, name: str) -> Optional[EPLType]:
        if name in self.classes:
            return self.classes[name]
        if self.parent:
            return self.parent.lookup_class(name)
        return None

    def define_interface(self, name: str, iface: InterfaceDef):
        self.interfaces[name] = iface

    def lookup_interface(self, name: str) -> Optional[InterfaceDef]:
        if name in self.interfaces:
            return self.interfaces[name]
        if self.parent:
            return self.parent.lookup_interface(name)
        return None

    def resolve_type_name(self, name: str) -> Optional[EPLType]:
        """Resolve a type name to an EPLType — checks primitives, aliases, classes, interfaces."""
        if name in PRIMITIVE_MAP:
            return PRIMITIVE_MAP[name]
        if name in self.type_aliases:
            return self.type_aliases[name]
        if name in self.classes:
            return self.classes[name]
        if name in self.interfaces:
            iface = self.interfaces[name]
            return EPLType(TypeKind.INTERFACE, name)
        if name in self.generic_vars:
            return self.generic_vars[name]
        if self.parent:
            return self.parent.resolve_type_name(name)
        return None

    def child(self, name: str = "local") -> 'TypeScope':
        return TypeScope(parent=self, name=name)


# ═══════════════════════════════════════════════════════════
#  Type Compatibility / Subtyping
# ═══════════════════════════════════════════════════════════

def is_assignable(target: EPLType, source: EPLType) -> bool:
    """Check if `source` type can be assigned to `target` type (target := source)."""
    if target is None or source is None:
        return True  # unknown types always pass
    if target == source:
        return True
    if target.kind == TypeKind.ANY or source.kind == TypeKind.ANY:
        return True
    if source.kind == TypeKind.NEVER:
        return True  # never is assignable to anything

    # Integer → decimal promotion
    if target == T_DECIMAL and source == T_INTEGER:
        return True

    # Optional: T? accepts T or nothing
    if target.kind == TypeKind.OPTIONAL:
        inner = target.params[0] if target.params else T_ANY
        return source == T_NOTHING or is_assignable(inner, source)

    # Union: target is A | B, source must match one member
    if target.kind == TypeKind.UNION:
        return any(is_assignable(m, source) for m in target.union_members)

    # Source is union: all members must be assignable to target
    if source.kind == TypeKind.UNION:
        return all(is_assignable(target, m) for m in source.union_members)

    # List<T> compatibility
    if target.kind == TypeKind.LIST and source.kind == TypeKind.LIST:
        t_inner = target.params[0] if target.params else T_ANY
        s_inner = source.params[0] if source.params else T_ANY
        return is_assignable(t_inner, s_inner)

    # Map<K,V> compatibility
    if target.kind == TypeKind.MAP and source.kind == TypeKind.MAP:
        t_k = target.params[0] if len(target.params) > 0 else T_ANY
        t_v = target.params[1] if len(target.params) > 1 else T_ANY
        s_k = source.params[0] if len(source.params) > 0 else T_ANY
        s_v = source.params[1] if len(source.params) > 1 else T_ANY
        return is_assignable(t_k, s_k) and is_assignable(t_v, s_v)

    # Class inheritance
    if target.kind == TypeKind.CLASS and source.kind == TypeKind.CLASS:
        # Check if source is a subclass — requires type environment context
        # For now, names must match (structural typing for interfaces handles the rest)
        return target.name == source.name

    # Interface structural typing: check that source has all required methods
    if target.kind == TypeKind.INTERFACE and source.kind == TypeKind.CLASS:
        for method_name, required_sig in target.methods.items():
            if method_name not in source.methods:
                return False
        return True

    return False


def infer_type_from_value(value) -> EPLType:
    """Infer EPL type from a Python runtime value."""
    if isinstance(value, bool):
        return T_BOOLEAN
    if isinstance(value, int):
        return T_INTEGER
    if isinstance(value, float):
        return T_DECIMAL
    if isinstance(value, str):
        return T_TEXT
    if isinstance(value, list):
        if not value:
            return make_list_type(T_ANY)
        elem_types = {infer_type_from_value(v) for v in value}
        if len(elem_types) == 1:
            return make_list_type(elem_types.pop())
        return make_list_type(T_ANY)
    if value is None:
        return T_NOTHING
    return T_ANY


# ═══════════════════════════════════════════════════════════
#  Type Checker — Static Analysis Pass
# ═══════════════════════════════════════════════════════════

@dataclass
class TypeDiagnostic:
    """A type error or warning found during checking."""
    level: str        # "error", "warning", "info"
    message: str
    line: int = 0
    column: int = 0

    def __repr__(self):
        return f"[{self.level.upper()}] line {self.line}: {self.message}"


class TypeChecker:
    """
    Static type checker for EPL programs.
    Runs as a pass over the AST before interpretation/compilation.

    Usage:
        checker = TypeChecker()
        diagnostics = checker.check(program_ast)
        for d in diagnostics:
            print(d)
    """

    def __init__(self, strict: bool = False):
        self.strict = strict       # strict mode requires all annotations
        self.scope = TypeScope(name="global")
        self.diagnostics: List[TypeDiagnostic] = []
        self._current_return_type: Optional[EPLType] = None  # expected return type of current function
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in function signatures."""
        builtins = {
            'length': FunctionType((T_ANY,), ('value',), T_INTEGER),
            'type_of': FunctionType((T_ANY,), ('value',), T_TEXT),
            'to_integer': FunctionType((T_ANY,), ('value',), T_INTEGER),
            'to_decimal': FunctionType((T_ANY,), ('value',), T_DECIMAL),
            'to_text': FunctionType((T_ANY,), ('value',), T_TEXT),
            'to_boolean': FunctionType((T_ANY,), ('value',), T_BOOLEAN),
            'absolute': FunctionType((T_NUMBER,), ('value',), T_NUMBER),
            'round': FunctionType((T_DECIMAL,), ('value',), T_INTEGER),
            'max': FunctionType((T_NUMBER, T_NUMBER), ('a', 'b'), T_NUMBER),
            'min': FunctionType((T_NUMBER, T_NUMBER), ('a', 'b'), T_NUMBER),
            'sqrt': FunctionType((T_NUMBER,), ('value',), T_DECIMAL),
            'power': FunctionType((T_NUMBER, T_NUMBER), ('base', 'exp'), T_NUMBER),
            'floor': FunctionType((T_DECIMAL,), ('value',), T_INTEGER),
            'ceil': FunctionType((T_DECIMAL,), ('value',), T_INTEGER),
            'range': FunctionType((T_INTEGER, T_INTEGER), ('start', 'end'), make_list_type(T_INTEGER)),
            'sum': FunctionType((make_list_type(T_NUMBER),), ('values',), T_NUMBER),
            'sorted': FunctionType((make_list_type(T_ANY),), ('values',), make_list_type(T_ANY)),
            'reversed': FunctionType((make_list_type(T_ANY),), ('values',), make_list_type(T_ANY)),
            'print': FunctionType((T_ANY,), ('value',), T_NOTHING),
            'json_parse': FunctionType((T_TEXT,), ('text',), T_ANY),
            'json_stringify': FunctionType((T_ANY,), ('value',), T_TEXT),
            'random': FunctionType((), (), T_DECIMAL),
        }
        for name, sig in builtins.items():
            self.scope.define_function(name, sig)

    def check(self, program) -> List[TypeDiagnostic]:
        """Run type checking on a full program AST. Returns list of diagnostics."""
        from epl import ast_nodes as ast
        self.diagnostics = []
        if isinstance(program, ast.Program):
            self._check_body(program.statements, self.scope)
        return self.diagnostics

    def _error(self, msg: str, line: int = 0):
        self.diagnostics.append(TypeDiagnostic("error", msg, line))

    def _warning(self, msg: str, line: int = 0):
        self.diagnostics.append(TypeDiagnostic("warning", msg, line))

    def _check_body(self, stmts, scope: TypeScope):
        """Check a list of statements, warning on unreachable code after return/break/continue."""
        from epl import ast_nodes as ast
        terminated = False
        for stmt in stmts:
            if stmt is None:
                continue
            if terminated:
                self._warning("Unreachable code.", getattr(stmt, 'line', 0))
                break
            self._check_statement(stmt, scope)
            if isinstance(stmt, (ast.ReturnStatement, ast.BreakStatement,
                                 ast.ContinueStatement, ast.ExitStatement)):
                terminated = True

    def _check_statement(self, node, scope: TypeScope):
        from epl import ast_nodes as ast
        if node is None:
            return

        if isinstance(node, ast.VarDeclaration):
            inferred = self._check_expr(node.value, scope) if node.value else T_ANY
            declared = None
            if node.var_type:
                declared = scope.resolve_type_name(node.var_type)
                if declared is None:
                    self._error(f'Unknown type "{node.var_type}".', getattr(node, 'line', 0))
                    declared = T_ANY
                if inferred and declared and not is_assignable(declared, inferred):
                    self._error(
                        f'Cannot assign {inferred} to variable "{node.name}" of type {declared}.',
                        getattr(node, 'line', 0)
                    )
            final_type = declared or inferred or T_ANY
            scope.define_var(node.name, final_type)

        elif isinstance(node, ast.VarAssignment):
            existing = scope.lookup_var(node.name)
            new_type = self._check_expr(node.value, scope) if node.value else T_ANY
            if existing and new_type and not is_assignable(existing, new_type):
                self._error(
                    f'Cannot assign {new_type} to variable "{node.name}" of type {existing}.',
                    getattr(node, 'line', 0)
                )

        elif isinstance(node, ast.ConstDeclaration):
            val_type = self._check_expr(node.value, scope) if node.value else T_ANY
            scope.define_var(node.name, val_type)

        elif isinstance(node, ast.PrintStatement):
            self._check_expr(node.expression, scope)

        elif isinstance(node, ast.IfStatement):
            self._check_expr(node.condition, scope)
            child = scope.child("if_true")
            self._check_body(node.true_body or [], child)
            if node.false_body:
                child2 = scope.child("if_false")
                self._check_body(node.false_body, child2)
            for elif_cond, elif_body in getattr(node, 'elif_clauses', []):
                self._check_expr(elif_cond, scope)
                child3 = scope.child("elif")
                self._check_body(elif_body, child3)

        elif isinstance(node, ast.WhileLoop):
            self._check_expr(node.condition, scope)
            child = scope.child("while")
            self._check_body(node.body, child)

        elif isinstance(node, ast.ForEachLoop):
            iter_type = self._check_expr(node.iterable, scope) if hasattr(node, 'iterable') else T_ANY
            child = scope.child("foreach")
            if iter_type and iter_type.kind == TypeKind.LIST and iter_type.params:
                child.define_var(node.var_name, iter_type.params[0])
            else:
                child.define_var(node.var_name, T_ANY)
            self._check_body(node.body, child)

        elif isinstance(node, ast.ForRange):
            child = scope.child("for_range")
            child.define_var(node.var_name, T_INTEGER)
            self._check_expr(node.start, scope)
            self._check_expr(node.end, scope)
            if hasattr(node, 'step_val') and node.step_val:
                self._check_expr(node.step_val, scope)
            self._check_body(node.body, child)

        elif isinstance(node, ast.RepeatLoop):
            self._check_expr(node.count, scope)
            child = scope.child("repeat")
            self._check_body(node.body, child)

        elif isinstance(node, ast.FunctionDef):
            self._check_function_def(node, scope)

        elif isinstance(node, ast.AsyncFunctionDef):
            self._check_function_def(node, scope, is_async=True)

        elif isinstance(node, ast.ClassDef):
            self._check_class_def(node, scope)

        elif isinstance(node, ast.TryCatch):
            child_try = scope.child("try")
            self._check_body(node.try_body or [], child_try)
            if node.catch_body:
                child_catch = scope.child("catch")
                if hasattr(node, 'error_var') and node.error_var:
                    child_catch.define_var(node.error_var, T_TEXT)
                self._check_body(node.catch_body, child_catch)
            if hasattr(node, 'finally_body') and node.finally_body:
                child_finally = scope.child("finally")
                self._check_body(node.finally_body, child_finally)

        elif isinstance(node, ast.ReturnStatement):
            if hasattr(node, 'value') and node.value:
                ret_type = self._check_expr(node.value, scope)
                if (self._current_return_type and ret_type
                        and self._current_return_type != T_ANY
                        and not is_assignable(self._current_return_type, ret_type)):
                    self._error(
                        f'Return type {ret_type} is not compatible with declared return type {self._current_return_type}.',
                        getattr(node, 'line', 0)
                    )

        elif isinstance(node, ast.ThrowStatement):
            if hasattr(node, 'expression'):
                self._check_expr(node.expression, scope)

        elif isinstance(node, ast.FunctionCall):
            self._check_function_call(node, scope)

        elif isinstance(node, ast.MatchStatement):
            self._check_expr(node.expression, scope)
            for clause in node.clauses:
                child = scope.child("when")
                self._check_body(clause.body if hasattr(clause, 'body') else [], child)

        elif isinstance(node, ast.AugmentedAssignment):
            var_type = scope.lookup_var(node.name)
            val_type = self._check_expr(node.value, scope)

        elif isinstance(node, (ast.BreakStatement, ast.ContinueStatement,
                                ast.ExitStatement, ast.WaitStatement)):
            pass  # no type checking needed

        elif isinstance(node, (ast.FileWrite, ast.FileAppend)):
            if hasattr(node, 'content'):
                self._check_expr(node.content, scope)

        elif isinstance(node, ast.ImportStatement):
            pass  # imports are resolved at runtime

        # Catch-all: try to check expressions in node
        elif isinstance(node, ast.IndexSet):
            self._check_expr(node.obj, scope)
            self._check_expr(node.index, scope)
            self._check_expr(node.value, scope)

        elif isinstance(node, ast.PropertySet):
            self._check_expr(node.value, scope)

    def _check_function_def(self, node, scope: TypeScope, is_async: bool = False):
        """Check a function definition and register its signature."""
        from epl import ast_nodes as ast

        param_types = []
        param_names = []
        for p in node.params:
            if isinstance(p, tuple):
                pname = p[0]
                ptype_name = p[1] if len(p) > 1 else None
                default = p[2] if len(p) > 2 else None
            else:
                pname = p
                ptype_name = None
                default = None
            param_names.append(pname)
            if ptype_name:
                resolved = scope.resolve_type_name(ptype_name)
                param_types.append(resolved or T_ANY)
            else:
                param_types.append(T_ANY)

        ret_type = None
        if hasattr(node, 'return_type') and node.return_type:
            ret_type = scope.resolve_type_name(node.return_type)
        if ret_type is None:
            ret_type = T_ANY

        sig = FunctionType(
            param_types=tuple(param_types),
            param_names=tuple(param_names),
            return_type=ret_type,
            is_async=is_async,
        )
        scope.define_function(node.name, sig)

        # Check function body
        child = scope.child(f"fn:{node.name}")
        for pname, ptype in zip(param_names, param_types):
            child.define_var(pname, ptype)
        saved_return_type = self._current_return_type
        self._current_return_type = ret_type
        self._check_body(node.body, child)
        self._current_return_type = saved_return_type

    def _check_class_def(self, node, scope: TypeScope):
        """Check a class definition and register it."""
        from epl import ast_nodes as ast_mod
        fields = {}
        methods = {}
        method_nodes = []

        # ClassDef.body is a list of statements (FunctionDef, VarDeclaration, etc.)
        for item in getattr(node, 'body', []):
            if isinstance(item, ast_mod.FunctionDef):
                param_types = []
                param_names = []
                for p in item.params:
                    if isinstance(p, tuple):
                        param_names.append(p[0])
                        param_types.append(T_ANY)
                    else:
                        param_names.append(p)
                        param_types.append(T_ANY)
                methods[item.name] = FunctionType(
                    param_types=tuple(param_types),
                    param_names=tuple(param_names),
                    return_type=T_ANY,
                )
                method_nodes.append(item)
            elif isinstance(item, ast_mod.VarDeclaration):
                fields[item.name] = T_ANY

        # Also check old-style 'defaults' dict if present
        for attr_name in getattr(node, 'defaults', {}).keys():
            if attr_name not in fields:
                fields[attr_name] = T_ANY

        class_type = EPLType(
            TypeKind.CLASS, node.name,
            fields=fields, methods=methods
        )
        scope.define_class(node.name, class_type)

        # Check method bodies
        for method_node in method_nodes:
            if method_node.body:
                child = scope.child(f"method:{node.name}.{method_node.name}")
                child.define_var('self', class_type)
                for p in method_node.params:
                    pname = p[0] if isinstance(p, tuple) else p
                    child.define_var(pname, T_ANY)
                self._check_body(method_node.body, child)

    def _check_function_call(self, node, scope: TypeScope) -> Optional[EPLType]:
        """Check a function call and return the return type."""
        sig = scope.lookup_function(node.name)
        if sig:
            n_args = len(node.arguments) if node.arguments else 0
            n_params = len(sig.param_types)
            if n_args > n_params and n_params > 0:
                self._warning(
                    f'Too many arguments to "{node.name}()": expected {n_params}, got {n_args}.',
                    getattr(node, 'line', 0)
                )
            if node.arguments:
                for i, arg in enumerate(node.arguments):
                    arg_type = self._check_expr(arg, scope)
                    if i < len(sig.param_types):
                        expected = sig.param_types[i]
                        if arg_type and not is_assignable(expected, arg_type):
                            self._warning(
                                f'Argument {i+1} to "{node.name}()": expected {expected}, got {arg_type}.',
                                getattr(node, 'line', 0)
                            )
        if sig:
            return sig.return_type
        # Unknown function — check args anyway
        if node.arguments:
            for arg in node.arguments:
                self._check_expr(arg, scope)
        return T_ANY

    def _check_expr(self, node, scope: TypeScope) -> Optional[EPLType]:
        """Check an expression and return its inferred type."""
        from epl import ast_nodes as ast
        if node is None:
            return T_NOTHING

        if isinstance(node, ast.Literal):
            val = node.value
            if isinstance(val, bool):
                return T_BOOLEAN
            if isinstance(val, int):
                return T_INTEGER
            if isinstance(val, float):
                return T_DECIMAL
            if isinstance(val, str):
                return T_TEXT
            if val is None:
                return T_NOTHING
            return T_ANY

        if isinstance(node, ast.Identifier):
            t = scope.lookup_var(node.name)
            if t is None and self.strict:
                self._error(f'Variable "{node.name}" used before declaration.', getattr(node, 'line', 0))
            return t or T_ANY

        if isinstance(node, ast.BinaryOp):
            left = self._check_expr(node.left, scope)
            right = self._check_expr(node.right, scope)
            if node.operator in ('+', '-', '*', '/', '%', '//', '**'):
                if left == T_TEXT or right == T_TEXT:
                    if node.operator == '+':
                        return T_TEXT
                return T_NUMBER if (left == T_DECIMAL or right == T_DECIMAL) else T_INTEGER
            if node.operator in ('>', '<', '>=', '<=', '==', '!=', 'and', 'or',
                                  'is greater than', 'is less than', 'is equal to',
                                  'is not equal to', 'is greater than or equal to',
                                  'is less than or equal to'):
                return T_BOOLEAN
            return T_ANY

        if isinstance(node, ast.UnaryOp):
            operand_type = self._check_expr(node.operand, scope)
            if node.operator == 'not':
                return T_BOOLEAN
            if node.operator == '-':
                return operand_type
            return T_ANY

        if isinstance(node, ast.ListLiteral):
            if not node.elements:
                return make_list_type(T_ANY)
            elem_types = [self._check_expr(e, scope) for e in node.elements]
            unique = set(t for t in elem_types if t is not None)
            if len(unique) == 1:
                return make_list_type(unique.pop())
            return make_list_type(T_ANY)

        if isinstance(node, ast.DictLiteral):
            return make_map_type(T_TEXT, T_ANY)

        if isinstance(node, ast.FunctionCall):
            return self._check_function_call(node, scope)

        if isinstance(node, ast.MethodCall):
            obj_type = self._check_expr(node.object, scope) if hasattr(node, 'object') else T_ANY
            for arg in (node.arguments or []):
                self._check_expr(arg, scope)
            # Infer return type from known methods
            method = node.method_name if hasattr(node, 'method_name') else ''
            if obj_type and obj_type.kind == TypeKind.LIST:
                if method in ('map', 'filter'):
                    return obj_type
                if method in ('length', 'index_of', 'count'):
                    return T_INTEGER
                if method in ('contains', 'every', 'some'):
                    return T_BOOLEAN
                if method in ('find',):
                    return obj_type.params[0] if obj_type.params else T_ANY
                if method in ('reduce', 'sum'):
                    return T_ANY
                if method == 'join':
                    return T_TEXT
            if obj_type == T_TEXT:
                if method in ('upper', 'lower', 'trim', 'replace', 'reverse', 'repeat',
                               'substr', 'substring', 'pad_left', 'pad_right', 'char_at'):
                    return T_TEXT
                if method in ('length', 'find', 'index_of', 'count'):
                    return T_INTEGER
                if method in ('contains', 'starts_with', 'ends_with', 'is_empty',
                               'is_number', 'is_alpha'):
                    return T_BOOLEAN
                if method == 'split':
                    return make_list_type(T_TEXT)
                if method == 'to_list':
                    return make_list_type(T_TEXT)
            return T_ANY

        if isinstance(node, ast.PropertyAccess):
            self._check_expr(node.object, scope)
            return T_ANY

        if isinstance(node, ast.IndexAccess):
            obj_type = self._check_expr(node.obj, scope) if hasattr(node, 'obj') else T_ANY
            self._check_expr(node.index, scope) if hasattr(node, 'index') else None
            if obj_type and obj_type.kind == TypeKind.LIST and obj_type.params:
                return obj_type.params[0]
            if obj_type == T_TEXT:
                return T_TEXT
            if obj_type and obj_type.kind == TypeKind.MAP and len(obj_type.params) > 1:
                return obj_type.params[1]
            return T_ANY

        if isinstance(node, ast.SliceAccess):
            return self._check_expr(node.obj, scope) if hasattr(node, 'obj') else T_ANY

        if isinstance(node, ast.LambdaExpression):
            return T_ANY  # lambda type inference is complex

        if isinstance(node, ast.TernaryExpression):
            self._check_expr(node.condition, scope)
            t_type = self._check_expr(node.true_expr, scope)
            f_type = self._check_expr(node.false_expr, scope)
            if t_type == f_type:
                return t_type
            return make_union_type(t_type, f_type) if t_type and f_type else T_ANY

        if isinstance(node, ast.NewInstance):
            class_type = scope.lookup_class(node.class_name)
            return class_type or T_ANY

        if isinstance(node, ast.AwaitExpression):
            return self._check_expr(node.expression, scope)

        if isinstance(node, ast.FileRead):
            return T_TEXT

        if isinstance(node, ast.InputStatement):
            return T_TEXT

        return T_ANY

    def has_errors(self) -> bool:
        return any(d.level == "error" for d in self.diagnostics)

    def format_diagnostics(self) -> str:
        lines = []
        for d in sorted(self.diagnostics, key=lambda x: x.line):
            prefix = "ERROR" if d.level == "error" else "WARNING" if d.level == "warning" else "INFO"
            lines.append(f"  [{prefix}] line {d.line}: {d.message}")
        return '\n'.join(lines)
