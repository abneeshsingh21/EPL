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


def inline_stdlib_imports(program, entry_path=None):
    """Return a Program with used stdlib definitions inlined ahead of user code.

    Non-destructive: builds a new statement list. Only plain imports of bundled
    stdlib modules are resolved; everything else (aliased imports, local files,
    packages, native modules) is left in place for the target to handle or report.
    """
    stmts = program.statements

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

    if not imported_any or not available:
        return program

    # Reachability: seed with names used in the user's own code, then transitively
    # pull in stdlib defs those (and their dependencies) reference.
    user_stmts = [s for s in stmts if not isinstance(s, ast.ImportStatement)]
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
        # Imports present but nothing used — drop them so the target doesn't choke.
        return ast.Program(user_stmts)

    # Order callee-before-caller: targets that lower top-level functions to local
    # `fun`s (Android) require a definition to precede its first use. Constants
    # sort ahead of everything (functions may close over them). Cyclic/mutually
    # recursive defs fall back to insertion order — those targets tolerate it.
    ordered = _topo_order(needed, available)

    return ast.Program(ordered + user_stmts)


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
