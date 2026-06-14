"""
Tests for the EPL Doctor (epl/doctor.py).

Tests cover:
- Individual check functions
- DoctorReport data structure
- JSON output mode
- Color helpers
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.doctor import (
    ALL_CHECKS,
    CheckResult,
    DoctorReport,
    check_dependencies,
    check_disk_space,
    check_encoding,
    check_epl_installation,
    check_git,
    check_node,
    check_npm,
    check_pip,
    check_platform,
    check_project_structure,
    check_python_version,
    run_doctor,
)

# ═══════════════════════════════════════════════════════════
# CheckResult Tests
# ═══════════════════════════════════════════════════════════


class TestCheckResult(unittest.TestCase):

    def test_ok_result(self):
        r = CheckResult(name='Test', status='ok', message='All good')
        self.assertEqual(r.name, 'Test')
        self.assertEqual(r.status, 'ok')
        self.assertEqual(r.message, 'All good')
        self.assertEqual(r.detail, '')
        self.assertEqual(r.fix_hint, '')

    def test_fail_result_with_hint(self):
        r = CheckResult(
            name='Python',
            status='fail',
            message='Too old',
            fix_hint='Upgrade Python',
        )
        self.assertEqual(r.status, 'fail')
        self.assertEqual(r.fix_hint, 'Upgrade Python')

    def test_warn_result_with_detail(self):
        r = CheckResult(
            name='Node',
            status='warn',
            message='Not found',
            detail='Optional dependency',
        )
        self.assertEqual(r.detail, 'Optional dependency')


# ═══════════════════════════════════════════════════════════
# DoctorReport Tests
# ═══════════════════════════════════════════════════════════


class TestDoctorReport(unittest.TestCase):

    def test_empty_report(self):
        r = DoctorReport()
        self.assertEqual(r.ok_count, 0)
        self.assertEqual(r.warn_count, 0)
        self.assertEqual(r.fail_count, 0)
        self.assertTrue(r.healthy)

    def test_counts(self):
        r = DoctorReport(
            checks=[
                CheckResult('a', 'ok', 'good'),
                CheckResult('b', 'ok', 'good'),
                CheckResult('c', 'warn', 'meh'),
                CheckResult('d', 'fail', 'bad'),
            ]
        )
        self.assertEqual(r.ok_count, 2)
        self.assertEqual(r.warn_count, 1)
        self.assertEqual(r.fail_count, 1)
        self.assertFalse(r.healthy)

    def test_healthy_with_warnings(self):
        r = DoctorReport(
            checks=[
                CheckResult('a', 'ok', 'good'),
                CheckResult('b', 'warn', 'meh'),
            ]
        )
        self.assertTrue(r.healthy)  # Warnings don't cause failure

    def test_duration(self):
        r = DoctorReport(start_time=1000.0, end_time=1002.5)
        self.assertAlmostEqual(r.duration, 2.5)

    def test_to_dict(self):
        r = DoctorReport(
            checks=[CheckResult('test', 'ok', 'fine')],
            start_time=100.0,
            end_time=100.1,
        )
        d = r.to_dict()
        self.assertTrue(d['healthy'])
        self.assertEqual(d['summary']['ok'], 1)
        self.assertEqual(len(d['checks']), 1)
        self.assertEqual(d['checks'][0]['name'], 'test')


# ═══════════════════════════════════════════════════════════
# Individual Check Tests
# ═══════════════════════════════════════════════════════════


class TestPythonVersionCheck(unittest.TestCase):

    def test_returns_ok_or_warn(self):
        result = check_python_version()
        self.assertIn(result.status, ('ok', 'warn'))
        self.assertIn('Python', result.message)

    def test_includes_version_number(self):
        result = check_python_version()
        major, minor = sys.version_info[:2]
        self.assertIn(f'{major}.{minor}', result.message)


class TestEPLInstallation(unittest.TestCase):

    def test_epl_found(self):
        result = check_epl_installation()
        self.assertEqual(result.status, 'ok')
        self.assertIn('EPL', result.message)


class TestNodeCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_node()
        self.assertIn(result.status, ('ok', 'warn'))

    def test_message_not_empty(self):
        result = check_node()
        self.assertTrue(len(result.message) > 0)


class TestNpmCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_npm()
        self.assertIn(result.status, ('ok', 'warn'))


class TestGitCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_git()
        self.assertIn(result.status, ('ok', 'warn'))


class TestPipCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_pip()
        self.assertIn(result.status, ('ok', 'warn'))


class TestPlatformCheck(unittest.TestCase):

    def test_always_ok(self):
        result = check_platform()
        self.assertEqual(result.status, 'ok')
        self.assertTrue(len(result.message) > 0)


class TestDiskSpaceCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_disk_space()
        self.assertIn(result.status, ('ok', 'warn', 'fail', 'skip'))

    def test_message_has_gb(self):
        result = check_disk_space()
        if result.status != 'skip':
            self.assertIn('GB', result.message)


class TestEncodingCheck(unittest.TestCase):

    def test_returns_valid_status(self):
        result = check_encoding()
        self.assertIn(result.status, ('ok', 'warn'))


class TestProjectStructure(unittest.TestCase):

    def test_in_epl_repo(self):
        result = check_project_structure()
        # Could be ok, warn, or skip depending on cwd
        self.assertIn(result.status, ('ok', 'warn', 'skip'))

    def test_with_epl_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'app.epl'), 'w') as f:
                f.write('Print "hello"')
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = check_project_structure()
                self.assertEqual(result.status, 'warn')
                self.assertIn('No manifest', result.message)
            finally:
                os.chdir(old_cwd)


class TestDependencies(unittest.TestCase):

    def test_no_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = check_dependencies()
                self.assertEqual(result.status, 'skip')
            finally:
                os.chdir(old_cwd)

    def test_with_json_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {'name': 'test', 'dependencies': {'pkg-a': '1.0'}}
            with open(os.path.join(tmpdir, 'epl.json'), 'w') as f:
                json.dump(manifest, f)
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                result = check_dependencies()
                self.assertEqual(result.status, 'ok')
                self.assertIn('1 dependencies', result.message)
            finally:
                os.chdir(old_cwd)


# ═══════════════════════════════════════════════════════════
# Full Doctor Runner
# ═══════════════════════════════════════════════════════════


class TestRunDoctor(unittest.TestCase):

    def test_all_checks_registered(self):
        self.assertEqual(len(ALL_CHECKS), 11)

    def test_run_returns_exit_code(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            code = run_doctor()
            self.assertIn(code, (0, 1))
        finally:
            sys.stdout = old_stdout

    def test_json_output(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            run_doctor(json_output=True)
            output = sys.stdout.getvalue()
            data = json.loads(output)
            self.assertIn('healthy', data)
            self.assertIn('checks', data)
            self.assertIsInstance(data['checks'], list)
        finally:
            sys.stdout = old_stdout


if __name__ == '__main__':
    unittest.main()
