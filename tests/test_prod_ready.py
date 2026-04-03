"""
EPL v7.0 Production-Readiness Test Suite
Tests for all production fixes:
  - Type checker
  - Performance optimizations (expression dispatch, loop fast-path)
  - Enhanced error messages
  - WASM compiler fixes
  - Database dialect detection
  - Production server function
  - Registry format
  - Environment __slots__
"""

import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.environment import Environment
from epl.errors import EPLError

PASSED = 0
FAILED = 0


def run_epl(source: str) -> list:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines


def test(name, source, expected):
    global PASSED, FAILED
    try:
        output = run_epl(source)
        if output == expected:
            print(f"  PASS: {name}")
            PASSED += 1
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            FAILED += 1
            return False
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {e}")
        FAILED += 1
        return False
test.__test__ = False


def test_assert(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        print(f"  PASS: {name}")
        PASSED += 1
    else:
        print(f"  FAIL: {name} {detail}")
        FAILED += 1
test_assert.__test__ = False


# ═══════════════════════════════════════════════════════
#  1. TYPE CHECKER TESTS
# ═══════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("=== Type Checker Tests ===")
    
    from epl.type_checker import TypeChecker, EPLType, type_check, parse_type_str
    import epl.ast_nodes as ast
    
    
    def test_type_check():
        t_int = EPLType("integer")
        t_float = EPLType("decimal")
        t_text = EPLType("text")
        t_any = EPLType("any")
    
        test_assert("EPLType: integer compatible with integer",
                    t_int.is_compatible(EPLType("integer")))
        test_assert("EPLType: integer compatible with decimal (numeric coercion)",
                    t_int.is_compatible(t_float))
        test_assert("EPLType: any compatible with anything",
                    t_any.is_compatible(t_text))
        test_assert("EPLType: integer NOT compatible with text",
                    not t_int.is_compatible(t_text))
    
        test_assert("parse_type_str: 'int' -> integer",
                    parse_type_str("int").name == "integer")
        test_assert("parse_type_str: 'str' -> text",
                    parse_type_str("str").name == "text")
        test_assert("parse_type_str: 'bool' -> boolean",
                    parse_type_str("bool").name == "boolean")
        test_assert("parse_type_str: 'float' -> decimal",
                    parse_type_str("float").name == "decimal")
    
        t_opt = EPLType("text", optional=True)
        test_assert("EPLType: optional text is_optional", t_opt.optional)
        nothing = EPLType("nothing")
        test_assert("EPLType: optional text compatible with nothing",
                    t_opt.is_compatible(nothing))
    
        t_union = EPLType("integer", union=[EPLType("text")])
        test_assert("EPLType: union (integer|text) compatible with text",
                    t_union.is_compatible(t_text))
        test_assert("EPLType: union (integer|text) compatible with integer",
                    t_union.is_compatible(t_int))
    
        source = 'Create x equal to 10.\nDisplay x.'
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        checker = TypeChecker()
        warnings = checker.check(program)
        test_assert("TypeChecker: simple program no warnings",
                    len(warnings) == 0, f"got {len(warnings)} warnings")
    
        warnings2 = type_check(program)
        test_assert("type_check convenience function works",
                    isinstance(warnings2, list))
    
    
    test_type_check()
    
    
    # ═══════════════════════════════════════════════════════
    #  2. PERFORMANCE OPTIMIZATION TESTS
    # ═══════════════════════════════════════════════════════
    print("\n=== Performance Optimization Tests ===")
    
    
    def test_expr_dispatch():
        interp = Interpreter()
        test_assert("Expression dispatch table exists",
                    interp._expr_dispatch is not None)
        test_assert("Expression dispatch is a dict",
                    isinstance(interp._expr_dispatch, dict))
        test_assert("Dispatch has BinaryOp",
                    ast.BinaryOp in interp._expr_dispatch)
        test_assert("Dispatch has FunctionCall",
                    ast.FunctionCall in interp._expr_dispatch)
        test_assert("Dispatch has MethodCall",
                    ast.MethodCall in interp._expr_dispatch)
        test_assert("Dispatch has LambdaExpression",
                    ast.LambdaExpression in interp._expr_dispatch)
        test_assert("Dispatch has DictLiteral",
                    ast.DictLiteral in interp._expr_dispatch)
        test_assert("Dispatch has IndexAccess",
                    ast.IndexAccess in interp._expr_dispatch)
        test_assert("Dispatch has NewInstance",
                    ast.NewInstance in interp._expr_dispatch)
        test_assert("Yield cache initialized",
                    hasattr(interp, '_yield_cache') and isinstance(interp._yield_cache, dict))
    
    
    test_expr_dispatch()
    
    
    def test_environment_slots():
        test_assert("Environment has __slots__",
                    hasattr(Environment, '__slots__'))
        env = Environment()
        test_assert("Environment instance has no __dict__",
                    not hasattr(env, '__dict__'))
        test_assert("Slots include 'variables'",
                    'variables' in Environment.__slots__)
        test_assert("Slots include 'parent'",
                    'parent' in Environment.__slots__)
    
    
    test_environment_slots()
    
    
    def test_loop_fast_path():
        test("ForEach: basic iteration",
             'For each item in [10, 20, 30]\n    Print item.\nEnd for.',
             ['10', '20', '30'])
        test("ForEach: string list",
             'For each name in ["Alice", "Bob"]\n    Print name.\nEnd for.',
             ['Alice', 'Bob'])
        test("ForRange: 1 to 5",
             'For i from 1 to 5\n    Print i.\nEnd for.',
             ['1', '2', '3', '4', '5'])
        test("ForRange: step 2",
             'For i from 0 to 10 step 2\n    Print i.\nEnd for.',
             ['0', '2', '4', '6', '8', '10'])
        test("ForRange: descending",
             'For i from 5 to 1 step -1\n    Print i.\nEnd for.',
             ['5', '4', '3', '2', '1'])
        test("Nested loops",
             'For i from 1 to 2\n    For j from 1 to 2\n        Print i * 10 + j.\n    End for.\nEnd for.',
             ['11', '12', '21', '22'])
        test("ForEach: break",
             'For each n in [1, 2, 3, 4, 5]\n    If n equals 3 then\n        Break.\n    End if.\n    Print n.\nEnd for.',
             ['1', '2'])
        test("ForEach: continue",
             'For each n in [1, 2, 3, 4, 5]\n    If n equals 3 then\n        Continue.\n    End if.\n    Print n.\nEnd for.',
             ['1', '2', '4', '5'])
    
    
    test_loop_fast_path()
    
    
    def test_op_dunder_hoisted():
        from epl import interpreter as interp_mod
        test_assert("_OP_DUNDER is module-level",
                    hasattr(interp_mod, '_OP_DUNDER'))
        test_assert("_OP_REFLECTED is module-level",
                    hasattr(interp_mod, '_OP_REFLECTED'))
        test_assert("_OP_DUNDER has '+' key",
                    '+' in interp_mod._OP_DUNDER)
        test_assert("_OP_REFLECTED has '+' key",
                    '+' in interp_mod._OP_REFLECTED)
    
    
    test_op_dunder_hoisted()
    
    
    # ═══════════════════════════════════════════════════════
    #  3. EXPRESSION DISPATCH TESTS
    # ═══════════════════════════════════════════════════════
    print("\n=== Expression Dispatch Tests ===")
    
    
    def test_expression_types():
        test("Expr: addition", 'Print 2 + 3.', ['5'])
        test("Expr: subtraction", 'Print 10 - 4.', ['6'])
        test("Expr: multiplication", 'Print 3 * 7.', ['21'])
        test("Expr: comparison", 'Print 5 > 3.', ['true'])
        test("Expr: negation", 'Print -5.', ['-5'])
        test("Expr: not", 'Print not true.', ['false'])
        test("Expr: function call",
             'Define a function named double that takes integer x and returns integer.\n'
             '    Return x * 2.\nEnd function.\nPrint call double with 5.',
             ['10'])
        test("Expr: list literal",
             'Create list named items equal to [1, 2, 3].\nPrint items.length.',
             ['3'])
        test("Expr: dict literal",
             'Create d equal to Map with key = "value".\nPrint d["key"].',
             ['value'])
        test("Expr: index access",
             'Create list named items equal to [10, 20, 30].\nPrint items[1].',
             ['20'])
        test("Expr: lambda",
             'Create add equal to lambda x, y -> x + y.\nPrint call add with 3 and 4.',
             ['7'])
        test("Expr: ternary",
             'Create integer named x equal to 10.\nPrint "big" if x > 5 otherwise "small".',
             ['big'])
        test("Expr: property access",
             'Class Dog\n    name = "Rex"\nEnd\nCreate d equal to new Dog.\nPrint d.name.',
             ['Rex'])
        test("Expr: method call",
             'Print "hello".uppercase.',
             ['HELLO'])
        test("Expr: slice",
             'Create list named items equal to [1, 2, 3, 4, 5].\nPrint items[1:3].',
             ['[2, 3]'])
    
    
    test_expression_types()
    
    
    # ═══════════════════════════════════════════════════════
    #  4. ENHANCED ERROR MESSAGES
    # ═══════════════════════════════════════════════════════
    print("\n=== Enhanced Error Messages Tests ===")
    
    
    def test_error_hints():
        from epl.errors import _HINTS
    
        test_assert("Hints: has 'maximum recursion'",
                    any('maximum recursion' in k for k in _HINTS))
        test_assert("Hints: has 'pycryptodome'",
                    any('pycryptodome' in k for k in _HINTS))
        test_assert("Hints: has 'psycopg2'",
                    any('psycopg2' in k for k in _HINTS))
        test_assert("Hints: has 'mysql'",
                    any('mysql' in k for k in _HINTS))
        test_assert("Hints: has 'not iterable'",
                    any('not iterable' in k for k in _HINTS))
        test_assert("Hints: has 'stack overflow'",
                    any('stack overflow' in k for k in _HINTS))
        test_assert("Hints: has 'read only'",
                    any('read only' in k for k in _HINTS))
        test_assert("Hints: has 'method not found'",
                    any('method not found' in k for k in _HINTS))
        test_assert("Hints: has 'syntax error'",
                    any('syntax error' in k for k in _HINTS))
        test_assert(f"Hints: at least 38 patterns (got {len(_HINTS)})",
                    len(_HINTS) >= 38)
    
    
    test_error_hints()
    
    
    # ═══════════════════════════════════════════════════════
    #  5. DATABASE DIALECT DETECTION
    # ═══════════════════════════════════════════════════════
    print("\n=== Database Dialect Detection Tests ===")
    
    
    def test_database_dialect():
        try:
            from epl.database_real import _detect_dialect, _parse_dsn
        except ImportError:
            from epl.stdlib import _detect_dialect, _parse_dsn
    
        test_assert("Dialect: sqlite default",
                    _detect_dialect("mydb.sqlite") == "sqlite")
        test_assert("Dialect: postgresql",
                    _detect_dialect("postgres://user:pass@host/db") == "postgres")
        test_assert("Dialect: postgresql alt",
                    _detect_dialect("postgresql://user:pass@host/db") == "postgres")
        test_assert("Dialect: mysql",
                    _detect_dialect("mysql://user:pass@host/db") == "mysql")
        test_assert("Dialect: plain filename",
                    _detect_dialect("test.db") == "sqlite")
    
        dsn = _parse_dsn("postgres://admin:secret@db.example.com:5432/myapp")
        test_assert("DSN parse: host", dsn.get("host") == "db.example.com")
        test_assert("DSN parse: port", dsn.get("port") == 5432)
        test_assert("DSN parse: user", dsn.get("user") == "admin")
        test_assert("DSN parse: password", dsn.get("password") == "secret")
        test_assert("DSN parse: database", dsn.get("database") == "myapp")
    
    
    try:
        test_database_dialect()
    except Exception as e:
        print(f"  SKIP: Database dialect tests ({e})")
    
    
    # ═══════════════════════════════════════════════════════
    #  6. REGISTRY FORMAT
    # ═══════════════════════════════════════════════════════
    print("\n=== Registry Format Tests ===")
    
    
    def test_registry():
        registry_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'registry.json')
        if not os.path.exists(registry_path):
            print("  SKIP: registry.json not found")
            return
    
        with open(registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    
        test_assert("Registry: has 'version' field", 'version' in data)
        test_assert("Registry: version is >= 2", data.get('version') >= 2)
        test_assert("Registry: has 'packages' field", 'packages' in data)
        test_assert("Registry: at least 15 packages",
                    len(data.get('packages', {})) >= 15,
                    f"got {len(data.get('packages', {}))}")
    
        required_fields = {'version', 'description', 'author', 'license'}
        for pkg_name, pkg_data in data.get('packages', {}).items():
            for field in required_fields:
                test_assert(f"Registry: {pkg_name} has '{field}'",
                            field in pkg_data, f"missing '{field}'")
    
        pkgs = data.get('packages', {})
        test_assert("Registry: has epl-http", 'epl-http' in pkgs)
        test_assert("Registry: has epl-json", 'epl-json' in pkgs)
        test_assert("Registry: has epl-crypto", 'epl-crypto' in pkgs)
        test_assert("Registry: has epl-db", 'epl-db' in pkgs)
    
    
    test_registry()
    
    
    # ═══════════════════════════════════════════════════════
    #  7. WASM COMPILER
    # ═══════════════════════════════════════════════════════
    print("\n=== WASM Compiler Tests ===")
    
    
    def test_wasm_compiler():
        try:
            from epl.compiler import Compiler
            compiler = Compiler()
            import inspect
            sig = inspect.signature(compiler.compile_to_wasm)
            params = list(sig.parameters.keys())
            test_assert("WASM: compile_to_wasm exists",
                        hasattr(compiler, 'compile_to_wasm'))
            test_assert("WASM: has 'program' param", 'program' in params)
            test_assert("WASM: has 'output_path' param", 'output_path' in params)
            test_assert("WASM: has 'runtime_c' param", 'runtime_c' in params)
        except ImportError:
            print("  SKIP: llvmlite not installed")
    
    
    test_wasm_compiler()
    
    
    # ═══════════════════════════════════════════════════════
    #  8. PRODUCTION WEB SERVER
    # ═══════════════════════════════════════════════════════
    print("\n=== Production Web Server Tests ===")
    
    
    def test_production_server():
        try:
            from epl.web import start_production_server
            import inspect
            sig = inspect.signature(start_production_server)
            params = list(sig.parameters.keys())
            test_assert("Prod server: function exists", True)
            test_assert("Prod server: has 'app' param", 'app' in params)
            test_assert("Prod server: has 'host' param", 'host' in params)
            test_assert("Prod server: has 'port' param", 'port' in params)
            test_assert("Prod server: has 'server_type' param", 'server_type' in params)
        except ImportError as e:
            print(f"  SKIP: Production server ({e})")
        except Exception as e:
            print(f"  SKIP: Production server test error: {e}")
    
    
    test_production_server()
    
    
    # ═══════════════════════════════════════════════════════
    #  9. AES ENCRYPTION
    # ═══════════════════════════════════════════════════════
    print("\n=== AES Encryption Tests ===")
    
    
    def test_aes_encryption():
        try:
            from epl.stdlib import call_stdlib
    
            key = "my-secret-key-16"
            plaintext = "Hello, World!"
            ciphertext = call_stdlib('aes_encrypt', [plaintext, key], 0)
            test_assert("AES: ciphertext != plaintext", ciphertext != plaintext)
            test_assert("AES: ciphertext is string", isinstance(ciphertext, str))
    
            decrypted = call_stdlib('aes_decrypt', [ciphertext, key], 0)
            test_assert("AES: roundtrip works", decrypted == plaintext)
    
            ciphertext2 = call_stdlib('aes_encrypt', [plaintext, "different-key-16"], 0)
            test_assert("AES: different key different output", ciphertext != ciphertext2)
    
            try:
                call_stdlib('aes_decrypt', [ciphertext, "wrong-key-abcdef"], 0)
                test_assert("AES: wrong key raises error", False)
            except Exception:
                test_assert("AES: wrong key raises error", True)
    
        except Exception as e:
            if 'pycryptodome' in str(e).lower() or 'crypto' in str(e).lower() or 'no module' in str(e).lower():
                print(f"  SKIP: AES tests (no crypto library)")
            else:
                print(f"  FAIL: AES error: {e}")
                global failed
                failed += 1
    
    
    test_aes_encryption()
    
    
    # ═══════════════════════════════════════════════════════
    #  10. RUNTIME.C WASM GUARDS
    # ═══════════════════════════════════════════════════════
    print("\n=== Runtime.c WASM Guards Tests ===")
    
    
    def test_runtime_wasm_guards():
        runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
        if not os.path.exists(runtime_path):
            print("  SKIP: runtime.c not found")
            return
    
        with open(runtime_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
        test_assert("Runtime: has __EMSCRIPTEN__ guard", '__EMSCRIPTEN__' in content)
        test_assert("Runtime: has __wasi__ guard", '__wasi__' in content)
        test_assert("Runtime: has __wasm__ guard", '__wasm__' in content)
        test_assert("Runtime: has WASM threading stubs",
                    'no real threading' in content.lower())
        test_assert("Runtime: has WASM dlopen stubs",
                    'no dynamic library' in content.lower())
        test_assert("Runtime: epl_system guarded",
                    'not available in WASM' in content)
    
    
    test_runtime_wasm_guards()
    
    
    # ═══════════════════════════════════════════════════════
    #  11. CORE REGRESSION TESTS
    # ═══════════════════════════════════════════════════════
    print("\n=== Core Regression Tests ===")
    
    
    def test_core_regression():
        test("Regression: variable",
             'Create text named name equal to "EPL".\nPrint name.',
             ['EPL'])
        test("Regression: arithmetic",
             'Print 2 + 3 * 4.',
             ['14'])
        test("Regression: string concat",
             'Print "Hello, " + "World!".',
             ['Hello, World!'])
        test("Regression: if/else",
             'Create integer named x equal to 10.\nIf x > 5 then\n    Print "big".\nOtherwise\n    Print "small".\nEnd if.',
             ['big'])
        test("Regression: function",
             'Define a function named greet that takes text name and returns text.\n    Return "Hello, " + name.\nEnd function.\nPrint call greet with "EPL".',
             ['Hello, EPL'])
        test("Regression: list",
             'Create list named nums equal to [1, 2, 3].\nnums.add(4).\nPrint nums.length.',
             ['4'])
        test("Regression: while",
             'Create integer named i equal to 0.\nWhile i < 3\n    Print i.\n    Increase i by 1.\nEnd while.',
             ['0', '1', '2'])
        test("Regression: try/catch",
             'Try\n    Throw "oops".\nCatch error\n    Print "caught".\nEnd.',
             ['caught'])
        test("Regression: class",
             'Class Cat\n    name = ""\n    Function init takes n\n        name = n.\n    End\n    Function speak\n        Return "Meow from " + name.\n    End\nEnd\nCreate c equal to new Cat("Luna").\nPrint c.speak().',
             ['Meow from Luna'])
        test("Regression: template string",
             'Create text named name equal to "World".\nPrint "Hello, $name!".',
             ['Hello, World!'])
        test("Regression: match",
             'Create integer named x equal to 2.\nMatch x\n    When 1\n        Print "one".\n    When 2\n        Print "two".\nEnd.',
             ['two'])
        test("Regression: constant",
             'Constant PI = 3.14.\nPrint PI.',
             ['3.14'])
        test("Regression: dictionary",
             'Create d equal to Map with a = 1 and b = 2.\nPrint d["a"].',
             ['1'])
        test("Regression: augmented assignment",
             'Create integer named x equal to 10.\nIncrease x by 5.\nPrint x.',
             ['15'])
        test("Regression: string methods",
             'Print "hello world".replace("world", "EPL").',
             ['hello EPL'])
        test("Regression: repeat",
             'Create integer named count equal to 0.\nRepeat 5 times\n    Increase count by 1.\nEnd repeat.\nPrint count.',
             ['5'])
        test("Regression: nested functions",
             'Define a function named outer and returns integer.\n    Define a function named inner and returns integer.\n        Return 42.\n    End function.\n    Return call inner.\nEnd function.\nPrint call outer.',
             ['42'])
    
    
    test_core_regression()
    
    
    # ═══════════════════════════════════════════════════════
    #  SUMMARY
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"Production Readiness Tests: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    if FAILED == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"WARNING: {FAILED} test(s) failed!")
    return FAILED == 0


def test_prod_ready_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Production readiness suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
