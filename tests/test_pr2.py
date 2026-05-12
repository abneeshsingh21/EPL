"""Tests for PR #2: Use syntax + epl use CLI alias + packages."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import epl.ast_nodes as ast
from epl.lexer import Lexer
from epl.parser import Parser

passed = 0
failed = 0


def test(name, condition):
    global passed, failed
    if condition:
        print(f'  PASS: {name}')
        passed += 1
    else:
        print(f'  FAIL: {name}')
        failed += 1


def parse(source):
    return Parser(Lexer(source).tokenize()).parse()


# ── Parser: Use "package" as Import alias ──────────────────
print('\n=== Parser: Use as Import ===')

prog = parse('Use "math_helpers"')
stmt = prog.statements[0]
test('Use string -> ImportStatement', isinstance(stmt, ast.ImportStatement))
test('filepath is math_helpers', stmt.filepath == 'math_helpers')

# ── Parser: Use python "lib" still works ───────────────────
print('\n=== Parser: Use python (backward compat) ===')

prog2 = parse('Use python "json" as json_lib')
stmt2 = prog2.statements[0]
test('Use python -> UseStatement', isinstance(stmt2, ast.UseStatement))
test('library is json', stmt2.library == 'json')
test('alias is json_lib', stmt2.alias == 'json_lib')

# ── Parser: Use python auto-alias ──────────────────────────
print('\n=== Parser: Use python auto-alias ===')

prog3 = parse('Use python "os.path"')
stmt3 = prog3.statements[0]
test('Auto alias derived', stmt3.alias == 'path')

# ── Parser: Use with alias ─────────────────────────────────
print('\n=== Parser: Use with alias ===')

prog4 = parse('Use "utils/helpers" as helpers')
stmt4 = prog4.statements[0]
test('Use with alias -> ImportStatement', isinstance(stmt4, ast.ImportStatement))
test('alias is helpers', getattr(stmt4, 'alias', None) == 'helpers')

# ── Parser: Import still works ─────────────────────────────
print('\n=== Parser: Import still works ===')

prog5 = parse('Import "stdlib"')
stmt5 = prog5.statements[0]
test('Import -> ImportStatement', isinstance(stmt5, ast.ImportStatement))
test('filepath is stdlib', stmt5.filepath == 'stdlib')

# ── CLI: epl use alias ─────────────────────────────────────
print('\n=== CLI: epl use command ===')

from unittest import mock

from epl.cli import cli_main

with mock.patch('epl.package_manager.install_dependencies', return_value=True) as install_deps:
    exit_code = cli_main(['use'])
test('epl use returns 0', exit_code == 0)
test('epl use calls install_dependencies', install_deps.called)

# ── CLI: epl install still works ───────────────────────────
print('\n=== CLI: epl install still works ===')

with mock.patch('epl.package_manager.install_dependencies', return_value=True) as install_deps2:
    exit_code2 = cli_main(['install'])
test('epl install returns 0', exit_code2 == 0)
test('epl install calls install_dependencies', install_deps2.called)

# ── Package structure validation ───────────────────────────
print('\n=== Package structure validation ===')

pkg_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'epl', 'official_packages'
)
new_packages = ['epl-array', 'epl-dataframe', 'epl-science', 'epl-learn', 'epl-plot']

for pkg in new_packages:
    pkg_path = os.path.join(pkg_dir, pkg)
    has_toml = os.path.exists(os.path.join(pkg_path, 'epl.toml'))
    has_main = os.path.exists(os.path.join(pkg_path, 'src', 'main.epl'))
    has_py = os.path.exists(os.path.join(pkg_path, 'python', '__init__.py'))
    has_readme = os.path.exists(os.path.join(pkg_path, 'README.md'))
    has_example = os.path.exists(os.path.join(pkg_path, 'examples', 'basic.epl'))

    test(f'{pkg}: epl.toml exists', has_toml)
    test(f'{pkg}: src/main.epl exists', has_main)
    test(f'{pkg}: python/__init__.py exists', has_py)
    test(f'{pkg}: README.md exists', has_readme)
    test(f'{pkg}: examples/basic.epl exists', has_example)

# ── EPL source parseability ────────────────────────────────
print('\n=== EPL source parseability ===')

for pkg in new_packages:
    main_path = os.path.join(pkg_dir, pkg, 'src', 'main.epl')
    try:
        with open(main_path, 'r', encoding='utf-8') as f:
            source = f.read()
        Parser(Lexer(source).tokenize()).parse()
        test(f'{pkg}/src/main.epl parses', True)
    except Exception as e:
        test(f'{pkg}/src/main.epl parses ({e})', False)

# ── Python backend importability ───────────────────────────
print('\n=== Python backend import check ===')

for pkg in new_packages:
    py_path = os.path.join(pkg_dir, pkg, 'python', '__init__.py')
    try:
        with open(py_path, 'r', encoding='utf-8') as f:
            source = f.read()
        # Check it compiles (syntax valid) without executing imports
        compile(source, py_path, 'exec')
        test(f'{pkg}/python/__init__.py compiles', True)
    except SyntaxError as e:
        test(f'{pkg}/python/__init__.py compiles ({e})', False)

# ── Summary ────────────────────────────────────────────────
print(f'\n{"=" * 50}')
print(f'TOTAL: {passed + failed} | PASSED: {passed} | FAILED: {failed}')
if failed > 0:
    print('VERDICT: DO NOT MERGE — failures detected')
else:
    print('VERDICT: SAFE TO MERGE — all tests pass')
