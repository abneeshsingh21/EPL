"""Tests for manifest-driven Python ecosystem dependencies in EPL."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import epl.interpreter as interpreter_mod
from epl.interpreter import Interpreter, PythonModule
from epl.lexer import Lexer
from epl.package_manager import install_dependencies, install_python_package, load_manifest, save_manifest
from epl.parser import Parser


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


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


class TestPythonDependencyBridge(unittest.TestCase):
    def test_manifest_round_trip_preserves_python_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="epl_pydeps_manifest_") as tmpdir:
            manifest = _base_manifest()
            manifest["python-dependencies"] = {
                "requests": "*",
                "yaml": "pyyaml>=6",
            }

            save_manifest(manifest, tmpdir, fmt="toml")
            loaded = load_manifest(tmpdir)

            self.assertEqual(
                loaded.get("python-dependencies"),
                {"requests": "*", "yaml": "pyyaml>=6"},
            )

    def test_install_python_package_saves_manifest(self):
        with tempfile.TemporaryDirectory(prefix="epl_pydeps_install_") as tmpdir:
            save_manifest(_base_manifest(), tmpdir, fmt="toml")

            with mock.patch("epl.package_manager.subprocess.check_call", return_value=0) as pip_call:
                ok = install_python_package("yaml", "pyyaml>=6", project_path=tmpdir)

            self.assertTrue(ok)
            pip_call.assert_called_once_with([sys.executable, "-m", "pip", "install", "pyyaml>=6"])
            loaded = load_manifest(tmpdir)
            self.assertEqual(loaded["python-dependencies"]["yaml"], "pyyaml>=6")

    def test_install_dependencies_installs_declared_python_dependencies(self):
        with tempfile.TemporaryDirectory(prefix="epl_pydeps_all_") as tmpdir:
            manifest = _base_manifest()
            manifest["python-dependencies"] = {
                "requests": "*",
                "yaml": "pyyaml>=6",
            }
            save_manifest(manifest, tmpdir, fmt="toml")

            with mock.patch("epl.package_manager.subprocess.check_call", return_value=0) as pip_call:
                ok = install_dependencies(tmpdir)

            self.assertTrue(ok)
            installed = [call.args[0][-1] for call in pip_call.call_args_list]
            self.assertEqual(installed, ["requests", "pyyaml>=6"])

    def test_use_python_auto_installs_manifest_declared_requirement(self):
        with tempfile.TemporaryDirectory(prefix="epl_pydeps_use_") as tmpdir:
            manifest = _base_manifest()
            manifest["entry"] = "src/main.epl"
            manifest["python-dependencies"] = {"yaml": "pyyaml>=6"}
            save_manifest(manifest, tmpdir, fmt="toml")
            Path(tmpdir, "src").mkdir(exist_ok=True)
            source_file = Path(tmpdir, "src", "main.epl")
            source_file.write_text('Use python "yaml"\n', encoding="utf-8")

            fake_module = types.SimpleNamespace(safe=True)
            interp = Interpreter(debug_interactive=False)
            interp._current_file = str(source_file)

            with mock.patch(
                "epl.interpreter._importlib.import_module",
                side_effect=[ImportError("missing"), fake_module],
            ) as import_module:
                with mock.patch.object(interpreter_mod._subprocess, "check_call", return_value=0) as pip_call:
                    interp.execute(_parse('Use python "yaml"\n'))

            self.assertEqual(import_module.call_count, 2)
            pip_call.assert_called_once()
            self.assertEqual(pip_call.call_args.args[0][:4], [sys.executable, "-m", "pip", "install"])
            self.assertEqual(pip_call.call_args.args[0][4], "pyyaml>=6")
            wrapped = interp.global_env.get_variable("yaml")
            self.assertIsInstance(wrapped, PythonModule)
            self.assertIs(wrapped.module, fake_module)

    def test_python_bridge_unwraps_epl_maps_and_lists_for_python_calls(self):
        interp = Interpreter(debug_interactive=False)
        program = _parse(
            'Use python "json" as json_mod\n'
            'Create payload equal to Map with message = "hello" and items = [1, 2, 3] and nested = Map with ok = True\n'
            'Create encoded equal to json_mod.dumps(payload)\n'
        )

        interp.execute(program)

        encoded = interp.global_env.get_variable("encoded")
        self.assertEqual(
            json.loads(encoded),
            {
                "message": "hello",
                "items": [1, 2, 3],
                "nested": {"ok": True},
            },
        )
