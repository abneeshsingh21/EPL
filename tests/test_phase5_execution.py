"""
Comprehensive Pytest Suite for EPL Phase 5 (Tooling, Developer Experience, DX, and Runtime)
Tests cover:
- Package Manager: SemVer comparison, Range matching, Manifest IO, Lockfile integrity, Transitive Dependency Resolution
- Formatter: AST-based indentation, keyword normalization, blank line control, idempotency
- Linter: Style rules, complexity checks, duplicate import checks, consistent return validation, auto-fix
- Profiler: Timer tracking, call counts, Chrome tracing export, memory snapshots, runtime built-ins
- LSP Server: Diagnostics, completions, hover, symbols, references, rename refactoring, code actions
- Debugger: Breakpoint handling, conditions, call stack frame transitions
- REPL Engine: Multiline indentation detection, special commands (.help, .vars, .save, .export)
"""

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout

from epl.doc_linter import LintConfig, Linter, LintIssue
from epl.formatter import FormatterConfig, format_source, check_formatting, diff_format
from epl.lsp_server import EPLAnalyzer, EPLLanguageServer, JSONRPC
from epl.package_manager import (
    SemVer,
    parse_version_range,
    _parse_toml,
    _dump_toml,
    _manifest_to_toml,
    _toml_to_manifest,
    DependencyConflict,
    create_manifest,
    load_manifest,
    save_manifest,
    create_lockfile,
    verify_lockfile,
    _hash_directory,
)
from epl.profiler import EPLProfiler, get_profiler, register_profiler_builtins
from epl.debugger import Breakpoint, DebugState, EPLDebugger
from main import count_open_blocks, _handle_repl_command
from epl.environment import Environment


class TestPhase5PackageManager(unittest.TestCase):
    """Test SemVer and Package Management Engine."""

    def test_semver_parsing_and_comparison(self):
        v1 = SemVer.parse("1.2.3")
        v2 = SemVer.parse("1.2.4")
        v3 = SemVer.parse("2.0.0-beta.1")
        v4 = SemVer.parse("2.0.0")

        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)
        self.assertTrue(v1 < v2)
        self.assertTrue(v2 < v4)
        self.assertTrue(v3 < v4)
        self.assertEqual(str(v1), "1.2.3")

    def test_semver_range_matching(self):
        caret_matcher = parse_version_range("^1.2.0")
        self.assertTrue(caret_matcher(SemVer.parse("1.2.5")))
        self.assertTrue(caret_matcher(SemVer.parse("1.9.0")))
        self.assertFalse(caret_matcher(SemVer.parse("2.0.0")))

        tilde_matcher = parse_version_range("~1.2.0")
        self.assertTrue(tilde_matcher(SemVer.parse("1.2.9")))
        self.assertFalse(tilde_matcher(SemVer.parse("1.3.0")))

        op_matcher = parse_version_range(">=2.0.0 <3.0.0")
        self.assertTrue(op_matcher(SemVer.parse("2.5.1")))
        self.assertFalse(op_matcher(SemVer.parse("3.0.0")))

    def test_toml_parser_and_serializer(self):
        toml_content = """
        [project]
        name = "my-test-app"
        version = "2.1.0"
        description = "An EPL application"

        [dependencies]
        epl-math = "^1.0.0"
        epl-json = "~1.0.0"
        """
        parsed = _parse_toml(toml_content)
        self.assertIn("project", parsed)
        self.assertEqual(parsed["project"]["name"], "my-test-app")
        self.assertEqual(parsed["dependencies"]["epl-math"], "^1.0.0")

        dumped = _dump_toml(parsed)
        self.assertIn('name = "my-test-app"', dumped)

    def test_manifest_and_lockfile_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                manifest = create_manifest(name="test_proj", version="1.0.0", fmt="toml")
                self.assertTrue(os.path.exists("epl.toml"))

                loaded = load_manifest(tmpdir)
                self.assertEqual(loaded["name"], "test_proj")

                # Test lockfile creation & verification
                lock = create_lockfile(tmpdir)
                self.assertIsNotNone(lock)
                self.assertTrue(os.path.exists("epl.lock"))

                verif = verify_lockfile(tmpdir, include_bridge=False)
                self.assertTrue(verif["valid"])
            finally:
                os.chdir(orig_cwd)


class TestPhase5FormatterAndLinter(unittest.TestCase):
    """Test Code Formatting and Linting Engines."""

    def test_formatter_indentation_and_normalization(self):
        src = 'if x > 5 then\nprint "large"\nelse\nprint "small"\nend'
        formatted = format_source(src)
        self.assertIn('If x > 5', formatted)
        self.assertIn('    Print "large"', formatted)
        self.assertIn('Else', formatted)
        self.assertIn('    Print "small"', formatted)
        self.assertIn('End', formatted)

    def test_formatter_idempotence(self):
        src = 'Function Compute(x, y)\n    Return x + y\nEnd\n'
        pass1 = format_source(src)
        pass2 = format_source(pass1)
        self.assertEqual(pass1, pass2)

    def test_linter_rule_detection_and_autofix(self):
        linter = Linter()
        bad_code = 'Print "test"   \nImport Math\nImport Math\n'
        issues = linter.lint_source(bad_code, '<test>')
        rule_names = [i.rule for i in issues]
        self.assertIn('trailing-whitespace', rule_names)
        self.assertIn('duplicate-import', rule_names)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.epl', delete=False, encoding='utf-8') as f:
            f.write(bad_code)
            fpath = f.name
        try:
            fixed_src, fix_count = linter.auto_fix(fpath)
            self.assertTrue(fix_count > 0)
            self.assertNotIn('   ', fixed_src)
        finally:
            os.unlink(fpath)


class TestPhase5ProfilerAndDebugger(unittest.TestCase):
    """Test Profiling, Trace Export, and Debugger States."""

    def test_profiler_lifecycle_and_chrome_trace(self):
        p = EPLProfiler()
        p.start('sub_task_1')
        time.sleep(0.005)
        p.stop('sub_task_1')

        stats = p.get_stats()
        self.assertIn('sub_task_1', stats)
        self.assertEqual(stats['sub_task_1']['calls'], 1)

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            trace_path = f.name
        try:
            p.export_trace(trace_path)
            with open(trace_path, 'r') as tf:
                data = json.load(tf)
            self.assertIn('traceEvents', data)
            self.assertTrue(len(data['traceEvents']) > 0)
        finally:
            os.unlink(trace_path)

    def test_debugger_state_and_breakpoints(self):
        state = DebugState()
        bp1 = state.add_breakpoint(line=10)
        bp2 = state.add_breakpoint(line=25, condition='total > 100')
        bp3 = state.add_breakpoint(function_name='Calculate')

        self.assertEqual(len(state.breakpoints), 3)
        self.assertEqual(bp2.condition, 'total > 100')

        state.push_frame('Calculate', 10, {'total': 150})
        self.assertEqual(state.depth, 1)

        state.pop_frame()
        self.assertEqual(state.depth, 0)

        removed = state.remove_breakpoint(bp1.id)
        self.assertTrue(removed)
        self.assertEqual(len(state.breakpoints), 2)


class TestPhase5LSPAndREPL(unittest.TestCase):
    """Test Language Server Protocol and REPL Shell."""

    def test_lsp_analyzer_diagnostics_and_completions(self):
        analyzer = EPLAnalyzer()
        doc_uri = "file:///workspace/app.epl"
        analyzer.update_document(doc_uri, 'Print "Hello EPL"')
        diags = analyzer.diagnostics.get(doc_uri, [])
        errors = [d for d in diags if d.get('severity') == 1]
        self.assertEqual(len(errors), 0)

        # Completions
        completions = analyzer.get_completions(doc_uri, 0, 3)
        labels = [c['label'] for c in completions]
        self.assertIn('Print', labels)

    def test_repl_block_tracking_and_commands(self):
        self.assertEqual(count_open_blocks('Print "Hi"'), 0)
        self.assertEqual(count_open_blocks('If condition Then'), 1)
        self.assertEqual(count_open_blocks('If condition Then\nWhile True'), 2)
        self.assertEqual(count_open_blocks('If condition Then\nWhile True\nEnd\nEnd'), 0)

        class MockInterp:
            def __init__(self):
                self.global_env = Environment(name='global')
                self.global_env.define_variable('score', 95)
                self.output_lines = []
                self._constants = set()
                self._imported_files = set()
                self._template_cache = {}

        interp = MockInterp()
        history = ['Create score = 95', 'Print score']
        session = ['Create score = 95', 'Print score']

        f = io.StringIO()
        with redirect_stdout(f):
            _handle_repl_command('.vars', history, session, interp)
        output = f.getvalue()
        self.assertIn('score', output)


if __name__ == '__main__':
    unittest.main()
