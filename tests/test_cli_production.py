"""Regression tests for the production-facing CLI and packager paths."""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.cli import cli_main
from epl.package_manager import load_manifest, save_manifest
from epl.packager import BuildConfig


def _write_manifest(project_dir: str, entry: str = "src/main.epl") -> None:
    manifest = {
        "name": "demo",
        "version": "1.0.0",
        "description": "demo project",
        "author": "",
        "entry": entry,
        "dependencies": {},
        "scripts": {},
    }
    save_manifest(manifest, project_dir, fmt="toml")


class TestCLIProduction(unittest.TestCase):
    def test_run_strict_uses_current_typechecker_api(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_strict_") as tmpdir:
            source = Path(tmpdir) / "hello.epl"
            source.write_text('Say "Hello strict"\n', encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "epl", "run", str(source), "--strict"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Hello strict", result.stdout)

    def test_run_sandbox_blocks_file_write(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_sandbox_") as tmpdir:
            output = Path(tmpdir) / "wrote.txt"
            source = Path(tmpdir) / "write.epl"
            source.write_text(
                f'Write "blocked" to file "{output.as_posix()}"\n',
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-m", "epl", "run", str(source), "--sandbox"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn("safe mode", result.stderr.lower())

    def test_build_defaults_to_manifest_entrypoint(self):
        tmpdir = tempfile.mkdtemp(prefix="epl_cli_build_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            os.makedirs("src", exist_ok=True)
            Path("src/main.epl").write_text('Say "Hello build"\n', encoding="utf-8")
            _write_manifest(tmpdir, entry="src/main.epl")

            with mock.patch("epl.cli._legacy_dispatch", return_value=0) as legacy_dispatch:
                exit_code = cli_main(["build"])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_called_once_with(["build", "src/main.epl"])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_build_defaults_to_manifest_entrypoint_when_only_flags_are_passed(self):
        tmpdir = tempfile.mkdtemp(prefix="epl_cli_build_flags_")
        old_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            os.makedirs("src", exist_ok=True)
            Path("src/main.epl").write_text('Say "Hello build flags"\n', encoding="utf-8")
            _write_manifest(tmpdir, entry="src/main.epl")

            with mock.patch("epl.cli._legacy_dispatch", return_value=0) as legacy_dispatch:
                exit_code = cli_main(["build", "--no-static"])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_called_once_with(["build", "src/main.epl", "--no-static"])
        finally:
            os.chdir(old_cwd)
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_legacy_build_returns_nonzero_on_native_compile_failure(self):
        import main as main_module

        with mock.patch("main.compile_file", return_value=False) as compile_file:
            exit_code = main_module.legacy_main(["build", "src/main.epl"])

        self.assertEqual(exit_code, 1)
        compile_file.assert_called_once_with("src/main.epl", opt_level=2, static=True, target=None)

    def test_packager_reads_toml_project_manifest(self):
        with tempfile.TemporaryDirectory(prefix="epl_packager_toml_") as tmpdir:
            os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
            Path(tmpdir, "src", "main.epl").write_text('Say "Hello package"\n', encoding="utf-8")
            _write_manifest(tmpdir, entry="src/main.epl")

            config = BuildConfig.from_epl_project(tmpdir)

            self.assertTrue(config.source_file.endswith(os.path.join("src", "main.epl")))
            self.assertEqual(config.output_name, "demo")
            self.assertEqual(config.version, "1.0.0")

    def test_new_project_readme_exposes_dependency_and_github_workflows(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_new_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with redirect_stdout(StringIO()):
                    exit_code = cli_main(["new", "sampleapp"])

                self.assertEqual(exit_code, 0)
                readme = Path(tmpdir, "sampleapp", "README.md").read_text(encoding="utf-8")
                self.assertIn("epl install", readme)
                self.assertIn("epl pyinstall requests", readme)
                self.assertIn("epl gitinstall owner/repo alias", readme)
                self.assertIn('epl github push . -m "Update project"', readme)
            finally:
                os.chdir(old_cwd)

    def test_new_project_web_template_uses_supported_packages(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_new_web_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with redirect_stdout(StringIO()):
                    exit_code = cli_main(["new", "webapp", "--template", "web"])

                self.assertEqual(exit_code, 0)
                manifest = load_manifest(Path(tmpdir, "webapp"))
                self.assertEqual(manifest["dependencies"]["epl-web"], "^7.0.0")
                self.assertEqual(manifest["scripts"]["serve"], "epl serve src/main.epl")

                source = Path(tmpdir, "webapp", "src", "main.epl").read_text(encoding="utf-8")
                self.assertIn('Import "epl-web"', source)
                self.assertIn('Call get_route(app, "/api/health"', source)
            finally:
                os.chdir(old_cwd)

    def test_new_project_lib_template_creates_testable_scaffold(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_new_lib_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with redirect_stdout(StringIO()):
                    exit_code = cli_main(["new", "mylib", "--template", "lib"])

                self.assertEqual(exit_code, 0)
                manifest = load_manifest(Path(tmpdir, "mylib"))
                self.assertEqual(manifest["dependencies"]["epl-test"], "^7.0.0")

                test_source = Path(tmpdir, "mylib", "tests", "test_main.epl").read_text(encoding="utf-8")
                self.assertIn('Import "src/main.epl"', test_source)
                self.assertIn('Import "epl-test"', test_source)
                self.assertIn('Call test_summary()', test_source)
            finally:
                os.chdir(old_cwd)

    def test_install_frozen_uses_package_manager_strict_mode(self):
        with mock.patch("epl.package_manager.install_dependencies", return_value=True) as install_deps:
            exit_code = cli_main(["install", "--frozen"])

        self.assertEqual(exit_code, 0)
        install_deps.assert_called_once_with(".", frozen=True)

    def test_uninstall_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.uninstall_package", return_value=True) as uninstall_package:
            exit_code = cli_main(["uninstall", "epl-web"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        uninstall_package.assert_called_once_with("epl-web")

    def test_packages_list_uses_package_manager_without_legacy_dispatch(self):
        stdout = StringIO()
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch(
                 "epl.package_manager.list_packages",
                 return_value=[("epl-web", "7.0.0", "Supported web facade")],
             ), \
             redirect_stdout(stdout):
            exit_code = cli_main(["packages"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        self.assertIn("epl-web @ 7.0.0", stdout.getvalue())

    def test_add_dependency_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.add_dependency", return_value=True) as add_dependency:
            exit_code = cli_main(["add", "epl-web", "^7.0.0", "--dev"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        add_dependency.assert_called_once_with("epl-web", "^7.0.0", path=".", dev=True)

    def test_remove_dependency_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.remove_dependency", return_value=True) as remove_dependency:
            exit_code = cli_main(["remove", "epl-web"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        remove_dependency.assert_called_once_with("epl-web", path=".")

    def test_tree_command_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.print_dependency_tree") as print_dependency_tree:
            exit_code = cli_main(["tree"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        print_dependency_tree.assert_called_once_with(".")

    def test_migrate_command_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.migrate_manifest_to_toml", return_value=True) as migrate_manifest:
            exit_code = cli_main(["migrate"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        migrate_manifest.assert_called_once_with(".")

    def test_cache_clean_uses_package_manager_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.package_manager.clean_cache") as clean_cache:
            exit_code = cli_main(["cache", "clean"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        clean_cache.assert_called_once_with()

    def test_publish_info_and_stats_use_direct_registry_paths(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.registry.registry_publish") as registry_publish, \
             mock.patch("epl.registry.registry_info") as registry_info, \
             mock.patch("epl.registry.registry_stats") as registry_stats:
            publish_exit = cli_main(["publish", ".", "--repo", "epl-lang/epl-web"])
            info_exit = cli_main(["info", "epl-web"])
            stats_exit = cli_main(["stats"])

        self.assertEqual(publish_exit, 0)
        self.assertEqual(info_exit, 0)
        self.assertEqual(stats_exit, 0)
        legacy_dispatch.assert_not_called()
        registry_publish.assert_called_once_with(".", repo="epl-lang/epl-web")
        registry_info.assert_called_once_with("epl-web")
        registry_stats.assert_called_once_with()

    def test_update_major_passes_allow_major_to_package_manager(self):
        with mock.patch("epl.package_manager.update_package", return_value=True) as update_pkg:
            exit_code = cli_main(["update", "epl-web", "--major"])

        self.assertEqual(exit_code, 0)
        update_pkg.assert_called_once_with("epl-web", ".", allow_major=True)

    def test_fmt_check_returns_nonzero_when_formatting_is_needed(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_fmt_check_") as tmpdir:
            source = Path(tmpdir, "main.epl")
            source.write_text('print "hello"\n', encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = cli_main(["fmt", str(source), "--check"])

            self.assertEqual(exit_code, 1)

    def test_fmt_in_place_formats_epl_source(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_fmt_write_") as tmpdir:
            source = Path(tmpdir, "main.epl")
            source.write_text('if x then\nprint "hello"\nend', encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = cli_main(["fmt", str(source), "--in-place"])

            self.assertEqual(exit_code, 0)
            content = source.read_text(encoding="utf-8")
            self.assertIn('If x then', content)
            self.assertIn('    Print "hello"', content)

    def test_serve_uses_direct_cli_runtime_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_serve_") as tmpdir:
            source = Path(tmpdir, "app.epl")
            source.write_text(
                'Create WebApp called app\n'
                'Route "/" shows\n'
                '    Page "Serve Test"\n'
                '        Text "ok"\n'
                '    End\n'
                'End\n',
                encoding="utf-8",
            )

            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                 mock.patch("epl.store_backends.configure_backends") as configure_backends, \
                 mock.patch("epl.deploy.serve") as serve:
                exit_code = cli_main(
                    [
                        "serve",
                        str(source),
                        "--port",
                        "8123",
                        "--workers",
                        "2",
                        "--store",
                        "sqlite",
                        "--session",
                        "memory",
                    ]
                )

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            configure_backends.assert_called_once_with(store="sqlite", session="memory")
            serve.assert_called_once()
            self.assertEqual(serve.call_args.kwargs["port"], 8123)
            self.assertEqual(serve.call_args.kwargs["workers"], 2)

    def test_deploy_uses_direct_module_cli_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.deploy.deploy_cli") as deploy_cli:
            exit_code = cli_main(["deploy", "docker"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        deploy_cli.assert_called_once_with(["docker"])

    def test_lint_emits_json_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_lint_") as tmpdir:
            source = Path(tmpdir, "lint_me.epl")
            source.write_text("Print \"hello\"   \n", encoding="utf-8")

            stdout = StringIO()
            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, redirect_stdout(stdout):
                exit_code = cli_main(["lint", str(source), "--format", "json"])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            payload = json.loads(stdout.getvalue())
            self.assertTrue(any(issue["rule"] == "trailing-whitespace" for issue in payload))

    def test_docs_generates_requested_output_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_docs_") as tmpdir:
            source = Path(tmpdir, "docs_me.epl")
            output_dir = Path(tmpdir, "generated-docs")
            source.write_text(
                "// Demo function\n"
                "Function Hello(name)\n"
                "    Return name\n"
                "End\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, redirect_stdout(stdout):
                exit_code = cli_main(
                    ["docs", str(source), "--output", str(output_dir), "--format", "json"]
                )

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            self.assertTrue((output_dir / "api.json").exists())

    def test_bench_uses_direct_runner_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("benchmarks.run_benchmarks.run_suite") as run_suite:
            exit_code = cli_main(["bench", "--runs=1", "--warmup=0", "--json"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        run_suite.assert_called_once_with(runs=1, warmup=0, json_output=True)

    def test_benchmark_command_runs_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_benchmark_") as tmpdir:
            source = Path(tmpdir, "bench.epl")
            source.write_text('Say "benchmark"\n', encoding="utf-8")

            stdout = StringIO()
            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, redirect_stdout(stdout):
                exit_code = cli_main(["benchmark", str(source), "--runs=1", "--warmup=0"])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            output = stdout.getvalue()
            self.assertIn("EPL Benchmark", output)
            self.assertIn("VM:", output)

    def test_profile_command_runs_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_profile_") as tmpdir:
            source = Path(tmpdir, "profile.epl")
            source.write_text('Say "profile"\n', encoding="utf-8")

            stdout = StringIO()
            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, redirect_stdout(stdout):
                exit_code = cli_main(["profile", str(source)])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            output = stdout.getvalue()
            self.assertIn("EPL Profiler", output)
            self.assertIn("Wall time:", output)

    def test_lsp_starts_direct_server_without_legacy_dispatch(self):
        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.lsp_server.EPLLanguageServer") as server_cls:
            exit_code = cli_main(["lsp", "--tcp", "--port", "2099"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        server_cls.return_value.start_tcp.assert_called_once_with(2099)

    def test_js_and_node_transpilers_use_direct_cli_paths(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_transpile_js_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("hello.epl")
                source.write_text('Say "Hello JS"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch:
                    js_exit = cli_main(["js", str(source)])
                    node_exit = cli_main(["node", str(source)])

                self.assertEqual(js_exit, 0)
                self.assertEqual(node_exit, 0)
                legacy_dispatch.assert_not_called()
                self.assertTrue(Path("hello.js").exists())
                self.assertTrue(Path("hello.node.js").exists())
            finally:
                os.chdir(old_cwd)

    def test_kotlin_and_python_transpilers_use_direct_cli_paths(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_transpile_langs_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("hello.epl")
                source.write_text('Say "Hello"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch:
                    kotlin_exit = cli_main(["kotlin", str(source)])
                    python_exit = cli_main(["python", str(source)])

                self.assertEqual(kotlin_exit, 0)
                self.assertEqual(python_exit, 0)
                legacy_dispatch.assert_not_called()
                self.assertTrue(Path("hello.kt").exists())
                self.assertTrue(Path("hello.py").exists())
            finally:
                os.chdir(old_cwd)

    def test_android_generation_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_android_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("mobile.epl")
                source.write_text('Say "mobile"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.kotlin_gen.generate_android_project") as generator:
                    exit_code = cli_main(["android", str(source), "--compose"])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                generator.assert_called_once()
                self.assertEqual(generator.call_args.args[1], "mobile_android")
            finally:
                os.chdir(old_cwd)

    def test_desktop_generation_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_desktop_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("desktop.epl")
                source.write_text('Say "desktop"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.desktop.generate_desktop_project") as generator:
                    exit_code = cli_main(
                        ["desktop", str(source), "--name", "DeskApp", "--width", "1024", "--height", "768"]
                    )

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                generator.assert_called_once()
                self.assertEqual(generator.call_args.args[1], "desktop_desktop")
                self.assertEqual(generator.call_args.kwargs["app_name"], "DeskApp")
                self.assertEqual(generator.call_args.kwargs["width"], 1024)
                self.assertEqual(generator.call_args.kwargs["height"], 768)
            finally:
                os.chdir(old_cwd)

    def test_web_generation_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_web_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("browser.epl")
                source.write_text('Say "browser"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.wasm_web.generate_web_project") as generator:
                    exit_code = cli_main(["web", str(source), "--mode", "wasm", "--name", "BrowserApp"])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                generator.assert_called_once()
                self.assertEqual(generator.call_args.args[1], "browser_web")
                self.assertEqual(generator.call_args.kwargs["app_name"], "BrowserApp")
                self.assertEqual(generator.call_args.kwargs["mode"], "wasm")
            finally:
                os.chdir(old_cwd)

    def test_ir_command_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_ir_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("irtest.epl")
                source.write_text('Say "ir"\n', encoding="utf-8")

                stdout = StringIO()
                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.compiler.Compiler") as compiler_cls, \
                     redirect_stdout(stdout):
                    compiler_cls.return_value.get_ir.return_value = "; mock ir"
                    exit_code = cli_main(["ir", str(source)])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                self.assertIn("; mock ir", stdout.getvalue())
            finally:
                os.chdir(old_cwd)

    def test_package_command_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_package_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("pack.epl")
                source.write_text('Say "pack"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.packager.package", return_value="dist/pack.zip") as package_fn:
                    exit_code = cli_main(["package", str(source), "--mode", "zip", "--output", "dist"])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                package_fn.assert_called_once()
                self.assertEqual(package_fn.call_args.kwargs["mode"], "zip")
                self.assertEqual(package_fn.call_args.kwargs["output_dir"], "dist")
            finally:
                os.chdir(old_cwd)

    def test_debug_command_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_debug_") as tmpdir:
            source = Path(tmpdir, "debug.epl")
            source.write_text('Say "debug"\n', encoding="utf-8")

            fake_state = mock.Mock()
            fake_state.breakpoints = []
            fake_state.source_lines = []
            fake_state.source_file = ""

            with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                 mock.patch("epl.debugger.EPLDebugger") as debugger_cls, \
                 mock.patch("epl.debugger.DebugInterpreter") as interpreter_cls:
                debugger_cls.return_value.state = fake_state
                exit_code = cli_main(["debug", str(source), "-b", "5", "-b", "main"])

            self.assertEqual(exit_code, 0)
            legacy_dispatch.assert_not_called()
            fake_state.add_breakpoint.assert_any_call(line=5)
            fake_state.add_breakpoint.assert_any_call(function_name="main")
            interpreter_cls.return_value.execute.assert_called_once()

    def test_test_command_uses_native_test_framework_without_legacy_dispatch(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_test_runner_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                tests_dir = Path("tests")
                tests_dir.mkdir()
                Path("tests", "test_math.epl").write_text(
                    'Define Function test_numbers\n'
                    '    Call expect_equal(2 + 2, 4, "two plus two")\n'
                    'End\n',
                    encoding="utf-8",
                )

                stdout = StringIO()
                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, redirect_stdout(stdout):
                    exit_code = cli_main(["test"])

                self.assertEqual(exit_code, 0, stdout.getvalue())
                legacy_dispatch.assert_not_called()
                self.assertIn("Test Results", stdout.getvalue())
                self.assertIn("passed", stdout.getvalue())
            finally:
                os.chdir(old_cwd)

    def test_gui_command_uses_direct_runtime_without_legacy_dispatch(self):
        fake_program = object()
        fake_interpreter = mock.Mock()
        fake_interpreter.global_env = mock.Mock()

        with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
             mock.patch("epl.cli._load_epl_program", return_value=("", fake_program)), \
             mock.patch("epl.gui.gui_available", return_value=True), \
             mock.patch("epl.interpreter.Interpreter", return_value=fake_interpreter):
            exit_code = cli_main(["gui", "app.epl"])

        self.assertEqual(exit_code, 0)
        legacy_dispatch.assert_not_called()
        fake_interpreter.global_env.define_variable.assert_called_once()
        fake_interpreter.execute.assert_called_once_with(fake_program)

    def test_wasm_command_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_wasm_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("module.epl")
                source.write_text('Say "wasm"\n', encoding="utf-8")

                stdout = StringIO()
                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch("epl.compiler.Compiler") as compiler_cls, \
                     redirect_stdout(stdout):
                    compiler_cls.return_value.compile_to_wasm.return_value = "module.wasm"
                    exit_code = cli_main(["wasm", str(source)])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                compiler_cls.return_value.compile_to_wasm.assert_called_once()
                self.assertIn("module.wasm", stdout.getvalue())
            finally:
                os.chdir(old_cwd)

    def test_micropython_command_uses_direct_cli_path(self):
        with tempfile.TemporaryDirectory(prefix="epl_cli_mpy_") as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                source = Path("board.epl")
                source.write_text('Say "mpy"\n', encoding="utf-8")

                with mock.patch("epl.cli._legacy_dispatch") as legacy_dispatch, \
                     mock.patch(
                         "epl.micropython_transpiler.transpile_to_micropython",
                         return_value="# micropython output\n",
                     ):
                    exit_code = cli_main(["micropython", str(source), "--target", "pico"])

                self.assertEqual(exit_code, 0)
                legacy_dispatch.assert_not_called()
                output_file = Path("board_pico_mpy.py")
                self.assertTrue(output_file.exists())
                self.assertIn("# micropython output", output_file.read_text(encoding="utf-8"))
            finally:
                os.chdir(old_cwd)
