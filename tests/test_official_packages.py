"""Regression tests for bundled official EPL packages."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from epl.lexer import Lexer
from epl.parser import Parser


REPO_ROOT = Path(__file__).resolve().parent.parent


def _assert_parses(path: Path) -> None:
    Parser(Lexer(path.read_text(encoding="utf-8")).tokenize()).parse()


class TestOfficialPackages(unittest.TestCase):
    def test_official_package_sources_and_examples_parse(self):
        paths = [
            REPO_ROOT / "epl" / "official_packages" / "epl-web" / "src" / "main.epl",
            REPO_ROOT / "epl" / "official_packages" / "epl-web" / "examples" / "basic.epl",
            REPO_ROOT / "epl" / "official_packages" / "epl-db" / "src" / "main.epl",
            REPO_ROOT / "epl" / "official_packages" / "epl-db" / "examples" / "basic.epl",
            REPO_ROOT / "epl" / "official_packages" / "epl-test" / "src" / "main.epl",
            REPO_ROOT / "epl" / "official_packages" / "epl-test" / "examples" / "basic.epl",
        ]
        for path in paths:
            with self.subTest(path=path.name):
                _assert_parses(path)

    def test_import_auto_installs_supported_official_packages(self):
        with tempfile.TemporaryDirectory(prefix="epl_official_pkg_home_") as home_dir, \
             tempfile.TemporaryDirectory(prefix="epl_official_pkg_run_") as run_dir:
            source = Path(run_dir) / "main.epl"
            source.write_text(
                'Import "epl-web"\n'
                'Import "epl-db"\n'
                'Import "epl-test"\n'
                'Say "loaded official packages"\n',
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["HOME"] = home_dir
            env["USERPROFILE"] = home_dir

            result = subprocess.run(
                [sys.executable, "-m", "epl", "run", str(source)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("loaded official packages", result.stdout)
            self.assertTrue((Path(home_dir) / ".epl" / "packages" / "epl-web").exists())
            self.assertTrue((Path(home_dir) / ".epl" / "packages" / "epl-db").exists())
            self.assertTrue((Path(home_dir) / ".epl" / "packages" / "epl-test").exists())


if __name__ == "__main__":
    unittest.main()
