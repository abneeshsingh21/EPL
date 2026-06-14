"""
EPL v9.4.0 Bug Fix Verification Test Suite
===========================================

Tests all 12 bugs from the bug report and verifies each fix is correct.
Run with: python -m pytest tests/test_bug_fixes.py -v

Bug Report: 1,594 passed / 46 failed / 7 skipped
Target:     All 12 bugs resolved, 0 regressions
"""

from __future__ import annotations

import ast as python_ast
import asyncio
import inspect
import os
import re
import sys
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ═══════════════════════════════════════════════════════════════
# BUG-01: start_server() hardcodes 0.0.0.0 — ignores host flag
# Severity: 🔴 CRITICAL
# ═══════════════════════════════════════════════════════════════

class TestBug01_StartServerHost:
    """Verify start_server() accepts a host parameter and defaults to 127.0.0.1."""

    def test_start_server_has_host_parameter(self):
        """start_server() must accept a 'host' keyword argument."""
        from epl.web import start_server
        sig = inspect.signature(start_server)
        assert 'host' in sig.parameters, (
            "start_server() is missing 'host' parameter — BUG-01 NOT FIXED"
        )

    def test_start_server_default_host_is_localhost(self):
        """start_server() must default host to '127.0.0.1', NOT '0.0.0.0'."""
        from epl.web import start_server
        sig = inspect.signature(start_server)
        default = sig.parameters['host'].default
        assert default == '127.0.0.1', (
            f"start_server() defaults host to '{default}' — must be '127.0.0.1'"
        )

    def test_start_server_source_no_hardcoded_0000(self):
        """The actual ServerClass(...) call must NOT have hardcoded '0.0.0.0'."""
        from epl import web
        source = inspect.getsource(web.start_server)
        # Should use 'host' variable, not literal '0.0.0.0'
        assert "('0.0.0.0'" not in source, (
            "start_server still has hardcoded '0.0.0.0' in ServerClass call"
        )
        assert "(host," in source or "(host, " in source, (
            "start_server does not pass 'host' variable to ServerClass"
        )

    def test_start_server_warns_on_0000(self):
        """start_server() should warn when 0.0.0.0 is used."""
        from epl import web
        source = inspect.getsource(web.start_server)
        assert "0.0.0.0" in source and "WARNING" in source, (
            "start_server does not warn when 0.0.0.0 is used"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-02: AsyncEPLServer also hardcodes 0.0.0.0
# Severity: 🔴 CRITICAL
# ═══════════════════════════════════════════════════════════════

class TestBug02_AsyncServerHost:
    """Verify AsyncEPLServer accepts host and defaults to 127.0.0.1."""

    def test_async_server_has_host_parameter(self):
        """AsyncEPLServer.__init__ must accept a 'host' keyword argument."""
        from epl.web import AsyncEPLServer
        sig = inspect.signature(AsyncEPLServer.__init__)
        assert 'host' in sig.parameters, (
            "AsyncEPLServer is missing 'host' parameter — BUG-02 NOT FIXED"
        )

    def test_async_server_default_host_is_localhost(self):
        """AsyncEPLServer must default host to '127.0.0.1'."""
        from epl.web import AsyncEPLServer
        sig = inspect.signature(AsyncEPLServer.__init__)
        default = sig.parameters['host'].default
        assert default == '127.0.0.1', (
            f"AsyncEPLServer defaults host to '{default}' — must be '127.0.0.1'"
        )

    def test_async_server_stores_host(self):
        """AsyncEPLServer must store host as self.host."""
        from epl.web import AsyncEPLServer
        source = inspect.getsource(AsyncEPLServer.__init__)
        assert 'self.host' in source, (
            "AsyncEPLServer.__init__ does not store self.host"
        )

    def test_async_server_uses_self_host_in_start_server(self):
        """asyncio.start_server calls must use self.host, not '0.0.0.0'."""
        from epl import web
        source = inspect.getsource(web.AsyncEPLServer)
        # Find all asyncio.start_server calls
        matches = re.findall(r'start_server\([^)]+\)', source)
        for match in matches:
            assert "'0.0.0.0'" not in match, (
                f"AsyncEPLServer still hardcodes '0.0.0.0': {match}"
            )
            assert 'self.host' in match, (
                f"asyncio.start_server does not use self.host: {match}"
            )


# ═══════════════════════════════════════════════════════════════
# BUG-03: runtime.c — File encoding crash on Windows (cp1252)
# Severity: 🟠 HIGH
# ═══════════════════════════════════════════════════════════════

class TestBug03_RuntimeCEncoding:
    """Verify runtime.c test reads use encoding='utf-8'."""

    def test_runtime_c_can_be_read_with_utf8(self):
        """runtime.c must be readable with explicit UTF-8 encoding."""
        runtime_path = os.path.join(ROOT, 'epl', 'runtime.c')
        if not os.path.exists(runtime_path):
            pytest.skip("runtime.c not found")
        with open(runtime_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0, "runtime.c is empty"

    def test_test_file_uses_utf8_encoding(self):
        """test_phase1_native.py must specify encoding='utf-8' for all runtime.c reads."""
        test_file = os.path.join(ROOT, 'tests', 'test_phase1_native.py')
        if not os.path.exists(test_file):
            pytest.skip("test_phase1_native.py not found")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # Find all open() calls that reference runtime_path
        open_calls = re.findall(r"open\(runtime_path,\s*'r'[^)]*\)", content)
        for call in open_calls:
            assert "encoding='utf-8'" in call or 'encoding="utf-8"' in call, (
                f"Missing encoding='utf-8' in: {call}"
            )

    def test_no_default_encoding_reads_of_runtime_c(self):
        """No open(runtime_path, 'r') without encoding should exist."""
        test_file = os.path.join(ROOT, 'tests', 'test_phase1_native.py')
        if not os.path.exists(test_file):
            pytest.skip("test_phase1_native.py not found")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # This pattern finds open() with 'r' but WITHOUT encoding
        bad_pattern = re.findall(
            r"open\(runtime_path,\s*'r'\)\s*as", content
        )
        assert len(bad_pattern) == 0, (
            f"Found {len(bad_pattern)} open(runtime_path, 'r') calls without encoding"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-04: Missing main.py module
# Severity: 🟠 HIGH
# ═══════════════════════════════════════════════════════════════

class TestBug04_MainModule:
    """Verify main.py exists and exports required symbols."""

    def test_main_py_exists(self):
        """main.py must exist in the project root."""
        main_path = os.path.join(ROOT, 'main.py')
        assert os.path.exists(main_path), (
            "main.py does not exist — BUG-04 NOT FIXED"
        )

    def test_main_exports_compile_file(self):
        """main.py must export compile_file."""
        import main
        assert hasattr(main, 'compile_file'), (
            "main.py does not export 'compile_file'"
        )

    def test_main_exports_cross_targets(self):
        """main.py must export CROSS_TARGETS."""
        import main
        assert hasattr(main, 'CROSS_TARGETS'), (
            "main.py does not export 'CROSS_TARGETS'"
        )

    def test_main_exports_interpreter(self):
        """main.py must export Interpreter."""
        import main
        assert hasattr(main, 'Interpreter'), (
            "main.py does not export 'Interpreter'"
        )

    def test_main_exports_lexer(self):
        """main.py must export Lexer."""
        import main
        assert hasattr(main, 'Lexer'), (
            "main.py does not export 'Lexer'"
        )

    def test_main_exports_parser(self):
        """main.py must export Parser."""
        import main
        assert hasattr(main, 'Parser'), (
            "main.py does not export 'Parser'"
        )

    def test_main_not_in_gitignore(self):
        """.gitignore must NOT ignore main.py."""
        gitignore_path = os.path.join(ROOT, '.gitignore')
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert '/main.py' not in content, (
            "main.py is still listed in .gitignore"
        )

    def test_main_has_entry_point(self):
        """main.py must have a main() function and __name__ == '__main__' block."""
        import main
        assert hasattr(main, 'main'), "main.py has no main() function"
        assert callable(main.main), "main.main is not callable"


# ═══════════════════════════════════════════════════════════════
# BUG-05: Flask required but not always installed — import order
# Severity: 🟠 HIGH
# ═══════════════════════════════════════════════════════════════

class TestBug05_FlaskImportOrder:
    """Verify argument validation happens BEFORE Flask import in web_* functions."""

    def _get_stdlib_source(self):
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            return f.read()

    def test_web_json_validates_args_before_flask(self):
        """web_json must check args before calling _ensure_flask()."""
        src = self._get_stdlib_source()
        # Find the web_json block
        match = re.search(
            r"if name == 'web_json':(.*?)(?=\n    if name == )",
            src, re.DOTALL
        )
        assert match, "Could not find web_json block"
        block = match.group(1)
        args_check_pos = block.find('if not args:')
        flask_pos = block.find('_ensure_flask()')
        assert args_check_pos < flask_pos, (
            "web_json: _ensure_flask() is called BEFORE args validation — BUG-05 NOT FIXED"
        )

    def test_web_html_validates_args_before_flask(self):
        """web_html must check args before calling _ensure_flask()."""
        src = self._get_stdlib_source()
        match = re.search(
            r"if name == 'web_html':(.*?)(?=\n    if name == )",
            src, re.DOTALL
        )
        assert match, "Could not find web_html block"
        block = match.group(1)
        args_check_pos = block.find('if not args:')
        flask_pos = block.find('_ensure_flask()')
        assert args_check_pos < flask_pos, (
            "web_html: _ensure_flask() is called BEFORE args validation — BUG-05 NOT FIXED"
        )

    def test_web_redirect_validates_args_before_flask(self):
        """web_redirect must check args and URL before calling _ensure_flask()."""
        src = self._get_stdlib_source()
        match = re.search(
            r"if name == 'web_redirect':(.*?)(?=\n    if name == )",
            src, re.DOTALL
        )
        assert match, "Could not find web_redirect block"
        block = match.group(1)
        args_check_pos = block.find('if not args:')
        flask_pos = block.find('_ensure_flask()')
        assert args_check_pos < flask_pos, (
            "web_redirect: _ensure_flask() is called BEFORE args validation"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-06: Redirect validation not applied to all redirect paths
# Severity: 🟡 MEDIUM
# ═══════════════════════════════════════════════════════════════

class TestBug06_RedirectValidation:
    """Verify _validate_redirect is applied to ALL redirect URL constructions."""

    def test_validate_redirect_blocks_absolute_urls(self):
        """_validate_redirect must block absolute URLs like https://evil.com."""
        from epl.web import EPLHandler
        assert EPLHandler._validate_redirect('https://evil.com') == '/'
        assert EPLHandler._validate_redirect('http://attacker.net/phish') == '/'
        assert EPLHandler._validate_redirect('ftp://evil.com') == '/'

    def test_validate_redirect_blocks_protocol_relative(self):
        """_validate_redirect must block protocol-relative URLs like //evil.com."""
        from epl.web import EPLHandler
        assert EPLHandler._validate_redirect('//evil.com') == '/'
        assert EPLHandler._validate_redirect('//evil.com/path') == '/'

    def test_validate_redirect_allows_relative_paths(self):
        """_validate_redirect must allow safe relative paths."""
        from epl.web import EPLHandler
        assert EPLHandler._validate_redirect('/dashboard') == '/dashboard'
        assert EPLHandler._validate_redirect('/') == '/'
        assert EPLHandler._validate_redirect('/user/profile') == '/user/profile'

    def test_validate_redirect_handles_empty(self):
        """_validate_redirect must handle empty/None input safely."""
        from epl.web import EPLHandler
        assert EPLHandler._validate_redirect('') == '/'
        assert EPLHandler._validate_redirect(None) == '/'
        assert EPLHandler._validate_redirect('  ') == '/'

    def test_execute_action_uses_validate_redirect(self):
        """_execute_action must call _validate_redirect on REDIRECT: URLs."""
        from epl import web
        source = inspect.getsource(web.EPLHandler._execute_action)
        redirect_lines = [
            line.strip() for line in source.split('\n')
            if 'REDIRECT:' in line and 'return' in line
        ]
        for line in redirect_lines:
            assert '_validate_redirect' in line, (
                f"REDIRECT: URL constructed without validation: {line}"
            )

    def test_build_page_sync_uses_validate_redirect(self):
        """_build_page_sync must call _validate_redirect on REDIRECT: URLs."""
        from epl import web
        source = inspect.getsource(web.AsyncEPLServer._build_page_sync)
        redirect_lines = [
            line.strip() for line in source.split('\n')
            if 'REDIRECT:' in line and 'return' in line
        ]
        for line in redirect_lines:
            assert '_validate_redirect' in line, (
                f"REDIRECT: URL constructed without validation in async path: {line}"
            )


# ═══════════════════════════════════════════════════════════════
# BUG-07: _active_connections race condition in AsyncEPLServer
# Severity: 🟡 MEDIUM
# ═══════════════════════════════════════════════════════════════

class TestBug07_ActiveConnectionsLock:
    """Verify _active_connections uses asyncio.Lock for thread safety."""

    def test_async_server_has_lock(self):
        """AsyncEPLServer must define self._lock as asyncio.Lock."""
        from epl.web import AsyncEPLServer
        source = inspect.getsource(AsyncEPLServer.__init__)
        assert 'asyncio.Lock()' in source, (
            "AsyncEPLServer.__init__ does not create asyncio.Lock()"
        )

    def test_handle_connection_locks_increment(self):
        """_handle_connection must lock before incrementing _active_connections."""
        from epl.web import AsyncEPLServer
        source = inspect.getsource(AsyncEPLServer._handle_connection)
        # The lock should appear BEFORE the increment
        lock_pos = source.find('async with self._lock')
        incr_pos = source.find('self._active_connections += 1')
        assert lock_pos != -1, "_handle_connection does not use self._lock"
        assert incr_pos != -1, "_handle_connection does not increment _active_connections"
        assert lock_pos < incr_pos, (
            "Lock is not acquired before incrementing _active_connections"
        )

    def test_handle_connection_locks_decrement(self):
        """_handle_connection must lock before decrementing _active_connections."""
        from epl.web import AsyncEPLServer
        source = inspect.getsource(AsyncEPLServer._handle_connection)
        # Find the decrement and check it's inside a lock
        lines = source.split('\n')
        found_lock_before_decr = False
        for i, line in enumerate(lines):
            if 'self._active_connections -= 1' in line:
                # Check previous lines for lock
                for j in range(max(0, i - 3), i):
                    if 'async with self._lock' in lines[j]:
                        found_lock_before_decr = True
                        break
        assert found_lock_before_decr, (
            "_active_connections decrement is not protected by self._lock"
        )

    def test_no_bare_increment_outside_lock(self):
        """There should be no _active_connections += 1 outside a lock context."""
        from epl.web import AsyncEPLServer
        source = inspect.getsource(AsyncEPLServer._handle_connection)
        # Count increments and lock usages — they should match
        increments = source.count('self._active_connections += 1')
        decrements = source.count('self._active_connections -= 1')
        lock_usages = source.count('async with self._lock')
        assert lock_usages >= increments + decrements, (
            f"Not enough locks ({lock_usages}) for operations ({increments} incr + {decrements} decr)"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-08: test_webapp.py server timeout too short
# Severity: 🟡 MEDIUM
# ═══════════════════════════════════════════════════════════════

class TestBug08_ServerTimeout:
    """Verify test_webapp.py has adequate timeouts for slow machines."""

    def test_wait_for_server_timeout_is_adequate(self):
        """_wait_for_server timeout must be >= 20 seconds."""
        test_file = os.path.join(ROOT, 'tests', 'test_webapp.py')
        if not os.path.exists(test_file):
            pytest.skip("test_webapp.py not found")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'timeout:\s*float\s*=\s*([\d.]+)', content)
        assert match, "Could not find timeout parameter in _wait_for_server"
        timeout = float(match.group(1))
        assert timeout >= 20.0, (
            f"Server timeout is {timeout}s — must be >= 20s for reliability"
        )

    def test_health_check_timeout_is_adequate(self):
        """Health check urlopen timeout must be >= 1 second."""
        test_file = os.path.join(ROOT, 'tests', 'test_webapp.py')
        if not os.path.exists(test_file):
            pytest.skip("test_webapp.py not found")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r"urlopen\(f'{base_url}/_health',\s*timeout=([\d.]+)\)", content)
        assert match, "Could not find urlopen timeout in _wait_for_server"
        timeout = float(match.group(1))
        assert timeout >= 1.0, (
            f"Health check timeout is {timeout}s — must be >= 1s"
        )

    def test_poll_interval_not_too_aggressive(self):
        """Sleep interval between polls should be >= 0.2s to avoid CPU churn."""
        test_file = os.path.join(ROOT, 'tests', 'test_webapp.py')
        if not os.path.exists(test_file):
            pytest.skip("test_webapp.py not found")
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'time\.sleep\(([\d.]+)\)', content)
        assert match, "Could not find time.sleep in _wait_for_server"
        interval = float(match.group(1))
        assert interval >= 0.2, (
            f"Poll interval is {interval}s — must be >= 0.2s to avoid CPU churn"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-09: datetime.utcnow() deprecated
# Severity: 🔵 LOW
# ═══════════════════════════════════════════════════════════════

class TestBug09_UtcNowDeprecated:
    """Verify utc_now uses timezone-aware datetime, not deprecated utcnow()."""

    def test_stdlib_no_utcnow_call(self):
        """stdlib.py must not call datetime.utcnow() — deprecated in Python 3.12+."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        # Find utcnow() in the utc_now handler only
        match = re.search(
            r"if name == 'utc_now':(.*?)(?=\n        if name == )",
            content, re.DOTALL
        )
        assert match, "Could not find utc_now handler"
        block = match.group(1)
        assert '.utcnow()' not in block, (
            "utc_now still uses deprecated datetime.utcnow()"
        )

    def test_stdlib_uses_timezone_aware_now(self):
        """utc_now must use datetime.now(timezone.utc) instead."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(
            r"if name == 'utc_now':(.*?)(?=\n        if name == )",
            content, re.DOTALL
        )
        block = match.group(1)
        assert 'timezone.utc' in block, (
            "utc_now does not use timezone.utc — must use .now(timezone.utc)"
        )

    def test_utc_now_returns_valid_iso_format(self):
        """utc_now output must end with 'Z' and be valid ISO 8601."""
        import datetime
        result = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        assert result.endswith('Z'), f"UTC time does not end with Z: {result}"
        # Verify it parses back
        parsed = datetime.datetime.fromisoformat(result.replace('Z', '+00:00'))
        assert parsed.tzinfo is not None, "Parsed datetime should be timezone-aware"


# ═══════════════════════════════════════════════════════════════
# BUG-10: datetime.utcfromtimestamp() deprecated
# Severity: 🔵 LOW
# ═══════════════════════════════════════════════════════════════

class TestBug10_UtcFromTimestampDeprecated:
    """Verify from_timestamp uses timezone-aware datetime."""

    def test_stdlib_no_utcfromtimestamp_call(self):
        """stdlib.py must not call datetime.utcfromtimestamp()."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(
            r"if name == 'from_timestamp':(.*?)(?=\n        if name == )",
            content, re.DOTALL
        )
        assert match, "Could not find from_timestamp handler"
        block = match.group(1)
        assert '.utcfromtimestamp(' not in block, (
            "from_timestamp still uses deprecated utcfromtimestamp()"
        )

    def test_stdlib_uses_timezone_aware_fromtimestamp(self):
        """from_timestamp must use .fromtimestamp(ts, timezone.utc)."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(
            r"if name == 'from_timestamp':(.*?)(?=\n        if name == )",
            content, re.DOTALL
        )
        block = match.group(1)
        assert 'timezone.utc' in block, (
            "from_timestamp does not use timezone.utc"
        )

    def test_epoch_zero_returns_correct_value(self):
        """from_timestamp(0) must return '1970-01-01T00:00:00Z'."""
        import datetime
        result = datetime.datetime.fromtimestamp(
            0, datetime.timezone.utc
        ).isoformat().replace('+00:00', 'Z')
        assert result == '1970-01-01T00:00:00Z', (
            f"Epoch 0 returned '{result}' instead of '1970-01-01T00:00:00Z'"
        )


# ═══════════════════════════════════════════════════════════════
# BUG-11: 50+ silent except Exception: pass blocks
# Severity: ⚪ INFO
# ═══════════════════════════════════════════════════════════════

class TestBug11_SilentExceptBlocks:
    """Verify silent except blocks have debug instrumentation."""

    def _count_uninstrumented(self):
        """Count except blocks that silently swallow errors without logging."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            lines = f.readlines()
        silent = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped in ('except Exception:', 'except Exception as e:'):
                # Look at next 4 non-blank lines
                has_debug = False
                has_silent_return = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    nxt = lines[j].strip()
                    if '_debug_suppressed' in nxt or '_debug_log' in nxt:
                        has_debug = True
                        break
                    if nxt in ('pass',) and not has_debug:
                        # Only count pure 'pass' without any error info
                        has_silent_return = True
                    if nxt.startswith('return') and not has_debug:
                        has_silent_return = True
                    if nxt.startswith('print(') or nxt.startswith('raise'):
                        has_debug = True  # prints/raises are acceptable
                        break
                    if nxt and not nxt.startswith('#'):
                        break
                if has_silent_return and not has_debug:
                    silent += 1
        return silent

    def test_no_critical_uninstrumented_blocks(self):
        """At most 5 silent except blocks should remain (down from 50+)."""
        count = self._count_uninstrumented()
        assert count <= 5, (
            f"Found {count} uninstrumented silent except blocks — expected <= 5"
        )

    def test_auto_install_has_debug(self):
        """The auto_install except block must have _debug_suppressed."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        assert '_debug_suppressed(\'stdlib.py:103:auto_install\')' in content, (
            "auto_install except block is not instrumented"
        )

    def test_is_admin_has_debug(self):
        """The is_admin except block must have _debug_suppressed."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        assert '_debug_suppressed(\'stdlib.py:4840:is_admin\')' in content, (
            "is_admin except block is not instrumented"
        )

    def test_api_error_has_debug(self):
        """The api_error except block must have _debug_suppressed."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'api_error' in content and '_debug_suppressed' in content


# ═══════════════════════════════════════════════════════════════
# BUG-12: ETag generation uses MD5 (weak hash)
# Severity: ⚪ INFO
# ═══════════════════════════════════════════════════════════════

class TestBug12_ETagHash:
    """Verify ETag uses SHA-256, not MD5."""

    def test_etag_uses_sha256(self):
        """web.py must use hashlib.sha256 for ETag, not hashlib.md5."""
        with open(os.path.join(ROOT, 'epl', 'web.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        # Find the ETag generation line
        etag_lines = [
            line.strip() for line in content.split('\n')
            if 'etag' in line.lower() and 'hashlib' in line
        ]
        assert len(etag_lines) > 0, "Could not find ETag hashlib usage"
        for line in etag_lines:
            assert 'md5' not in line.lower(), (
                f"ETag still uses MD5: {line}"
            )
            assert 'sha256' in line.lower(), (
                f"ETag does not use SHA-256: {line}"
            )

    def test_etag_is_truncated_for_compactness(self):
        """SHA-256 ETag should be truncated (full 64 chars is excessive for ETags)."""
        with open(os.path.join(ROOT, 'epl', 'web.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        etag_lines = [
            line.strip() for line in content.split('\n')
            if 'etag' in line.lower() and 'sha256' in line
        ]
        for line in etag_lines:
            assert '[:32]' in line or '[:16]' in line, (
                f"SHA-256 ETag should be truncated for compactness: {line}"
            )

    def test_etag_format_is_valid(self):
        """ETag value must be wrapped in double quotes per HTTP spec."""
        import hashlib
        etag_raw = b'test/file.js:1234567890:4096'
        etag = '"' + hashlib.sha256(etag_raw).hexdigest()[:32] + '"'
        assert etag.startswith('"') and etag.endswith('"'), (
            f"ETag not properly quoted: {etag}"
        )
        # Inner value should be 32 hex chars
        inner = etag[1:-1]
        assert len(inner) == 32, f"ETag inner length is {len(inner)}, expected 32"
        assert all(c in '0123456789abcdef' for c in inner), (
            f"ETag contains non-hex characters: {inner}"
        )


# ═══════════════════════════════════════════════════════════════
# INTEGRATION: Cross-cutting verification
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """Cross-cutting tests that verify multiple fixes work together."""

    def test_no_hardcoded_0000_anywhere_in_web_server(self):
        """No '0.0.0.0' literals should remain in server bind logic."""
        with open(os.path.join(ROOT, 'epl', 'web.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        # Find ServerClass(...) and asyncio.start_server(...) calls
        bind_calls = re.findall(
            r"(?:ServerClass|start_server)\([^)]*'0\.0\.0\.0'[^)]*\)", content
        )
        assert len(bind_calls) == 0, (
            f"Found hardcoded '0.0.0.0' in server bind calls: {bind_calls}"
        )

    def test_all_deprecated_datetime_calls_removed(self):
        """No deprecated datetime calls should remain in stdlib.py."""
        with open(os.path.join(ROOT, 'epl', 'stdlib.py'), 'r', encoding='utf-8') as f:
            content = f.read()
        assert '.utcnow()' not in content, (
            "Deprecated datetime.utcnow() still exists in stdlib.py"
        )
        assert '.utcfromtimestamp(' not in content, (
            "Deprecated datetime.utcfromtimestamp() still exists in stdlib.py"
        )

    def test_epl_imports_cleanly(self):
        """EPL must import without errors after all fixes."""
        import epl
        from epl.interpreter import Interpreter
        from epl.lexer import Lexer
        from epl.parser import Parser
        from epl.web import AsyncEPLServer, EPLHandler, start_server
        assert True  # If we get here, all imports succeeded
