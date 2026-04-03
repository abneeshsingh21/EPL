"""
EPL v4.0 Feature Test Suite
Tests for: interfaces, modules, try/catch/finally, error hierarchy,
visibility, static methods, abstract methods, type system, profiler.
"""

import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError


def run_epl(source: str) -> list:
    """Run EPL source and return captured output lines."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines


def test(name, source, expected):
    try:
        output = run_epl(source)
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


def test_error(name, source, expected_substring):
    try:
        run_epl(source)
        print(f"  FAIL: {name} (expected error)")
        return False
    except EPLError as e:
        if expected_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected containing: {expected_substring}")
            print(f"    Got: {e}")
            return False
    except Exception as e:
        if expected_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        print(f"  FAIL: {name} ({type(e).__name__}: {e})")
        return False
test_error.__test__ = False


def test_no_error(name, source):
    """Test that code runs without error (output doesn't matter)."""
    try:
        run_epl(source)
        print(f"  PASS: {name}")
        return True
    except Exception as e:
        print(f"  FAIL: {name}")
        print(f"    Error: {type(e).__name__}: {e}")
        return False
test_no_error.__test__ = False


def run_suite():
    print("=" * 60)
    print("  EPL v4.0 Feature Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0

    def track(result):
        nonlocal passed, failed
        if result:
            passed += 1
        else:
            failed += 1

    # ─── Try / Catch / Finally ───────────────────────────
    print("\n--- Try/Catch/Finally ---")

    track(test("Basic try/catch",
        'Try\n    Print "in try"\nCatch err\n    Print "caught"\nEnd',
        ["in try"]))

    track(test("Try with error caught",
        'Try\n    Throw "boom"\nCatch err\n    Print "caught"\nEnd',
        ["caught"]))

    track(test("Try/catch/finally - no error",
        'Try\n    Print "try"\nCatch err\n    Print "catch"\nFinally\n    Print "finally"\nEnd',
        ["try", "finally"]))

    track(test("Try/catch/finally - with error",
        'Try\n    Throw "fail"\nCatch err\n    Print "caught"\nFinally\n    Print "cleanup"\nEnd',
        ["caught", "cleanup"]))

    track(test("Try with only finally",
        'Try\n    Print "body"\nFinally\n    Print "done"\nEnd',
        ["body", "done"]))

    # ─── Interface Definition ────────────────────────────
    print("\n--- Interfaces ---")

    track(test_no_error("Define interface",
        'Interface Renderable\n    Function render takes text message\nEnd'))

    track(test("Class implements interface",
        'Interface Greetable\n    Function greet takes nothing\nEnd\n\nClass Greeter implements Greetable\n    Define a function named greet that takes nothing and returns text\n        Return "Hello!"\n    End\nEnd\n\nCreate instance equal to new Greeter()\nPrint instance.greet()',
        ["Hello!"]))

    track(test_error("Missing interface method",
        'Interface Showable\n    Function render takes nothing\n    Function toggle takes nothing\nEnd\n\nClass Widget implements Showable\n    Define a function named render that takes nothing and returns nothing\n        Print "visible"\n    End\nEnd',
        "toggle"))

    # ─── Module System ───────────────────────────────────
    print("\n--- Modules ---")

    track(test("Module definition and access",
        'Module MathLib\n    Define a function named square that takes integer x and returns integer\n        Return x * x\n    End\n    Export square\nEnd\n\nPrint MathLib::square(5)',
        ["25"]))

    track(test("Module with multiple exports",
        'Module Utils\n    Define a function named add that takes integer a, integer b and returns integer\n        Return a + b\n    End\n    Define a function named multiply that takes integer a, integer b and returns integer\n        Return a * b\n    End\n    Export add\n    Export multiply\nEnd\n\nPrint Utils::add(3, 4)\nPrint Utils::multiply(3, 4)',
        ["7", "12"]))

    track(test_error("Module access non-existent member",
        'Module M\n    Define a function named foo that takes nothing and returns nothing\n        Print "foo"\n    End\n    Export foo\nEnd\nM::bar()',
        "no member"))

    # ─── Error Hierarchy ─────────────────────────────────
    print("\n--- Error Hierarchy ---")

    track(test("Throw and catch error",
        'Try\n    Throw "custom error"\nCatch e\n    Print "caught"\nEnd',
        ["caught"]))

    track(test_error("Uncaught throw",
        'Throw "boom"',
        "boom"))

    # ─── Static Methods ──────────────────────────────────
    print("\n--- Static Methods ---")

    track(test("Static method in class",
        'Class Calculator\n    Static Function add takes integer a, integer b\n        Return a + b\n    End\nEnd\n\nPrint Calculator.add(10, 20)',
        ["30"]))

    track(test("Static method with string return",
        'Class Greeter\n    Static Function hello takes text name\n        Return "Hi " + name\n    End\nEnd\n\nPrint Greeter.hello("World")',
        ["Hi World"]))

    # ─── Visibility Modifiers ────────────────────────────
    print("\n--- Visibility ---")

    track(test("Private method in class",
        'Class Secret\n    Private Define a function named internal that takes nothing and returns text\n        Return "hidden"\n    End\n    Define a function named reveal that takes nothing and returns text\n        Return this.internal()\n    End\nEnd\n\nCreate s equal to new Secret()\nPrint s.reveal()',
        ["hidden"]))

    # ─── Abstract Methods ────────────────────────────────
    print("\n--- Abstract Methods ---")

    track(test_no_error("Abstract method declaration",
        'Abstract Function speak takes text message'))

    # ─── Yield ───────────────────────────────────────────
    print("\n--- Yield ---")

    track(test("Yield function definition",
        'Define a function named gen that takes integer n and returns nothing\n    For i from 1 to n\n        Yields i\n    End\nEnd\nPrint "yield ok"',
        ["yield ok"]))

    # ─── Constants ───────────────────────────────────────
    print("\n--- Constants ---")

    track(test("Constant declaration",
        'Constant PI = 3.14\nPrint PI',
        ["3.14"]))

    track(test_error("Cannot reassign constant",
        'Constant MAX = 100\nSet MAX to 200',
        "constant"))

    track(test("Multiple constants",
        'Constant X = 10\nConstant Y = 20\nPrint X + Y',
        ["30"]))

    # ─── Transpiler Load Tests ───────────────────────────
    print("\n--- Transpilers ---")

    track(_test_js_transpiler())
    track(_test_kotlin_transpiler())

    # ─── Profiler ────────────────────────────────────────
    print("\n--- Profiler ---")
    track(_test_profiler())

    # ─── Type System ─────────────────────────────────────
    print("\n--- Type System ---")
    track(_test_type_system())

    # ─── Async IO Module ─────────────────────────────────
    print("\n--- Async IO ---")
    track(_test_async_module())

    # ─── WSGI Module ─────────────────────────────────────
    print("\n--- WSGI ---")
    track(_test_wsgi_module())

    # ─── Package Manager ─────────────────────────────────
    print("\n--- Packages ---")
    track(_test_package_manager())

    # ─── Summary ─────────────────────────────────────────
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed == 0:
        print("  All v4 tests passed!")
    else:
        print(f"  {failed} test(s) failed")
    print("=" * 60)
    return failed


def _test_js_transpiler():
    """Test JS transpiler with v4 AST nodes."""
    try:
        from epl.js_transpiler import JSTranspiler

        source = 'Module MathLib\n    Define a function named square that takes integer x and returns integer\n        Return x * x\n    End\n    Export square\nEnd\n\nTry\n    Print "test"\nCatch err\n    Print err\nFinally\n    Print "done"\nEnd'
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        transpiler = JSTranspiler(target='browser')
        js = transpiler.transpile(program)
        if 'MathLib' in js and 'finally' in js:
            print("  PASS: JS transpiler v4 nodes")
            return True
        else:
            print(f"  FAIL: JS transpiler v4 nodes (missing keywords in output)")
            return False
    except Exception as e:
        print(f"  FAIL: JS transpiler v4 nodes ({e})")
        return False


def _test_kotlin_transpiler():
    """Test Kotlin transpiler with v4 AST nodes."""
    try:
        from epl.kotlin_gen import KotlinGenerator

        source = 'Interface Drawable\n    Function draw takes nothing\nEnd\n\nModule Config\n    Define a function named get_version that takes nothing and returns text\n        Return "4.0"\n    End\n    Export get_version\nEnd\n\nTry\n    Print "test"\nFinally\n    Print "cleanup"\nEnd'
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        gen = KotlinGenerator()
        kt = gen.generate(program)
        if 'interface Drawable' in kt and 'object Config' in kt and 'finally' in kt:
            print("  PASS: Kotlin transpiler v4 nodes")
            return True
        else:
            print(f"  FAIL: Kotlin transpiler v4 nodes (missing keywords)")
            print(f"    Output preview: {kt[:200]}")
            return False
    except Exception as e:
        print(f"  FAIL: Kotlin transpiler v4 nodes ({e})")
        return False


def _test_profiler():
    """Test profiler functionality."""
    try:
        from epl.profiler import EPLProfiler
        p = EPLProfiler()
        p.start("test_func")
        import time
        time.sleep(0.01)
        elapsed = p.stop("test_func")
        if elapsed > 5:  # at least 5ms
            report = p.report()
            if "test_func" in report:
                print("  PASS: Profiler timing + report")
                return True
        print(f"  FAIL: Profiler timing ({elapsed:.2f}ms)")
        return False
    except Exception as e:
        print(f"  FAIL: Profiler ({e})")
        return False


def _test_type_system():
    """Test type system module."""
    try:
        from epl.type_system import TypeChecker, EPLType, TypeKind
        tc = TypeChecker()
        # Test basic type creation
        prim = EPLType(TypeKind.PRIMITIVE, "integer")
        any_t = EPLType(TypeKind.ANY, "any")
        if prim.kind == TypeKind.PRIMITIVE and any_t.kind == TypeKind.ANY:
            print("  PASS: Type system basics")
            return True
        print("  FAIL: Type system basics")
        return False
    except Exception as e:
        print(f"  FAIL: Type system ({e})")
        return False


def _test_async_module():
    """Test async IO module loads."""
    try:
        from epl.async_io import EPLEventLoop, EPLTask, EPLChannel, EPLTaskGroup
        print("  PASS: Async IO module loads")
        return True
    except Exception as e:
        print(f"  FAIL: Async IO module ({e})")
        return False


def _test_wsgi_module():
    """Test WSGI module loads."""
    try:
        from epl.wsgi import EPLWSGIApp, EPLRequest, EPLResponse
        app = EPLWSGIApp()
        # EPLWSGIApp is callable (WSGI entry) and has route decorator
        if hasattr(app, 'route') and callable(app):
            print("  PASS: WSGI module loads")
            return True
        print("  FAIL: WSGI module missing methods")
        return False
    except Exception as e:
        print(f"  FAIL: WSGI module ({e})")
        return False


def _test_package_manager():
    """Test package manager with v4 packages."""
    try:
        from epl.package_manager import BUILTIN_REGISTRY
        v4_packages = [k for k in BUILTIN_REGISTRY
                       if BUILTIN_REGISTRY[k].get('version', '') == '4.0.0']
        if len(v4_packages) >= 7:
            print(f"  PASS: Package registry ({len(BUILTIN_REGISTRY)} total, {len(v4_packages)} v4)")
            return True
        print(f"  FAIL: Package registry (only {len(v4_packages)} v4 packages)")
        return False
    except Exception as e:
        print(f"  FAIL: Package manager ({e})")
        return False


def test_v4_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    raise SystemExit(run_suite())
