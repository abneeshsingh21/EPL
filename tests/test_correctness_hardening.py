"""
EPL Correctness Hardening — regression tests for the v9.0 hardening pass.

Covers:
  - EPLGenerator.next() raises EPLRuntimeError on timeout (no more silent stale value)
  - EPL_GENERATOR_TIMEOUT env var can disable the timeout
  - epl/watcher.py _execute() accepts a per-run timeout, defaults to None
  - main._run_serve_command defaults host to 127.0.0.1, warns on 0.0.0.0,
    accepts --host CLI flag, and warns on unknown flags
"""

import io
import os
import sys
import threading
import time
import unittest
from contextlib import redirect_stderr
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.interpreter import EPLGenerator


class TestGeneratorTimeout(unittest.TestCase):
    def test_timeout_raises_instead_of_returning_stale(self):
        # Bare-metal harness — no need for the interpreter; we drive next() ourselves.
        gen = EPLGenerator.__new__(EPLGenerator)
        gen.interpreter = None
        gen.body = None
        gen.env = None
        gen.name = 'wedged'
        gen._exhausted = False
        gen._value_ready = threading.Event()
        gen._resume = threading.Event()
        gen._current_value = None
        gen._error = None
        gen._thread = None
        gen._started = True  # skip the run_body branch
        gen._closed = False

        # Override the timeout to keep the test fast.
        with mock.patch.object(EPLGenerator, '_resolve_yield_timeout', return_value=0.05):
            with self.assertRaises(EPLRuntimeError) as ctx:
                gen.next()
        self.assertIn('timed out', str(ctx.exception).lower())

    def test_timeout_env_var_none_disables_timeout(self):
        with mock.patch.dict(os.environ, {'EPL_GENERATOR_TIMEOUT': 'none'}):
            self.assertIsNone(EPLGenerator._resolve_yield_timeout())
        with mock.patch.dict(os.environ, {'EPL_GENERATOR_TIMEOUT': '0'}):
            self.assertIsNone(EPLGenerator._resolve_yield_timeout())
        with mock.patch.dict(os.environ, {'EPL_GENERATOR_TIMEOUT': '7.5'}):
            self.assertEqual(EPLGenerator._resolve_yield_timeout(), 7.5)

    def test_timeout_env_var_invalid_falls_back_to_default(self):
        with mock.patch.dict(os.environ, {'EPL_GENERATOR_TIMEOUT': 'banana'}):
            self.assertEqual(
                EPLGenerator._resolve_yield_timeout(),
                EPLGenerator.DEFAULT_YIELD_TIMEOUT,
            )


class TestWatcherTimeoutFlag(unittest.TestCase):
    def test_execute_default_timeout_is_none(self):
        """_execute must not pass a hardcoded 60s ceiling anymore."""
        from epl import watcher

        captured = {}

        def fake_run(cmd, **kwargs):
            captured['kwargs'] = kwargs

            class _Result:
                returncode = 0

            return _Result()

        with mock.patch.object(watcher.subprocess, 'run', fake_run):
            watcher._execute('/tmp/whatever.epl', set(), False, False)
        self.assertIn('timeout', captured['kwargs'])
        self.assertIsNone(captured['kwargs']['timeout'])

    def test_execute_honors_custom_timeout(self):
        from epl import watcher

        captured = {}

        def fake_run(cmd, **kwargs):
            captured['kwargs'] = kwargs

            class _Result:
                returncode = 0

            return _Result()

        with mock.patch.object(watcher.subprocess, 'run', fake_run):
            watcher._execute('/tmp/x.epl', set(), False, False, timeout=5.0)
        self.assertEqual(captured['kwargs']['timeout'], 5.0)


class TestServeDefaults(unittest.TestCase):
    """The --host flag was added so `epl serve` no longer silently binds 0.0.0.0."""

    def _run(self, extra_args):
        """Run _run_serve_command with a minimal stubbed environment, returning the
        (host, port, workers, reload, stderr) tuple actually passed to serve()."""
        import main as main_mod

        recorded = {}

        def fake_serve(wsgi_app, **kwargs):
            recorded.update(kwargs)

        # Build a temp .epl file so the file-exists check passes.
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix='.epl', delete=False, mode='w')
        tmp.write('Print "hi"\n')
        tmp.close()
        argv = [tmp.name] + extra_args

        # Stub out everything beyond arg parsing.
        with (
            mock.patch.object(main_mod, 'set_source_context'),
            mock.patch.object(main_mod, 'Lexer'),
            mock.patch.object(main_mod, 'Parser'),
            mock.patch.object(main_mod, 'Interpreter') as fake_interp_cls,
        ):
            fake_interp = mock.Mock()
            fake_interp._web_app = mock.Mock()
            fake_interp_cls.return_value = fake_interp

            with (
                mock.patch('epl.store_backends.configure_backends'),
                mock.patch('epl.deploy.serve', side_effect=fake_serve),
                mock.patch('epl.deploy.WSGIAdapter', return_value=mock.Mock()),
            ):
                err = io.StringIO()
                with redirect_stderr(err):
                    try:
                        main_mod._run_serve_command(argv)
                    except SystemExit:
                        pass

        try:
            os.unlink(tmp.name)
        except OSError:
            pass

        return recorded, err.getvalue()

    def test_default_host_is_localhost(self):
        recorded, stderr = self._run([])
        self.assertEqual(recorded.get('host'), '127.0.0.1')

    def test_host_flag_overrides_default(self):
        recorded, _ = self._run(['--host', '192.168.1.5'])
        self.assertEqual(recorded.get('host'), '192.168.1.5')

    def test_0_0_0_0_emits_warning(self):
        recorded, stderr = self._run(['--host', '0.0.0.0'])
        self.assertEqual(recorded.get('host'), '0.0.0.0')
        self.assertIn('0.0.0.0', stderr)
        self.assertIn('WARNING', stderr.upper())

    def test_unknown_flag_warns(self):
        _, stderr = self._run(['--bogus-flag'])
        self.assertIn('bogus-flag', stderr)


if __name__ == '__main__':
    unittest.main()
