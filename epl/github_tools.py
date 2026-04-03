"""GitHub project helpers for EPL CLI workflows."""

from __future__ import annotations

import os
import shutil
import subprocess


def _require_git():
    git_path = shutil.which("git")
    if not git_path:
        raise RuntimeError("git is not installed or not available on PATH.")
    return git_path


def _run_git(args, cwd=None, capture_output=False):
    git = _require_git()
    cmd = [git] + list(args)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture_output,
        text=True,
        check=True,
    )


def clone_repo(repo, dest=None, branch=None):
    from epl.package_manager import _validate_github_repo

    repo = _validate_github_repo(repo)
    clone_url = f"https://github.com/{repo}.git"
    cmd = ["clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.append(clone_url)
    if dest:
        if os.path.exists(dest):
            raise RuntimeError(f"Destination already exists: {dest}")
        cmd.append(dest)
    _run_git(cmd)
    return True


def pull_repo(path="."):
    path = os.path.abspath(path)
    _run_git(["pull", "--ff-only"], cwd=path)
    return True


def current_branch(path="."):
    path = os.path.abspath(path)
    result = _run_git(["branch", "--show-current"], cwd=path, capture_output=True)
    branch = result.stdout.strip()
    if not branch:
        raise RuntimeError("Could not determine current git branch.")
    return branch


def repo_status(path="."):
    path = os.path.abspath(path)
    result = _run_git(["status", "--porcelain"], cwd=path, capture_output=True)
    return result.stdout.strip().splitlines() if result.stdout.strip() else []


def push_repo(path=".", message="Update via EPL", remote="origin", branch=None):
    path = os.path.abspath(path)
    if branch is None:
        branch = current_branch(path)

    _run_git(["add", "-A"], cwd=path)
    changes = repo_status(path)
    if changes:
        _run_git(["commit", "-m", message, "--no-gpg-sign"], cwd=path)
    _run_git(["push", remote, branch], cwd=path)
    return True
