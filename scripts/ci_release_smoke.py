"""Cross-platform clean-room smoke checks for wheel releases."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _venv_executable(venv_dir: Path, name: str) -> Path:
    bindir = "Scripts" if sys.platform.startswith("win") else "bin"
    suffix = ".exe" if sys.platform.startswith("win") else ""
    return venv_dir / bindir / f"{name}{suffix}"


def _run(args, *, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, args))}\n{output}")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", help="Directory containing built wheels")
    parser.add_argument("--llvm-smoke", action="store_true", help="Run Linux-only native build smoke")
    args = parser.parse_args(argv)

    dist_dir = Path(args.dist_dir).resolve()
    wheel_path = next(dist_dir.glob("*.whl"), None)
    if wheel_path is None:
        raise SystemExit(f"no wheel found in {dist_dir}")

    root = Path(tempfile.mkdtemp(prefix="epl_release_smoke_"))
    try:
        home_dir = root / "home"
        home_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)

        venv_dir = root / "venv"
        venv.EnvBuilder(with_pip=True).create(venv_dir)
        venv_python = _venv_executable(venv_dir, "python")
        epl_exe = _venv_executable(venv_dir, "epl")

        _run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root, env=env)
        _run([venv_python, "-m", "pip", "install", wheel_path], cwd=root, env=env)

        version_out = _run([epl_exe, "--version"], cwd=root, env=env)
        if "epl " not in version_out.lower():
            raise RuntimeError(f"unexpected version output:\n{version_out}")

        _run([epl_exe, "new", "smoke-demo"], cwd=root, env=env)
        project_dir = root / "smoke-demo"

        run_out = _run([epl_exe, "run"], cwd=project_dir, env=env)
        if "Hello from smoke-demo!" not in run_out:
            raise RuntimeError(f"unexpected run output:\n{run_out}")

        _run([epl_exe, "lock"], cwd=project_dir, env=env)
        _run([epl_exe, "install", "--frozen"], cwd=project_dir, env=env)
        official_out = _run([epl_exe, "install", "--no-save", "epl-web"], cwd=project_dir, env=env)
        if "Installed: epl-web" not in official_out:
            raise RuntimeError(f"unexpected official package output:\n{official_out}")

        if args.llvm_smoke:
            _run([venv_python, "-m", "pip", "install", "llvmlite"], cwd=root, env=env)
            build_out = _run([epl_exe, "build"], cwd=project_dir, env=env)
            if "Compiled successfully" not in build_out:
                raise RuntimeError(f"unexpected build output:\n{build_out}")

        print("release smoke passed")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
