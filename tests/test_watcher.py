"""
Tests for the EPL Watch Mode (epl/watcher.py).

Tests cover:
- FileWatcher initialization and snapshot
- Change detection (modified, added, deleted)
- Debounce behavior
- Extension filtering
- Watch mode runner configuration
- CLI flag parsing
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.watcher import FileWatcher

# ═══════════════════════════════════════════════════════════
# FileWatcher — Snapshot & Change Detection
# ═══════════════════════════════════════════════════════════


class TestFileWatcherInit(unittest.TestCase):
    """Tests for FileWatcher initialization."""

    def test_init_with_file(self):
        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False, mode='w') as f:
            f.write('Print "hello"')
            path = f.name
        try:
            watcher = FileWatcher([path])
            self.assertEqual(len(watcher._snapshot), 1)
            self.assertIn(os.path.abspath(path), watcher._snapshot)
        finally:
            os.unlink(path)

    def test_init_with_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some .epl files
            for name in ['a.epl', 'b.epl', 'c.txt']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write('test')

            watcher = FileWatcher([tmpdir])
            # Should only track .epl files
            self.assertEqual(len(watcher._snapshot), 2)

    def test_init_with_custom_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ['a.epl', 'b.py', 'c.js']:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write('test')

            watcher = FileWatcher([tmpdir], extensions={'.epl', '.py'})
            self.assertEqual(len(watcher._snapshot), 2)

    def test_init_nonexistent_path(self):
        watcher = FileWatcher(['/nonexistent/path'])
        self.assertEqual(len(watcher._snapshot), 0)


class TestChangeDetection(unittest.TestCase):
    """Tests for file change detection."""

    def test_detect_modification(self):
        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False, mode='w') as f:
            f.write('Print "v1"')
            path = f.name
        try:
            watcher = FileWatcher([path])
            # No changes initially
            self.assertEqual(watcher.check_changes(), [])

            # Modify the file (need to ensure mtime changes)
            time.sleep(0.1)
            with open(path, 'w') as f:
                f.write('Print "v2"')
            # Force mtime change
            os.utime(path, (time.time() + 1, time.time() + 1))

            changes = watcher.check_changes()
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][1], 'modified')
        finally:
            os.unlink(path)

    def test_detect_addition(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            watcher = FileWatcher([tmpdir])
            self.assertEqual(watcher.check_changes(), [])

            # Add a new file
            new_file = os.path.join(tmpdir, 'new_test.epl')
            with open(new_file, 'w') as f:
                f.write('Print "new"')

            changes = watcher.check_changes()
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][1], 'added')

    def test_detect_deletion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, 'temp.epl')
            with open(target, 'w') as f:
                f.write('Print "temp"')

            watcher = FileWatcher([tmpdir])
            self.assertEqual(len(watcher._snapshot), 1)

            # Delete the file
            os.unlink(target)

            changes = watcher.check_changes()
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][1], 'deleted')

    def test_no_changes(self):
        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False, mode='w') as f:
            f.write('Print "stable"')
            path = f.name
        try:
            watcher = FileWatcher([path])
            self.assertEqual(watcher.check_changes(), [])
            self.assertEqual(watcher.check_changes(), [])
            self.assertEqual(watcher.check_changes(), [])
        finally:
            os.unlink(path)

    def test_multiple_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = os.path.join(tmpdir, 'a.epl')
            f2 = os.path.join(tmpdir, 'b.epl')
            for f in [f1, f2]:
                with open(f, 'w') as fh:
                    fh.write('original')

            watcher = FileWatcher([tmpdir])

            # Modify both files
            time.sleep(0.1)
            for f in [f1, f2]:
                with open(f, 'w') as fh:
                    fh.write('modified')
                os.utime(f, (time.time() + 1, time.time() + 1))

            changes = watcher.check_changes()
            self.assertEqual(len(changes), 2)

    def test_ignores_non_epl_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            epl_file = os.path.join(tmpdir, 'main.epl')
            txt_file = os.path.join(tmpdir, 'notes.txt')
            with open(epl_file, 'w') as f:
                f.write('epl')
            with open(txt_file, 'w') as f:
                f.write('txt')

            watcher = FileWatcher([tmpdir])

            # Modify only the txt file
            time.sleep(0.1)
            with open(txt_file, 'w') as f:
                f.write('changed txt')
            os.utime(txt_file, (time.time() + 1, time.time() + 1))

            changes = watcher.check_changes()
            self.assertEqual(len(changes), 0)


# ═══════════════════════════════════════════════════════════
# Debounce Behavior
# ═══════════════════════════════════════════════════════════


class TestDebounce(unittest.TestCase):
    """Tests for debounce configuration."""

    def test_default_debounce(self):
        watcher = FileWatcher([], debounce_ms=300)
        self.assertAlmostEqual(watcher.debounce_s, 0.3, places=2)

    def test_custom_debounce(self):
        watcher = FileWatcher([], debounce_ms=500)
        self.assertAlmostEqual(watcher.debounce_s, 0.5, places=2)

    def test_zero_debounce(self):
        watcher = FileWatcher([], debounce_ms=0)
        self.assertAlmostEqual(watcher.debounce_s, 0.0, places=2)


# ═══════════════════════════════════════════════════════════
# Hidden Directory Filtering
# ═══════════════════════════════════════════════════════════


class TestDirectoryFiltering(unittest.TestCase):
    """Tests for skipping hidden dirs and __pycache__."""

    def test_skip_hidden_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a hidden directory
            hidden = os.path.join(tmpdir, '.hidden')
            os.makedirs(hidden)
            with open(os.path.join(hidden, 'secret.epl'), 'w') as f:
                f.write('hidden')

            # Create a normal file
            with open(os.path.join(tmpdir, 'visible.epl'), 'w') as f:
                f.write('visible')

            watcher = FileWatcher([tmpdir])
            self.assertEqual(len(watcher._snapshot), 1)

    def test_skip_pycache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = os.path.join(tmpdir, '__pycache__')
            os.makedirs(cache)
            with open(os.path.join(cache, 'cached.epl'), 'w') as f:
                f.write('cached')

            with open(os.path.join(tmpdir, 'main.epl'), 'w') as f:
                f.write('main')

            watcher = FileWatcher([tmpdir])
            self.assertEqual(len(watcher._snapshot), 1)


# ═══════════════════════════════════════════════════════════
# Helper Function Tests
# ═══════════════════════════════════════════════════════════


class TestHelperFunctions(unittest.TestCase):
    """Tests for watcher helper functions."""

    def test_format_time(self):
        from epl.watcher import _format_time

        result = _format_time()
        self.assertRegex(result, r'\d{2}:\d{2}:\d{2}')

    def test_clear_screen_function_exists(self):
        from epl.watcher import _clear_screen

        self.assertTrue(callable(_clear_screen))

    def test_color_functions(self):
        from epl.watcher import _bold, _cyan, _dim, _green, _red

        # These should return strings regardless
        self.assertIsInstance(_green('test'), str)
        self.assertIsInstance(_red('test'), str)
        self.assertIsInstance(_cyan('test'), str)
        self.assertIsInstance(_dim('test'), str)
        self.assertIsInstance(_bold('test'), str)


# ═══════════════════════════════════════════════════════════
# run_watch Configuration
# ═══════════════════════════════════════════════════════════


class TestRunWatchConfig(unittest.TestCase):
    """Tests for run_watch argument handling."""

    def test_nonexistent_target_returns_error(self):
        from epl.watcher import run_watch

        result = run_watch('/nonexistent/file.epl')
        self.assertEqual(result, 1)


# ═══════════════════════════════════════════════════════════
# Subprocess timeout — v9.3.0 Phase 7
# Previously hardcoded 60s, which killed servers/bots/anything
# that ran under `epl watch` for more than a minute.
# ═══════════════════════════════════════════════════════════


class TestWatcherTimeout(unittest.TestCase):
    """Verify the per-run subprocess timeout is configurable and defaults to no cap."""

    def test_execute_passes_timeout_to_subprocess(self):
        """_execute(timeout=N) must pass N as subprocess.run(timeout=N)."""
        from unittest import mock

        from epl import watcher

        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False) as f:
            target = f.name
            f.write(b'Print "hi"\n')

        try:
            with mock.patch.object(watcher.subprocess, 'run') as fake_run:
                fake_run.return_value = mock.Mock(returncode=0)
                watcher._execute(target, set(), test_mode=False, clear=False, timeout=12.5)

            self.assertEqual(fake_run.call_args.kwargs['timeout'], 12.5)
        finally:
            os.unlink(target)

    def test_execute_defaults_to_no_timeout(self):
        """Default timeout=None means subprocess.run is called with timeout=None."""
        from unittest import mock

        from epl import watcher

        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False) as f:
            target = f.name
            f.write(b'Print "hi"\n')

        try:
            with mock.patch.object(watcher.subprocess, 'run') as fake_run:
                fake_run.return_value = mock.Mock(returncode=0)
                # No timeout kwarg — uses the function's default.
                watcher._execute(target, set(), test_mode=False, clear=False)

            self.assertIsNone(fake_run.call_args.kwargs['timeout'])
        finally:
            os.unlink(target)

    def test_timeout_expired_reports_and_does_not_raise(self):
        """When the subprocess times out, the watcher reports it cleanly."""
        from unittest import mock

        from epl import watcher

        with tempfile.NamedTemporaryFile(suffix='.epl', delete=False) as f:
            target = f.name
            f.write(b'Print "hi"\n')

        try:
            with mock.patch.object(watcher.subprocess, 'run') as fake_run:
                fake_run.side_effect = watcher.subprocess.TimeoutExpired(cmd='x', timeout=5)
                # Must not raise.
                watcher._execute(target, set(), test_mode=False, clear=False, timeout=5)
        finally:
            os.unlink(target)


class TestWatcherCliTimeoutParsing(unittest.TestCase):
    """The `--timeout=` flag accepted by `epl watch` must parse to the right value."""

    def _parse(self, flag_val):
        """Drive the CLI helper and capture the timeout it would forward."""
        from unittest import mock

        from epl import cli

        captured = {}

        def fake_run_watch(target, **kwargs):
            captured.update(kwargs)
            return 0

        with mock.patch('epl.watcher.run_watch', side_effect=fake_run_watch):
            cli._watch(['.'], {f'--timeout={flag_val}'} if flag_val is not None else set())
        return captured

    def test_numeric_timeout_parsed_as_float(self):
        result = self._parse('30')
        self.assertEqual(result.get('timeout'), 30.0)

    def test_decimal_timeout_parsed_as_float(self):
        result = self._parse('2.5')
        self.assertEqual(result.get('timeout'), 2.5)

    def test_timeout_none_disables_cap(self):
        for sentinel in ('none', 'off', '0', 'disable'):
            with self.subTest(sentinel=sentinel):
                result = self._parse(sentinel)
                self.assertIsNone(result.get('timeout'))

    def test_default_timeout_is_none(self):
        """No --timeout flag → run_watch receives timeout=None (no cap)."""
        result = self._parse(None)
        self.assertIsNone(result.get('timeout'))

    def test_invalid_timeout_returns_error_code(self):
        """A non-numeric --timeout returns 1 instead of forwarding garbage."""
        from epl import cli

        rc = cli._watch(['.'], {'--timeout=banana'})
        self.assertEqual(rc, 1)


if __name__ == '__main__':
    unittest.main()
