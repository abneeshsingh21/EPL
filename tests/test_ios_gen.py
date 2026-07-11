"""Coverage for the SwiftUI / iOS code generator.

`test_ios_style_3d.py` covers Style/Layout/Scene3D/Draw emission via
`SwiftUIGenerator.generate`; this module adds the pieces it doesn't — the
app/runtime scaffolding, the pure color/type/op helpers, the empty-program
fallback, and the on-disk `IOSProjectGenerator` project tree (re-expressed as
hermetic pytest with `tmp_path`, where the old coverage lived under a
`__main__` harness).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.ios_gen import IOSProjectGenerator, SwiftUIGenerator, generate_ios_project
from epl.lexer import Lexer
from epl.parser import Parser


def to_swift(src):
    # A fresh generator per program — instances accumulate state across generate().
    prog = Parser(Lexer(src).tokenize()).parse()
    return SwiftUIGenerator('TestApp', 'com.test.app').generate(prog)


GEN = SwiftUIGenerator('TestApp', 'com.test.app')


# ── App / runtime scaffolding ────────────────────────────
SCAFFOLD_CASES = [
    ('app_is_main', lambda: '@main' in GEN.generate_app()),
    ('app_struct', lambda: 'struct TestAppApp: App' in GEN.generate_app()),
    ('app_shows_contentview', lambda: 'ContentView()' in GEN.generate_app()),
    ('runtime_class', lambda: 'class EPLRuntime' in GEN.generate_runtime()),
    ('empty_program_fallback', lambda: 'Welcome to TestApp' in to_swift('')),
]


# ── Pure helpers ─────────────────────────────────────────
HELPER_CASES = [
    ('color_hex', lambda: GEN._css_color_to_swift('#ff0000') == 'Color(red: 255/255.0, green: 0/255.0, blue: 0/255.0)'),
    ('color_short_hex', lambda: GEN._css_color_to_swift('#f00') == 'Color(red: 255/255.0, green: 0/255.0, blue: 0/255.0)'),
    ('color_named', lambda: 'Color(red: 255' in GEN._css_color_to_swift('red')),
    ('swift_type_integer', lambda: GEN._swift_type('integer') == 'Int'),
    ('swift_type_unknown_is_string', lambda: GEN._swift_type('somethingelse') == 'String'),
    ('swift_op_plus', lambda: GEN._swift_op('plus') == '+'),
]


@pytest.mark.parametrize(('name', 'check_fn'), SCAFFOLD_CASES, ids=[n for n, _ in SCAFFOLD_CASES])
def test_scaffolding(name, check_fn):
    assert check_fn(), name


@pytest.mark.parametrize(('name', 'check_fn'), HELPER_CASES, ids=[n for n, _ in HELPER_CASES])
def test_pure_helpers(name, check_fn):
    assert check_fn(), name


def test_generator_defaults():
    g = IOSProjectGenerator()
    assert g.app_name == 'EPLApp'
    assert g.bundle_id == 'com.epl.app'
    assert g.SWIFT_VERSION == '5.9'
    assert g.IOS_DEPLOYMENT_TARGET == '16.0'


def test_project_generation_writes_tree(tmp_path):
    prog = Parser(Lexer('Say "hi"\n').tokenize()).parse()
    out = IOSProjectGenerator(app_name='TestApp').generate(prog, str(tmp_path / 'TestApp'))
    assert os.path.isdir(out)
    present = {p.name for p in tmp_path.rglob('*') if p.is_file()}
    assert 'project.pbxproj' in present
    assert 'ContentView.swift' in present
    assert 'EPLRuntime.swift' in present
    assert 'Info.plist' in present


def test_pbxproj_is_well_formed(tmp_path):
    prog = Parser(Lexer('Say "hi"\n').tokenize()).parse()
    out = IOSProjectGenerator(app_name='TestApp').generate(prog, str(tmp_path / 'TestApp'))
    pbxproj = next(p for p in tmp_path.rglob('project.pbxproj')).read_text(encoding='utf-8')
    assert 'archiveVersion = 1' in pbxproj
    assert 'PBXNativeTarget' in pbxproj


def test_convenience_function_matches_class(tmp_path):
    prog = Parser(Lexer('Say "hi"\n').tokenize()).parse()
    out = generate_ios_project(prog, str(tmp_path / 'MyApp'), app_name='MyApp')
    assert os.path.isdir(out)
    assert any(p.name == 'ContentView.swift' for p in tmp_path.rglob('*'))
