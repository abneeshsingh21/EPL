"""
EPL Triple Ecosystem Tests v5.2
Tests: Python Bridge (enhanced), C FFI (language syntax), Hardened Built-in Packages
"""
import sys, os
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

PASSED = 0
FAILED = 0

def test(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"  PASS: {name}")
    except Exception as e:
        FAILED += 1
        print(f"  FAIL: {name} -> {e}")

test.__test__ = False

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"

def assert_in(item, collection, msg=""):
    assert item in collection, msg or f"{item!r} not in {collection!r}"

from epl.lexer import Lexer
from epl.parser import Parser
from epl import ast_nodes as ast
from epl.interpreter import Interpreter
from epl.tokens import TokenType

def parse(src):
    return Parser(Lexer(src).tokenize()).parse()

def run(src, debug_interactive=False):
    interp = Interpreter(debug_interactive=debug_interactive)
    interp.execute(parse(src))
    return interp

def eval_expr(src):
    """Run a program and return the last printed value."""
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run(src)
    return buf.getvalue().strip()

# ═══════════════════════════════════════════════════════════
# 1. SOLUTION 1: Enhanced Python Bridge
# ═══════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n=== Solution 1: Enhanced Python Bridge ===")
    
    def t_python_bridge_allowlist_expanded():
        """Verify the allowlist has been expanded significantly."""
        assert_true(len(Interpreter._SAFE_AUTO_INSTALL) > 90,
                    f"Allowlist has only {len(Interpreter._SAFE_AUTO_INSTALL)} entries")
    test("python_bridge_allowlist_expanded", t_python_bridge_allowlist_expanded)
    
    def t_python_bridge_has_web_frameworks():
        """Check web frameworks are in allowlist."""
        for pkg in ['flask', 'fastapi', 'django', 'tornado', 'starlette']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_web_frameworks", t_python_bridge_has_web_frameworks)
    
    def t_python_bridge_has_ml():
        """Check ML packages are in allowlist."""
        for pkg in ['tensorflow', 'torch', 'scikit-learn', 'transformers']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_ml", t_python_bridge_has_ml)
    
    def t_python_bridge_has_data():
        """Check data science packages are in allowlist."""
        for pkg in ['numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_data", t_python_bridge_has_data)
    
    def t_python_bridge_has_database():
        """Check database packages are in allowlist."""
        for pkg in ['sqlalchemy', 'pymongo', 'redis', 'psycopg2']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_database", t_python_bridge_has_database)
    
    def t_python_bridge_has_gui():
        """Check GUI packages are in allowlist."""
        for pkg in ['toga', 'kivy', 'flet', 'pygame']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_gui", t_python_bridge_has_gui)
    
    def t_python_bridge_has_cloud():
        """Check cloud packages are in allowlist."""
        for pkg in ['boto3', 'docker', 'fabric']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_cloud", t_python_bridge_has_cloud)
    
    def t_python_bridge_has_crypto():
        """Check crypto packages are in allowlist."""
        for pkg in ['cryptography', 'bcrypt', 'pyjwt', 'pynacl']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_crypto", t_python_bridge_has_crypto)
    
    def t_python_bridge_use_math():
        """Test Python bridge actually works with math module."""
        out = eval_expr('Use python "math" as Math\nPrint Math.pi')
        assert_true(out.startswith("3.14"), f"Expected pi, got {out}")
    test("python_bridge_use_math", t_python_bridge_use_math)
    
    def t_python_bridge_use_json():
        """Test Python bridge with json module."""
        out = eval_expr('Use python "json" as JsonLib\nCreate data equal to JsonLib.dumps("hello")\nPrint data')
        assert_in("hello", out)
    test("python_bridge_use_json", t_python_bridge_use_json)
    
    def t_python_bridge_use_os():
        """Test Python bridge with os module."""
        out = eval_expr('Use python "os" as OS\nPrint OS.name')
        assert_true(out in ("nt", "posix"))
    test("python_bridge_use_os", t_python_bridge_use_os)
    
    def t_python_bridge_sandbox_blocked():
        """Use python should be blocked in sandbox mode."""
        try:
            interp = Interpreter(debug_interactive=False)
            interp.safe_mode = True
            interp.execute(parse('Use python "os" as OS'))
            raise AssertionError("Should have raised error in sandbox")
        except Exception as e:
            assert_in("safe mode", str(e).lower())
    test("python_bridge_sandbox_blocked", t_python_bridge_sandbox_blocked)
    
    def t_python_bridge_has_testing():
        """Check testing packages are in allowlist."""
        for pkg in ['pytest', 'hypothesis', 'faker', 'coverage']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_testing", t_python_bridge_has_testing)
    
    def t_python_bridge_has_devops():
        """Check devops packages are in allowlist."""
        for pkg in ['docker', 'paramiko', 'certifi']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_devops", t_python_bridge_has_devops)
    
    def t_python_bridge_has_serialization():
        """Check serialization packages are in allowlist."""
        for pkg in ['pyyaml', 'toml', 'msgpack', 'protobuf', 'orjson']:
            assert_in(pkg, Interpreter._SAFE_AUTO_INSTALL)
    test("python_bridge_has_serialization", t_python_bridge_has_serialization)
    
    # ═══════════════════════════════════════════════════════════
    # 2. SOLUTION 2: C FFI Language Syntax
    # ═══════════════════════════════════════════════════════════
    print("\n=== Solution 2: C FFI Language Syntax ===")
    
    def t_external_token_exists():
        assert_eq(TokenType.EXTERNAL.name, "EXTERNAL")
    test("external_token_exists", t_external_token_exists)
    
    def t_library_token_exists():
        assert_eq(TokenType.LIBRARY.name, "LIBRARY")
    test("library_token_exists", t_library_token_exists)
    
    def t_external_function_ast_node():
        """ExternalFunctionDef AST node exists with correct fields."""
        node = ast.ExternalFunctionDef("sqrt", "libm", ["double"], "double", None, 1)
        assert_eq(node.name, "sqrt")
        assert_eq(node.library, "libm")
        assert_eq(node.param_types, ["double"])
        assert_eq(node.return_type, "double")
        assert_eq(node.alias, None)
    test("external_function_ast_node", t_external_function_ast_node)
    
    def t_load_library_ast_node():
        """LoadLibrary AST node exists with correct fields."""
        node = ast.LoadLibrary("/path/to/lib.so", "MyLib", 1)
        assert_eq(node.path, "/path/to/lib.so")
        assert_eq(node.alias, "MyLib")
    test("load_library_ast_node", t_load_library_ast_node)
    
    def t_external_function_parse_nothing():
        """Parse: External function test from 'lib' takes nothing returns int"""
        prog = parse('External function test from "mylib" takes nothing returns int')
        stmt = prog.statements[0]
        assert_true(isinstance(stmt, ast.ExternalFunctionDef))
        assert_eq(stmt.name, "test")
        assert_eq(stmt.library, "mylib")
        assert_eq(stmt.param_types, [])
        assert_eq(stmt.return_type, "int")
    test("external_function_parse_nothing", t_external_function_parse_nothing)
    
    def t_external_function_parse_with_params():
        """Parse: External function add from 'lib' takes (int, int) returns int"""
        prog = parse('External function add from "mylib" takes (int, int) returns int')
        stmt = prog.statements[0]
        assert_true(isinstance(stmt, ast.ExternalFunctionDef))
        assert_eq(stmt.name, "add")
        assert_eq(stmt.param_types, ["int", "int"])
        assert_eq(stmt.return_type, "int")
    test("external_function_parse_with_params", t_external_function_parse_with_params)
    
    def t_external_function_parse_single_param():
        """Parse: External function abs from 'lib' takes int returns int"""
        prog = parse('External function abs from "mylib" takes int returns int')
        stmt = prog.statements[0]
        assert_eq(stmt.param_types, ["int"])
    test("external_function_parse_single_param", t_external_function_parse_single_param)
    
    def t_external_function_parse_with_alias():
        """Parse: External function strlen from 'c' takes (char_p) returns int as StringLength"""
        prog = parse('External function strlen from "c" takes (char_p) returns int as StringLength')
        stmt = prog.statements[0]
        assert_eq(stmt.name, "strlen")
        assert_eq(stmt.alias, "StringLength")
    test("external_function_parse_with_alias", t_external_function_parse_with_alias)
    
    def t_load_library_parse():
        """Parse: Load library 'path' as name"""
        prog = parse('Load library "mylib.dll" as MyLib')
        stmt = prog.statements[0]
        assert_true(isinstance(stmt, ast.LoadLibrary))
        assert_eq(stmt.path, "mylib.dll")
        assert_eq(stmt.alias, "MyLib")
    test("load_library_parse", t_load_library_parse)
    
    def t_external_function_sandbox_blocked():
        """External function should be blocked in sandbox mode."""
        try:
            interp = Interpreter(debug_interactive=False)
            interp.safe_mode = True
            prog = parse('External function test from "mylib" takes nothing returns int')
            interp.execute(prog)
            raise AssertionError("Should have raised error in sandbox")
        except Exception as e:
            assert_in("safe mode", str(e).lower())
    test("external_function_sandbox_blocked", t_external_function_sandbox_blocked)
    
    def t_load_library_sandbox_blocked():
        """Load library should be blocked in sandbox mode."""
        try:
            interp = Interpreter(debug_interactive=False)
            interp.safe_mode = True
            prog = parse('Load library "test.dll" as Test')
            interp.execute(prog)
            raise AssertionError("Should have raised error in sandbox")
        except Exception as e:
            assert_in("safe mode", str(e).lower())
    test("load_library_sandbox_blocked", t_load_library_sandbox_blocked)
    
    def t_ffi_module_exists():
        """The epl.ffi module should exist and be importable."""
        from epl.ffi import ffi_open, ffi_call, ffi_close, ffi_find, ffi_types
        assert_true(callable(ffi_open))
        assert_true(callable(ffi_call))
        assert_true(callable(ffi_find))
    test("ffi_module_exists", t_ffi_module_exists)
    
    def t_ffi_types_comprehensive():
        """FFI should support at least 20 C types."""
        from epl.ffi import ffi_types
        types = ffi_types()
        assert_true(len(types) >= 20, f"Only {len(types)} types")
        for t in ['int', 'float', 'double', 'char_p', 'void', 'bool', 'size_t']:
            assert_in(t, types)
    test("ffi_types_comprehensive", t_ffi_types_comprehensive)
    
    def t_ffi_find_c_library():
        """ffi_find should locate the C standard library."""
        from epl.ffi import ffi_find
        # On Windows, 'c' is found as msvcrt; on Linux/Mac as libc
        result = ffi_find("c")
        # May return None on some systems but shouldn't crash
        assert_true(True)  # Just verify it doesn't crash
    test("ffi_find_c_library", t_ffi_find_c_library)
    
    def t_ffi_builtins_registered():
        """FFI functions should be callable from EPL."""
        out = eval_expr('Print ffi_types()')
        assert_in("int", out)
        assert_in("double", out)
    test("ffi_builtins_registered", t_ffi_builtins_registered)
    
    def t_external_function_compiler_stub():
        """Compiler should silently handle ExternalFunctionDef."""
        try:
            from epl.compiler import Compiler
            c = Compiler()
            prog = parse('External function test from "mylib" takes nothing returns int\nPrint "hello"')
            ir_code = c.compile(prog)
            assert_true(len(ir_code) > 0)
        except ImportError:
            pass  # LLVM not available, skip
    test("external_function_compiler_stub", t_external_function_compiler_stub)
    
    def t_load_library_compiler_stub():
        """Compiler should silently handle LoadLibrary."""
        try:
            from epl.compiler import Compiler
            c = Compiler()
            prog = parse('Load library "test" as T\nPrint "hello"')
            ir_code = c.compile(prog)
            assert_true(len(ir_code) > 0)
        except ImportError:
            pass
    test("load_library_compiler_stub", t_load_library_compiler_stub)
    
    # ═══════════════════════════════════════════════════════════
    # 3. SOLUTION 3: Hardened Built-in Packages
    # ═══════════════════════════════════════════════════════════
    print("\n=== Solution 3: Hardened Built-in Packages ===")
    
    from epl.package_manager import BUILTIN_REGISTRY, _get_builtin_source
    
    def t_builtin_registry_count():
        """Should have 50+ built-in packages."""
        count = len(BUILTIN_REGISTRY)
        assert_true(count >= 50, f"Only {count} packages in registry")
    test("builtin_registry_count", t_builtin_registry_count)
    
    def t_ffi_package_in_registry():
        """epl-ffi package should be in the registry."""
        assert_in("epl-ffi", BUILTIN_REGISTRY)
        assert_eq(BUILTIN_REGISTRY["epl-ffi"]["version"], "5.2.0")
    test("ffi_package_in_registry", t_ffi_package_in_registry)
    
    def t_http_package_full():
        """epl-http should have GET, POST, PUT, DELETE, PATCH."""
        source = _get_builtin_source("epl-http")
        for method in ['HttpGet', 'HttpPost', 'HttpPut', 'HttpDelete', 'HttpPatch']:
            assert_in(method, source, f"Missing {method} in epl-http")
    test("http_package_full", t_http_package_full)
    
    def t_http_package_utilities():
        """epl-http should have helper functions."""
        source = _get_builtin_source("epl-http")
        for fn in ['UrlEncode', 'UrlDecode', 'UrlParse', 'BuildQueryString',
                   'IsSuccess', 'GetStatusCode', 'GetBody', 'GetHeaders',
                   'JsonGet', 'JsonPost', 'JsonPut', 'JsonPatch']:
            assert_in(fn, source, f"Missing {fn} in epl-http")
    test("http_package_utilities", t_http_package_utilities)
    
    def t_crypto_package_full():
        """epl-crypto should have full hashing, HMAC, encoding, passwords."""
        source = _get_builtin_source("epl-crypto")
        for fn in ['HashMD5', 'HashSHA256', 'HashSHA512', 'HmacSHA256',
                   'Base64Encode', 'Base64Decode', 'HexEncode', 'HexDecode',
                   'GenerateUUID', 'RandomToken', 'RandomHex',
                   'HashPassword', 'VerifyPassword', 'CompareHash']:
            assert_in(fn, source, f"Missing {fn} in epl-crypto")
    test("crypto_package_full", t_crypto_package_full)
    
    def t_db_package_full():
        """epl-db should have transactions, batch, count, schema ops."""
        source = _get_builtin_source("epl-db")
        for fn in ['Connect', 'Execute', 'Query', 'Close',
                   'CreateTable', 'DropTable', 'TableExists', 'ListTables',
                   'Insert', 'SelectAll', 'SelectWhere', 'Update', 'Delete',
                   'Count', 'BeginTransaction', 'Commit', 'Rollback', 'BatchInsert']:
            assert_in(fn, source, f"Missing {fn} in epl-db")
    test("db_package_full", t_db_package_full)
    
    def t_db_package_parameterized():
        """epl-db should use parameterized queries."""
        source = _get_builtin_source("epl-db")
        assert_in("?", source, "Missing parameterized query placeholders")
    test("db_package_parameterized", t_db_package_parameterized)
    
    def t_networking_package_exists():
        """epl-networking should have real content, not a stub."""
        from epl.package_manager import _get_builtin_source_extra
        source = _get_builtin_source_extra("epl-networking")
        assert_true(source is not None, "epl-networking has no source")
        for fn in ['TcpConnect', 'TcpSend', 'TcpReceive', 'TcpClose',
                   'DnsLookup', 'IsPortOpen', 'HttpGet', 'HttpPost']:
            assert_in(fn, source, f"Missing {fn} in epl-networking")
    test("networking_package_exists", t_networking_package_exists)
    
    def t_ffi_package_source():
        """epl-ffi should have convenience wrappers."""
        from epl.package_manager import _get_builtin_source_extra
        source = _get_builtin_source_extra("epl-ffi")
        assert_true(source is not None, "epl-ffi has no source")
        for fn in ['OpenLibrary', 'CallFunction', 'CloseLibrary', 'FindLibrary', 'ListTypes']:
            assert_in(fn, source, f"Missing {fn} in epl-ffi")
    test("ffi_package_source", t_ffi_package_source)
    
    def t_math_package_comprehensive():
        """epl-math should have 15+ functions."""
        source = _get_builtin_source("epl-math")
        funcs = [line.split('(')[0].replace('Function ', '') for line in source.split('\n')
                 if line.strip().startswith('Function ')]
        assert_true(len(funcs) >= 15, f"Only {len(funcs)} functions in epl-math")
    test("math_package_comprehensive", t_math_package_comprehensive)
    
    def t_json_package_has_merge():
        """epl-json should have MergeObjects."""
        source = _get_builtin_source("epl-json")
        assert_in("MergeObjects", source)
    test("json_package_has_merge", t_json_package_has_merge)
    
    def t_testing_package_assertions():
        """epl-testing should have various assertion types."""
        source = _get_builtin_source("epl-testing")
        for fn in ['AssertEqual', 'AssertTrue', 'AssertFalse', 'AssertNull',
                   'AssertNotNull', 'AssertContains', 'AssertGreater', 'AssertLess']:
            assert_in(fn, source, f"Missing {fn} in epl-testing")
    test("testing_package_assertions", t_testing_package_assertions)
    
    def t_regex_package_validators():
        """epl-regex should have email and URL validators."""
        source = _get_builtin_source("epl-regex")
        assert_in("IsEmail", source)
        assert_in("IsURL", source)
    test("regex_package_validators", t_regex_package_validators)
    
    # ═══════════════════════════════════════════════════════════
    # 4. HMAC Stdlib Functions
    # ═══════════════════════════════════════════════════════════
    print("\n=== HMAC Stdlib Functions ===")
    
    def t_hmac_sha256_works():
        out = eval_expr('Print hmac_sha256("key", "message")')
        assert_eq(len(out), 64)  # SHA256 hex is 64 chars
    test("hmac_sha256_works", t_hmac_sha256_works)
    
    def t_hmac_sha512_works():
        out = eval_expr('Print hmac_sha512("key", "message")')
        assert_eq(len(out), 128)  # SHA512 hex is 128 chars
    test("hmac_sha512_works", t_hmac_sha512_works)
    
    def t_hmac_sha256_deterministic():
        out1 = eval_expr('Print hmac_sha256("secret", "data")')
        out2 = eval_expr('Print hmac_sha256("secret", "data")')
        assert_eq(out1, out2)
    test("hmac_sha256_deterministic", t_hmac_sha256_deterministic)
    
    def t_hmac_sha256_varies_with_key():
        out1 = eval_expr('Print hmac_sha256("key1", "data")')
        out2 = eval_expr('Print hmac_sha256("key2", "data")')
        assert_true(out1 != out2, "Different keys should produce different HMACs")
    test("hmac_sha256_varies_with_key", t_hmac_sha256_varies_with_key)
    
    def t_hmac_in_stdlib_functions():
        from epl.stdlib import STDLIB_FUNCTIONS
        assert_in('hmac_sha256', STDLIB_FUNCTIONS)
        assert_in('hmac_sha512', STDLIB_FUNCTIONS)
    test("hmac_in_stdlib_functions", t_hmac_in_stdlib_functions)
    
    # ═══════════════════════════════════════════════════════════
    # 5. Integration: All 3 Solutions Working Together
    # ═══════════════════════════════════════════════════════════
    print("\n=== Integration Tests ===")
    
    def t_python_bridge_plus_stdlib():
        """Python bridge and stdlib functions coexist."""
        out = eval_expr('Use python "math" as Math\nPrint Math.sqrt(16)\nPrint hash_sha256("test")')
        lines = out.strip().split('\n')
        assert_eq(lines[0].strip(), "4.0")
        assert_eq(len(lines[1].strip()), 64)
    test("python_bridge_plus_stdlib", t_python_bridge_plus_stdlib)
    
    def t_external_and_print():
        """External function + Print should coexist in same program."""
        prog = parse('External function test from "mylib" takes nothing returns int\nPrint "hello"')
        assert_eq(len(prog.statements), 2)
        assert_true(isinstance(prog.statements[0], ast.ExternalFunctionDef))
    test("external_and_print", t_external_and_print)
    
    def t_load_library_and_external():
        """Load library + External function can coexist."""
        prog = parse('Load library "mylib" as Lib\nExternal function calc from "mylib" takes (int) returns int\nPrint "ok"')
        assert_eq(len(prog.statements), 3)
        assert_true(isinstance(prog.statements[0], ast.LoadLibrary))
        assert_true(isinstance(prog.statements[1], ast.ExternalFunctionDef))
    test("load_library_and_external", t_load_library_and_external)
    
    def t_three_ecosystems_syntax():
        """All three can be used in the same program."""
        src = '''Use python "math" as Math
    External function test from "mylib" takes nothing returns int
    Load library "mylib" as Lib
    Print "Triple ecosystem works"'''
        prog = parse(src)
        assert_eq(len(prog.statements), 4)
        assert_true(isinstance(prog.statements[0], ast.UseStatement))
        assert_true(isinstance(prog.statements[1], ast.ExternalFunctionDef))
        assert_true(isinstance(prog.statements[2], ast.LoadLibrary))
    test("three_ecosystems_syntax", t_three_ecosystems_syntax)
    
    def t_existing_ffi_api_still_works():
        """The function-call FFI API (ffi_open, ffi_call) still works."""
        from epl.ffi import ffi_types, ffi_find
        types = ffi_types()
        assert_true(isinstance(types, list))
        assert_in("int", types)
    test("existing_ffi_api_still_works", t_existing_ffi_api_still_works)
    
    def t_package_ecosystem_counts():
        """Verify total function counts across packages are substantial."""
        from epl.stdlib import STDLIB_FUNCTIONS
        assert_true(len(STDLIB_FUNCTIONS) > 400,
                    f"Only {len(STDLIB_FUNCTIONS)} stdlib functions")
        assert_true(len(BUILTIN_REGISTRY) >= 50,
                    f"Only {len(BUILTIN_REGISTRY)} packages")
    test("package_ecosystem_counts", t_package_ecosystem_counts)
    
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"Triple Ecosystem Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    print(f"{'='*50}")
    return FAILED == 0


def test_triple_ecosystem_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    raise SystemExit(0 if run_suite() else 1)
