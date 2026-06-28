"""Tests for .env auto-loading and source-file-relative import resolution.

Covers two enterprise-grade fixes:
1. epl.dotenv — zero-dependency .env loading (the API-key integration path).
2. VM import resolution relative to the importing file's directory, so a
   program finds its sibling modules regardless of the current working dir
   (previously the VM resolved relative to the CWD only, silently falling back
   to the interpreter and losing the speed benefit, or failing outright under
   `epl vm` / `epl build`).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.dotenv import load_dotenv, load_for_program, parse_dotenv
from epl.vm import _resolve_import_path, compile_and_run


class TestParseDotenv(unittest.TestCase):
    def test_basic_pairs(self):
        parsed = parse_dotenv('A=1\nB=two')
        self.assertEqual(parsed, {'A': '1', 'B': 'two'})

    def test_comments_and_blanks_ignored(self):
        parsed = parse_dotenv('# comment\n\nA=1\n   # indented comment\nB=2\n')
        self.assertEqual(parsed, {'A': '1', 'B': '2'})

    def test_export_prefix(self):
        self.assertEqual(parse_dotenv('export TOKEN=abc'), {'TOKEN': 'abc'})

    def test_quotes_stripped(self):
        parsed = parse_dotenv('A="double"\nB=\'single\'')
        self.assertEqual(parsed, {'A': 'double', 'B': 'single'})

    def test_value_with_equals_and_url(self):
        parsed = parse_dotenv('DB=postgres://u:p@host/db?ssl=true')
        self.assertEqual(parsed['DB'], 'postgres://u:p@host/db?ssl=true')

    def test_whitespace_trimmed(self):
        self.assertEqual(parse_dotenv('  A =  val  '), {'A': 'val'})

    def test_line_without_equals_skipped(self):
        self.assertEqual(parse_dotenv('NOPE\nA=1'), {'A': '1'})


class TestLoadDotenv(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def _write(self, text):
        import tempfile

        fd, path = tempfile.mkstemp(suffix='.env')
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_loads_into_environ(self):
        os.environ.pop('EPL_TEST_K1', None)
        path = self._write('EPL_TEST_K1=loaded')
        n = load_dotenv(path)
        self.assertEqual(n, 1)
        self.assertEqual(os.environ['EPL_TEST_K1'], 'loaded')

    def test_existing_env_not_overridden(self):
        os.environ['EPL_TEST_K2'] = 'from_shell'
        path = self._write('EPL_TEST_K2=from_file')
        load_dotenv(path)
        self.assertEqual(os.environ['EPL_TEST_K2'], 'from_shell')

    def test_override_true(self):
        os.environ['EPL_TEST_K3'] = 'from_shell'
        path = self._write('EPL_TEST_K3=from_file')
        load_dotenv(path, override=True)
        self.assertEqual(os.environ['EPL_TEST_K3'], 'from_file')

    def test_missing_file_is_noop(self):
        self.assertEqual(load_dotenv('/no/such/.env'), 0)


class TestLoadForProgram(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def _mkdir_env(self, contents):
        import tempfile

        d = tempfile.mkdtemp()
        with open(os.path.join(d, '.env'), 'w', encoding='utf-8') as handle:
            handle.write(contents)
        return d

    def test_loads_from_program_dir(self):
        os.environ.pop('EPL_TEST_PROG', None)
        d = self._mkdir_env('EPL_TEST_PROG=yes')
        prog = os.path.join(d, 'app.epl')
        load_for_program(prog, safe_mode=False)
        self.assertEqual(os.environ.get('EPL_TEST_PROG'), 'yes')

    def test_safe_mode_skips(self):
        os.environ.pop('EPL_TEST_SAFE', None)
        d = self._mkdir_env('EPL_TEST_SAFE=should_not_load')
        prog = os.path.join(d, 'app.epl')
        load_for_program(prog, safe_mode=True)
        self.assertIsNone(os.environ.get('EPL_TEST_SAFE'))

    def test_opt_out_env_var(self):
        os.environ.pop('EPL_TEST_OPTOUT', None)
        os.environ['EPL_NO_DOTENV'] = '1'
        d = self._mkdir_env('EPL_TEST_OPTOUT=should_not_load')
        prog = os.path.join(d, 'app.epl')
        load_for_program(prog, safe_mode=False)
        self.assertIsNone(os.environ.get('EPL_TEST_OPTOUT'))


class TestVMImportResolution(unittest.TestCase):
    """The VM must resolve imports relative to the importing file's directory."""

    def _make_module_pair(self):
        import tempfile

        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'helper.epl'), 'w', encoding='utf-8') as handle:
            handle.write('Function greet(n)\n    Return "hi " + n\nEnd\n')
        main = os.path.join(d, 'main.epl')
        with open(main, 'w', encoding='utf-8') as handle:
            handle.write('Import "helper.epl"\nPrint greet("x")\n')
        return d, main

    def test_resolve_relative_to_base_dir(self):
        d, _ = self._make_module_pair()
        resolved = _resolve_import_path('helper.epl', base_dir=d)
        self.assertIsNotNone(resolved)
        self.assertEqual(os.path.abspath(resolved), os.path.join(d, 'helper.epl'))

    def test_unresolvable_without_base_dir_from_other_cwd(self):
        d, _ = self._make_module_pair()
        # With no base_dir and a CWD that lacks the file, resolution fails —
        # exactly the bug that base_dir fixes.
        old = os.getcwd()
        other = os.path.dirname(os.path.dirname(d)) or os.path.sep
        try:
            os.chdir(other)
            self.assertIsNone(_resolve_import_path('helper.epl'))
        finally:
            os.chdir(old)

    def test_vm_runs_sibling_import_from_any_cwd(self):
        d, main = self._make_module_pair()
        old = os.getcwd()
        # Run from a directory that does NOT contain the modules.
        other = os.path.dirname(os.path.dirname(d)) or os.path.sep
        try:
            os.chdir(other)
            with open(main, 'r', encoding='utf-8') as handle:
                source = handle.read()
            result = compile_and_run(source, base_dir=d)
            self.assertFalse(result.get('error'), result.get('error'))
        finally:
            os.chdir(old)

    def test_nested_import_resolves_per_module_dir(self):
        import tempfile

        d = tempfile.mkdtemp()
        with open(os.path.join(d, 'mathx.epl'), 'w', encoding='utf-8') as h:
            h.write('Function square(n)\n    Return n * n\nEnd\n')
        with open(os.path.join(d, 'mid.epl'), 'w', encoding='utf-8') as h:
            h.write('Import "mathx.epl"\nFunction area(s)\n    Return square(s)\nEnd\n')
        main = os.path.join(d, 'main.epl')
        with open(main, 'w', encoding='utf-8') as h:
            h.write('Import "mid.epl"\nPrint area(5)\n')
        with open(main, 'r', encoding='utf-8') as h:
            source = h.read()
        result = compile_and_run(source, base_dir=d)
        self.assertFalse(result.get('error'), result.get('error'))


if __name__ == '__main__':
    unittest.main()
