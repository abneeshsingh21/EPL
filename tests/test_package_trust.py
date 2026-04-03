"""Regression tests for package trust and supported official packages."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.package_manager import (
    LOCKFILE_NAME,
    audit_packages,
    install_package,
    load_local_registry,
    outdated_packages,
    save_manifest,
    search_packages,
)


def _project_manifest() -> dict:
    return {
        "name": "trust-demo",
        "version": "1.0.0",
        "description": "trust demo",
        "author": "",
        "entry": "src/main.epl",
        "dependencies": {"epl-web": "^7.0.0"},
        "python-dependencies": {"yaml": "pyyaml>=6"},
        "github-dependencies": {"web-kit": "epl-lang/web-kit"},
        "scripts": {},
    }


class TestPackageTrust(unittest.TestCase):
    def _patch_package_dirs(self, tmpdir: str):
        packages_dir = Path(tmpdir, "packages")
        packages_dir.mkdir(parents=True, exist_ok=True)
        epl_home = Path(tmpdir, "epl_home")
        epl_home.mkdir(parents=True, exist_ok=True)
        cache_dir = epl_home / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return mock.patch.multiple(
            "epl.package_manager",
            PACKAGES_DIR=str(packages_dir),
            EPL_HOME=str(epl_home),
            CACHE_DIR=str(cache_dir),
        )

    def test_search_packages_merges_package_index_results(self):
        fake_entry = SimpleNamespace(
            name="epl-web",
            latest_version=SimpleNamespace(version="7.1.0"),
            metadata=SimpleNamespace(description="Official EPL web package"),
        )
        with mock.patch("epl.package_index.PackageIndex.search", return_value=[fake_entry]):
            results = search_packages("web")

        match = next((item for item in results if item["name"] == "epl-web"), None)
        self.assertIsNotNone(match)
        self.assertEqual(match["latest"], "7.1.0")
        self.assertEqual(match["description"], "Official EPL web package")

    def test_outdated_packages_uses_index_latest_and_marks_major_updates(self):
        with tempfile.TemporaryDirectory(prefix="epl_trust_outdated_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                project_dir = Path(tmpdir, "project")
                project_dir.mkdir()
                (project_dir / "src").mkdir()
                (project_dir / "src" / "main.epl").write_text('Say "hi"\n', encoding="utf-8")
                save_manifest(_project_manifest(), str(project_dir), fmt="toml")

                installed_pkg = Path(tmpdir, "packages", "epl-web")
                installed_pkg.mkdir(parents=True)
                save_manifest(
                    {
                        "name": "epl-web",
                        "version": "7.0.0",
                        "description": "installed web facade",
                        "author": "EPL Team",
                        "entry": "src/main.epl",
                        "dependencies": {},
                        "scripts": {},
                    },
                    str(installed_pkg),
                    fmt="toml",
                )
                (installed_pkg / "src").mkdir()
                (installed_pkg / "src" / "main.epl").write_text('Say "web"\n', encoding="utf-8")

                fake_entry = SimpleNamespace(
                    latest_version=SimpleNamespace(version="8.0.0"),
                )
                with mock.patch("epl.package_manager._get_index_entry", return_value=fake_entry):
                    results = outdated_packages(str(project_dir))

                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["name"], "epl-web")
                self.assertEqual(results[0]["current"], "7.0.0")
                self.assertEqual(results[0]["latest"], "8.0.0")
                self.assertEqual(results[0]["constraint"], "^7.0.0")
                self.assertTrue(results[0]["major_update"])

    def test_audit_packages_flags_unpinned_github_and_missing_python_lock_entries(self):
        with tempfile.TemporaryDirectory(prefix="epl_trust_audit_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                project_dir = Path(tmpdir, "project")
                project_dir.mkdir()
                (project_dir / "src").mkdir()
                (project_dir / "src" / "main.epl").write_text('Say "hi"\n', encoding="utf-8")
                save_manifest(_project_manifest(), str(project_dir), fmt="toml")

                Path(project_dir, LOCKFILE_NAME).write_text(
                    json.dumps(
                        {
                            "lockfileVersion": 3,
                            "metadata": {"project": "trust-demo", "manifest": "epl.toml"},
                            "packages": {},
                            "python_packages": {},
                            "github_packages": {
                                "web-kit": {
                                    "repo": "epl-lang/web-kit",
                                    "version": "1.0.0",
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                results = audit_packages(str(project_dir))

                self.assertIn("yaml: missing from lockfile python_packages", results["warnings"])
                self.assertIn("web-kit: lockfile is not pinned to a commit", results["errors"])

    def test_install_package_prefers_bundled_official_package(self):
        with tempfile.TemporaryDirectory(prefix="epl_trust_official_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                ok = install_package("epl-web", save=False, project_path=tmpdir)

                self.assertTrue(ok)
                installed_manifest = Path(tmpdir, "packages", "epl-web", "epl.toml").read_text(
                    encoding="utf-8"
                )
                self.assertIn('name = "epl-web"', installed_manifest)
                self.assertTrue(
                    Path(tmpdir, "packages", "epl-web", "src", "main.epl").is_file()
                )

                registry = load_local_registry()
                self.assertEqual(registry["epl-web"]["source"], "official:epl-web")

    def test_install_package_resolves_prefixed_official_package_names(self):
        with tempfile.TemporaryDirectory(prefix="epl_trust_prefixed_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                ok = install_package("test", save=False, project_path=tmpdir)

                self.assertTrue(ok)
                self.assertTrue(
                    Path(tmpdir, "packages", "epl-test", "src", "main.epl").is_file()
                )

                registry = load_local_registry()
                self.assertEqual(registry["epl-test"]["source"], "official:epl-test")
