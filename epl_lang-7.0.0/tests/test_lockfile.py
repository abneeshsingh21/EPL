"""Lockfile v3 regression tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.package_manager import (
    LOCKFILE_NAME,
    create_lockfile,
    install_dependencies,
    install_from_lockfile,
    load_lockfile,
    register_installed_package,
    save_manifest,
)


def _base_manifest() -> dict:
    return {
        "name": "demo",
        "version": "1.0.0",
        "description": "demo project",
        "author": "",
        "entry": "src/main.epl",
        "dependencies": {"demo-lib": "^1.2.3"},
        "python-dependencies": {"yaml": "pyyaml>=6"},
        "github-dependencies": {"web-kit": "epl-lang/web-kit"},
        "scripts": {},
    }


class TestLockfileV3(unittest.TestCase):
    def _patch_package_dirs(self, tmpdir: str):
        packages_dir = Path(tmpdir, "packages")
        packages_dir.mkdir(parents=True, exist_ok=True)
        epl_home = Path(tmpdir, "epl_home")
        epl_home.mkdir(parents=True, exist_ok=True)
        return mock.patch.multiple(
            "epl.package_manager",
            PACKAGES_DIR=str(packages_dir),
            EPL_HOME=str(epl_home),
        )

    def test_load_lockfile_migrates_v2_shape(self):
        with tempfile.TemporaryDirectory(prefix="epl_lock_v2_") as tmpdir:
            Path(tmpdir, LOCKFILE_NAME).write_text(
                json.dumps(
                    {
                        "lockfileVersion": 2,
                        "created": 123.0,
                        "packages": {"demo-lib": {"version": "1.2.3", "integrity": "abc"}},
                    }
                ),
                encoding="utf-8",
            )

            lock = load_lockfile(tmpdir)

            self.assertEqual(lock["lockfileVersion"], 3)
            self.assertEqual(lock["metadata"]["created"], 123.0)
            self.assertEqual(lock["packages"]["demo-lib"]["version"], "1.2.3")
            self.assertEqual(lock["python_packages"], {})
            self.assertEqual(lock["github_packages"], {})

    def test_create_lockfile_v3_is_deterministic_and_tracks_all_dependency_types(self):
        with tempfile.TemporaryDirectory(prefix="epl_lock_create_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                project_dir = Path(tmpdir, "project")
                project_dir.mkdir()
                Path(project_dir, "src").mkdir()
                Path(project_dir, "src", "main.epl").write_text('Say "hi"\n', encoding="utf-8")
                save_manifest(_base_manifest(), str(project_dir), fmt="toml")

                package_dir = Path(tmpdir, "packages", "demo-lib")
                package_dir.mkdir(parents=True)
                save_manifest(
                    {
                        "name": "demo-lib",
                        "version": "1.2.3",
                        "description": "",
                        "author": "",
                        "entry": "main.epl",
                        "dependencies": {},
                        "scripts": {},
                    },
                    str(package_dir),
                    fmt="toml",
                )
                Path(package_dir, "main.epl").write_text('Say "demo"\n', encoding="utf-8")

                github_pkg_dir = Path(tmpdir, "packages", "web-kit-pkg")
                github_pkg_dir.mkdir(parents=True)
                save_manifest(
                    {
                        "name": "web-kit-pkg",
                        "version": "2.1.0",
                        "description": "",
                        "author": "",
                        "entry": "main.epl",
                        "dependencies": {},
                        "scripts": {},
                    },
                    str(github_pkg_dir),
                    fmt="toml",
                )
                Path(github_pkg_dir, "main.epl").write_text('Say "web"\n', encoding="utf-8")
                register_installed_package(
                    "web-kit-pkg",
                    "2.1.0",
                    "github:epl-lang/web-kit",
                    str(github_pkg_dir),
                    metadata={
                        "repo": "epl-lang/web-kit",
                        "commit": "abc123def456",
                        "archive_integrity": "ziphash",
                    },
                )

                resolved = {"demo-lib": {"version": "1.2.3", "required_by": ["root"]}}
                py_info = {
                    "distribution": "PyYAML",
                    "version": "6.0.1",
                    "integrity": "pyhash",
                }
                with mock.patch("epl.package_manager.resolve_dependencies", return_value=resolved):
                    with mock.patch(
                        "epl.package_manager._resolve_installed_python_package",
                        return_value=py_info,
                    ):
                        create_lockfile(str(project_dir))
                        first = Path(project_dir, LOCKFILE_NAME).read_text(encoding="utf-8")
                        create_lockfile(str(project_dir))
                        second = Path(project_dir, LOCKFILE_NAME).read_text(encoding="utf-8")

                self.assertEqual(first, second)
                lock = load_lockfile(str(project_dir))
                self.assertEqual(lock["lockfileVersion"], 3)
                self.assertNotIn("created", lock)
                self.assertEqual(lock["packages"]["demo-lib"]["version"], "1.2.3")
                self.assertEqual(lock["python_packages"]["yaml"]["distribution"], "PyYAML")
                self.assertEqual(lock["github_packages"]["web-kit"]["repo"], "epl-lang/web-kit")
                self.assertEqual(lock["github_packages"]["web-kit"]["commit"], "abc123def456")

    def test_install_dependencies_frozen_requires_lockfile(self):
        with tempfile.TemporaryDirectory(prefix="epl_lock_frozen_missing_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                project_dir = Path(tmpdir, "project")
                project_dir.mkdir()
                Path(project_dir, "src").mkdir()
                Path(project_dir, "src", "main.epl").write_text('Say "hi"\n', encoding="utf-8")
                save_manifest(_base_manifest(), str(project_dir), fmt="toml")

                ok = install_dependencies(str(project_dir), frozen=True)

                self.assertFalse(ok)

    def test_install_from_lockfile_uses_exact_locked_versions(self):
        with tempfile.TemporaryDirectory(prefix="epl_lock_install_") as tmpdir:
            with self._patch_package_dirs(tmpdir):
                project_dir = Path(tmpdir, "project")
                project_dir.mkdir()
                Path(project_dir, "src").mkdir()
                Path(project_dir, "src", "main.epl").write_text('Say "hi"\n', encoding="utf-8")
                save_manifest(_base_manifest(), str(project_dir), fmt="toml")

                Path(project_dir, LOCKFILE_NAME).write_text(
                    json.dumps(
                        {
                            "lockfileVersion": 3,
                            "metadata": {"project": "demo", "manifest": "epl.toml"},
                            "packages": {
                                "demo-lib": {
                                    "version": "1.2.3",
                                    "integrity": "pkg-hash",
                                    "required_by": ["root"],
                                }
                            },
                            "python_packages": {
                                "yaml": {
                                    "distribution": "PyYAML",
                                    "version": "6.0.1",
                                    "pip_spec": "pyyaml>=6",
                                    "integrity": "py-hash",
                                }
                            },
                            "github_packages": {
                                "web-kit": {
                                    "repo": "epl-lang/web-kit",
                                    "commit": "abc123",
                                    "package": "web-kit-pkg",
                                    "version": "2.1.0",
                                    "integrity": "pkg-hash",
                                    "archive_integrity": "zip-hash",
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                with mock.patch("epl.package_manager.install_package", return_value=True) as install_pkg:
                    with mock.patch("epl.package_manager._install_from_github", return_value=True) as install_git:
                        with mock.patch("epl.package_manager.subprocess.check_call", return_value=0) as pip_call:
                            with mock.patch(
                                "epl.package_manager._resolve_installed_python_package",
                                return_value={
                                    "distribution": "PyYAML",
                                    "version": "6.0.1",
                                    "integrity": "py-hash",
                                },
                            ):
                                with mock.patch(
                                    "epl.package_manager.verify_lockfile",
                                    return_value={"valid": True, "mismatches": [], "missing": []},
                                ):
                                    ok = install_from_lockfile(
                                        str(project_dir),
                                        include_bridge=True,
                                        strict=True,
                                    )

                self.assertTrue(ok)
                install_pkg.assert_called_once_with("demo-lib", "1.2.3")
                install_git.assert_called_once_with(
                    "epl-lang/web-kit",
                    commit="abc123",
                    expected_sha256="zip-hash",
                )
                pip_call.assert_called_once_with(
                    [sys.executable, "-m", "pip", "install", "PyYAML==6.0.1"]
                )
