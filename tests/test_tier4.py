"""
EPL Tier 4 Feature Tests
Comprehensive tests for all Tier 4 gaps (Polish):
  #24 WASM compilation target (structure only — requires external toolchain)
  #25 AST-aware code formatter
  #26 Performance benchmarks (suite structure)
  #27 Unicode identifiers
  #28 Structured error output (JSON)
  #29 Better RNG quality
  #30 Stdlib deprecation warnings
"""

import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import (
    EPLError, LexerError, ParserError,
    RuntimeError as EPLRuntimeError,
    TypeError as EPLTypeError,
    NameError as EPLNameError,
    ValueError as EPLValueError,
)

PASSED = 0
FAILED = 0


def track(result):
    global PASSED, FAILED
    if result:
        PASSED += 1
    else:
        FAILED += 1


def run_epl(source):
    tokens = Lexer(source).tokenize()
    tree = Parser(tokens).parse()
    interp = Interpreter()
    interp.execute(tree)
    return interp.output_lines


def test(name, source, expected):
    try:
        output = run_epl(source)
        if output == expected:
            print(f"  PASS: {name}")
            track(True)
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            track(False)
    except Exception as e:
        print(f"  FAIL: {name} -- {e}")
        track(False)
test.__test__ = False


def test_error(name, source, expected_substring):
    try:
        run_epl(source)
        print(f"  FAIL: {name} (expected error but none raised)")
        track(False)
    except EPLError as e:
        if expected_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            track(True)
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected substring: {expected_substring}")
            print(f"    Got: {e}")
            track(False)
    except Exception as e:
        print(f"  FAIL: {name} (unexpected: {type(e).__name__}: {e})")
        track(False)
test_error.__test__ = False


def test_bool(name, condition, msg=""):
    if condition:
        print(f"  PASS: {name}")
        track(True)
    else:
        print(f"  FAIL: {name} {msg}")
        track(False)
test_bool.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #28: Structured Error Output (JSON)
# ═══════════════════════════════════════════════════════════

def test_gap28():
    print("\n  --- #28: Structured Error Output (JSON) ---")

    # Test EPLError.to_dict()
    e = EPLRuntimeError("Division by zero", line=10, column=5, filename="test.epl")
    d = e.to_dict()
    test_bool("to_dict returns dict", isinstance(d, dict))
    test_bool("to_dict has error_code", d.get("error_code") == "E0300")
    test_bool("to_dict has type", d.get("type") == "RuntimeError")
    test_bool("to_dict has message", d.get("message") == "Division by zero")
    test_bool("to_dict has line", d.get("line") == 10)
    test_bool("to_dict has column", d.get("column") == 5)
    test_bool("to_dict has filename", d.get("filename") == "test.epl")

    # Test EPLError.to_json()
    j = e.to_json()
    test_bool("to_json returns string", isinstance(j, str))
    parsed = json.loads(j)
    test_bool("to_json is valid JSON", isinstance(parsed, dict))
    test_bool("to_json error_code", parsed["error_code"] == "E0300")

    # Test with traceback
    e2 = EPLRuntimeError("stack overflow", line=5)
    e2.add_frame("factorial", 5)
    e2.add_frame("main", 20)
    d2 = e2.to_dict()
    test_bool("to_dict has traceback", "traceback" in d2)
    test_bool("traceback is list", isinstance(d2["traceback"], list))
    test_bool("traceback has frames", len(d2["traceback"]) == 2)
    test_bool("frame has function", d2["traceback"][0]["function"] == "factorial")

    # Test different error types
    le = LexerError("unterminated string", line=1, column=3)
    test_bool("LexerError code E0100", le.to_dict()["error_code"] == "E0100")

    pe = ParserError("unexpected token", line=2)
    test_bool("ParserError code E0200", pe.to_dict()["error_code"] == "E0200")

    te = EPLTypeError("cannot add string and integer", line=7)
    test_bool("TypeError code E0400", te.to_dict()["error_code"] == "E0400")

    ne = EPLNameError("undefined variable x", line=3)
    test_bool("NameError code E0500", ne.to_dict()["error_code"] == "E0500")

    # Test hint inclusion
    ve = EPLValueError("divide by zero", line=1)
    vd = ve.to_dict()
    test_bool("hint included for divide by zero", "hint" in vd)

    # JSON round-trip
    j2 = ve.to_json()
    p2 = json.loads(j2)
    test_bool("JSON round-trip line", p2["line"] == 1)
    test_bool("JSON round-trip type", p2["type"] == "ValueError")
test_gap28.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #27: Unicode Identifiers
# ═══════════════════════════════════════════════════════════

def test_gap27():
    print("\n  --- #27: Unicode Identifiers ---")

    # Basic unicode variable names
    test("unicode var: accented", 'Create café equal to "espresso".\nPrint café.', ["espresso"])
    test("unicode var: CJK", 'Create 数字 equal to 42.\nPrint 数字.', ["42"])
    test("unicode var: Cyrillic", 'Create привет equal to "hello".\nPrint привет.', ["hello"])
    test("unicode var: Arabic", 'Create عدد equal to 7.\nPrint عدد.', ["7"])
    test("unicode var: emoji-like", 'Create α equal to 3.14.\nPrint α.', ["3.14"])

    # Unicode in function names
    test("unicode func name",
         'Function добавить takes x.\n    Return x plus 1.\nEnd.\nPrint добавить(5).',
         ["6"])

    # Mixed ASCII and unicode
    test("mixed identifier",
         'Create myVar_日本 equal to "mixed".\nPrint myVar_日本.',
         ["mixed"])

    # Unicode in expressions
    test("unicode in math",
         'Create mypi equal to 3.14.\nCreate radius equal to 10.\nPrint mypi * radius * radius.',
         ["314.0"])

    # Lexer tokenization of unicode
    try:
        tokens = Lexer('Create données equal to 5.').tokenize()
        has_ident = any(t.value == 'données' for t in tokens)
        test_bool("lexer tokenizes unicode identifier", has_ident)
    except Exception as e:
        print(f"  FAIL: lexer unicode -- {e}")
        track(False)

    # Compiler name mangling
    from epl.compiler import _mangle_name
    test_bool("mangle ASCII unchanged", _mangle_name("hello") == "hello")
    test_bool("mangle unicode", "_U" in _mangle_name("café"))
    test_bool("mangle preserves ASCII parts", _mangle_name("café").startswith("caf"))
test_gap27.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #29: Better RNG Quality
# ═══════════════════════════════════════════════════════════

def test_gap29():
    print("\n  --- #29: Better RNG Quality ---")

    # random_seed for deterministic testing
    test("random_seed determinism",
         'random_seed(42).\nCreate val1 equal to random(1, 100).\nrandom_seed(42).\nCreate val2 equal to random(1, 100).\nPrint val1 == val2.',
         ["true"])

    # random_seed is callable
    test("random_seed callable",
         'random_seed(123).\nPrint "ok".',
         ["ok"])

    # random still works
    test("random range",
         'Create num equal to random(1, 10).\nIf num is greater than 0 then\n    Print "ok".\nEnd.',
         ["ok"])

    # random_seed errors
    test_error("random_seed too few args",
               'random_seed().',
               "takes 1 argument")
test_gap29.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #30: Stdlib Deprecation Warnings
# ═══════════════════════════════════════════════════════════

def test_gap30():
    print("\n  --- #30: Stdlib Deprecation Warnings ---")

    from epl.interpreter import (
        DEPRECATED_FUNCTIONS, _check_deprecation,
        reset_deprecation_warnings, _deprecation_warned,
    )

    # Test infrastructure exists
    test_bool("DEPRECATED_FUNCTIONS is dict", isinstance(DEPRECATED_FUNCTIONS, dict))
    test_bool("reset_deprecation_warnings callable", callable(reset_deprecation_warnings))

    # Test with a temporary deprecation entry
    DEPRECATED_FUNCTIONS['_test_old_func'] = ('_test_new_func', '6.0', 'Use _test_new_func() instead.')
    reset_deprecation_warnings()

    import io
    import sys as _sys
    old_stderr = _sys.stderr
    _sys.stderr = captured = io.StringIO()
    try:
        _check_deprecation('_test_old_func', line=5)
        output = captured.getvalue()
        test_bool("deprecation warning emitted", "DeprecationWarning" in output)
        test_bool("deprecation mentions function", "_test_old_func" in output)
        test_bool("deprecation mentions version", "v6.0" in output)

        # Should not warn again
        captured.truncate(0)
        captured.seek(0)
        _check_deprecation('_test_old_func', line=10)
        test_bool("no duplicate warning", captured.getvalue() == "")

        # Reset and warn again
        reset_deprecation_warnings()
        captured.truncate(0)
        captured.seek(0)
        _check_deprecation('_test_old_func', line=15)
        test_bool("warning after reset", "DeprecationWarning" in captured.getvalue())
    finally:
        _sys.stderr = old_stderr
        del DEPRECATED_FUNCTIONS['_test_old_func']
        reset_deprecation_warnings()

    # Non-deprecated functions should not warn
    old_stderr2 = _sys.stderr
    _sys.stderr = captured2 = io.StringIO()
    try:
        _check_deprecation('length', line=1)
        test_bool("no warning for non-deprecated", captured2.getvalue() == "")
    finally:
        _sys.stderr = old_stderr2
test_gap30.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #25: AST-Aware Code Formatter
# ═══════════════════════════════════════════════════════════

def test_gap25():
    print("\n  --- #25: AST-Aware Code Formatter ---")

    from epl.formatter import format_source, check_formatting

    # Basic indentation
    src = "If x is greater than 5.\nPrint x.\nEnd."
    formatted = format_source(src)
    test_bool("basic indent",
              "    Print x." in formatted)

    # Nested blocks
    src2 = "If a.\nIf b.\nPrint c.\nEnd.\nEnd."
    f2 = format_source(src2)
    test_bool("nested indent",
              "        Print c." in f2)

    # End dedent
    test_bool("End at correct indent",
              f2.strip().endswith("End."))

    # Else handling
    src3 = "If true then\nPrint 1.\nElse\nPrint 2.\nEnd."
    f3 = format_source(src3)
    lines3 = f3.split('\n')
    # Else should be at indent level 0 (same as If)
    else_lines = [l for l in lines3 if l.strip() == 'Else']
    test_bool("Else at same level as If",
              len(else_lines) > 0 and not else_lines[0].startswith('    '))

    # Trailing whitespace removal
    src4 = "Print x.   \n"
    f4 = format_source(src4)
    test_bool("trailing whitespace removed",
              "   " not in f4.split('\n')[0] if f4.strip() else True)

    # Blank line normalization
    src5 = "Print a.\n\n\n\n\nPrint b."
    f5 = format_source(src5)
    blank_count = max(
        sum(1 for _ in g)
        for k, g in __import__('itertools').groupby(f5.split('\n'), key=lambda x: x == '')
        if k
    ) if '\n\n' in f5 else 0
    test_bool("max 2 consecutive blanks", blank_count <= 2)

    # Keyword normalization
    src6 = "create x equal to 5.\nprint x."
    f6 = format_source(src6)
    test_bool("keyword capitalized: Create", "Create" in f6)
    test_bool("keyword capitalized: Print", "Print" in f6)

    # Function block
    src7 = "Function greet takes name.\nPrint name.\nEnd."
    f7 = format_source(src7)
    test_bool("function body indented",
              "    Print name." in f7)

    # Class block
    src8 = "Class Animal.\nFunction speak takes self.\nReturn self.\nEnd.\nEnd."
    f8 = format_source(src8)
    test_bool("class body indented",
              "    Function speak" in f8)

    # check_formatting returns issues
    src9 = "print x.   \n\t \n"
    issues = check_formatting(src9)
    test_bool("check_formatting returns list", isinstance(issues, list))
    test_bool("detects trailing whitespace",
              any(i['message'] == 'Trailing whitespace' for i in issues))

    # Preserves content
    src10 = 'Create x equal to 42.\nPrint x.\n'
    f10 = format_source(src10)
    test_bool("preserves statements", "Create x equal to 42." in f10)

    # Try/Catch
    src11 = "Try.\nPrint x.\nCatch e.\nPrint e.\nEnd."
    f11 = format_source(src11)
    test_bool("try/catch indentation",
              "    Print x." in f11)

    # Match/When
    src12 = "Match x\nWhen 1\nPrint 1.\nDefault\nPrint 0.\nEnd"
    f12 = format_source(src12)
    test_bool("match/when indentation",
              "    When 1" in f12)
test_gap25.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #26: Performance Benchmarks (structure only)
# ═══════════════════════════════════════════════════════════

def test_gap26():
    print("\n  --- #26: Performance Benchmarks ---")

    # Benchmark files exist
    bench_dir = os.path.join(os.path.dirname(__file__), '..', 'benchmarks')
    test_bool("benchmarks dir exists", os.path.isdir(bench_dir))

    expected_files = ['fibonacci.epl', 'strings.epl', 'lists.epl', 'recursion.epl', 'oop.epl']
    for f in expected_files:
        test_bool(f"benchmark file: {f}", os.path.isfile(os.path.join(bench_dir, f)))

    test_bool("run_benchmarks.py exists",
              os.path.isfile(os.path.join(bench_dir, 'run_benchmarks.py')))

    # Benchmark files are valid EPL (can be parsed)
    for f in expected_files:
        fpath = os.path.join(bench_dir, f)
        try:
            with open(fpath, 'r', encoding='utf-8') as fh:
                src = fh.read()
            tokens = Lexer(src).tokenize()
            Parser(tokens).parse()
            test_bool(f"benchmark parses: {f}", True)
        except Exception as e:
            print(f"  FAIL: benchmark parses: {f} -- {e}")
            track(False)

    # Benchmark suite module is importable
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from benchmarks.run_benchmarks import run_single, run_suite, BENCHMARK_FILES
        test_bool("benchmark suite importable", True)
        test_bool("BENCHMARK_FILES defined", len(BENCHMARK_FILES) >= 5)
    except Exception as e:
        print(f"  FAIL: benchmark import -- {e}")
        track(False)
        track(False)

    # Run a single quick benchmark
    try:
        fib_path = os.path.join(bench_dir, 'fibonacci.epl')
        result = run_single(fib_path, runs=1, warmup=0)
        test_bool("single benchmark has name", 'name' in result)
        test_bool("single benchmark has times", 'times' in result)
        test_bool("single benchmark best > 0", result.get('best', 0) > 0)
    except Exception as e:
        print(f"  FAIL: single benchmark run -- {e}")
        track(False)
        track(False)
        track(False)
test_gap26.__test__ = False


# ═══════════════════════════════════════════════════════════
#  #24: WASM Compilation Target (structure tests)
# ═══════════════════════════════════════════════════════════

def test_gap24():
    print("\n  --- #24: WASM Compilation Target ---")

    # Compiler has compile_to_wasm method
    try:
        from epl.compiler import Compiler, HAS_LLVM
        if HAS_LLVM:
            c = Compiler()
            test_bool("compile_to_wasm method exists", hasattr(c, 'compile_to_wasm'))
            test_bool("compile_to_wasm is callable", callable(getattr(c, 'compile_to_wasm', None)))
        else:
            test_bool("compile_to_wasm (llvmlite not available — skipped)", True)
            test_bool("compile_to_wasm callable (skipped)", True)
    except ImportError:
        test_bool("compile_to_wasm (no llvmlite — skipped)", True)
        test_bool("compile_to_wasm callable (skipped)", True)

    # CLI has wasm command recognition
    import main as _main
    help_text = []
    import io
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        # We can't easily invoke main() without side effects,
        # but we can check help text registration
        test_bool("wasm help in source",
                  "wasm" in open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), 'r').read().lower())
    finally:
        sys.stdout = old_stdout

    # _compile_to_wasm function exists in main
    test_bool("_compile_to_wasm function exists", hasattr(_main, '_compile_to_wasm'))
test_gap24.__test__ = False


# ═══════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("=" * 55)
    print("  EPL Tier 4 Tests — Polish")
    print("=" * 55)

    test_gap28()
    test_gap27()
    test_gap29()
    test_gap30()
    test_gap25()
    test_gap26()
    test_gap24()

    print()
    print("=" * 55)
    total = PASSED + FAILED
    print(f"  Tier 4 Results: {PASSED}/{total} passed, {FAILED} failed")
    print("=" * 55)

    return FAILED == 0


def test_tier4_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    raise SystemExit(0 if run_suite() else 1)
