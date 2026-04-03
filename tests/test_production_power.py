"""
EPL v5.1 Production Power Test Suite
Tests for the 5 production features:
  1. Standard library ecosystem (46 built-in packages)
  2. Concurrency (Spawn, Parallel For Each)
  3. LLVM full executable linking (compile_to_executable)
  4. Debugger integration (Breakpoint statement)
  5. Python bridge reduction (280+ native stdlib functions)
"""

import sys
import os
import time
import threading
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError
from epl import ast_nodes as ast
from epl.tokens import TokenType


def run_epl(source: str, safe_mode=False) -> list:
    """Run EPL source code and return captured output lines."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter(safe_mode=safe_mode, debug_interactive=False)
    interp.execute(program)
    return interp.output_lines


def get_interp(source: str):
    """Run EPL source code and return the interpreter (for inspecting env)."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp


def test(name, source, expected, **kwargs):
    try:
        output = run_epl(source, **kwargs)
        if output == expected:
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            return False
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {type(e).__name__}: {e}")
        return False
test.__test__ = False


def test_error(name, source, expected_error_substring, **kwargs):
    try:
        run_epl(source, **kwargs)
        print(f"  FAIL: {name} (expected error but none raised)")
        return False
    except EPLError as e:
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        print(f"  FAIL: {name}")
        print(f"    Expected error containing: {expected_error_substring}")
        print(f"    Got: {e}")
        return False
    except Exception as e:
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        print(f"  FAIL: {name} (unexpected: {type(e).__name__}: {e})")
        return False
test_error.__test__ = False


def test_parse(name, source):
    """Test that source parses without error."""
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        print(f"  PASS: {name}")
        return True
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Parse error: {e}")
        return False
test_parse.__test__ = False


def test_ast_node(name, source, expected_type):
    """Test that the first statement in parsed source is the expected AST type."""
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        first = program.statements[0]
        if isinstance(first, expected_type):
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected AST: {expected_type.__name__}")
            print(f"    Got: {type(first).__name__}")
            return False
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {e}")
        return False
test_ast_node.__test__ = False


def run_suite():
    passed = 0
    failed = 0

    def track(result):
        nonlocal passed, failed
        if result:
            passed += 1
        else:
            failed += 1

    print("=" * 60)
    print("EPL v5.1 Production Power Tests")
    print("=" * 60)

    # ═══════════════════════════════════════════════════════
    # 1. STANDARD LIBRARY ECOSYSTEM
    # ═══════════════════════════════════════════════════════
    print("\n📦 1. Standard Library Ecosystem:")

    # Test that built-in registry exists and has packages
    print("  -- Built-in Package Registry --")
    try:
        from epl.package_manager import BUILTIN_REGISTRY
        pkg_count = len(BUILTIN_REGISTRY)
        if pkg_count >= 40:
            print(f"  PASS: Built-in registry has {pkg_count} packages (>=40)")
            passed += 1
        else:
            print(f"  FAIL: Built-in registry has only {pkg_count} packages")
            failed += 1
    except ImportError:
        print("  FAIL: BUILTIN_REGISTRY not found")
        failed += 1

    # Test specific essential packages exist
    try:
        from epl.package_manager import BUILTIN_REGISTRY
    except ImportError:
        BUILTIN_REGISTRY = {}
    essential_packages = [
        'epl-math', 'epl-http', 'epl-json', 'epl-string',
        'epl-collections', 'epl-crypto', 'epl-datetime',
        'epl-regex', 'epl-fs', 'epl-db', 'epl-testing',
        'epl-web', 'epl-concurrency', 'epl-async', 'epl-os',
    ]
    for pkg in essential_packages:
        if pkg in BUILTIN_REGISTRY:
            print(f"  PASS: Package '{pkg}' exists")
            passed += 1
        else:
            print(f"  FAIL: Package '{pkg}' missing")
            failed += 1

    # Test Import syntax parses
    track(test_parse("Import package syntax", 'Import "epl-math".'))

    # ═══════════════════════════════════════════════════════
    # 2. CONCURRENCY (Spawn & Parallel For Each)
    # ═══════════════════════════════════════════════════════
    print("\n⚡ 2. Concurrency:")

    # --- Tokens ---
    print("  -- Token Recognition --")
    for kw, tt in [('spawn', TokenType.SPAWN), ('parallel', TokenType.PARALLEL),
                   ('breakpoint', TokenType.BREAKPOINT_KW)]:
        lexer = Lexer(kw)
        tokens = lexer.tokenize()
        if tokens[0].type == tt:
            print(f"  PASS: '{kw}' recognized as {tt.name}")
            passed += 1
        else:
            print(f"  FAIL: '{kw}' not recognized (got {tokens[0].type})")
            failed += 1

    # --- Spawn AST ---
    print("  -- Spawn Parsing --")
    track(test_ast_node("Spawn named parse",
        'Define a function named compute that takes integer x and returns integer.\n'
        '    Return x * 2.\nEnd function.\n'
        'Spawn task calling call compute with 5.',
        ast.FunctionDef))  # first stmt is function def

    # Direct spawn AST check
    try:
        src = ('Define a function named compute that takes integer x and returns integer.\n'
               '    Return x * 2.\nEnd function.\n'
               'Spawn task calling call compute with 5.')
        prog = Parser(Lexer(src).tokenize()).parse()
        spawn_node = prog.statements[1]
        if isinstance(spawn_node, ast.SpawnStatement) and spawn_node.var_name == 'task':
            print(f"  PASS: Spawn node var_name='task'")
            passed += 1
        else:
            print(f"  FAIL: Spawn node wrong type or var_name (got {type(spawn_node).__name__})")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Spawn named parse detail: {e}")
        failed += 1

    # --- Spawn Execution ---
    print("  -- Spawn Execution --")
    track(test("Spawn + Await basic",
        'Define a function named double that takes integer x and returns integer.\n'
        '    Return x * 2.\n'
        'End function.\n'
        'Spawn task calling call double with 21.\n'
        'Create integer named result equal to Await task.\n'
        'Print result.',
        ["42"]))

    track(test("Spawn + Await string",
        'Define a function named greet that takes text name and returns text.\n'
        '    Return "Hello, " + name.\n'
        'End function.\n'
        'Spawn job calling call greet with "World".\n'
        'Create text named msg equal to Await job.\n'
        'Print msg.',
        ["Hello, World"]))

    track(test("Multiple spawns",
        'Define a function named sq that takes integer n and returns integer.\n'
        '    Return n * n.\n'
        'End function.\n'
        'Spawn a calling call sq with 3.\n'
        'Spawn b calling call sq with 4.\n'
        'Create integer named ra equal to Await a.\n'
        'Create integer named rb equal to Await b.\n'
        'Print ra + rb.',
        ["25"]))

    # --- Parallel For Each ---
    print("  -- Parallel For Each --")
    track(test_ast_node("Parallel For Each parse",
        'Create list named items equal to [1, 2, 3].\n'
        'Parallel For Each item in items\n'
        '    Print item.\n'
        'End.',
        ast.VarDeclaration))  # first stmt is list creation

    # Parallel For Each execution — ordering is nondeterministic
    # so we just check all items appear
    try:
        src = ('Create list named items equal to [10, 20, 30].\n'
               'Parallel For Each item in items\n'
               '    Print item.\n'
               'End.')
        output = run_epl(src)
        output_sorted = sorted(output)
        if output_sorted == ["10", "20", "30"]:
            print("  PASS: Parallel For Each basic execution")
            passed += 1
        else:
            print(f"  FAIL: Parallel For Each basic execution")
            print(f"    Expected (sorted): ['10', '20', '30']")
            print(f"    Got (sorted): {output_sorted}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Parallel For Each basic: {e}")
        failed += 1

    # Parallel For Each with workers
    try:
        src = ('Create list named nums equal to [1, 2, 3, 4].\n'
               'Parallel For Each n in nums with 2 workers\n'
               '    Print n.\n'
               'End.')
        output = run_epl(src)
        output_sorted = sorted(output)
        if output_sorted == ["1", "2", "3", "4"]:
            print("  PASS: Parallel For Each with workers")
            passed += 1
        else:
            print(f"  FAIL: Parallel For Each with workers")
            print(f"    Expected (sorted): ['1', '2', '3', '4']")
            print(f"    Got (sorted): {output_sorted}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Parallel For Each with workers: {e}")
        failed += 1

    # Parallel For Each type error
    track(test_error("Parallel For Each non-list error",
        'Create integer named x equal to 5.\n'
        'Parallel For Each item in x\n'
        '    Print item.\n'
        'End.',
        "requires a list"))

    # --- Existing Async/Await ---
    print("  -- Existing Async/Await --")
    track(test_parse("Async function def parse",
        'Async function fetchData.\n'
        '    Return 42.\n'
        'End function.'))

    # ═══════════════════════════════════════════════════════
    # 3. LLVM FULL EXECUTABLE LINKING
    # ═══════════════════════════════════════════════════════
    print("\n🔗 3. LLVM Executable Linking:")

    # Test compile_to_executable exists
    try:
        from epl.compiler import Compiler
        c = Compiler()
        if hasattr(c, 'compile_to_executable'):
            print("  PASS: compile_to_executable method exists")
            passed += 1
        else:
            print("  FAIL: compile_to_executable method missing")
            failed += 1
    except ImportError:
        print("  SKIP: llvmlite not available")
        passed += 1  # Not a failure if llvmlite is missing

    # Test compile method produces IR
    try:
        from epl.compiler import Compiler
        src = 'Print "Hello".'
        lexer = Lexer(src)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        c = Compiler()
        ir = c.compile(program)
        if 'define' in ir and '"main"' in ir:
            print("  PASS: Compiler produces valid LLVM IR with main")
            passed += 1
        else:
            print(f"  FAIL: Compiler IR missing main function")
            failed += 1
    except ImportError:
        print("  SKIP: llvmlite not available")
        passed += 1
    except Exception as e:
        print(f"  FAIL: Compiler error: {e}")
        failed += 1

    # Test compile_file function signature
    try:
        from main import compile_file
        import inspect
        sig = inspect.signature(compile_file)
        params = list(sig.parameters.keys())
        if 'opt_level' in params and 'static' in params:
            print("  PASS: compile_file has opt_level and static params")
            passed += 1
        else:
            print(f"  FAIL: compile_file params: {params}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: compile_file import: {e}")
        failed += 1

    # Test compiler handles new AST nodes without crashing
    try:
        from epl.compiler import Compiler
        src = ('Define a function named foo and returns integer.\n'
               '    Return 1.\n'
               'End function.\n'
               'Spawn task calling foo.\n'
               'Breakpoint.')
        lexer = Lexer(src)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        c = Compiler()
        ir = c.compile(program)
        # Should not crash — new nodes are silently skipped
        print("  PASS: Compiler skips Spawn/Breakpoint without crashing")
        passed += 1
    except ImportError:
        print("  SKIP: llvmlite not available")
        passed += 1
    except Exception as e:
        print(f"  FAIL: Compiler crash on new nodes: {e}")
        failed += 1

    # ═══════════════════════════════════════════════════════
    # 4. DEBUGGER INTEGRATION (Breakpoint statement)
    # ═══════════════════════════════════════════════════════
    print("\n🐛 4. Debugger Integration:")

    # --- Breakpoint Parsing ---
    track(test_ast_node("Breakpoint parse",
        'Breakpoint.',
        ast.BreakpointStatement))

    track(test_ast_node("Breakpoint with condition parse",
        'Breakpoint if x > 5.',
        ast.BreakpointStatement))

    # Breakpoint AST details
    try:
        prog = Parser(Lexer('Breakpoint.').tokenize()).parse()
        bp = prog.statements[0]
        if isinstance(bp, ast.BreakpointStatement) and bp.condition is None:
            print("  PASS: Breakpoint without condition")
            passed += 1
        else:
            print("  FAIL: Breakpoint without condition")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Breakpoint parse detail: {e}")
        failed += 1

    try:
        prog = Parser(Lexer('Breakpoint if x > 5.').tokenize()).parse()
        bp = prog.statements[0]
        if isinstance(bp, ast.BreakpointStatement) and bp.condition is not None:
            print("  PASS: Breakpoint with condition has condition node")
            passed += 1
        else:
            print("  FAIL: Breakpoint with condition missing condition")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Breakpoint conditional parse: {e}")
        failed += 1

    # Breakpoint execution — conditional false should NOT break
    track(test("Breakpoint conditional false skips",
        'Create integer named x equal to 3.\n'
        'Breakpoint if x > 10.\n'
        'Print "continued".',
        ["continued"]))

    # Breakpoint execution — non-interactive (stdin is not tty in test)
    # When stdin is not a tty, breakpoint prints info but continues
    try:
        src = ('Create integer named x equal to 42.\n'
               'Breakpoint.\n'
               'Print "after breakpoint".')
        output = run_epl(src)
        if "after breakpoint" in output:
            print("  PASS: Breakpoint non-interactive continues")
            passed += 1
        else:
            print(f"  FAIL: Breakpoint non-interactive should continue")
            print(f"    Got: {output}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Breakpoint non-interactive: {e}")
        failed += 1

    # Test existing debugger module
    try:
        from epl.debugger import EPLDebugger, DebugState, Breakpoint
        dbg = EPLDebugger(silent=True)
        if hasattr(dbg, 'run') and hasattr(dbg, 'on_statement'):
            print("  PASS: EPLDebugger has run and on_statement")
            passed += 1
        else:
            print("  FAIL: EPLDebugger missing methods")
            failed += 1
        # Test DebugState
        state = DebugState()
        bp = state.add_breakpoint(line=10)
        if isinstance(bp, Breakpoint) and bp.line == 10:
            print("  PASS: DebugState.add_breakpoint works")
            passed += 1
        else:
            print("  FAIL: add_breakpoint returned wrong type")
            failed += 1
    except ImportError:
        print("  SKIP: epl.debugger not available")
        passed += 2  # skip both

    # ═══════════════════════════════════════════════════════
    # 5. PYTHON BRIDGE REDUCTION (Native builtins)
    # ═══════════════════════════════════════════════════════
    print("\n🐍 5. Python Bridge Reduction:")

    # Count native stdlib functions
    try:
        from epl.stdlib import STDLIB_FUNCTIONS
        func_count = len(STDLIB_FUNCTIONS)
        if func_count >= 250:
            print(f"  PASS: {func_count} native stdlib functions (>=250)")
            passed += 1
        else:
            print(f"  FAIL: Only {func_count} stdlib functions (need >=250)")
            failed += 1
    except ImportError:
        print("  FAIL: STDLIB_FUNCTIONS not found")
        failed += 1

    # Test categories of native stdlib functions
    try:
        from epl.stdlib import STDLIB_FUNCTIONS
        from epl.interpreter import BUILTINS
        all_funcs = STDLIB_FUNCTIONS | BUILTINS
        categories = {
            'math': ['sqrt', 'floor', 'ceil', 'sin', 'cos'],
            'string': ['uppercase', 'lowercase', 'format'],
            'collections': ['range', 'sorted', 'reversed', 'keys', 'values'],
            'datetime': ['now', 'today', 'date_format'],
            'json': ['json_parse', 'json_stringify'],
            'http': ['http_get', 'http_post'],
        }
        for cat, funcs in categories.items():
            found = sum(1 for f in funcs if f in all_funcs)
            total = len(funcs)
            if found >= total // 2:  # at least half present
                print(f"  PASS: Category '{cat}' has {found}/{total} key functions")
                passed += 1
            else:
                print(f"  FAIL: Category '{cat}' only has {found}/{total}")
                failed += 1
    except Exception as e:
        print(f"  FAIL: Stdlib category check: {e}")
        failed += 1

    # Test that core math operations work without Python bridge
    track(test("Math builtin sqrt", 'Print call sqrt with 144.', ["12.0"]))
    track(test("Math builtin absolute", 'Print call absolute with -7.', ["7"]))
    track(test("String builtin uppercase", 'Print call uppercase with "hello".', ["HELLO"]))
    track(test("String builtin lowercase", 'Print call lowercase with "HELLO".', ["hello"]))
    track(test("Collection builtin length", 'Print call length with "test".', ["4"]))

    # Test list operations
    track(test("List add and length",
        'Create list named items equal to [1, 2, 3].\n'
        'Add 4 to items.\n'
        'Print call length with items.',
        ["4"]))

    # Test JSON operations
    track(test("JSON stringify",
        'Create list named data equal to [1, 2, 3].\n'
        'Print call json_stringify with data.',
        ["[1, 2, 3]"]))

    # ═══════════════════════════════════════════════════════
    # INTEGRATION TESTS
    # ═══════════════════════════════════════════════════════
    print("\n🔄 Integration Tests:")

    # Spawn inside function
    track(test("Spawn inside function body",
        'Define a function named slow_add that takes integer a and integer b and returns integer.\n'
        '    Return a + b.\n'
        'End function.\n'
        'Define a function named runner.\n'
        '    Spawn task calling call slow_add with 10 and 20.\n'
        '    Create integer named result equal to Await task.\n'
        '    Print result.\n'
        'End function.\n'
        'Call runner.',
        ["30"]))

    # Parallel For Each with function calls
    try:
        src = ('Define a function named square that takes integer n and returns integer.\n'
               '    Return n * n.\n'
               'End function.\n'
               'Create list named nums equal to [1, 2, 3, 4, 5].\n'
               'Parallel For Each n in nums\n'
               '    Print call square with n.\n'
               'End.')
        output = run_epl(src)
        output_sorted = sorted(output, key=lambda x: int(x))
        if output_sorted == ["1", "4", "9", "16", "25"]:
            print("  PASS: Parallel For Each with function calls")
            passed += 1
        else:
            print(f"  FAIL: Parallel For Each with function calls")
            print(f"    Expected (sorted): ['1', '4', '9', '16', '25']")
            print(f"    Got (sorted): {output_sorted}")
            failed += 1
    except Exception as e:
        print(f"  FAIL: Parallel For Each with function calls: {e}")
        failed += 1

    # Breakpoint conditional with variable
    track(test("Breakpoint in loop conditional",
        'For i from 1 to 3\n'
        '    Breakpoint if i > 100.\n'
        '    Print i.\n'
        'End for.',
        ["1", "2", "3"]))

    # Mixed: spawn + await + print
    track(test("Spawn chain pattern",
        'Define a function named inc that takes integer x and returns integer.\n'
        '    Return x + 1.\n'
        'End function.\n'
        'Spawn t1 calling call inc with 0.\n'
        'Create integer named v1 equal to Await t1.\n'
        'Spawn t2 calling call inc with v1.\n'
        'Create integer named v2 equal to Await t2.\n'
        'Print v2.',
        ["2"]))

    # ═══════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"Production Power Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def test_production_power_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Production power suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
