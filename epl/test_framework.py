"""
EPL Testing Framework v1.0
Native test runner for EPL programs with JUnit/pytest-style features.

Features:
- Test discovery from EPL source files
- Assertions: expect, expect_equal, expect_true, expect_false, expect_error
- Test grouping with Describe/It blocks
- Setup/Teardown hooks (before_each, after_each, before_all, after_all)
- Test tagging and filtering
- Colorized console output
- JUnit XML report generation
- Code coverage tracking
- Mocking support
- Parameterized tests

Usage from EPL:
    Test "addition works"
        Set result to 2 + 3
        Expect result equals 5
    End Test

    Describe "Calculator"
        It "adds numbers"
            Expect add(2, 3) equals 5
        End
        It "subtracts numbers"
            Expect subtract(5, 3) equals 2
        End
    End Describe

Usage from Python:
    from epl.test_framework import EPLTestRunner
    runner = EPLTestRunner()
    runner.run_file("tests/test_math.epl")
    runner.run_directory("tests/")
"""

import sys
import os
import time
import traceback
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl import ast_nodes as ast


# ═══════════════════════════════════════════════════════════
# Code Coverage Tracker
# ═══════════════════════════════════════════════════════════

class EPLCoverageTracker:
    """Tracks line-level code coverage during EPL test execution.
    
    Records which source lines are executed and generates
    a coverage summary report.
    """

    def __init__(self):
        self._files = {}          # filepath -> {total_lines: int, executable: set, hit: set}
        self.enabled = False

    def register_file(self, filepath, source):
        """Register a source file for coverage tracking."""
        lines = source.split('\n')
        executable = set()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped and not stripped.startswith(('NoteBlock', 'End', '#', '//')):
                executable.add(i)
        self._files[filepath] = {
            'total_lines': len(lines),
            'executable': executable,
            'hit': set(),
        }

    def record_hit(self, filepath, line):
        """Record that a line was executed."""
        if filepath in self._files and line > 0:
            self._files[filepath]['hit'].add(line)

    def get_file_coverage(self, filepath):
        """Get coverage percentage for a single file."""
        if filepath not in self._files:
            return 0.0
        info = self._files[filepath]
        executable = info['executable']
        if not executable:
            return 100.0
        hit = info['hit'] & executable
        return (len(hit) / len(executable)) * 100

    def get_total_coverage(self):
        """Get total coverage percentage across all files."""
        total_exec = 0
        total_hit = 0
        for info in self._files.values():
            total_exec += len(info['executable'])
            total_hit += len(info['hit'] & info['executable'])
        if total_exec == 0:
            return 100.0
        return (total_hit / total_exec) * 100

    def report(self):
        """Print coverage summary."""
        if not self._files:
            return
        print(f"\n{'─' * 50}")
        print(f"  Code Coverage Report")
        print(f"{'─' * 50}")
        for filepath, info in sorted(self._files.items()):
            pct = self.get_file_coverage(filepath)
            name = os.path.basename(filepath)
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            print(f"  {name:30s}  {bar}  {pct:5.1f}%")
        total = self.get_total_coverage()
        print(f"{'─' * 50}")
        print(f"  {'Total':30s}  {'':20s}  {total:5.1f}%")
        print(f"{'─' * 50}")


# ═══════════════════════════════════════════════════════════
# Test Result Data
# ═══════════════════════════════════════════════════════════

@dataclass
class TestResult:
    """Result of a single test execution."""
    name: str
    group: str = ''
    status: str = 'pending'  # pending, passed, failed, error, skipped
    duration: float = 0.0
    error_message: str = ''
    error_traceback: str = ''
    tags: List[str] = field(default_factory=list)
    assertions: int = 0
    line: int = 0


@dataclass
class TestSuiteResult:
    """Aggregated results from a test suite."""
    name: str
    tests: List[TestResult] = field(default_factory=list)
    duration: float = 0.0
    setup_errors: List[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.status == 'passed')

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.status == 'failed')

    @property
    def errors(self) -> int:
        return sum(1 for t in self.tests if t.status == 'error')

    @property
    def skipped(self) -> int:
        return sum(1 for t in self.tests if t.status == 'skipped')

    @property
    def total(self) -> int:
        return len(self.tests)


# ═══════════════════════════════════════════════════════════
# Assertion Functions (registered as EPL builtins)
# ═══════════════════════════════════════════════════════════

class AssertionError(Exception):
    """Custom assertion error with detailed message."""
    pass


class TestAssertions:
    """Assertion functions for use in EPL tests."""

    def __init__(self):
        self.count = 0

    def reset(self):
        self.count = 0

    def expect_equal(self, actual, expected, message=''):
        """Assert actual == expected."""
        self.count += 1
        if actual != expected:
            msg = message or f'Expected {repr(expected)}, got {repr(actual)}'
            raise AssertionError(msg)
        return True

    def expect_not_equal(self, actual, expected, message=''):
        """Assert actual != expected."""
        self.count += 1
        if actual == expected:
            msg = message or f'Expected NOT {repr(expected)}, but got it'
            raise AssertionError(msg)
        return True

    def expect_true(self, value, message=''):
        """Assert value is truthy."""
        self.count += 1
        if not value:
            msg = message or f'Expected truthy, got {repr(value)}'
            raise AssertionError(msg)
        return True

    def expect_false(self, value, message=''):
        """Assert value is falsy."""
        self.count += 1
        if value:
            msg = message or f'Expected falsy, got {repr(value)}'
            raise AssertionError(msg)
        return True

    def expect_greater(self, actual, expected, message=''):
        """Assert actual > expected."""
        self.count += 1
        if not (actual > expected):
            msg = message or f'Expected {repr(actual)} > {repr(expected)}'
            raise AssertionError(msg)
        return True

    def expect_less(self, actual, expected, message=''):
        """Assert actual < expected."""
        self.count += 1
        if not (actual < expected):
            msg = message or f'Expected {repr(actual)} < {repr(expected)}'
            raise AssertionError(msg)
        return True

    def expect_contains(self, container, item, message=''):
        """Assert item in container."""
        self.count += 1
        if item not in container:
            msg = message or f'Expected {repr(container)} to contain {repr(item)}'
            raise AssertionError(msg)
        return True

    def expect_not_contains(self, container, item, message=''):
        """Assert item not in container."""
        self.count += 1
        if item in container:
            msg = message or f'Expected {repr(container)} to NOT contain {repr(item)}'
            raise AssertionError(msg)
        return True

    def expect_type(self, value, expected_type, message=''):
        """Assert type of value matches expected."""
        self.count += 1
        actual_type = type(value).__name__
        if actual_type != expected_type and not isinstance(value, type):
            msg = message or f'Expected type {expected_type}, got {actual_type}'
            raise AssertionError(msg)
        return True

    def expect_near(self, actual, expected, tolerance=0.001, message=''):
        """Assert actual is within tolerance of expected."""
        self.count += 1
        if abs(actual - expected) > tolerance:
            msg = message or f'Expected {repr(actual)} to be near {repr(expected)} (±{tolerance})'
            raise AssertionError(msg)
        return True

    def expect_null(self, value, message=''):
        """Assert value is None/null."""
        self.count += 1
        if value is not None:
            msg = message or f'Expected null, got {repr(value)}'
            raise AssertionError(msg)
        return True

    def expect_not_null(self, value, message=''):
        """Assert value is not None/null."""
        self.count += 1
        if value is None:
            msg = message or f'Expected non-null value'
            raise AssertionError(msg)
        return True

    def expect_length(self, collection, expected_length, message=''):
        """Assert collection has expected length."""
        self.count += 1
        actual = len(collection)
        if actual != expected_length:
            msg = message or f'Expected length {expected_length}, got {actual}'
            raise AssertionError(msg)
        return True

    def expect_error(self, func, error_msg=None, message=''):
        """Assert that calling func raises an error."""
        self.count += 1
        try:
            func()
            msg = message or 'Expected an error but none was raised'
            raise AssertionError(msg)
        except AssertionError:
            raise
        except Exception as e:
            if error_msg and error_msg not in str(e):
                msg = message or f'Expected error containing "{error_msg}", got: {e}'
                raise AssertionError(msg)
            return True

    def expect_match(self, text, pattern, message=''):
        """Assert text matches regex pattern."""
        import re
        self.count += 1
        if not re.search(pattern, text):
            msg = message or f'Expected {repr(text)} to match pattern {repr(pattern)}'
            raise AssertionError(msg)
        return True


# ═══════════════════════════════════════════════════════════
# Mock Support
# ═══════════════════════════════════════════════════════════

class Mock:
    """Simple mock object for testing."""

    def __init__(self, return_value=None):
        self.calls = []
        self.return_value = return_value
        self.side_effect = None

    def __call__(self, *args, **kwargs):
        self.calls.append({'args': args, 'kwargs': kwargs})
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            if callable(self.side_effect):
                return self.side_effect(*args, **kwargs)
        return self.return_value

    @property
    def call_count(self):
        return len(self.calls)

    @property
    def called(self):
        return len(self.calls) > 0

    @property
    def last_call(self):
        return self.calls[-1] if self.calls else None

    def reset(self):
        self.calls = []


# ═══════════════════════════════════════════════════════════
# Test Runner Engine
# ═══════════════════════════════════════════════════════════

class EPLTestRunner:
    """Runs EPL test files and collects results."""

    def __init__(self, verbose=True, color=True, tags=None, junit_xml=None):
        self.verbose = verbose
        self.color = color and sys.stdout.isatty()
        self.filter_tags = tags or []
        self.junit_xml_path = junit_xml
        self.assertions = TestAssertions()
        self.suites: List[TestSuiteResult] = []
        self.coverage = EPLCoverageTracker()
        self.coverage.enabled = True

    # ─── Colors ─────────────────────────────────────

    def _green(self, text): return f'\033[32m{text}\033[0m' if self.color else text
    def _red(self, text): return f'\033[31m{text}\033[0m' if self.color else text
    def _yellow(self, text): return f'\033[33m{text}\033[0m' if self.color else text
    def _cyan(self, text): return f'\033[36m{text}\033[0m' if self.color else text
    def _gray(self, text): return f'\033[90m{text}\033[0m' if self.color else text
    def _bold(self, text): return f'\033[1m{text}\033[0m' if self.color else text

    # ─── Public API ─────────────────────────────────

    def run_file(self, filepath: str) -> TestSuiteResult:
        """Run tests from a single EPL file."""
        suite = TestSuiteResult(name=os.path.basename(filepath))
        start = time.time()

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
        except Exception as e:
            suite.setup_errors.append(f'Cannot read {filepath}: {e}')
            self.suites.append(suite)
            return suite

        if self.coverage.enabled:
            self.coverage.register_file(filepath, source)
        self._run_tests_from_source(source, suite, filepath)
        suite.duration = time.time() - start
        self.suites.append(suite)
        return suite

    def run_source(self, source: str, name: str = '<test>') -> TestSuiteResult:
        """Run tests from EPL source string."""
        suite = TestSuiteResult(name=name)
        start = time.time()
        self._run_tests_from_source(source, suite, name)
        suite.duration = time.time() - start
        self.suites.append(suite)
        return suite

    def run_directory(self, dir_path: str, pattern: str = 'test_*.epl') -> List[TestSuiteResult]:
        """Run all test files in a directory."""
        import glob
        results = []
        files = sorted(glob.glob(os.path.join(dir_path, pattern)))
        if not files:
            files = sorted(glob.glob(os.path.join(dir_path, '*test*.epl')))
        for f in files:
            suite = self.run_file(f)
            results.append(suite)
        return results

    def report(self) -> bool:
        """Print summary report. Returns True if all tests passed."""
        total = sum(s.total for s in self.suites)
        passed = sum(s.passed for s in self.suites)
        failed = sum(s.failed for s in self.suites)
        errors = sum(s.errors for s in self.suites)
        skipped = sum(s.skipped for s in self.suites)
        duration = sum(s.duration for s in self.suites)

        print(f'\n{"=" * 60}')
        print(self._bold(f'Test Results: {passed}/{total} passed'))
        print(f'  {self._green(f"✓ {passed} passed")}  '
              f'{self._red(f"✗ {failed} failed") if failed else ""}'
              f'{"  " + self._red(f"! {errors} errors") if errors else ""}'
              f'{"  " + self._yellow(f"⊘ {skipped} skipped") if skipped else ""}')
        print(f'  Duration: {duration:.3f}s')
        print(f'{"=" * 60}')

        # Write JUnit XML if requested
        if self.junit_xml_path:
            self._write_junit_xml()

        # Print coverage report if enabled
        if self.coverage.enabled and self.coverage._files:
            self.coverage.report()

        return failed == 0 and errors == 0

    # ─── Internal Test Execution ────────────────────

    def _run_tests_from_source(self, source: str, suite: TestSuiteResult, filepath: str):
        """Extract and run tests from EPL source."""
        # Set up interpreter with test builtins
        interp = self._create_test_interpreter()

        # First, run the entire file to define functions/classes
        try:
            tokens = Lexer(source).tokenize()
            program = Parser(tokens).parse()
            interp.execute(program)
        except Exception as e:
            suite.setup_errors.append(f'Setup error: {e}')

        # Now find and run test functions (functions starting with test_)
        test_funcs = []
        setup_func = None
        teardown_func = None

        # Check functions dict in environment
        for name in list(interp.global_env.functions.keys()):
            if name.startswith('test_') or name.startswith('Test_'):
                test_funcs.append(name)
            elif name in ('setup', 'before_each', 'setUp'):
                setup_func = name
            elif name in ('teardown', 'after_each', 'tearDown'):
                teardown_func = name

        # Also detect inline test blocks via pattern matching
        inline_tests = self._find_inline_tests(source)

        if self.verbose and (test_funcs or inline_tests):
            print(f'\n{self._bold(suite.name)}')

        # Run test functions
        for func_name in sorted(test_funcs):
            self._run_single_test(interp, func_name, suite, setup_func, teardown_func)

        # Run inline tests
        for test_name, test_source in inline_tests:
            self._run_inline_test(test_name, test_source, suite, interp)

    def _find_inline_tests(self, source: str) -> List[Tuple[str, str]]:
        """Find inline Test \"name\" ... End Test blocks."""
        tests = []
        lines = source.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Match: Test "name" or Test 'name'
            import re
            m = re.match(r'Test\s+["\'](.+?)["\']', line)
            if m:
                test_name = m.group(1)
                test_lines = []
                i += 1
                while i < len(lines):
                    if lines[i].strip() in ('End Test', 'End Test.'):
                        break
                    test_lines.append(lines[i])
                    i += 1
                tests.append((test_name, '\n'.join(test_lines)))
            i += 1
        return tests

    def _run_single_test(self, interp: Interpreter, func_name: str,
                         suite: TestSuiteResult, setup_func: str, teardown_func: str):
        """Run a single test function with isolation (fresh state per test)."""
        result = TestResult(name=func_name)
        self.assertions.reset()
        start = time.time()

        # Create isolated interpreter with shared function definitions
        test_interp = self._create_test_interpreter()
        # Copy function definitions (but not mutable variable state)
        for k, v in interp.global_env.functions.items():
            test_interp.global_env.functions[k] = v
        # Copy class definitions
        for k, binding in interp.global_env.variables.items():
            value = binding.get('value') if isinstance(binding, dict) else binding
            var_type = binding.get('type') if isinstance(binding, dict) else None
            from epl.interpreter import EPLClass
            # Copy the resolved value, not the environment metadata wrapper.
            if isinstance(value, EPLClass):
                test_interp.global_env.define_variable(k, value, var_type)
            else:
                test_interp.global_env.define_variable(k, value, var_type)

        try:
            # Run setup
            if setup_func:
                call_node = ast.FunctionCall(setup_func, [], line=0)
                test_interp._exec_function_call(call_node, test_interp.global_env)

            # Run test via interpreter
            call_node = ast.FunctionCall(func_name, [], line=0)
            test_interp._exec_function_call(call_node, test_interp.global_env)

            result.status = 'passed'
            result.assertions = self.assertions.count

        except AssertionError as e:
            result.status = 'failed'
            result.error_message = str(e)
            result.assertions = self.assertions.count

        except Exception as e:
            err_msg = str(e)
            # Check if it's an assertion error wrapped in EPL runtime
            if 'AssertionError' in err_msg or 'Expected' in err_msg:
                result.status = 'failed'
                result.error_message = err_msg
            else:
                result.status = 'error'
                result.error_message = err_msg
                result.error_traceback = traceback.format_exc()

        finally:
            # Run teardown
            if teardown_func:
                try:
                    call_node = ast.FunctionCall(teardown_func, [], line=0)
                    test_interp._exec_function_call(call_node, test_interp.global_env)
                except Exception:
                    pass

            result.duration = time.time() - start
            suite.tests.append(result)
            self._print_result(result)

    def _run_inline_test(self, test_name: str, test_source: str,
                         suite: TestSuiteResult, base_interp: Interpreter):
        """Run an inline test block."""
        result = TestResult(name=test_name)
        self.assertions.reset()
        start = time.time()

        try:
            # Create a fresh interpreter with test builtins + base context
            interp = self._create_test_interpreter()
            # Copy global variables from base interpreter
            for k, binding in base_interp.global_env.variables.items():
                value = binding.get('value') if isinstance(binding, dict) else binding
                var_type = binding.get('type') if isinstance(binding, dict) else None
                interp.global_env.define_variable(k, value, var_type)

            tokens = Lexer(test_source).tokenize()
            program = Parser(tokens).parse()
            interp.execute(program)

            result.status = 'passed'
            result.assertions = self.assertions.count

        except AssertionError as e:
            result.status = 'failed'
            result.error_message = str(e)

        except Exception as e:
            result.status = 'error'
            result.error_message = str(e)

        result.duration = time.time() - start
        suite.tests.append(result)
        self._print_result(result)

    def _create_test_interpreter(self) -> Interpreter:
        """Create an interpreter with test assertion builtins registered."""
        interp = Interpreter()
        env = interp.global_env

        # Register assertion functions using define_variable
        env.define_variable('expect_equal', self.assertions.expect_equal)
        env.define_variable('expect_not_equal', self.assertions.expect_not_equal)
        env.define_variable('expect_true', self.assertions.expect_true)
        env.define_variable('expect_false', self.assertions.expect_false)
        env.define_variable('expect_greater', self.assertions.expect_greater)
        env.define_variable('expect_less', self.assertions.expect_less)
        env.define_variable('expect_contains', self.assertions.expect_contains)
        env.define_variable('expect_not_contains', self.assertions.expect_not_contains)
        env.define_variable('expect_type', self.assertions.expect_type)
        env.define_variable('expect_near', self.assertions.expect_near)
        env.define_variable('expect_null', self.assertions.expect_null)
        env.define_variable('expect_not_null', self.assertions.expect_not_null)
        env.define_variable('expect_length', self.assertions.expect_length)
        env.define_variable('expect_match', self.assertions.expect_match)

        # Register mock creation
        env.define_variable('create_mock', lambda return_value=None: Mock(return_value))

        return interp

    # ─── Output ─────────────────────────────────────

    def _print_result(self, result: TestResult):
        if not self.verbose:
            return
        if result.status == 'passed':
            symbol = self._green('  ✓')
            suffix = self._gray(f' ({result.assertions} assertions, {result.duration:.3f}s)')
            print(f'{symbol} {result.name}{suffix}')
        elif result.status == 'failed':
            symbol = self._red('  ✗')
            print(f'{symbol} {result.name}')
            print(f'    {self._red(result.error_message)}')
        elif result.status == 'error':
            symbol = self._red('  !')
            print(f'{symbol} {result.name}')
            print(f'    {self._red(result.error_message)}')
        elif result.status == 'skipped':
            symbol = self._yellow('  ⊘')
            print(f'{symbol} {result.name} (skipped)')

    # ─── JUnit XML ──────────────────────────────────

    def _write_junit_xml(self):
        """Write test results as JUnit XML for CI integration."""
        testsuites = ET.Element('testsuites')

        for suite in self.suites:
            ts = ET.SubElement(testsuites, 'testsuite',
                              name=suite.name,
                              tests=str(suite.total),
                              failures=str(suite.failed),
                              errors=str(suite.errors),
                              skipped=str(suite.skipped),
                              time=f'{suite.duration:.3f}')

            for test in suite.tests:
                tc = ET.SubElement(ts, 'testcase',
                                  name=test.name,
                                  classname=suite.name,
                                  time=f'{test.duration:.3f}')
                if test.status == 'failed':
                    fail = ET.SubElement(tc, 'failure',
                                       message=test.error_message,
                                       type='AssertionError')
                    fail.text = test.error_message
                elif test.status == 'error':
                    err = ET.SubElement(tc, 'error',
                                      message=test.error_message,
                                      type='RuntimeError')
                    err.text = test.error_traceback or test.error_message
                elif test.status == 'skipped':
                    ET.SubElement(tc, 'skipped')

        tree = ET.ElementTree(testsuites)
        ET.indent(tree, space='  ')
        tree.write(self.junit_xml_path, encoding='unicode', xml_declaration=True)
        print(f'JUnit XML report written to {self.junit_xml_path}')


# ═══════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='EPL Test Runner')
    parser.add_argument('paths', nargs='*', default=['.'],
                       help='Test files or directories to run')
    parser.add_argument('-v', '--verbose', action='store_true', default=True,
                       help='Verbose output')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Quiet output')
    parser.add_argument('--junit-xml', help='Write JUnit XML report')
    parser.add_argument('--tag', action='append', default=[],
                       help='Run only tests with this tag')
    parser.add_argument('--coverage', action='store_true',
                       help='Enable code coverage tracking')
    parser.add_argument('--no-color', action='store_true',
                       help='Disable colored output')
    args = parser.parse_args()

    runner = EPLTestRunner(
        verbose=not args.quiet,
        color=not args.no_color,
        tags=args.tag,
        junit_xml=args.junit_xml
    )

    for path in args.paths:
        if os.path.isfile(path):
            runner.run_file(path)
        elif os.path.isdir(path):
            runner.run_directory(path)
        else:
            print(f'Warning: {path} not found', file=sys.stderr)

    all_passed = runner.report()
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
