"""Inline used EPL-stdlib definitions into a Program AST for native codegen.

The interpreter and VM auto-resolve `Import "string"` at runtime by executing the
matching ``epl/stdlib/<name>.epl`` module. The native transpilers (Kotlin/Android,
Swift, …) have no runtime import loader, so those imports were silently dropped and
programs that called stdlib helpers (``word_count``, ``repeat_string``, …) emitted
unresolved references.

This module resolves plain ``Import "<stdlib>"`` statements, parses the referenced
pure-EPL modules, and splices the *reachable* function/constant definitions into the
program so the transpiler emits them alongside the user's own code. Reachability
keeps output minimal and — crucially — avoids inlining stdlib helpers that lean on
builtins a given target can't provide, unless the program actually calls them.

Scope: plain (non-aliased) imports of bundled stdlib modules whose bodies are pure
definitions. Aliased imports (``Import "math" as Math``) use a namespace mechanism the
native targets don't model yet and are left untouched.
"""

import os

from epl import ast_nodes as ast

_STDLIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stdlib')


def _module_path(name):
    """Absolute path of a bundled stdlib module, or None if it isn't one."""
    if not name or name.endswith('.epl'):
        name = name[:-4] if name.endswith('.epl') else name
    path = os.path.join(_STDLIB_DIR, name + '.epl')
    return path if os.path.isfile(path) else None


def _parse(source):
    from epl.lexer import Lexer
    from epl.parser import Parser

    return Parser(Lexer(source).tokenize()).parse()


def _def_name(node):
    """Name a top-level definition binds, or None if it isn't a definition.

    Besides functions and constants, module-level ``Create`` state (a
    ``VarDeclaration``) is treated as a definition: stdlib modules such as
    ``testing`` keep mutable counters at module scope that their functions close
    over, so the native targets must see that shared state, not re-declare it as
    a per-function local.
    """
    if isinstance(node, (ast.FunctionDef, ast.ConstDeclaration, ast.VarDeclaration)):
        return node.name
    return None


def _walk(node):
    """Yield every AST node in the subtree (descending into list attributes)."""
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
        return
    if not hasattr(node, '__dict__'):
        return
    yield node
    for value in vars(node).values():
        if isinstance(value, list):
            for item in value:
                if hasattr(item, '__dict__'):
                    yield from _walk(item)
        elif hasattr(value, '__dict__'):
            yield from _walk(value)


def _referenced_names(node):
    """Free function/identifier names referenced anywhere in a subtree."""
    names = set()
    for n in _walk(node):
        if isinstance(n, ast.FunctionCall):
            names.add(n.name)
        elif isinstance(n, ast.Identifier):
            names.add(n.name)
        elif isinstance(n, ast.VarAssignment):
            # A write-only `Set <global> to ...` still needs the shared module
            # state pulled in, even when no read makes it appear as an Identifier.
            names.add(n.name)
    return names


def _mangled(alias, member):
    """Collision-safe top-level name for a member imported under a namespace alias."""
    return f'{alias}__{member}'


def _mangle_member_refs(node, rename):
    """In place: rewrite bare references to sibling module members into their
    mangled names, so a flattened namespace module stays internally consistent."""
    for n in _walk(node):
        if isinstance(n, (ast.FunctionCall, ast.Identifier, ast.VarAssignment)):
            if getattr(n, 'name', None) in rename:
                n.name = rename[n.name]


def _rewrite_ma(node, alias_member_map):
    """Return a replacement for a `Namespace::member` node, or None if it isn't one
    we resolved. A member access becomes an Identifier; a call becomes a FunctionCall."""
    if isinstance(node, ast.ModuleAccess):
        key = (node.module_name, node.member_name)
        name = alias_member_map.get(key)
        if name is not None:
            line = getattr(node, 'line', 0)
            if node.arguments is None:
                return ast.Identifier(name, line)
            return ast.FunctionCall(name, node.arguments, line)
    return None


def _rewrite_ma_tree(node, alias_member_map):
    """In place: replace every `Namespace::member` node in a subtree with its
    flattened call/identifier form, recursing into replacements for nested access."""
    if not hasattr(node, '__dict__'):
        return
    for attr, value in list(vars(node).items()):
        if isinstance(value, list):
            for i, item in enumerate(value):
                if not hasattr(item, '__dict__'):
                    continue
                repl = _rewrite_ma(item, alias_member_map)
                if repl is not None:
                    value[i] = repl
                    _rewrite_ma_tree(repl, alias_member_map)
                else:
                    _rewrite_ma_tree(item, alias_member_map)
        elif hasattr(value, '__dict__'):
            repl = _rewrite_ma(value, alias_member_map)
            if repl is not None:
                setattr(node, attr, repl)
                _rewrite_ma_tree(repl, alias_member_map)
            else:
                _rewrite_ma_tree(value, alias_member_map)


def _resolve_aliased_imports(stmts):
    """Flatten ``Import "<mod>" as <Alias>`` into mangled top-level definitions.

    Native targets have no namespace model, so a `Alias::member` reference is
    lowered to a plain top-level def uniquely named per alias (collision-safe
    across modules). Returns ``(ordered_defs, alias_member_map)`` where
    ``alias_member_map`` maps ``(Alias, member)`` to the mangled name and
    ``ordered_defs`` are the reachable, renamed defs in dependency order.
    """
    imports = [
        s
        for s in stmts
        if isinstance(s, ast.ImportStatement) and s.alias and _module_path(s.filepath)
    ]
    if not imports:
        return [], {}

    user_stmts = [s for s in stmts if not isinstance(s, ast.ImportStatement)]
    accessed = {}  # alias -> {member names used in user code}
    for n in _walk(user_stmts):
        if isinstance(n, ast.ModuleAccess):
            accessed.setdefault(n.module_name, set()).add(n.member_name)

    alias_member_map = {}
    all_defs = {}  # mangled name -> renamed def node
    for imp in imports:
        alias = imp.alias
        used = accessed.get(alias)
        if not used:
            continue  # imported but never referenced
        try:
            with open(_module_path(imp.filepath), 'r', encoding='utf-8') as f:
                mod = _parse(f.read())
        except Exception:
            continue
        members = {}  # member name -> def node
        for node in mod.statements:
            nm = _def_name(node)
            if nm and nm not in members:
                members[nm] = node
        rename = {m: _mangled(alias, m) for m in members}
        # Reachability within the module, seeded by the members user code touches.
        needed = set()
        frontier = set(used) & set(members)
        while frontier:
            m = frontier.pop()
            if m in needed:
                continue
            needed.add(m)
            for ref in _referenced_names(members[m]):
                if ref in members and ref not in needed:
                    frontier.add(ref)
        for m in needed:
            node = members[m]
            _mangle_member_refs(node, rename)
            node.name = rename[m]
            all_defs[rename[m]] = node
            alias_member_map[(alias, m)] = rename[m]

    ordered = _topo_order(set(all_defs), all_defs) if all_defs else []
    return ordered, alias_member_map


def inline_stdlib_imports(program, entry_path=None):
    """Return a Program with used stdlib definitions inlined ahead of user code.

    Non-destructive: builds a new statement list. Plain imports of bundled stdlib
    modules are flattened by bare name; aliased imports (``Import "math" as Math``)
    are flattened under mangled per-alias names with their ``Alias::member`` uses
    rewritten to plain calls. Everything else (local files, packages, native
    modules) is left in place for the target to handle or report.
    """
    stmts = program.statements

    # Aliased imports: flatten `Import "<mod>" as <Alias>` into mangled top-level
    # defs and learn the `Alias::member` -> mangled-name mapping.
    aliased_ordered, alias_member_map = _resolve_aliased_imports(stmts)

    # Collect stdlib definitions available via plain imports, keyed by name.
    available = {}  # name -> definition node
    imported_any = False
    for s in stmts:
        if not isinstance(s, ast.ImportStatement) or s.alias:
            continue
        path = _module_path(s.filepath)
        if not path:
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                mod = _parse(f.read())
        except Exception:
            continue
        for node in mod.statements:
            name = _def_name(node)
            if name and name not in available:
                available[name] = node
        imported_any = True

    # User code minus import statements; rewrite namespaced access in place so the
    # target sees plain calls/identifiers against the flattened aliased defs.
    user_stmts = [s for s in stmts if not isinstance(s, ast.ImportStatement)]
    if alias_member_map:
        for i, s in enumerate(user_stmts):
            repl = _rewrite_ma(s, alias_member_map)
            if repl is not None:
                user_stmts[i] = repl
            else:
                _rewrite_ma_tree(s, alias_member_map)

    if not imported_any or not available:
        # No plain stdlib defs to inline, but aliased flattening may still have
        # rewritten the program — return that (with imports dropped) if so.
        if aliased_ordered or alias_member_map:
            return ast.Program(aliased_ordered + user_stmts)
        return program

    # Reachability: seed with names used in the user's own code, then transitively
    # pull in stdlib defs those (and their dependencies) reference. (Names rewritten
    # to mangled aliased calls aren't in `available`, so they don't seed here.)
    needed = set()
    frontier = set()
    for name in _referenced_names(user_stmts):
        if name in available:
            frontier.add(name)
    while frontier:
        name = frontier.pop()
        if name in needed:
            continue
        needed.add(name)
        for ref in _referenced_names(available[name]):
            if ref in available and ref not in needed:
                frontier.add(ref)

    if not needed:
        # Plain imports present but nothing used — drop them so the target doesn't
        # choke; keep any aliased defs that were flattened.
        return ast.Program(aliased_ordered + user_stmts)

    # Order callee-before-caller: targets that lower top-level functions to local
    # `fun`s (Android) require a definition to precede its first use. Constants
    # sort ahead of everything (functions may close over them). Cyclic/mutually
    # recursive defs fall back to insertion order — those targets tolerate it.
    ordered = _topo_order(needed, available)

    return ast.Program(aliased_ordered + ordered + user_stmts)


def _topo_order(needed, available):
    """Definitions in dependency order: a def appears after the stdlib defs it calls."""
    # Value bindings (constants + module-level mutable state) seed first so they
    # precede the functions that close over them; targets that lower functions to
    # local `fun`s require the enclosing var to be declared earlier lexically.
    consts = [
        n for n in needed if isinstance(available[n], (ast.ConstDeclaration, ast.VarDeclaration))
    ]
    result = []
    visiting = set()
    placed = set()

    def visit(name):
        if name in placed or name in visiting:
            return
        visiting.add(name)
        for ref in _referenced_names(available[name]):
            if ref in needed and ref != name:
                visit(ref)
        visiting.discard(name)
        placed.add(name)
        result.append(available[name])

    for name in consts:
        visit(name)
    for name in needed:
        visit(name)
    return result
