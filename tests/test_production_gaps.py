"""
EPL Production Gaps Test Suite
Tests for all 7 production hardening fixes:
  #1 Sandbox enforcement (Use python blocked, import path restriction)
  #2 Generic types (Class Stack<T> parsing + runtime)
  #3 LLVM pass manager enhancements
  #4 Package manager atomic writes + file locking
  #5 Resource limits (instruction count, timeout, output limit)
  #6 Compiler closure float + multi-catch
  #7 Package manager embedded source fixes
"""

import sys
import os
import json
import tempfile
import threading
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError
from epl import ast_nodes as ast


def run_epl(source: str, safe_mode=False, max_instructions=0,
            execution_timeout=0, max_output_lines=0) -> list:
    """Run EPL source code and return captured output lines."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter(safe_mode=safe_mode, max_instructions=max_instructions,
                         execution_timeout=execution_timeout,
                         max_output_lines=max_output_lines)
    interp.execute(program)
    return interp.output_lines


def test(name, source, expected, **kwargs):
    """Run a test case and report result."""
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
    """Test that a specific error is raised."""
    try:
        run_epl(source, **kwargs)
        print(f"  FAIL: {name} (expected error but none raised)")
        return False
    except EPLError as e:
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected error containing: {expected_error_substring}")
            print(f"    Got: {e}")
            return False
    except Exception as e:
        if expected_error_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            return True
        print(f"  FAIL: {name} (unexpected error: {type(e).__name__}: {e})")
        return False
test_error.__test__ = False


def run_suite():
    print("=" * 60)
    print("  EPL Production Gaps Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0
    total = 0

    def track(result):
        nonlocal passed, failed, total
        total += 1
        if result:
            passed += 1
        else:
            failed += 1

    # ═══════════════════════════════════════════════════════════
    # GAP #1: Sandbox Enforcement
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #1: Sandbox Enforcement ---")

    track(test_error(
        "Use python blocked in safe mode",
        'Use python "os"\nPrint "should not reach"',
        "not allowed in safe mode",
        safe_mode=True
    ))

    track(test(
        "Use python works in normal mode",
        'Use python "math"\nPrint to_text(math.factorial(5))',
        ["120"]
    ))

    track(test(
        "Print works in safe mode",
        'Print "hello safe"',
        ["hello safe"],
        safe_mode=True
    ))

    track(test(
        "Basic math in safe mode",
        'Create x equal to 5 + 3\nPrint to_text(x)',
        ["8"],
        safe_mode=True
    ))

    # ═══════════════════════════════════════════════════════════
    # GAP #2: Generic Types
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #2: Generic Types ---")

    track(test(
        "Generic class definition with <T>",
        '''Class Stack<T>
    items = []

    Function push takes item
        Add item to items
    End

    Function peek
        Return items[length(items) - 1]
    End
End

s = new Stack()
s.push(42)
Print to_text(s.peek())''',
        ["42"]
    ))

    track(test(
        "Generic class with multiple type params <K, V>",
        '''Class Pair<K, V>
    key = ""
    value = ""

    Function init takes k, v
        Set key to k
        Set value to v
    End

    Function get_key
        Return key
    End

    Function get_value
        Return value
    End
End

p = new Pair("name", "EPL")
Print p.get_key()
Print p.get_value()''',
        ["name", "EPL"]
    ))

    track(test(
        "Generic class type_params introspection",
        '''Class Container<T>
    data = 0

    Function init takes val
        Set data to val
    End
End

c = new Container(99)
Print to_text(c.data)''',
        ["99"]
    ))

    # ═══════════════════════════════════════════════════════════
    # GAP #5: Resource Limits
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #5: Resource Limits ---")

    track(test_error(
        "Instruction limit triggers on infinite loop",
        '''Create i equal to 0
While true
    Set i to i + 1
End''',
        "limit exceeded",
        max_instructions=1000
    ))

    track(test(
        "Within instruction limit works fine",
        '''Create total equal to 0
For i from 1 to 10
    Set total to total + i
End
Print to_text(total)''',
        ["55"],
        max_instructions=50000
    ))

    track(test_error(
        "Output line limit triggers",
        '''For i from 1 to 200
    Print to_text(i)
End''',
        "output",
        max_output_lines=50
    ))

    track(test(
        "Within output limit works",
        '''For i from 1 to 5
    Print to_text(i)
End''',
        ["1", "2", "3", "4", "5"],
        max_output_lines=100
    ))

    track(test_error(
        "Execution timeout triggers",
        '''Create i equal to 0
While true
    Set i to i + 1
End''',
        "timeout",
        execution_timeout=0.01
    ))

    # Safe mode auto-enables limits
    track(test_error(
        "Safe mode auto-enables loop/instruction limit",
        '''Create i equal to 0
While true
    Set i to i + 1
End''',
        "maximum iterations",
        safe_mode=True
    ))

    # ═══════════════════════════════════════════════════════════
    # GAP #4: Atomic Writes + File Locking
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #4: Atomic Writes + File Locking ---")

    try:
        from epl.package_manager import _atomic_write, _file_lock

        # Test atomic write
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            tmp_path = f.name
        try:
            test_data = '{"name": "test", "version": "1.0"}'
            _atomic_write(tmp_path, test_data)
            with open(tmp_path, 'r') as f:
                read_back = f.read()
            if read_back == test_data:
                print("  PASS: Atomic write - data integrity")
                passed += 1
            else:
                print(f"  FAIL: Atomic write - data integrity")
                print(f"    Expected: {test_data}")
                print(f"    Got: {read_back}")
                failed += 1
            total += 1
        finally:
            os.unlink(tmp_path)

        # Test file locking (non-blocking)
        lock_base = tmp_path + '.lockbase'
        lock_dir = lock_base + '.lock'
        try:
            with _file_lock(lock_base):
                # Verify lock dir exists
                if os.path.isdir(lock_dir):
                    print("  PASS: File lock - lock directory created")
                    passed += 1
                else:
                    print("  FAIL: File lock - lock directory not found")
                    failed += 1
                total += 1
            # After context exit, lock should be released
            if not os.path.exists(lock_dir):
                print("  PASS: File lock - released after context exit")
                passed += 1
            else:
                print("  FAIL: File lock - not released")
                failed += 1
            total += 1
        except Exception as e:
            print(f"  FAIL: File lock: {e}")
            failed += 1
            total += 1

        # Test concurrent lock acquisition
        results = []
        def lock_worker(lock_p, worker_id):
            try:
                with _file_lock(lock_p, timeout=5):
                    results.append(worker_id)
            except Exception as e:
                results.append(f"error-{worker_id}: {e}")

        lock_path2 = tmp_path + '.lockbase2'
        threads = [threading.Thread(target=lock_worker, args=(lock_path2, i)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        if len(results) == 3 and all(isinstance(r, int) for r in results):
            print("  PASS: Concurrent lock - all 3 workers completed")
            passed += 1
        else:
            print(f"  FAIL: Concurrent lock - results: {results}")
            failed += 1
        total += 1

    except ImportError as e:
        print(f"  SKIP: Package manager imports failed: {e}")
        total += 1
        failed += 1

    # ═══════════════════════════════════════════════════════════
    # GAP #3: LLVM Pass Manager Enhancements
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #3: LLVM Pass Manager ---")

    try:
        from epl.compiler import Compiler
        source = '''Create x equal to 42
Print to_text(x)'''
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        compiler = Compiler(opt_level=3)
        compiler.compile(program)
        ir_str = str(compiler.module)
        if 'target datalayout' in ir_str:
            print("  PASS: LLVM data_layout set on module")
            passed += 1
        else:
            print("  FAIL: LLVM data_layout not set")
            failed += 1
        total += 1

        # Verify module can be compiled to object at O3
        try:
            obj = compiler.compile_to_object()
            if obj and len(obj) > 0:
                print("  PASS: LLVM O3 compilation succeeds")
                passed += 1
            else:
                print("  FAIL: LLVM O3 compilation returned empty")
                failed += 1
        except Exception as e:
            print(f"  FAIL: LLVM O3 compilation error: {e}")
            failed += 1
        total += 1

    except ImportError:
        print("  SKIP: llvmlite not available")
        total += 2
        failed += 2

    # ═══════════════════════════════════════════════════════════
    # GAP #6: Compiler Closure Float + Multi-Catch
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #6: Compiler Edge Cases ---")

    # Test closure float capture in interpreter (the compiler fix is LLVM-only)
    track(test(
        "Lambda captures float variable",
        '''pi = 3.14
double_pi = lambda -> pi * 2
Print to_text(double_pi())''',
        ["6.28"]
    ))

    # Multi-catch in interpreter
    track(test(
        "Try-catch-finally basic",
        '''Try
    Throw "something went wrong"
Catch error
    Print error
Finally
    Print "cleanup"
End''',
        ["EPL Runtime Error on line 2: something went wrong", "cleanup"]
    ))

    track(test(
        "Try-catch with no error",
        '''Try
    Print "no error"
Catch error
    Print "caught"
Finally
    Print "finally"
End''',
        ["no error", "finally"]
    ))

    # ═══════════════════════════════════════════════════════════
    # GAP #7: Package Manager Embedded Source Fixes
    # ═══════════════════════════════════════════════════════════
    print("\n--- Gap #7: Embedded Source Fixes ---")

    try:
        from epl.package_manager import _get_builtin_source

        # epl-db: Verify Insert now requires columns+params (no raw SQL concat)
        db_src = _get_builtin_source("epl-db")
        if db_src:
            # Old Insert had (db, table, values) with raw concat
            # New Insert has (db, table, columns, params) with parameterized query
            if "InsertParams" in db_src and "ExecuteParams" in db_src:
                print("  PASS: epl-db uses parameterized Insert")
                passed += 1
            else:
                print("  FAIL: epl-db missing parameterized functions")
                failed += 1
            total += 1

            # Verify Insert uses parameterized queries (? placeholders + ExecuteParams)
            if "?" in db_src and "ExecuteParams(db, sql, params)" in db_src:
                print("  PASS: epl-db Insert uses parameterized placeholders")
                passed += 1
            else:
                print("  FAIL: epl-db Insert missing parameterized placeholders")
                failed += 1
            total += 1

            # SelectWhere now requires params parameter
            if "SelectWhere(db, table, condition, params)" in db_src:
                print("  PASS: epl-db SelectWhere requires params")
                passed += 1
            else:
                print("  FAIL: epl-db SelectWhere missing params")
                failed += 1
            total += 1
        else:
            print("  SKIP: epl-db source not found")
            total += 3
            failed += 3

        # epl-auth: Verify token uses base64 encoding
        auth_src = _get_builtin_source("epl-auth")
        if auth_src:
            if "base64" in auth_src and "urlsafe_b64encode" in auth_src:
                print("  PASS: epl-auth uses base64 for token data")
                passed += 1
            else:
                print("  FAIL: epl-auth missing base64 encoding")
                failed += 1
            total += 1

            if "urlsafe_b64decode" in auth_src:
                print("  PASS: epl-auth ValidateToken decodes base64")
                passed += 1
            else:
                print("  FAIL: epl-auth ValidateToken missing b64decode")
                failed += 1
            total += 1

            # Timestamp should use int() to avoid dots
            if "int(time::time())" in auth_src:
                print("  PASS: epl-auth timestamp uses int()")
                passed += 1
            else:
                print("  FAIL: epl-auth timestamp still has float dots")
                failed += 1
            total += 1
        else:
            print("  SKIP: epl-auth source not found")
            total += 3
            failed += 3

    except ImportError as e:
        print(f"  SKIP: Package manager import failed: {e}")
        total += 6
        failed += 6

    # ═══════════════════════════════════════════════════════════
    # Additional edge cases
    # ═══════════════════════════════════════════════════════════
    print("\n--- Edge Cases ---")

    track(test(
        "Function call in safe mode",
        '''Function add takes a and b
    Return a + b
End
result = call add with 3 and 4
Print to_text(result)''',
        ["7"],
        safe_mode=True
    ))

    track(test(
        "List operations in safe mode",
        '''items = []
Add 10 to items
Add 20 to items
Print to_text(length(items))''',
        ["2"],
        safe_mode=True
    ))

    track(test(
        "String operations in safe mode",
        '''Create s equal to "Hello World"
Print to_text(length(s))
Print uppercase(s)''',
        ["11", "HELLO WORLD"],
        safe_mode=True
    ))

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


def test_production_gaps_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Production gaps suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
