"""Release-tooling regression tests for packaging and import surfaces."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest
import venv
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_ENV_VAR = "EPL_RUN_RELEASE_TESTS"


class TestReleasePackaging(unittest.TestCase):
    def _run(
        self,
        args,
        *,
        cwd,
        env=None,
        expect=0,
    ):
        result = subprocess.run(
            [str(arg) for arg in args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
        )
        output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
        self.assertEqual(result.returncode, expect, output)
        return result

    def _venv_executable(self, venv_dir: Path, name: str) -> Path:
        bindir = "Scripts" if os.name == "nt" else "bin"
        suffix = ".exe" if os.name == "nt" else ""
        return venv_dir / bindir / f"{name}{suffix}"

    def _write_local_python_package(self, package_dir: Path) -> None:
        src_dir = package_dir / "demo_pydep"
        src_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "pyproject.toml").write_text(
            textwrap.dedent(
                """
                [build-system]
                requires = ["setuptools>=68"]
                build-backend = "setuptools.build_meta"

                [project]
                name = "demo-pydep"
                version = "0.1.0"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (src_dir / "__init__.py").write_text(
            "def hello():\n"
            "    return 'hello from demo_pydep'\n",
            encoding="utf-8",
        )

    def test_public_api_exports_are_lazy(self):
        script = (
            "import sys, epl; "
            "print(int('epl.interpreter' in sys.modules)); "
            "_ = epl.Interpreter; "
            "print(int('epl.interpreter' in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ["0", "1"])

    @unittest.skipUnless(
        os.environ.get(RELEASE_ENV_VAR) == "1",
        f"set {RELEASE_ENV_VAR}=1 to run release build checks",
    )
    def test_python_build_includes_runtime_assets(self):
        outdir = Path(tempfile.mkdtemp(prefix="epl_release_dist_"))
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--sdist",
                    "--outdir",
                    str(outdir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            build_output = result.stdout + "\n" + result.stderr
            self.assertEqual(result.returncode, 0, build_output)

            wheel_path = next(outdir.glob("*.whl"), None)
            sdist_path = next(outdir.glob("*.tar.gz"), None)
            self.assertIsNotNone(wheel_path, build_output)
            self.assertIsNotNone(sdist_path, build_output)

            with zipfile.ZipFile(wheel_path) as wheel_zip:
                wheel_names = set(wheel_zip.namelist())

            required_wheel_files = {
                "main.py",
                "epl/registry.json",
                "epl/runtime.c",
                "epl/models/Modelfile",
                "epl/official_packages/epl-web/epl.toml",
                "epl/official_packages/epl-web/src/main.epl",
                "epl/official_packages/epl-db/epl.toml",
                "epl/official_packages/epl-db/src/main.epl",
                "epl/official_packages/epl-test/epl.toml",
                "epl/official_packages/epl-test/src/main.epl",
                "epl/stdlib/math.epl",
                "epl/stdlib/registry.json",
                "epl/templates/android/gradlew",
                "epl/templates/android/gradlew.bat",
                "epl/templates/android/gradle/wrapper/gradle-wrapper.jar",
            }
            self.assertTrue(
                required_wheel_files.issubset(wheel_names),
                sorted(required_wheel_files - wheel_names),
            )

            with tarfile.open(sdist_path, "r:gz") as sdist_tar:
                sdist_names = set(sdist_tar.getnames())

            prefix = next(name.split("/", 1)[0] for name in sdist_names if name.endswith("PKG-INFO"))
            required_sdist_suffixes = {
                "MANIFEST.in",
                "bundle.py",
                "main.py",
                "epl/registry.json",
                "epl/runtime.c",
                "epl/models/Modelfile",
                "epl/official_packages/epl-web/epl.toml",
                "epl/official_packages/epl-web/src/main.epl",
                "epl/official_packages/epl-db/epl.toml",
                "epl/official_packages/epl-db/src/main.epl",
                "epl/official_packages/epl-test/epl.toml",
                "epl/official_packages/epl-test/src/main.epl",
                "epl/stdlib/math.epl",
                "epl/stdlib/registry.json",
                "epl/templates/android/gradlew",
                "epl/templates/android/gradlew.bat",
                "epl/templates/android/gradle/wrapper/gradle-wrapper.jar",
            }
            missing = sorted(
                suffix for suffix in required_sdist_suffixes if f"{prefix}/{suffix}" not in sdist_names
            )
            self.assertEqual(missing, [], missing)
        finally:
            shutil.rmtree(outdir, ignore_errors=True)
            shutil.rmtree(REPO_ROOT / "build", ignore_errors=True)
            for egg_info in REPO_ROOT.glob("*.egg-info"):
                shutil.rmtree(egg_info, ignore_errors=True)

    @unittest.skipUnless(
        os.environ.get(RELEASE_ENV_VAR) == "1",
        f"set {RELEASE_ENV_VAR}=1 to run clean-room release checks",
    )
    @unittest.skipIf(
        os.name == "nt",
        "clean-room native build smoke runs in the Linux release job",
    )
    def test_clean_room_install_and_cli_workflow(self):
        if shutil.which("git") is None:
            self.skipTest("git is required for the clean-room Git workflow smoke test")

        root = Path(tempfile.mkdtemp(prefix="epl_clean_room_"))
        dist_dir = root / "dist"
        venv_dir = root / "venv"
        python_pkg_dir = root / "demo_pydep"
        remote_repo = root / "remote.git"
        upstream_clone = root / "upstream"
        try:
            home_dir = root / "home"
            home_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["HOME"] = str(home_dir)
            env["USERPROFILE"] = str(home_dir)

            self._run(
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--outdir",
                    dist_dir,
                ],
                cwd=REPO_ROOT,
                env=env,
            )
            wheel_path = next(dist_dir.glob("*.whl"))

            venv.EnvBuilder(with_pip=True).create(venv_dir)
            venv_python = self._venv_executable(venv_dir, "python")
            epl_exe = self._venv_executable(venv_dir, "epl")

            self._run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], cwd=root, env=env)
            self._run([venv_python, "-m", "pip", "install", wheel_path, "llvmlite"], cwd=root, env=env)

            version_out = self._run([epl_exe, "--version"], cwd=root, env=env)
            self.assertIn("epl ", version_out.stdout)

            self._run([epl_exe, "new", "demo"], cwd=root, env=env)
            project_dir = root / "demo"

            run_out = self._run([epl_exe, "run"], cwd=project_dir, env=env)
            self.assertIn("Hello from demo!", run_out.stdout)

            self._run([epl_exe, "install"], cwd=project_dir, env=env)
            self._run([epl_exe, "lock"], cwd=project_dir, env=env)
            self._run([epl_exe, "install", "--frozen"], cwd=project_dir, env=env)
            official_pkg_out = self._run([epl_exe, "install", "--no-save", "epl-web"], cwd=project_dir, env=env)
            self.assertIn("Installed: epl-web", official_pkg_out.stdout)

            self._write_local_python_package(python_pkg_dir)
            self._run([epl_exe, "pyinstall", "demo_pydep", python_pkg_dir], cwd=project_dir, env=env)
            (project_dir / "src" / "main.epl").write_text(
                'Use python "demo_pydep"\n'
                'Print demo_pydep.hello()\n',
                encoding="utf-8",
            )
            py_bridge_out = self._run([epl_exe, "run"], cwd=project_dir, env=env)
            self.assertIn("hello from demo_pydep", py_bridge_out.stdout)

            manifest_path = project_dir / "epl.toml"
            manifest_path.write_text(
                manifest_path.read_text(encoding="utf-8").rstrip()
                + '\n\n[github-dependencies]\nweb-kit = "epl-lang/web-kit"\n',
                encoding="utf-8",
            )
            gitdeps_out = self._run([epl_exe, "gitdeps"], cwd=project_dir, env=env)
            self.assertIn("web-kit", gitdeps_out.stdout)
            self._run([epl_exe, "gitremove", "web-kit"], cwd=project_dir, env=env)
            self.assertNotIn("github-dependencies", manifest_path.read_text(encoding="utf-8"))

            self._run(["git", "init", "--bare", remote_repo], cwd=root)
            self._run(["git", "init", "-b", "main"], cwd=project_dir)
            self._run(["git", "config", "user.name", "EPL Test"], cwd=project_dir)
            self._run(["git", "config", "user.email", "epl@example.com"], cwd=project_dir)
            self._run(["git", "add", "-A"], cwd=project_dir)
            self._run(["git", "commit", "-m", "Initial commit"], cwd=project_dir)
            self._run(["git", "remote", "add", "origin", remote_repo], cwd=project_dir)
            self._run(["git", "push", "-u", "origin", "main"], cwd=project_dir)

            (project_dir / "README.md").write_text("# demo\n\nupdated by EPL push\n", encoding="utf-8")
            self._run([epl_exe, "github", "push", ".", "-m", "Update via EPL"], cwd=project_dir, env=env)

            self._run(["git", "clone", remote_repo, upstream_clone], cwd=root)
            self._run(["git", "config", "user.name", "EPL Test"], cwd=upstream_clone)
            self._run(["git", "config", "user.email", "epl@example.com"], cwd=upstream_clone)
            (upstream_clone / "README.md").write_text("# demo\n\nupdated upstream\n", encoding="utf-8")
            self._run(["git", "add", "README.md"], cwd=upstream_clone)
            self._run(["git", "commit", "-m", "Upstream change"], cwd=upstream_clone)
            self._run(["git", "push", "origin", "main"], cwd=upstream_clone)

            self._run([epl_exe, "github", "pull", "."], cwd=project_dir, env=env)
            self.assertIn("updated upstream", (project_dir / "README.md").read_text(encoding="utf-8"))

            build_out = self._run([epl_exe, "build"], cwd=project_dir, env=env)
            self.assertIn("Compiled successfully", build_out.stdout)
        finally:
            shutil.rmtree(root, ignore_errors=True)
            shutil.rmtree(REPO_ROOT / "build", ignore_errors=True)
            for egg_info in REPO_ROOT.glob("*.egg-info"):
                shutil.rmtree(egg_info, ignore_errors=True)
