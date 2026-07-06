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
from epl.interpreter import EPLDict, Interpreter
from epl.lexer import Lexer
from epl.package_manager import (
    install_dependencies,
    install_python_package,
    load_manifest,
    save_manifest,
)
from epl.parser import Parser
from epl.python_bridge import (
    PythonModule,
    call_python_function,
    call_python_method,
    resolve_python_module,
    unwrap_python_argument,
    wrap_python_result,
)


def _parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def _base_manifest() -> dict:
    return {
        'name': 'demo',
        'version': '1.0.0',
        'description': 'demo project',
        'author': '',
        'entry': 'main.epl',
        'dependencies': {},
        'scripts': {},
    }


class TestPythonDependencyBridge(unittest.TestCase):
    def test_manifest_round_trip_preserves_python_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='epl_pydeps_manifest_') as tmpdir:
            manifest = _base_manifest()
            manifest['python-dependencies'] = {
                'requests': '*',
                'yaml': 'pyyaml>=6',
            }

            save_manifest(manifest, tmpdir, fmt='toml')
            loaded = load_manifest(tmpdir)

            self.assertEqual(
                loaded.get('python-dependencies'),
                {'requests': '*', 'yaml': 'pyyaml>=6'},
            )

    def test_install_python_package_saves_manifest(self):
        with tempfile.TemporaryDirectory(prefix='epl_pydeps_install_') as tmpdir:
            save_manifest(_base_manifest(), tmpdir, fmt='toml')

            with mock.patch(
                'epl.package_manager.subprocess.check_call', return_value=0
            ) as pip_call:
                ok = install_python_package('yaml', 'pyyaml>=6', project_path=tmpdir)

            self.assertTrue(ok)
            pip_call.assert_called_once_with(
                [sys.executable, '-m', 'pip', 'install', '--', 'pyyaml>=6']
            )
            loaded = load_manifest(tmpdir)
            self.assertEqual(loaded['python-dependencies']['yaml'], 'pyyaml>=6')

    def test_install_dependencies_installs_declared_python_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='epl_pydeps_all_') as tmpdir:
            manifest = _base_manifest()
            manifest['python-dependencies'] = {
                'requests': '*',
                'yaml': 'pyyaml>=6',
            }
            save_manifest(manifest, tmpdir, fmt='toml')

            with mock.patch(
                'epl.package_manager.subprocess.check_call', return_value=0
            ) as pip_call:
                ok = install_dependencies(tmpdir)

            self.assertTrue(ok)
            installed = [call.args[0][-1] for call in pip_call.call_args_list]
            self.assertEqual(installed, ['requests', 'pyyaml>=6'])

    def test_use_python_auto_installs_manifest_declared_requirement(self):
        # A declared requirement installs only with explicit consent. The
        # EPL_AUTO_INSTALL=1 opt-in is the CI/automation consent path.
        with tempfile.TemporaryDirectory(prefix='epl_pydeps_use_') as tmpdir:
            manifest = _base_manifest()
            manifest['entry'] = 'src/main.epl'
            manifest['python-dependencies'] = {'yaml': 'pyyaml>=6'}
            save_manifest(manifest, tmpdir, fmt='toml')
            Path(tmpdir, 'src').mkdir(exist_ok=True)
            source_file = Path(tmpdir, 'src', 'main.epl')
            source_file.write_text('Use python "yaml"\n', encoding='utf-8')

            fake_module = types.SimpleNamespace(safe=True)
            interp = Interpreter(debug_interactive=False)
            interp._current_file = str(source_file)

            with mock.patch.dict(os.environ, {'EPL_AUTO_INSTALL': '1'}):
                with mock.patch(
                    'epl.interpreter._importlib.import_module',
                    side_effect=[ImportError('missing'), fake_module],
                ) as import_module:
                    with mock.patch.object(
                        interpreter_mod._subprocess, 'check_call', return_value=0
                    ) as pip_call:
                        interp.execute(_parse('Use python "yaml"\n'))

            self.assertEqual(import_module.call_count, 2)
            pip_call.assert_called_once()
            self.assertEqual(
                pip_call.call_args.args[0][:5],
                [sys.executable, '-m', 'pip', 'install', '--'],
            )
            self.assertEqual(pip_call.call_args.args[0][5], 'pyyaml>=6')
            wrapped = interp.global_env.get_variable('yaml')
            self.assertIsInstance(wrapped, PythonModule)
            self.assertIs(wrapped.module, fake_module)

    def test_use_python_declared_requirement_requires_consent(self):
        # M2: merely running a (possibly untrusted) project must NOT silently
        # pip-install its declared deps. Without EPL_AUTO_INSTALL and with no
        # interactive TTY, consent is withheld and pip is never invoked.
        from epl.errors import RuntimeError as EPLRuntimeError

        with tempfile.TemporaryDirectory(prefix='epl_pydeps_noconsent_') as tmpdir:
            manifest = _base_manifest()
            manifest['entry'] = 'src/main.epl'
            manifest['python-dependencies'] = {'yaml': 'pyyaml>=6'}
            save_manifest(manifest, tmpdir, fmt='toml')
            Path(tmpdir, 'src').mkdir(exist_ok=True)
            source_file = Path(tmpdir, 'src', 'main.epl')
            source_file.write_text('Use python "yaml"\n', encoding='utf-8')

            interp = Interpreter(debug_interactive=False)
            interp._current_file = str(source_file)

            env_without_optin = {
                k: v for k, v in os.environ.items() if k != 'EPL_AUTO_INSTALL'
            }
            with mock.patch.dict(os.environ, env_without_optin, clear=True):
                with mock.patch(
                    'epl.interpreter._importlib.import_module',
                    side_effect=ImportError('missing'),
                ):
                    with mock.patch.object(
                        interpreter_mod._subprocess, 'check_call', return_value=0
                    ) as pip_call:
                        with self.assertRaises(EPLRuntimeError):
                            interp.execute(_parse('Use python "yaml"\n'))
            pip_call.assert_not_called()

    def test_python_bridge_unwraps_epl_maps_and_lists_for_python_calls(self):
        interp = Interpreter(debug_interactive=False)
        program = _parse(
            'Use python "json" as json_mod\n'
            'Create payload equal to Map with message = "hello" and items = [1, 2, 3] and nested = Map with ok = True\n'
            'Create encoded equal to json_mod.dumps(payload)\n'
        )

        interp.execute(program)

        encoded = interp.global_env.get_variable('encoded')
        self.assertEqual(
            json.loads(encoded),
            {
                'message': 'hello',
                'items': [1, 2, 3],
                'nested': {'ok': True},
            },
        )

    def test_wrap_python_result_converts_nested_values_and_objects(self):
        class Holder:
            pass

        wrapped = wrap_python_result(
            {'items': [1, {'ok': True}], 'holder': Holder()},
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )

        self.assertIsInstance(wrapped, EPLDict)
        self.assertEqual(wrapped.data['items'][0], 1)
        self.assertIsInstance(wrapped.data['items'][1], EPLDict)
        self.assertTrue(wrapped.data['items'][1].data['ok'])
        self.assertIsInstance(wrapped.data['holder'], PythonModule)

    def test_wrap_python_result_guards_circular_references(self):
        payload = {}
        payload['self'] = payload

        wrapped = wrap_python_result(
            payload,
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )

        self.assertIsInstance(wrapped, EPLDict)
        self.assertEqual(wrapped.data['self'], '<circular ref dict>')

    def test_unwrap_python_argument_restores_epl_values_and_python_modules(self):
        py_obj = types.SimpleNamespace(name='demo')
        wrapped_module = PythonModule(py_obj, 'demo')
        value = EPLDict(
            {
                'message': 'hello',
                'items': [1, 2],
                'nested': EPLDict({'ok': True}),
                'module': wrapped_module,
            }
        )

        unwrapped = unwrap_python_argument(
            value,
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )

        self.assertEqual(unwrapped['message'], 'hello')
        self.assertEqual(unwrapped['items'], [1, 2])
        self.assertEqual(unwrapped['nested'], {'ok': True})
        self.assertIs(unwrapped['module'], py_obj)

    def test_call_python_function_round_trips_epl_payloads(self):
        payload = EPLDict({'message': 'hello', 'items': [1, 2, 3], 'nested': EPLDict({'ok': True})})

        encoded = call_python_function(
            'json',
            json,
            'dumps',
            [payload],
            1,
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )

        self.assertEqual(
            json.loads(encoded),
            {'message': 'hello', 'items': [1, 2, 3], 'nested': {'ok': True}},
        )

    def test_call_python_method_wraps_noncallable_attributes(self):
        wrapped = PythonModule(types.SimpleNamespace(config={'ok': True}), 'cfg')

        result = call_python_method(
            wrapped,
            'config',
            [],
            1,
            epl_dict_type=EPLDict,
            python_module_type=PythonModule,
        )

        self.assertIsInstance(result, EPLDict)
        self.assertEqual(result.data['ok'], True)

    def test_resolve_python_module_imports_stdlib_modules(self):
        module = resolve_python_module('json', 1)
        self.assertEqual(module.loads('{"ok": true}'), {'ok': True})
