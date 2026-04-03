"""Structured pytest/unittest smoke coverage for stable legacy test harnesses."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestLegacyHarnessSmoke(unittest.TestCase):
    def _run_command(self, args: list[str]) -> str:
        with tempfile.TemporaryDirectory(prefix="epl_legacy_home_") as tmp_home:
            appdata = Path(tmp_home) / "AppData" / "Roaming"
            local_appdata = Path(tmp_home) / "AppData" / "Local"
            epl_home = Path(tmp_home) / ".epl"
            appdata.mkdir(parents=True, exist_ok=True)
            local_appdata.mkdir(parents=True, exist_ok=True)
            epl_home.mkdir(parents=True, exist_ok=True)

            env = dict(os.environ)
            env["HOME"] = tmp_home
            env["USERPROFILE"] = tmp_home
            env["APPDATA"] = str(appdata)
            env["LOCALAPPDATA"] = str(local_appdata)

            result = subprocess.run(
                args,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def _run_script(self, relative_path: str) -> str:
        return self._run_command([sys.executable, relative_path])

    def test_core_legacy_harness(self):
        output = self._run_script("tests/test_epl.py")
        self.assertIn("44/44 passed", output)

    def test_package_ecosystem_legacy_harness(self):
        output = self._run_script("tests/test_phase4.py")
        self.assertIn("344/344 passed", output)

    def test_package_manager_legacy_harness(self):
        output = self._run_script("tests/test_package_manager.py")
        self.assertIn("91/91 passed", output)

    def test_package_ux_pytest_module(self):
        output = self._run_command([sys.executable, "-m", "pytest", "tests/test_package_ux.py", "-q"])
        self.assertIn("16 passed", output)

    def test_phase3_legacy_harness(self):
        output = self._run_script("tests/test_phase3.py")
        self.assertIn("107 passed, 0 failed", output)

    def test_phase6_legacy_harness(self):
        output = self._run_script("tests/test_phase6.py")
        self.assertIn("443 passed, 0 failed", output)
