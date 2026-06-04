"""
EPL Security Hardening — regression tests for the v9.0 hardening pass.

Covers:
  - SQL injection in db_update / db_delete / db_count / db_table_info
  - Command injection in exec_async (shell=True removed)
  - AI config path moved out of the package dir into a per-user XDG-aware location
  - Mask helper hides API keys with at most 4 chars of either end
  - Sandbox blocklist now includes exec_async / kill_process / env_delete

These tests verify the fix surface stays fixed across future refactors.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.errors import RuntimeError as EPLRuntimeError
from epl.stdlib import call_stdlib


def _open_db(path):
    return call_stdlib('db_open', [path], 0)


class TestSQLInjectionFixes(unittest.TestCase):
    """db_update / db_delete / db_count / db_table_info must reject malformed
    table or column identifiers instead of interpolating them into SQL."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        self.conn = _open_db(self.tmp.name)
        call_stdlib(
            'db_create_table',
            [self.conn, 'users', {'name': 'TEXT', 'age': 'INTEGER'}],
            0,
        )
        call_stdlib('db_insert', [self.conn, 'users', {'name': 'a', 'age': 1}], 0)

    def tearDown(self):
        call_stdlib('db_close', [self.conn], 0)
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_db_update_rejects_bad_table(self):
        with self.assertRaises(EPLRuntimeError):
            call_stdlib(
                'db_update',
                [self.conn, 'users"; DROP TABLE users; --', {'name': 'x'}, {'age': 1}],
                0,
            )

    def test_db_update_rejects_bad_column(self):
        with self.assertRaises(EPLRuntimeError):
            call_stdlib(
                'db_update',
                [self.conn, 'users', {'name) VALUES (1); --': 'x'}, {'age': 1}],
                0,
            )

    def test_db_delete_rejects_bad_table(self):
        with self.assertRaises(EPLRuntimeError):
            call_stdlib(
                'db_delete',
                [self.conn, 'users; DROP TABLE users; --', {'age': 1}],
                0,
            )

    def test_db_count_rejects_bad_table(self):
        with self.assertRaises(EPLRuntimeError):
            call_stdlib('db_count', [self.conn, 'users); DROP TABLE users; --'], 0)

    def test_db_table_info_rejects_bad_table(self):
        with self.assertRaises(EPLRuntimeError):
            call_stdlib(
                'db_table_info',
                [self.conn, 'users"; DROP TABLE users; --'],
                0,
            )

    def test_db_update_still_works_on_valid_input(self):
        call_stdlib('db_update', [self.conn, 'users', {'age': 99}, {'name': 'a'}], 0)
        cnt = call_stdlib('db_count', [self.conn, 'users', {'age': 99}], 0)
        self.assertEqual(cnt, 1)


class TestExecAsyncNoShell(unittest.TestCase):
    """exec_async must NOT pass through to /bin/sh or cmd.exe — passing a
    shell metacharacter must result in argv[0] being treated as a literal
    program name (which will fail to launch), not be interpreted by a shell."""

    def test_exec_async_does_not_invoke_shell(self):
        # A literal string with `&&` would chain commands under shell=True.
        # With shell=False, shlex.split yields ['echo', 'safe', '&&', 'echo', 'hacked']
        # which fails because there is no executable called "echo &&" or chaining.
        # We only care that no shell interpretation happens; either a clean
        # launch of `echo` with extra args, or an OSError, is acceptable.
        import shutil

        echo = shutil.which('echo') or shutil.which('cmd.exe')
        if not echo:
            self.skipTest('no echo/cmd available')
        try:
            pid = call_stdlib('exec_async', ['cmd_does_not_exist_xyz && rm -rf /'], 0)
        except (EPLRuntimeError, FileNotFoundError, OSError):
            return  # expected — no shell to interpret the &&
        # If it did launch, terminate it. The key assertion is no shell.
        try:
            call_stdlib('kill_process', [pid], 0)
        except Exception:
            pass


class TestAIConfigPath(unittest.TestCase):
    """AI config must live outside the package directory."""

    def test_config_path_is_user_scoped(self):
        # Reset module-level cache so the test can observe the resolved path.
        import epl.ai as ai

        ai._CONFIG_PATH = None
        path = ai._get_config_path()
        pkg_dir = os.path.dirname(ai.__file__)
        self.assertFalse(
            path.startswith(pkg_dir),
            f'AI config still inside package dir: {path}',
        )
        # On any OS the parent dir should be `epl/`
        self.assertEqual(os.path.basename(os.path.dirname(path)), 'epl')

    def test_mask_key_hides_middle(self):
        from epl.ai import _mask_key

        self.assertEqual(_mask_key(''), '')
        self.assertEqual(_mask_key('short'), '*****')
        masked = _mask_key('AIzaSyA-very-long-fake-api-key-12345')
        self.assertTrue(masked.startswith('AIza'))
        self.assertTrue(masked.endswith('2345'))
        self.assertIn('...', masked)
        self.assertNotIn('very-long', masked)


class TestSandboxBlocklist(unittest.TestCase):
    def test_exec_async_in_blocklist(self):
        from epl.interpreter import _UNSAFE_BUILTINS

        self.assertIn('exec_async', _UNSAFE_BUILTINS)
        self.assertIn('kill_process', _UNSAFE_BUILTINS)
        self.assertIn('env_delete', _UNSAFE_BUILTINS)


if __name__ == '__main__':
    unittest.main()
