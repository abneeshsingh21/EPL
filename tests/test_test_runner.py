"""
Tests for the EPL Test Runner v2.

Tests cover:
- EPLTestRunner construction and configuration
- Test discovery and execution
- Filter pattern matching
- Fail-fast behavior
- Timeout enforcement
- Assertion functions
- Result aggregation and reporting
- JUnit XML generation
- Collection header
- Coverage tracker
- Quiet mode progress dots
- Mock support
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ═══════════════════════════════════════════════════════════
# Test Runner Configuration
# ═══════════════════════════════════════════════════════════


class TestRunnerConfig(unittest.TestCase):
    """Tests for EPLTestRunner initialization and configuration."""

    def test_default_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner()
        self.assertTrue(runner.verbose)
        self.assertFalse(runner.fail_fast)
        self.assertIsNone(runner.timeout)
        self.assertIsNone(runner.filter_pattern)
        self.assertFalse(runner.coverage.enabled)
        self.assertFalse(runner._stop_requested)

    def test_fail_fast_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(fail_fast=True)
        self.assertTrue(runner.fail_fast)

    def test_timeout_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(timeout=5.0)
        self.assertEqual(runner.timeout, 5.0)

    def test_filter_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(filter_pattern='test_add*')
        self.assertEqual(runner.filter_pattern, 'test_add*')

    def test_coverage_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(coverage_enabled=True)
        self.assertTrue(runner.coverage.enabled)

    def test_junit_config(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(junit_xml='report.xml')
        self.assertEqual(runner.junit_xml_path, 'report.xml')


# ═══════════════════════════════════════════════════════════
# Filter Pattern Matching
# ═══════════════════════════════════════════════════════════


class TestFilterPattern(unittest.TestCase):
    """Tests for test name filter matching."""

    def setUp(self):
        from epl.test_framework import EPLTestRunner

        self.runner = EPLTestRunner()

    def test_no_filter_matches_all(self):
        self.runner.filter_pattern = None
        self.assertTrue(self.runner._matches_filter('test_anything'))

    def test_substring_match(self):
        self.runner.filter_pattern = 'add'
        self.assertTrue(self.runner._matches_filter('test_addition'))
        self.assertFalse(self.runner._matches_filter('test_subtraction'))

    def test_glob_pattern(self):
        self.runner.filter_pattern = 'test_math_*'
        self.assertTrue(self.runner._matches_filter('test_math_add'))
        self.assertTrue(self.runner._matches_filter('test_math_subtract'))
        self.assertFalse(self.runner._matches_filter('test_string_concat'))

    def test_case_insensitive(self):
        self.runner.filter_pattern = 'ADD'
        self.assertTrue(self.runner._matches_filter('test_addition'))

    def test_exact_name(self):
        self.runner.filter_pattern = 'test_specific'
        self.assertTrue(self.runner._matches_filter('test_specific'))
        self.assertFalse(self.runner._matches_filter('test_other'))


# ═══════════════════════════════════════════════════════════
# Assertion Functions
# ═══════════════════════════════════════════════════════════


class TestAssertions(unittest.TestCase):
    """Tests for TestAssertions class."""

    def setUp(self):
        from epl.test_framework import TestAssertions

        self.assertions = TestAssertions()

    def test_expect_equal_pass(self):
        self.assertTrue(self.assertions.expect_equal(5, 5))
        self.assertEqual(self.assertions.count, 1)

    def test_expect_equal_fail(self):
        from epl.test_framework import AssertionError

        with self.assertRaises(AssertionError):
            self.assertions.expect_equal(5, 10)

    def test_expect_true_pass(self):
        self.assertTrue(self.assertions.expect_true(True))

    def test_expect_true_fail(self):
        from epl.test_framework import AssertionError

        with self.assertRaises(AssertionError):
            self.assertions.expect_true(False)

    def test_expect_false_pass(self):
        self.assertTrue(self.assertions.expect_false(False))

    def test_expect_contains_pass(self):
        self.assertTrue(self.assertions.expect_contains([1, 2, 3], 2))

    def test_expect_contains_fail(self):
        from epl.test_framework import AssertionError

        with self.assertRaises(AssertionError):
            self.assertions.expect_contains([1, 2, 3], 5)

    def test_expect_greater_pass(self):
        self.assertTrue(self.assertions.expect_greater(10, 5))

    def test_expect_less_pass(self):
        self.assertTrue(self.assertions.expect_less(3, 7))

    def test_expect_near_pass(self):
        self.assertTrue(self.assertions.expect_near(0.3, 0.3001, 0.01))

    def test_expect_near_fail(self):
        from epl.test_framework import AssertionError

        with self.assertRaises(AssertionError):
            self.assertions.expect_near(0.3, 0.5, 0.01)

    def test_expect_null_pass(self):
        self.assertTrue(self.assertions.expect_null(None))

    def test_expect_not_null_pass(self):
        self.assertTrue(self.assertions.expect_not_null('hello'))

    def test_expect_length_pass(self):
        self.assertTrue(self.assertions.expect_length([1, 2, 3], 3))

    def test_expect_match_pass(self):
        self.assertTrue(self.assertions.expect_match('hello123', r'\d+'))

    def test_reset_clears_count(self):
        self.assertions.expect_true(True)
        self.assertions.expect_true(True)
        self.assertEqual(self.assertions.count, 2)
        self.assertions.reset()
        self.assertEqual(self.assertions.count, 0)

    def test_custom_message(self):
        from epl.test_framework import AssertionError

        with self.assertRaises(AssertionError) as ctx:
            self.assertions.expect_equal(1, 2, 'Custom message here')
        self.assertEqual(str(ctx.exception), 'Custom message here')


# ═══════════════════════════════════════════════════════════
# Test Execution with EPL Source
# ═══════════════════════════════════════════════════════════


class TestExecution(unittest.TestCase):
    """Tests for running EPL test source code."""

    def test_run_passing_source(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_basic
    expect_equal(2 + 3, 5)
End
"""
        runner = EPLTestRunner(verbose=False, color=False)
        suite = runner.run_source(source)
        self.assertEqual(suite.passed, 1)
        self.assertEqual(suite.failed, 0)

    def test_run_failing_source(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_bad
    expect_equal(2 + 3, 10)
End
"""
        runner = EPLTestRunner(verbose=False, color=False)
        suite = runner.run_source(source)
        self.assertEqual(suite.failed, 1)

    def test_run_multiple_tests(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_one
    expect_true(1 is equal to 1)
End

Function test_two
    expect_equal(10, 10)
End

Function test_three
    expect_false(1 is equal to 2)
End
"""
        runner = EPLTestRunner(verbose=False, color=False)
        suite = runner.run_source(source)
        self.assertEqual(suite.total, 3)
        self.assertEqual(suite.passed, 3)

    def test_inline_test_block(self):
        from epl.test_framework import EPLTestRunner

        source = """
Test "inline addition"
    expect_equal(1 + 1, 2)
End Test
"""
        runner = EPLTestRunner(verbose=False, color=False)
        suite = runner.run_source(source)
        self.assertEqual(suite.total, 1)
        self.assertEqual(suite.passed, 1)


# ═══════════════════════════════════════════════════════════
# Fail-Fast Behavior
# ═══════════════════════════════════════════════════════════


class TestFailFast(unittest.TestCase):
    """Tests for fail-fast mode."""

    def test_fail_fast_stops_after_first_failure(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_a_pass
    expect_true(1 is equal to 1)
End

Function test_b_fail
    expect_equal(1, 999)
End

Function test_c_would_pass
    expect_true(1 is equal to 1)
End
"""
        runner = EPLTestRunner(verbose=False, color=False, fail_fast=True)
        suite = runner.run_source(source)
        # test_a passes, test_b fails → test_c should be skipped
        self.assertTrue(suite.failed >= 1)
        # Total should be less than 3 (test_c was skipped)
        self.assertLess(suite.total, 3)

    def test_no_fail_fast_runs_all(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_a_pass
    expect_true(1 is equal to 1)
End

Function test_b_fail
    expect_equal(1, 999)
End

Function test_c_pass
    expect_true(1 is equal to 1)
End
"""
        runner = EPLTestRunner(verbose=False, color=False, fail_fast=False)
        suite = runner.run_source(source)
        self.assertEqual(suite.total, 3)


# ═══════════════════════════════════════════════════════════
# Filter Execution
# ═══════════════════════════════════════════════════════════


class TestFilterExecution(unittest.TestCase):
    """Tests for filtered test execution."""

    def test_filter_runs_only_matching(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_math_add
    expect_equal(2 + 3, 5)
End

Function test_math_sub
    expect_equal(5 - 3, 2)
End

Function test_string_concat
    expect_equal("a" + "b", "ab")
End
"""
        runner = EPLTestRunner(verbose=False, color=False, filter_pattern='test_math_*')
        suite = runner.run_source(source)
        self.assertEqual(suite.total, 2)
        self.assertEqual(suite.passed, 2)


# ═══════════════════════════════════════════════════════════
# File Discovery
# ═══════════════════════════════════════════════════════════


class TestFileDiscovery(unittest.TestCase):
    """Tests for test file discovery."""

    def test_run_file(self):
        from epl.test_framework import EPLTestRunner

        # Create a temp test file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.epl', delete=False, encoding='utf-8'
        ) as f:
            f.write('Function test_temp\n    expect_true(1 is equal to 1)\nEnd\n')
            path = f.name
        try:
            runner = EPLTestRunner(verbose=False, color=False)
            suite = runner.run_file(path)
            self.assertEqual(suite.passed, 1)
        finally:
            os.unlink(path)

    def test_run_nonexistent_file(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(verbose=False, color=False)
        suite = runner.run_file('/nonexistent/test.epl')
        self.assertTrue(len(suite.setup_errors) > 0)


# ═══════════════════════════════════════════════════════════
# JUnit XML Report
# ═══════════════════════════════════════════════════════════


class TestJUnitXML(unittest.TestCase):
    """Tests for JUnit XML report generation."""

    def test_junit_xml_output(self):
        from epl.test_framework import EPLTestRunner

        source = """
Function test_pass
    expect_equal(1, 1)
End

Function test_fail
    expect_equal(1, 2)
End
"""
        with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
            xml_path = f.name

        try:
            runner = EPLTestRunner(verbose=False, color=False, junit_xml=xml_path)
            runner.run_source(source)
            runner.report()

            self.assertTrue(os.path.exists(xml_path))
            with open(xml_path, 'r') as f:
                content = f.read()
            self.assertIn('<testsuites>', content)
            self.assertIn('test_pass', content)
            self.assertIn('test_fail', content)
            self.assertIn('<failure', content)
        finally:
            os.unlink(xml_path)


# ═══════════════════════════════════════════════════════════
# Coverage Tracker
# ═══════════════════════════════════════════════════════════


class TestCoverageTracker(unittest.TestCase):
    """Tests for EPLCoverageTracker."""

    def test_register_and_hit(self):
        from epl.test_framework import EPLCoverageTracker

        tracker = EPLCoverageTracker()
        tracker.register_file('test.epl', 'Set x to 1\nSet y to 2\nSay x + y\n')
        tracker.record_hit('test.epl', 1)
        tracker.record_hit('test.epl', 2)
        pct = tracker.get_file_coverage('test.epl')
        self.assertGreater(pct, 0)

    def test_empty_coverage(self):
        from epl.test_framework import EPLCoverageTracker

        tracker = EPLCoverageTracker()
        self.assertEqual(tracker.get_total_coverage(), 100.0)

    def test_unregistered_file(self):
        from epl.test_framework import EPLCoverageTracker

        tracker = EPLCoverageTracker()
        self.assertEqual(tracker.get_file_coverage('unknown.epl'), 0.0)


# ═══════════════════════════════════════════════════════════
# Mock Support
# ═══════════════════════════════════════════════════════════


class TestMockSupport(unittest.TestCase):
    """Tests for Mock class."""

    def test_mock_returns_value(self):
        from epl.test_framework import Mock

        mock = Mock(return_value=42)
        self.assertEqual(mock(), 42)

    def test_mock_tracks_calls(self):
        from epl.test_framework import Mock

        mock = Mock()
        mock(1, 2)
        mock(3)
        self.assertEqual(mock.call_count, 2)
        self.assertTrue(mock.called)

    def test_mock_reset(self):
        from epl.test_framework import Mock

        mock = Mock()
        mock()
        mock.reset()
        self.assertEqual(mock.call_count, 0)
        self.assertFalse(mock.called)

    def test_mock_side_effect(self):
        from epl.test_framework import Mock

        mock = Mock()
        mock.side_effect = ValueError('boom')
        with self.assertRaises(ValueError):
            mock()


# ═══════════════════════════════════════════════════════════
# Test Result Data Classes
# ═══════════════════════════════════════════════════════════


class TestResultData(unittest.TestCase):
    """Tests for TestResult and TestSuiteResult data classes."""

    def test_test_result_defaults(self):
        from epl.test_framework import TestResult

        result = TestResult(name='test_example')
        self.assertEqual(result.name, 'test_example')
        self.assertEqual(result.status, 'pending')
        self.assertEqual(result.assertions, 0)

    def test_suite_result_counts(self):
        from epl.test_framework import TestResult, TestSuiteResult

        suite = TestSuiteResult(name='test_suite')
        suite.tests.append(TestResult(name='t1', status='passed'))
        suite.tests.append(TestResult(name='t2', status='passed'))
        suite.tests.append(TestResult(name='t3', status='failed'))
        suite.tests.append(TestResult(name='t4', status='error'))
        suite.tests.append(TestResult(name='t5', status='skipped'))
        self.assertEqual(suite.total, 5)
        self.assertEqual(suite.passed, 2)
        self.assertEqual(suite.failed, 1)
        self.assertEqual(suite.errors, 1)
        self.assertEqual(suite.skipped, 1)


# ═══════════════════════════════════════════════════════════
# Collection Header
# ═══════════════════════════════════════════════════════════


class TestCollectionHeader(unittest.TestCase):
    """Tests for collection header output."""

    def test_collection_header_sets_counts(self):
        from epl.test_framework import EPLTestRunner

        runner = EPLTestRunner(verbose=False, color=False)
        runner.print_collection_header(3, 15)
        self.assertEqual(runner._files_collected, 3)
        self.assertEqual(runner._total_collected, 15)


if __name__ == '__main__':
    unittest.main()
