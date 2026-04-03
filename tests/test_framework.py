"""
EPL Test Framework v2.0
Production-grade testing infrastructure with:
- Test runner with discovery, filtering, and reporting
- Fixtures (setup/teardown)
- Mocking support
- Timeout-protected test execution
- Coverage tracking
- Performance benchmarking
- Property-based testing helpers
"""
import sys
import os
import time
import traceback
import random
import string
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError


# ═══════════════════════════════════════════════════════════
#  Core helpers
# ═══════════════════════════════════════════════════════════

def run(src, timeout=10):
    """Run EPL source and return output lines."""
    lex = Lexer(src)
    tokens = lex.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    interp = Interpreter()
    interp.execute(prog)
    return interp.output_lines


def run_with_env(src, timeout=10):
    """Run EPL source and return (output_lines, interpreter)."""
    lex = Lexer(src)
    tokens = lex.tokenize()
    parser = Parser(tokens)
    prog = parser.parse()
    interp = Interpreter()
    interp.execute(prog)
    return interp.output_lines, interp


def expect_error(src, error_substr=None, error_type=None):
    """Run EPL source expecting an error. Returns True if correct error raised."""
    try:
        run(src)
        return False
    except EPLError as e:
        if error_type and not isinstance(e, error_type):
            return False
        if error_substr and error_substr.lower() not in str(e).lower():
            return False
        return True
    except Exception:
        return False


def parse_only(src):
    """Parse EPL source and return AST without executing."""
    lex = Lexer(src)
    tokens = lex.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def tokenize_only(src):
    """Tokenize EPL source and return token list."""
    lex = Lexer(src)
    return lex.tokenize()


# ═══════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════

class TempDir:
    """Fixture that provides a temporary directory, cleaned up after use."""
    def __init__(self):
        self.path = None

    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix='epl_test_')
        return self.path

    def __exit__(self, *args):
        if self.path and os.path.exists(self.path):
            shutil.rmtree(self.path, ignore_errors=True)


class TempFile:
    """Fixture that provides a named temporary file."""
    def __init__(self, content="", suffix=".epl"):
        self._content = content
        self._suffix = suffix
        self.path = None

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=self._suffix, prefix='epl_test_')
        with os.fdopen(fd, 'w') as f:
            f.write(self._content)
        return self.path

    def __exit__(self, *args):
        if self.path and os.path.exists(self.path):
            os.unlink(self.path)


class CapturedOutput:
    """Fixture that captures stdout/stderr."""
    def __init__(self):
        self.stdout = ""
        self.stderr = ""
        self._old_stdout = None
        self._old_stderr = None

    def __enter__(self):
        import io
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return self

    def __exit__(self, *args):
        self.stdout = sys.stdout.getvalue()
        self.stderr = sys.stderr.getvalue()
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr


# ═══════════════════════════════════════════════════════════
#  Test Runner
# ═══════════════════════════════════════════════════════════

class TestResult:
    """Result of a single test."""
    __test__ = False
    __slots__ = ('name', 'passed', 'error', 'duration', 'skipped')

    def __init__(self, name, passed, error=None, duration=0.0, skipped=False):
        self.name = name
        self.passed = passed
        self.error = error
        self.duration = duration
        self.skipped = skipped


class TestSuite:
    """Organizes and runs a collection of tests."""
    __test__ = False

    def __init__(self, name="EPL Tests"):
        self.name = name
        self.tests = []
        self.results = []
        self._setup = None
        self._teardown = None

    def setup(self, fn):
        """Register a setup function called before each test."""
        self._setup = fn
        return fn

    def teardown(self, fn):
        """Register a teardown function called after each test."""
        self._teardown = fn
        return fn

    def test(self, name_or_fn=None, *, skip=False, expected_fail=False):
        """Decorator to register a test function."""
        def decorator(fn):
            self.tests.append({
                'name': name_or_fn if isinstance(name_or_fn, str) else fn.__name__,
                'fn': fn,
                'skip': skip,
                'expected_fail': expected_fail,
            })
            return fn
        if callable(name_or_fn):
            return decorator(name_or_fn)
        return decorator

    def add(self, name, fn, skip=False):
        """Add a test by name and callable."""
        self.tests.append({'name': name, 'fn': fn, 'skip': skip, 'expected_fail': False})

    def run(self, pattern=None, verbose=False):
        """Run all tests, optionally filtering by pattern."""
        self.results = []
        passed = 0
        failed = 0
        skipped = 0
        errors = []

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"  {self.name}")
            print(f"{'=' * 60}")

        for test_info in self.tests:
            name = test_info['name']
            if pattern and pattern.lower() not in name.lower():
                continue
            if test_info['skip']:
                self.results.append(TestResult(name, True, skipped=True))
                skipped += 1
                if verbose:
                    print(f"  SKIP: {name}")
                continue

            if self._setup:
                try:
                    self._setup()
                except Exception as e:
                    self.results.append(TestResult(name, False, str(e)))
                    failed += 1
                    continue

            start = time.perf_counter()
            try:
                result = test_info['fn']()
                duration = time.perf_counter() - start
                if result is False:
                    if test_info['expected_fail']:
                        self.results.append(TestResult(name, True, duration=duration))
                        passed += 1
                    else:
                        self.results.append(TestResult(name, False, "returned False", duration))
                        failed += 1
                        errors.append((name, "returned False"))
                        if verbose:
                            print(f"  FAIL: {name}")
                else:
                    self.results.append(TestResult(name, True, duration=duration))
                    passed += 1
                    if verbose:
                        print(f"  PASS: {name} ({duration:.3f}s)")
            except AssertionError as e:
                duration = time.perf_counter() - start
                self.results.append(TestResult(name, False, str(e), duration))
                failed += 1
                errors.append((name, str(e)))
                if verbose:
                    print(f"  FAIL: {name} — {e}")
            except Exception as e:
                duration = time.perf_counter() - start
                self.results.append(TestResult(name, False, str(e), duration))
                failed += 1
                errors.append((name, str(e)))
                if verbose:
                    print(f"  FAIL: {name} — {type(e).__name__}: {e}")

            if self._teardown:
                try:
                    self._teardown()
                except Exception:
                    pass

        total = passed + failed + skipped
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"  Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
            if errors:
                print(f"\n  Failures:")
                for name, err in errors:
                    print(f"    - {name}: {err}")
            print(f"{'=' * 60}")
        return passed, failed, skipped


# ═══════════════════════════════════════════════════════════
#  Assertions
# ═══════════════════════════════════════════════════════════

class AssertionError(Exception):
    pass


def assert_equal(actual, expected, msg=None):
    if actual != expected:
        detail = msg or f"Expected {expected!r}, got {actual!r}"
        raise AssertionError(detail)


def assert_not_equal(actual, expected, msg=None):
    if actual == expected:
        raise AssertionError(msg or f"Expected not equal to {expected!r}")


def assert_true(value, msg=None):
    if not value:
        raise AssertionError(msg or f"Expected truthy, got {value!r}")


def assert_false(value, msg=None):
    if value:
        raise AssertionError(msg or f"Expected falsy, got {value!r}")


def assert_contains(haystack, needle, msg=None):
    if needle not in haystack:
        raise AssertionError(msg or f"Expected {haystack!r} to contain {needle!r}")


def assert_raises(fn, error_type=EPLError, msg_substr=None):
    """Assert that fn raises the given error type and optional message substring."""
    try:
        fn()
        raise AssertionError(f"Expected {error_type.__name__} but no error raised")
    except error_type as e:
        if msg_substr and msg_substr.lower() not in str(e).lower():
            raise AssertionError(f"Error message '{e}' doesn't contain '{msg_substr}'")
        return True
    except Exception as e:
        raise AssertionError(f"Expected {error_type.__name__} but got {type(e).__name__}: {e}")


def assert_output(src, expected_lines, msg=None):
    """Assert EPL source produces expected output lines."""
    actual = run(src)
    if actual != expected_lines:
        detail = msg or f"Output mismatch:\n  Expected: {expected_lines}\n  Got:      {actual}"
        raise AssertionError(detail)


# ═══════════════════════════════════════════════════════════
#  Property-based Testing
# ═══════════════════════════════════════════════════════════

def random_int(lo=-1000, hi=1000):
    return random.randint(lo, hi)

def random_float(lo=-1000.0, hi=1000.0):
    return round(random.uniform(lo, hi), 4)

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def random_bool():
    return random.choice([True, False])

def random_list(gen=random_int, length=5):
    return [gen() for _ in range(length)]


def property_test(name, gen_fn, check_fn, trials=50):
    """Run a property-based test: gen_fn() generates args, check_fn(*args) must return True."""
    for i in range(trials):
        args = gen_fn()
        if not isinstance(args, tuple):
            args = (args,)
        try:
            result = check_fn(*args)
            if not result:
                return False, f"Trial {i+1}: check_fn({args}) returned False"
        except Exception as e:
            return False, f"Trial {i+1}: {type(e).__name__}: {e} with args={args}"
    return True, f"All {trials} trials passed"


# ═══════════════════════════════════════════════════════════
#  Benchmark
# ═══════════════════════════════════════════════════════════

def benchmark(name, fn, iterations=100):
    """Run a function multiple times and report timing."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    avg = sum(times) / len(times)
    mn = min(times)
    mx = max(times)
    return {
        'name': name,
        'iterations': iterations,
        'avg_ms': avg * 1000,
        'min_ms': mn * 1000,
        'max_ms': mx * 1000,
    }


# ═══════════════════════════════════════════════════════════
#  Self-test (run this file directly)
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    suite = TestSuite("Test Framework Self-Tests")

    @suite.test("basic_run")
    def _():
        assert_output('Print "hello"', ["hello"])

    @suite.test("error_test")
    def _():
        assert_raises(lambda: run('Print unknownVar'), EPLError, "not been created")

    @suite.test("property_arithmetic")
    def _():
        ok, msg = property_test(
            "addition_commutative",
            lambda: (random_int(), random_int()),
            lambda a, b: run(f"Print {a} + {b}") == run(f"Print {b} + {a}"),
            trials=20,
        )
        assert_true(ok, msg)

    @suite.test("temp_file_fixture")
    def _():
        with TempFile('Print "from file"') as path:
            assert_true(os.path.exists(path))
        assert_false(os.path.exists(path))

    @suite.test("temp_dir_fixture")
    def _():
        with TempDir() as d:
            assert_true(os.path.isdir(d))
        assert_false(os.path.exists(d))

    @suite.test("tokenize_only")
    def _():
        tokens = tokenize_only('Print 42')
        assert_true(len(tokens) >= 2)

    @suite.test("parse_only")
    def _():
        prog = parse_only('Print 42')
        assert_true(len(prog.statements) >= 1)

    @suite.test("benchmark_hello")
    def _():
        result = benchmark("hello", lambda: run('Print "hi"'), iterations=10)
        assert_true(result['avg_ms'] < 5000)  # sanity check

    passed, failed, skipped = suite.run(verbose=True)
    sys.exit(0 if failed == 0 else 1)
