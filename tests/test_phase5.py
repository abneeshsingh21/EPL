"""
EPL Phase 5 Test Suite — Production Ready
Tests for: VM as Default, LLVM Compiler Hardening, MicroPython Transpiler,
           C FFI module, Benchmark command.
"""

import sys
import os
import tempfile
import time
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0


def _start_tracker():
    _TrackerState.current = {
        "passed": 0,
        "failed": 0,
        "failures": [],
    }


def _finish_tracker():
    tracker = _TrackerState.current
    _TrackerState.current = None
    if tracker is None:
        return
    _TrackerState.total_pass += tracker["passed"]
    _TrackerState.total_fail += tracker["failed"]
    if tracker["failures"]:
        raise AssertionError("\n".join(tracker["failures"]))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            _finish_tracker()

    return wrapper


def check(name, condition, detail=""):
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("check() called outside an active test tracker.")
    if condition:
        print(f"  PASS: {name}")
        tracker["passed"] += 1
    else:
        print(f"  FAIL: {name} {detail}")
        tracker["failed"] += 1
        tracker["failures"].append(f"{name}: {detail}" if detail else name)


def run_epl(source):
    """Run EPL via interpreter, return output lines."""
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.interpreter import Interpreter
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines


def run_vm(source):
    """Run EPL via bytecode VM, return output lines."""
    from epl.vm import compile_and_run
    result = compile_and_run(source)
    return result['output']


def parse_epl(source):
    """Parse EPL source, return AST program node."""
    from epl.lexer import Lexer
    from epl.parser import Parser
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


# ══════════════════════════════════════════════════════════
# 5.1  Bytecode VM as Default
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_vm_default():
    print("\n=== 5.1 Bytecode VM as Default ===")

    # T1: VM can run basic program
    try:
        result = run_vm('Print "Hello from VM"')
        check("VM runs basic program", result == ["Hello from VM"])
    except Exception as e:
        check("VM runs basic program", False, str(e))

    # T2: VM runs arithmetic
    try:
        result = run_vm('Print 2 + 3 * 4')
        check("VM arithmetic", result == ["14"])
    except Exception as e:
        check("VM arithmetic", False, str(e))

    # T3: VM runs variables
    try:
        result = run_vm('x = 42\nPrint x')
        check("VM variables", result == ["42"])
    except Exception as e:
        check("VM variables", False, str(e))

    # T4: VM runs functions
    try:
        result = run_vm('Function add takes a, b\n    Return a + b\nEnd\nPrint add(3, 7)')
        check("VM functions", result == ["10"])
    except Exception as e:
        check("VM functions", False, str(e))

    # T5: VM runs loops
    try:
        result = run_vm('total = 0\nRepeat 5 times\n    Increase total by 1\nEnd\nPrint total')
        check("VM loops", result == ["5"])
    except Exception as e:
        check("VM loops", False, str(e))

    # T6: VM runs conditionals
    try:
        result = run_vm('x = 10\nIf x > 5 Then\n    Print "big"\nOtherwise\n    Print "small"\nEnd')
        check("VM conditionals", result == ["big"])
    except Exception as e:
        check("VM conditionals", False, str(e))

    # T7: VM runs lists
    try:
        result = run_vm('items = [1, 2, 3]\nPrint length(items)')
        check("VM lists", result == ["3"])
    except Exception as e:
        check("VM lists", False, str(e))

    # T8: Interpreter still works as fallback
    try:
        result = run_epl('Print "Hello from Interpreter"')
        check("Interpreter fallback works", result == ["Hello from Interpreter"])
    except Exception as e:
        check("Interpreter fallback works", False, str(e))

    # T9: VM runs string operations
    try:
        result = run_vm('Print upper("hello")')
        check("VM string builtins", "HELLO" in str(result))
    except Exception as e:
        check("VM string builtins", False, str(e))

    # T10: VM runs classes
    try:
        result = run_vm('Class Dog\n    name = "Rex"\nEnd\nPrint "ok"')
        check("VM classes", result == ["ok"])
    except Exception as e:
        check("VM classes", False, str(e))

    # T11: Benchmark function exists
    try:
        from main import run_benchmark
        check("Benchmark function exists", callable(run_benchmark))
    except Exception as e:
        check("Benchmark function exists", False, str(e))

    # T12: VM speed > 0 (simple timing check)
    try:
        src = 'x = 0\nRepeat 100 times\n    Increase x by 1\nEnd'
        t0 = time.time()
        run_vm(src)
        vm_time = time.time() - t0
        check("VM completes in < 5 seconds", vm_time < 5.0, f"took {vm_time:.2f}s")
    except Exception as e:
        check("VM completes in < 5 seconds", False, str(e))

    # T13: VM dict support
    try:
        result = run_vm('d = Map with a = 1 and b = 2\nPrint keys(d)')
        check("VM dict support", len(result) > 0)
    except Exception as e:
        check("VM dict support", False, str(e))

    # T14: VM for-each loop
    try:
        result = run_vm('items = [10, 20, 30]\nFor each item in items\n    Print item\nEnd')
        check("VM for-each loop", result == ["10", "20", "30"])
    except Exception as e:
        check("VM for-each loop", False, str(e))

    # T15: VM try-catch
    try:
        src = 'Try\n    Throw "oops"\nCatch e\n    Print "caught"\nEnd'
        result = run_vm(src)
        check("VM try-catch", any("caught" in str(r) for r in result))
    except Exception as e:
        check("VM try-catch", False, str(e))


# ══════════════════════════════════════════════════════════
# 5.2  LLVM Compiler Hardening
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_llvm_hardening():
    print("\n=== 5.2 LLVM Compiler Hardening ===")

    # T1: Compiler module imports
    try:
        from epl.compiler import Compiler
        check("Compiler module imports", True)
    except ImportError as e:
        check("Compiler module imports", False, str(e))
        return

    # T2: Compiler can be instantiated
    try:
        c = Compiler()
        check("Compiler instantiation", c is not None)
    except Exception as e:
        check("Compiler instantiation", False, str(e))

    # T3: Compile basic expression
    try:
        program = parse_epl('Print 42')
        c = Compiler()
        c.compile(program)
        ir = str(c.module)
        check("Compile basic expression to IR", 'epl_print' in ir or '@main' in ir or 'define' in ir)
    except Exception as e:
        check("Compile basic expression to IR", False, str(e))

    # T4: Compile variables
    try:
        program = parse_epl('x = 10\nPrint x')
        c = Compiler()
        c.compile(program)
        check("Compile variables to IR", True)
    except Exception as e:
        check("Compile variables to IR", False, str(e))

    # T5: Compile function
    try:
        program = parse_epl('Function add takes a, b\n    Return a + b\nEnd\nPrint add(3, 4)')
        c = Compiler()
        c.compile(program)
        check("Compile function to IR", True)
    except Exception as e:
        check("Compile function to IR", False, str(e))

    # T6: Compile class
    try:
        program = parse_epl('Class Point\n    x = 0\n    y = 0\nEnd')
        c = Compiler()
        c.compile(program)
        check("Compile class to IR", True)
    except Exception as e:
        check("Compile class to IR", False, str(e))

    # T7: Compile conditional
    try:
        program = parse_epl('x = 5\nIf x > 3 Then\n    Print "yes"\nEnd')
        c = Compiler()
        c.compile(program)
        check("Compile conditional to IR", True)
    except Exception as e:
        check("Compile conditional to IR", False, str(e))

    # T8: Compile loop
    try:
        program = parse_epl('Repeat 3 times\n    Print "loop"\nEnd')
        c = Compiler()
        c.compile(program)
        check("Compile loop to IR", True)
    except Exception as e:
        check("Compile loop to IR", False, str(e))

    # T9: Compile string operations
    try:
        program = parse_epl('s = "hello"\nPrint s')
        c = Compiler()
        c.compile(program)
        check("Compile strings to IR", True)
    except Exception as e:
        check("Compile strings to IR", False, str(e))

    # T10: Compiler generates valid LLVM IR structure
    try:
        program = parse_epl('Print 1 + 2')
        c = Compiler()
        c.compile(program)
        ir = str(c.module)
        check("Valid LLVM IR structure", 'define' in ir)
    except Exception as e:
        check("Valid LLVM IR structure", False, str(e))


# ══════════════════════════════════════════════════════════
# 5.3  Embedded/IoT Target (MicroPython Transpiler)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_micropython_transpiler():
    print("\n=== 5.3 MicroPython Transpiler ===")

    # T1: Module imports
    try:
        from epl.micropython_transpiler import MicroPythonTranspiler, transpile_to_micropython
        check("MicroPython module imports", True)
    except ImportError as e:
        check("MicroPython module imports", False, str(e))
        return

    # T2: Transpiler instantiation
    try:
        t = MicroPythonTranspiler(target='esp32')
        check("Transpiler instantiation (ESP32)", t is not None and t.target == 'esp32')
    except Exception as e:
        check("Transpiler instantiation (ESP32)", False, str(e))

    # T3: Transpiler for Pico
    try:
        t = MicroPythonTranspiler(target='pico')
        check("Transpiler instantiation (Pico)", t.target == 'pico')
    except Exception as e:
        check("Transpiler instantiation (Pico)", False, str(e))

    # T4: Transpile basic print
    try:
        program = parse_epl('Print "Hello"')
        result = transpile_to_micropython(program, target='esp32')
        check("Transpile Say statement", 'print(' in result and "'Hello'" in result)
    except Exception as e:
        check("Transpile Say statement", False, str(e))

    # T5: Transpile variable
    try:
        program = parse_epl('x = 42\nPrint x')
        result = transpile_to_micropython(program)
        check("Transpile variables", 'x = 42' in result and 'print(x)' in result)
    except Exception as e:
        check("Transpile variables", False, str(e))

    # T6: Transpile function
    try:
        program = parse_epl('Function greet takes name\n    Print "Hello " + name\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile function", 'def greet(name):' in result)
    except Exception as e:
        check("Transpile function", False, str(e))

    # T7: Transpile if/otherwise
    try:
        program = parse_epl('x = 10\nIf x > 5 Then\n    Print "big"\nOtherwise\n    Print "small"\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile if/else", 'if ' in result and 'else:' in result)
    except Exception as e:
        check("Transpile if/else", False, str(e))

    # T8: Transpile while loop
    try:
        program = parse_epl('x = 0\nWhile x < 5\n    Increase x by 1\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile while loop", 'while ' in result)
    except Exception as e:
        check("Transpile while loop", False, str(e))

    # T9: Transpile for-each
    try:
        program = parse_epl('For each item in [1, 2, 3]\n    Print item\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile for-each", 'for item in' in result)
    except Exception as e:
        check("Transpile for-each", False, str(e))

    # T10: Transpile repeat loop
    try:
        program = parse_epl('Repeat 5 times\n    Print "hi"\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile repeat loop", 'for __i in range(' in result)
    except Exception as e:
        check("Transpile repeat loop", False, str(e))

    # T11: Transpile class
    try:
        program = parse_epl('Class Dog\n    name = "Rex"\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile class", 'class Dog' in result)
    except Exception as e:
        check("Transpile class", False, str(e))

    # T12: Transpile list literal
    try:
        program = parse_epl('items = [1, 2, 3]')
        result = transpile_to_micropython(program)
        check("Transpile list literal", '[1, 2, 3]' in result)
    except Exception as e:
        check("Transpile list literal", False, str(e))

    # T13: Transpile dict literal
    try:
        program = parse_epl('d = Map with a = 1')
        result = transpile_to_micropython(program)
        check("Transpile dict literal", 'a' in result and '1' in result)
    except Exception as e:
        check("Transpile dict literal", False, str(e))

    # T14: Output contains ESP32 header
    try:
        program = parse_epl('Print "test"')
        result = transpile_to_micropython(program, target='esp32')
        check("ESP32 header present", 'ESP32' in result)
    except Exception as e:
        check("ESP32 header present", False, str(e))

    # T15: Output contains Pico header
    try:
        program = parse_epl('Print "test"')
        result = transpile_to_micropython(program, target='pico')
        check("Pico header present", 'Pico' in result)
    except Exception as e:
        check("Pico header present", False, str(e))

    # T16: Output contains gc.collect
    try:
        program = parse_epl('Print 1')
        result = transpile_to_micropython(program)
        check("gc.collect at end", 'gc.collect()' in result)
    except Exception as e:
        check("gc.collect at end", False, str(e))

    # T17: Transpile try/catch
    try:
        program = parse_epl('Try\n    Print "ok"\nCatch e\n    Print e\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile try/catch", 'try:' in result and 'except' in result)
    except Exception as e:
        check("Transpile try/catch", False, str(e))

    # T18: Transpile return
    try:
        program = parse_epl('Function f\n    Return 42\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile return", 'return 42' in result)
    except Exception as e:
        check("Transpile return", False, str(e))

    # T19: Hardware scan detects GPIO keywords
    try:
        from epl.micropython_transpiler import MicroPythonTranspiler
        t = MicroPythonTranspiler()
        # Manually test scan with a mock statement list
        check("Hardware scanner exists", hasattr(t, '_scan_hardware'))
    except Exception as e:
        check("Hardware scanner exists", False, str(e))

    # T20: Transpile ternary expression
    try:
        program = parse_epl('x = 5\nresult = x if x > 3 otherwise 0')
        result = transpile_to_micropython(program)
        check("Transpile ternary", 'if' in result)
    except Exception as e:
        check("Transpile ternary", False, str(e))

    # T21: CLI function exists
    try:
        from main import transpile_micropython
        check("CLI transpile_micropython exists", callable(transpile_micropython))
    except Exception as e:
        check("CLI transpile_micropython exists", False, str(e))

    # T22: Transpile break/continue
    try:
        program = parse_epl('While true\n    Break\nEnd')
        result = transpile_to_micropython(program)
        check("Transpile break", 'break' in result)
    except Exception as e:
        check("Transpile break", False, str(e))

    # T23: Safe name handling
    try:
        t = MicroPythonTranspiler()
        check("Safe name: reserved word", t._safe_name('class') == 'class_')
        check("Safe name: normal word", t._safe_name('myvar') == 'myvar')
    except Exception as e:
        check("Safe name handling", False, str(e))


# ══════════════════════════════════════════════════════════
# 5.4  C FFI (Foreign Function Interface)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_ffi():
    print("\n=== 5.4 C FFI ===")

    # T1: Module imports
    try:
        from epl.ffi import ffi_open, ffi_call, ffi_close, ffi_find, ffi_types, FFILibrary
        check("FFI module imports", True)
    except ImportError as e:
        check("FFI module imports", False, str(e))
        return

    # T2: ffi_types returns supported types
    try:
        types = ffi_types()
        check("ffi_types returns list", isinstance(types, list) and len(types) > 10)
    except Exception as e:
        check("ffi_types returns list", False, str(e))

    # T3: Common types present
    try:
        types = ffi_types()
        for t in ['int', 'float', 'double', 'char_p', 'void', 'bool']:
            check(f"Type '{t}' supported", t in types)
    except Exception as e:
        check("Common types present", False, str(e))

    # T4: ffi_find returns path for C library
    try:
        path = ffi_find('c')
        # On some systems this returns None, on others a path
        check("ffi_find returns for 'c'", True)  # Just check it doesn't crash
    except Exception as e:
        check("ffi_find returns for 'c'", False, str(e))

    # T5: ffi_find for nonexistent returns None
    try:
        path = ffi_find('nonexistent_lib_12345')
        check("ffi_find nonexistent returns None", path is None)
    except Exception as e:
        check("ffi_find nonexistent returns None", False, str(e))

    # T6: FFILibrary class exists
    try:
        check("FFILibrary class exists", FFILibrary is not None)
    except Exception as e:
        check("FFILibrary class exists", False, str(e))

    # T7: Open C standard library (platform-dependent)
    lib = None
    try:
        if sys.platform == 'win32':
            lib = ffi_open('msvcrt')
        else:
            lib = ffi_open('c')
        check("Open C library", isinstance(lib, FFILibrary))
    except Exception as e:
        check("Open C library", False, str(e))

    # T8: Call abs() from C library
    if lib is not None:
        try:
            result = ffi_call(lib, 'abs', 'int', [-42], ['int'])
            check("Call C abs(-42)", result == 42)
        except Exception as e:
            check("Call C abs(-42)", False, str(e))

        # T9: Call abs with positive number
        try:
            result = ffi_call(lib, 'abs', 'int', [7], ['int'])
            check("Call C abs(7)", result == 7)
        except Exception as e:
            check("Call C abs(7)", False, str(e))

        # T10: Close library
        try:
            ffi_close(lib)
            check("Close C library", True)
        except Exception as e:
            check("Close C library", False, str(e))
    else:
        check("Call C abs(-42)", False, "library not loaded")
        check("Call C abs(7)", False, "library not loaded")
        check("Close C library", False, "library not loaded")

    # T11: Open math library and call sqrt
    try:
        if sys.platform == 'win32':
            math_lib = ffi_open('msvcrt')
        else:
            math_lib = ffi_open('m')
        result = ffi_call(math_lib, 'sqrt', 'double', [16.0], ['double'])
        check("Call C sqrt(16)", abs(result - 4.0) < 0.001)
        ffi_close(math_lib)
    except Exception as e:
        check("Call C sqrt(16)", False, str(e))

    # T12: Error on nonexistent function
    try:
        if sys.platform == 'win32':
            lib2 = ffi_open('msvcrt')
        else:
            lib2 = ffi_open('c')
        try:
            ffi_call(lib2, 'nonexistent_func_12345', 'int', [], [])
            check("Error on nonexistent function", False, "should have raised")
        except AttributeError:
            check("Error on nonexistent function", True)
        finally:
            ffi_close(lib2)
    except Exception as e:
        check("Error on nonexistent function", False, str(e))

    # T13: Error on wrong argument count
    try:
        from epl.ffi import ffi_call as fc
        if sys.platform == 'win32':
            lib3 = ffi_open('msvcrt')
        else:
            lib3 = ffi_open('c')
        try:
            fc(lib3, 'abs', 'int', [1, 2], ['int'])
            check("Error on arg count mismatch", False, "should have raised")
        except ValueError:
            check("Error on arg count mismatch", True)
        finally:
            ffi_close(lib3)
    except Exception as e:
        check("Error on arg count mismatch", False, str(e))

    # T14: ffi_close on non-library raises nothing
    try:
        ffi_close("not a library")
        check("ffi_close on non-library is safe", True)
    except Exception as e:
        check("ffi_close on non-library is safe", False, str(e))

    # T15: FFI builtins registered in interpreter
    try:
        from epl.interpreter import BUILTINS
        for name in ('ffi_open', 'ffi_call', 'ffi_close', 'ffi_find', 'ffi_types'):
            check(f"'{name}' in BUILTINS", name in BUILTINS)
    except Exception as e:
        check("FFI builtins in interpreter", False, str(e))

    # T16: FFI builtins registered in VM
    try:
        from epl.vm import VM
        vm = VM.__new__(VM)
        vm._builtins = {}
        vm.stack = []
        vm.call_stack = []
        dispatch = vm._build_builtin_dispatch()
        for name in ('ffi_open', 'ffi_call', 'ffi_close', 'ffi_find', 'ffi_types'):
            check(f"VM dispatch has '{name}'", name in dispatch)
    except Exception as e:
        check("FFI builtins in VM dispatch", False, str(e))

    # T17: register_ffi_builtins helper
    try:
        from epl.ffi import register_ffi_builtins
        reg = register_ffi_builtins()
        check("register_ffi_builtins returns dict", isinstance(reg, dict) and len(reg) == 5)
    except Exception as e:
        check("register_ffi_builtins", False, str(e))


# ══════════════════════════════════════════════════════════
# 5.5  Version & Integration
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_version_integration():
    print("\n=== 5.5 Version & Integration ===")

    # T1: Version is 7.0.0
    try:
        from epl import __version__
        check("Version is 7.0.0", __version__ == "7.0.0")
    except Exception as e:
        check("Version is 7.0.0", False, str(e))

    # T2: VM module importable
    try:
        from epl.vm import compile_and_run, VM, BytecodeCompiler
        check("VM module importable", True)
    except ImportError as e:
        check("VM module importable", False, str(e))

    # T3: Compiler module importable
    try:
        from epl.compiler import Compiler
        check("Compiler module importable", True)
    except ImportError as e:
        check("Compiler module importable", False, str(e))

    # T4: MicroPython module importable
    try:
        from epl.micropython_transpiler import transpile_to_micropython
        check("MicroPython module importable", True)
    except ImportError as e:
        check("MicroPython module importable", False, str(e))

    # T5: FFI module importable
    try:
        from epl.ffi import ffi_open, ffi_call
        check("FFI module importable", True)
    except ImportError as e:
        check("FFI module importable", False, str(e))

    # T6: All Phase 5 AST nodes usable
    try:
        from epl import ast_nodes as ast
        check("AST module has PrintStatement", hasattr(ast, 'PrintStatement'))
        check("AST module has ClassDef", hasattr(ast, 'ClassDef'))
        check("AST module has FunctionDef", hasattr(ast, 'FunctionDef'))
    except Exception as e:
        check("AST module check", False, str(e))


# ══════════════════════════════════════════════════════════
#  Run all Phase 5 tests
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 60)
    print("  EPL Phase 5 Test Suite — Production Ready")
    print("=" * 60)

    test_functions = [
        test_vm_default,
        test_llvm_hardening,
        test_micropython_transpiler,
        test_ffi,
        test_version_integration,
    ]
    failed_sections = 0

    for fn in test_functions:
        try:
            fn()
        except AssertionError as exc:
            failed_sections += 1
            print(str(exc))

    print("\n" + "=" * 60)
    print(
        f"  Phase 5 Results: {_TrackerState.total_pass} passed, "
        f"{_TrackerState.total_fail} failed "
        f"({_TrackerState.total_pass + _TrackerState.total_fail} total)"
    )
    print("=" * 60)

    sys.exit(1 if failed_sections > 0 else 0)
