"""Tests for GitHub dependency and project workflows."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.github_tools import clone_repo, pull_repo, push_repo
from epl.package_manager import (
    add_github_dependency,
    install_dependencies,
    list_github_dependencies,
    load_manifest,
    remove_github_dependency,
    save_manifest,
)


def _base_manifest() -> dict:
    return {
        "name": "demo",
        "version": "1.0.0",
        "description": "demo project",
        "author": "",
        "entry": "main.epl",
        "dependencies": {},
        "scripts": {},
    }


class TestGitHubWorkflows(unittest.TestCase):
    def test_manifest_round_trip_preserves_github_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="epl_gitdeps_manifest_") as tmpdir:
            manifest = _base_manifest()
            manifest["github-dependencies"] = {
                "web-kit": "epl-lang/web-kit",
                "starter": "someone/starter",
            }
            save_manifest(manifest, tmpdir, fmt="toml")

            loaded = load_manifest(tmpdir)
            self.assertEqual(
                loaded.get("github-dependencies"),
                {"web-kit": "epl-lang/web-kit", "starter": "someone/starter"},
            )

    def test_add_and_remove_github_dependency(self):
        with tempfile.TemporaryDirectory(prefix="epl_gitdeps_add_") as tmpdir:
            save_manifest(_base_manifest(), tmpdir, fmt="toml")

            with mock.patch("epl.package_manager.install_package", return_value=True) as install_pkg:
                ok = add_github_dependency("epl-lang/web-kit", alias="web-kit", path=tmpdir)

            self.assertTrue(ok)
            install_pkg.assert_called_once_with("github:epl-lang/web-kit", save=False, project_path=tmpdir)
            self.assertEqual(list_github_dependencies(tmpdir), [("web-kit", "epl-lang/web-kit")])

            removed = remove_github_dependency("web-kit", tmpdir)
            self.assertTrue(removed)
            self.assertEqual(list_github_dependencies(tmpdir), [])

    def test_install_dependencies_installs_declared_github_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="epl_gitdeps_install_") as tmpdir:
            manifest = _base_manifest()
            manifest["github-dependencies"] = {
                "web-kit": "epl-lang/web-kit",
                "starter": "someone/starter",
            }
            save_manifest(manifest, tmpdir, fmt="toml")

            with mock.patch("epl.package_manager.install_package", return_value=True) as install_pkg:
                ok = install_dependencies(tmpdir)

            self.assertTrue(ok)
            installed_specs = [call.args[0] for call in install_pkg.call_args_list]
            self.assertEqual(installed_specs, ["github:epl-lang/web-kit", "github:someone/starter"])

    def test_clone_repo_uses_git(self):
        with mock.patch("epl.github_tools.shutil.which", return_value="git"):
            with mock.patch("epl.github_tools.subprocess.run") as run_git:
                clone_repo("epl-lang/epl", dest="demo")

        run_git.assert_called_once()
        cmd = run_git.call_args.kwargs.get("args") or run_git.call_args.args[0]
        self.assertEqual(cmd[:5], ["git", "clone", "--depth", "1", "https://github.com/epl-lang/epl.git"])
        self.assertEqual(cmd[-1], "demo")

    def test_pull_repo_uses_ff_only(self):
        with mock.patch("epl.github_tools.shutil.which", return_value="git"):
            with mock.patch("epl.github_tools.subprocess.run") as run_git:
                pull_repo(".")

        cmd = run_git.call_args.kwargs.get("args") or run_git.call_args.args[0]
        self.assertEqual(cmd[:3], ["git", "pull", "--ff-only"])

    def test_push_repo_commits_when_repo_is_dirty(self):
        with mock.patch("epl.github_tools.shutil.which", return_value="git"):
            with mock.patch("epl.github_tools.subprocess.run") as run_git:
                run_git.side_effect = [
                    mock.Mock(stdout="main\n"),
                    mock.Mock(stdout=""),
                    mock.Mock(stdout="M README.md\n"),
                    mock.Mock(stdout=""),
                    mock.Mock(stdout=""),
                ]
                ok = push_repo(path=".", message="Update", remote="origin", branch=None)

        self.assertTrue(ok)
        calls = [call.kwargs.get("args") or call.args[0] for call in run_git.call_args_list]
        self.assertEqual(calls[0][:3], ["git", "branch", "--show-current"])
        self.assertEqual(calls[1][:3], ["git", "add", "-A"])
        self.assertEqual(calls[2][:3], ["git", "status", "--porcelain"])
        self.assertEqual(calls[3][:5], ["git", "commit", "-m", "Update", "--no-gpg-sign"])
        self.assertEqual(calls[4][:4], ["git", "push", "origin", "main"])
