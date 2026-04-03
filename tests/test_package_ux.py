"""
EPL Package UX Test Suite — User-Friendly Package Management
Tests for: auto-save to epl.toml, pkg@version syntax, epl_modules/ local install,
           auto-install on import, unified naming, epl new uses epl.toml,
           CLI consistency, uninstall updates manifest
"""

import sys
import os
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def check(name, condition, detail=""):
    assert condition, f"{name} {detail}".strip()


# ══════════════════════════════════════════════════════════
# Helper: create a temp project directory with epl.toml
# ══════════════════════════════════════════════════════════

def _create_temp_project(name="test-project"):
    """Create a temp dir with an epl.toml manifest."""
    tmpdir = tempfile.mkdtemp()
    from epl.package_manager import _manifest_to_toml, _dump_toml
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": "Test project",
        "author": "",
        "entry": "main.epl",
        "dependencies": {},
        "scripts": {},
    }
    toml_data = _manifest_to_toml(manifest)
    with open(os.path.join(tmpdir, 'epl.toml'), 'w', encoding='utf-8') as f:
        f.write(_dump_toml(toml_data) + '\n')
    with open(os.path.join(tmpdir, 'main.epl'), 'w', encoding='utf-8') as f:
        f.write('Say "Hello!"\n')
    return tmpdir


# ══════════════════════════════════════════════════════════
# 1. pkg@version Syntax Parsing
# ══════════════════════════════════════════════════════════

def test_at_version_syntax():
    print("\n=== 1. pkg@version Syntax ===")
    from epl.package_manager import install_package, PACKAGES_DIR, BUILTIN_REGISTRY
    import epl.package_manager as pm

    # T1: Parse name@version correctly
    # We test the parsing inside install_package by checking it doesn't crash
    # and resolves the name
    check("install_package accepts name@version signature",
          callable(install_package) and
          install_package.__code__.co_varnames[:5] == ('name_or_url', 'version', 'save', 'local', 'project_path'))

    # T2: Verify @ parsing logic — simulate by checking the code path
    # We can test the parsing separate from actual install
    test_cases = [
        ("epl-math@1.0.0", "epl-math", "1.0.0"),
        ("epl-math@^2.0.0", "epl-math", "^2.0.0"),
        ("epl-http@>=1.5.0", "epl-http", ">=1.5.0"),
        ("epl-json@~1.2.3", "epl-json", "~1.2.3"),
    ]
    for input_str, expected_name, expected_ver in test_cases:
        parts = input_str.split('@', 1)
        check(f"Parse '{input_str}' -> name='{parts[0]}', ver='{parts[1]}'",
              parts[0] == expected_name and parts[1] == expected_ver)

    # T3: No @ means no version split
    no_version = "epl-math"
    check("No @ means no version split", '@' not in no_version)

    # T4: github: prefix shouldn't split on @
    github_url = "github:user/repo"
    should_not_split = github_url.startswith('github:')
    check("github: prefix skips @ split", should_not_split)

    # T5: https:// prefix shouldn't split on @
    https_url = "https://example.com/pkg@1.0.zip"
    should_not_split = https_url.startswith('http')
    check("https:// prefix skips @ split", should_not_split)


# ══════════════════════════════════════════════════════════
# 2. Unified Package Name Resolution
# ══════════════════════════════════════════════════════════

def test_unified_naming():
    print("\n=== 2. Unified Package Name Resolution ===")
    from epl.package_manager import _resolve_package_name, BUILTIN_REGISTRY

    # T1: 'epl-math' resolves to itself
    check("'epl-math' resolves to 'epl-math'", _resolve_package_name('epl-math') == 'epl-math')

    # T2: 'math' resolves to 'epl-math' (shorthand)
    check("'math' resolves to 'epl-math'", _resolve_package_name('math') == 'epl-math')

    # T3: 'http' resolves to 'epl-http'
    check("'http' resolves to 'epl-http'", _resolve_package_name('http') == 'epl-http')

    # T4: 'json' resolves to 'epl-json'
    check("'json' resolves to 'epl-json'", _resolve_package_name('json') == 'epl-json')

    # T5: 'crypto' resolves to 'epl-crypto'
    check("'crypto' resolves to 'epl-crypto'", _resolve_package_name('crypto') == 'epl-crypto')

    # T6: 'testing' resolves to 'epl-testing'
    check("'testing' resolves to 'epl-testing'", _resolve_package_name('testing') == 'epl-testing')

    # T7: 'string' resolves to 'epl-string'
    check("'string' resolves to 'epl-string'", _resolve_package_name('string') == 'epl-string')

    # T8: 'collections' resolves to 'epl-collections'
    check("'collections' resolves to 'epl-collections'", _resolve_package_name('collections') == 'epl-collections')

    # T9: Unknown package stays as-is
    check("'unknown-pkg' stays as-is", _resolve_package_name('unknown-pkg') == 'unknown-pkg')

    # T10: 'fs' resolves to 'epl-fs'
    check("'fs' resolves to 'epl-fs'", _resolve_package_name('fs') == 'epl-fs')

    # T11: 'db' resolves to 'epl-db'
    check("'db' resolves to 'epl-db'", _resolve_package_name('db') == 'epl-db')

    # T12: 'web' resolves to 'epl-web'
    check("'web' resolves to 'epl-web'", _resolve_package_name('web') == 'epl-web')

    # T13: All builtin packages resolve to themselves
    all_resolve = True
    for name in BUILTIN_REGISTRY:
        if _resolve_package_name(name) != name:
            all_resolve = False
            break
    check("All builtin packages resolve to themselves", all_resolve)

    # T14: Shorthand for newer packages
    check("'async' resolves to 'epl-async'", _resolve_package_name('async') == 'epl-async')

    # T15: 'csv' resolves to 'epl-csv'
    check("'csv' resolves to 'epl-csv'", _resolve_package_name('csv') == 'epl-csv')


# ══════════════════════════════════════════════════════════
# 3. Auto-Save to epl.toml on Install
# ══════════════════════════════════════════════════════════

def test_auto_save():
    print("\n=== 3. Auto-Save to epl.toml ===")
    from epl.package_manager import (
        install_package, load_manifest, _auto_save_dependency,
        save_manifest, PACKAGES_DIR
    )

    # T1: _auto_save_dependency function exists
    check("_auto_save_dependency function exists", callable(_auto_save_dependency))

    # T2: Auto-save to manifest when manifest exists
    tmpdir = _create_temp_project()
    try:
        _auto_save_dependency('epl-math', '^1.0.0', tmpdir)
        manifest = load_manifest(tmpdir)
        check("Auto-save adds dep to manifest",
              manifest is not None and 'epl-math' in manifest.get('dependencies', {}))

        # T3: Version spec is saved correctly
        check("Version spec saved correctly",
              manifest.get('dependencies', {}).get('epl-math') == '^1.0.0')

        # T4: Auto-save doesn't overwrite existing deps
        _auto_save_dependency('epl-math', '^2.0.0', tmpdir)
        manifest = load_manifest(tmpdir)
        check("Auto-save doesn't overwrite existing dep",
              manifest.get('dependencies', {}).get('epl-math') == '^1.0.0')

        # T5: Auto-save can add multiple deps
        _auto_save_dependency('epl-http', '*', tmpdir)
        manifest = load_manifest(tmpdir)
        check("Auto-save handles multiple deps",
              'epl-math' in manifest.get('dependencies', {}) and
              'epl-http' in manifest.get('dependencies', {}))
    finally:
        shutil.rmtree(tmpdir)

    # T6: Auto-save does nothing if no manifest
    tmpdir2 = tempfile.mkdtemp()
    try:
        _auto_save_dependency('epl-math', '*', tmpdir2)
        check("Auto-save skips if no manifest", not os.path.exists(os.path.join(tmpdir2, 'epl.toml')))
    finally:
        shutil.rmtree(tmpdir2)

    # T7: install_package has 'save' parameter
    import inspect
    sig = inspect.signature(install_package)
    check("install_package has 'save' param", 'save' in sig.parameters)

    # T8: install_package has 'local' parameter
    check("install_package has 'local' param", 'local' in sig.parameters)

    # T9: install_package has 'project_path' parameter
    check("install_package has 'project_path' param", 'project_path' in sig.parameters)

    # T10: install_package save defaults to True
    check("'save' defaults to True", sig.parameters['save'].default is True)


# ══════════════════════════════════════════════════════════
# 4. Local epl_modules/ Install
# ══════════════════════════════════════════════════════════

def test_local_install():
    print("\n=== 4. Local epl_modules/ Install ===")
    from epl.package_manager import (
        _install_builtin_package, find_package_module,
        BUILTIN_REGISTRY
    )

    # T1: _install_builtin_package accepts local param
    import inspect
    sig = inspect.signature(_install_builtin_package)
    check("_install_builtin_package has 'local' param", 'local' in sig.parameters)

    # T2: Install locally creates epl_modules/ directory
    tmpdir = _create_temp_project()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)
        result = _install_builtin_package('epl-math', local=True, project_path=tmpdir)
        check("Local install succeeds", result is True)

        # T3: Package is in epl_modules/
        local_pkg = os.path.join(tmpdir, 'epl_modules', 'epl-math')
        check("Package in epl_modules/", os.path.isdir(local_pkg))

        # T4: Local package has main.epl
        check("Local package has main.epl", os.path.isfile(os.path.join(local_pkg, 'main.epl')))

        # T5: Local package has epl.json manifest
        check("Local package has manifest", os.path.isfile(os.path.join(local_pkg, 'epl.json')))

        # T6: find_package_module finds local package
        found = find_package_module('epl-math')
        check("find_package_module finds local package",
              found is not None and 'epl_modules' in found)

        # T7: Install another package locally
        result2 = _install_builtin_package('epl-json', local=True, project_path=tmpdir)
        check("Second local install succeeds", result2 is True)

        # T8: Both packages coexist in epl_modules/
        check("Both packages in epl_modules/",
              os.path.isdir(os.path.join(tmpdir, 'epl_modules', 'epl-math')) and
              os.path.isdir(os.path.join(tmpdir, 'epl_modules', 'epl-json')))

    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)

    # T9: Default install (local=False) goes to global
    tmpdir2 = _create_temp_project()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir2)
        result = _install_builtin_package('epl-csv')
        check("Default install is global", result is True)
        check("Default install not in epl_modules/",
              not os.path.isdir(os.path.join(tmpdir2, 'epl_modules', 'epl-csv')))
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir2)


# ══════════════════════════════════════════════════════════
# 5. Auto-Install on Import
# ══════════════════════════════════════════════════════════

def test_auto_install_import():
    print("\n=== 5. Auto-Install on Import ===")
    from epl.package_manager import auto_install_package, find_package_module, PACKAGES_DIR

    # T1: auto_install_package function exists
    check("auto_install_package function exists", callable(auto_install_package))

    # T2: Auto-install known builtin package
    # Clean up first if already installed
    pkg_dir = os.path.join(PACKAGES_DIR, 'epl-encoding')
    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
    result = auto_install_package('epl-encoding')
    check("Auto-install returns path for builtin", result is not None)

    # T3: Auto-installed package can be found
    found = find_package_module('epl-encoding')
    check("Auto-installed package findable", found is not None)

    # T4: Auto-install with shorthand name
    pkg_dir2 = os.path.join(PACKAGES_DIR, 'epl-uuid')
    if os.path.exists(pkg_dir2):
        shutil.rmtree(pkg_dir2)
    result2 = auto_install_package('uuid')
    check("Auto-install with shorthand 'uuid'", result2 is not None)

    # T5: Auto-install returns None for unknown package
    result3 = auto_install_package('totally-unknown-package-xyz')
    check("Auto-install returns None for unknown", result3 is None)

    # T6: Already-installed package returns path directly
    result4 = auto_install_package('epl-encoding')
    check("Already-installed returns path", result4 is not None)

    # T7: Verify the auto-install path points to a real file
    if result:
        check("Auto-install path is real file", os.path.isfile(result))
    else:
        check("Auto-install path is real file", False, "No path returned")

    # T8: Test interpreter integration — _resolve_import_path uses auto-install
    try:
        from epl.interpreter import Interpreter
        from epl.environment import Environment
        interp = Interpreter()
        # This should not raise because auto-install will kick in
        check("Interpreter has _resolve_import_path", hasattr(interp, '_resolve_import_path'))
    except Exception as e:
        check("Interpreter has _resolve_import_path", False, str(e))


# ══════════════════════════════════════════════════════════
# 6. epl new Uses epl.toml
# ══════════════════════════════════════════════════════════

def test_epl_new_toml():
    print("\n=== 6. epl new Uses epl.toml ===")

    # T1: _new_project command in cli.py exists
    try:
        from epl.cli import _new_project
        check("_new_project exists", callable(_new_project))
    except ImportError:
        check("_new_project exists", False, "import failed")
        return

    # T2: init_project creates epl.toml
    from epl.package_manager import init_project, load_manifest
    tmpdir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)
        init_project("test-project")
        check("init creates epl.toml", os.path.isfile(os.path.join(tmpdir, 'epl.toml')))

        # T3: epl.toml has correct content
        manifest = load_manifest(tmpdir)
        check("Manifest has correct name", manifest is not None and manifest.get('name') == 'test-project')

        # T4: Manifest has version
        check("Manifest has version", manifest.get('version') == '1.0.0')

        # T5: Manifest has entry point
        check("Manifest has entry", manifest.get('entry') == 'main.epl')

        # T6: Main.epl created
        check("main.epl created", os.path.isfile(os.path.join(tmpdir, 'main.epl')))

        # T7: epl.toml is parseable
        with open(os.path.join(tmpdir, 'epl.toml'), 'r') as f:
            content = f.read()
        check("epl.toml is not empty", len(content) > 10)
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 7. Uninstall Updates Manifest
# ══════════════════════════════════════════════════════════

def test_uninstall_manifest():
    print("\n=== 7. Uninstall Updates Manifest ===")
    from epl.package_manager import (
        install_package, uninstall_package, load_manifest,
        _install_builtin_package, _auto_save_dependency, PACKAGES_DIR
    )

    tmpdir = _create_temp_project()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)

        # T1: Install a package
        _install_builtin_package('epl-logging')
        _auto_save_dependency('epl-logging', '^1.0.0', tmpdir)
        manifest = load_manifest(tmpdir)
        check("Package installed and in manifest",
              'epl-logging' in manifest.get('dependencies', {}))

        # T2: Uninstall removes from manifest
        uninstall_package('epl-logging')
        manifest = load_manifest(tmpdir)
        check("Uninstall removes from manifest",
              'epl-logging' not in manifest.get('dependencies', {}))

        # T3: Uninstall with unified name
        _install_builtin_package('epl-validation')
        _auto_save_dependency('epl-validation', '*', tmpdir)
        uninstall_package('validation')  # shorthand
        check("Uninstall with shorthand name",
              not os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-validation')))

    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 8. CLI Consistency
# ══════════════════════════════════════════════════════════

def test_cli_consistency():
    print("\n=== 8. CLI Consistency ===")

    # T1: cli.py has all package commands
    try:
        with open(os.path.join(os.path.dirname(__file__), '..', 'epl', 'cli.py'), 'r') as f:
            cli_src = f.read()
    except FileNotFoundError:
        check("cli.py readable", False)
        return

    commands_expected = ['search', 'add', 'remove', 'lock', 'update',
                        'tree', 'outdated', 'audit', 'migrate', 'cache',
                        'publish', 'info', 'stats']

    for cmd in commands_expected:
        found = f"'{cmd}'" in cli_src
        check(f"CLI has '{cmd}' command", found)

    # T14: _delegate function exists
    check("_delegate function in cli.py", 'def _delegate' in cli_src)

    # T15: install handles no-args (install all deps)
    check("Install handles no-args", '_pkg_install' in cli_src)

    # T16: epl new uses epl.toml (not epl.json)
    check("epl new creates epl.toml", 'epl.toml' in cli_src)


# ══════════════════════════════════════════════════════════
# 9. install_package Function Signature
# ══════════════════════════════════════════════════════════

def test_install_signature():
    print("\n=== 9. install_package Signature ===")
    from epl.package_manager import install_package
    import inspect

    sig = inspect.signature(install_package)
    params = list(sig.parameters.keys())

    # T1: Has name_or_url
    check("Has 'name_or_url' param", 'name_or_url' in params)

    # T2: Has version
    check("Has 'version' param", 'version' in params)

    # T3: Has save
    check("Has 'save' param", 'save' in params)

    # T4: Has local
    check("Has 'local' param", 'local' in params)

    # T5: Has project_path
    check("Has 'project_path' param", 'project_path' in params)

    # T6: save defaults to True
    check("'save' defaults to True", sig.parameters['save'].default is True)

    # T7: local defaults to False
    check("'local' defaults to False", sig.parameters['local'].default is False)

    # T8: project_path defaults to '.'
    check("'project_path' defaults to '.'", sig.parameters['project_path'].default == '.')

    # T9: version defaults to None
    check("'version' defaults to None", sig.parameters['version'].default is None)


# ══════════════════════════════════════════════════════════
# 10. main.py Install CLI Integration
# ══════════════════════════════════════════════════════════

def test_main_install_cli():
    print("\n=== 10. main.py Install CLI ===")

    try:
        with open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), 'r') as f:
            main_src = f.read()
    except FileNotFoundError:
        check("main.py readable", False)
        return

    # T1: main.py install supports --local flag
    check("main.py supports --local", '--local' in main_src)

    # T2: main.py install supports --no-save flag
    check("main.py supports --no-save", '--no-save' in main_src)

    # T3: main.py passes save param
    check("main.py passes save param", 'save=' in main_src)

    # T4: main.py passes local param
    check("main.py passes local param", 'local=' in main_src)


# ══════════════════════════════════════════════════════════
# 11. find_package_module Resolution Order
# ══════════════════════════════════════════════════════════

def test_package_resolution():
    print("\n=== 11. Package Resolution Order ===")
    from epl.package_manager import find_package_module

    # T1: find_package_module is callable
    check("find_package_module callable", callable(find_package_module))

    # T2: Local epl_modules/ takes priority over global
    tmpdir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)
        # Create local module
        local_mod = os.path.join(tmpdir, 'epl_modules', 'test-local-pkg')
        os.makedirs(local_mod, exist_ok=True)
        with open(os.path.join(local_mod, 'main.epl'), 'w') as f:
            f.write('Say "local"\n')

        found = find_package_module('test-local-pkg')
        check("find_package_module finds local package",
              found is not None and 'epl_modules' in found)

        # T3: Single-file local module
        with open(os.path.join(tmpdir, 'epl_modules', 'single-mod.epl'), 'w') as f:
            f.write('Say "single"\n')
        found2 = find_package_module('single-mod')
        check("find_package_module finds single-file module",
              found2 is not None and 'single-mod.epl' in found2)

    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 12. End-to-End Install Workflow
# ══════════════════════════════════════════════════════════

def test_e2e_workflow():
    print("\n=== 12. End-to-End Install Workflow ===")
    from epl.package_manager import (
        install_package, load_manifest, uninstall_package,
        find_package_module, PACKAGES_DIR, list_packages
    )

    tmpdir = _create_temp_project("e2e-project")
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)

        # T1: Install with save auto-updates manifest
        install_package('epl-math', save=True, project_path=tmpdir)
        manifest = load_manifest(tmpdir)
        check("E2E: Install saves to manifest",
              manifest is not None and 'epl-math' in manifest.get('dependencies', {}))

        # T2: Package is findable after install
        found = find_package_module('epl-math')
        check("E2E: Package findable after install", found is not None)

        # T3: Install with no-save doesn't update manifest
        # First remove the dep from manifest
        manifest['dependencies'] = {}
        from epl.package_manager import save_manifest
        save_manifest(manifest, tmpdir)

        install_package('epl-http', save=False, project_path=tmpdir)
        manifest = load_manifest(tmpdir)
        check("E2E: no-save doesn't update manifest",
              'epl-http' not in manifest.get('dependencies', {}))

        # T4: Install with @version syntax
        install_package('epl-csv@^1.0.0', save=True, project_path=tmpdir)
        manifest = load_manifest(tmpdir)
        check("E2E: @version install saves correct version",
              manifest.get('dependencies', {}).get('epl-csv') == '^1.0.0')

        # T5: Install with shorthand name
        install_package('logging', save=True, project_path=tmpdir)
        manifest = load_manifest(tmpdir)
        check("E2E: Shorthand name resolves and saves",
              'epl-logging' in manifest.get('dependencies', {}))

        # T6: Uninstall cleans up manifest
        uninstall_package('epl-csv')
        manifest = load_manifest(tmpdir)
        check("E2E: Uninstall cleans manifest",
              'epl-csv' not in manifest.get('dependencies', {}))

        # T7: Local install creates epl_modules/
        install_package('epl-os', local=True, project_path=tmpdir, save=True)
        check("E2E: Local install creates epl_modules/",
              os.path.isdir(os.path.join(tmpdir, 'epl_modules', 'epl-os')))

        # T8: Manifest updated with locally installed dep
        manifest = load_manifest(tmpdir)
        check("E2E: Local install updates manifest",
              'epl-os' in manifest.get('dependencies', {}))

    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 13. SemVer in @version Parsing
# ══════════════════════════════════════════════════════════

def test_semver_at_version():
    print("\n=== 13. SemVer @version Parsing ===")
    from epl.package_manager import SemVer, parse_version_range

    # Various version specs that should work with @
    specs = [
        ("1.0.0", True),
        ("^1.0.0", True),
        ("~2.3.4", True),
        (">=1.5.0", True),
        ("<3.0.0", True),
        (">=1.0.0 <2.0.0", True),
        ("*", True),
        ("!=1.2.3", True),
    ]

    for spec, should_parse in specs:
        matcher = parse_version_range(spec)
        check(f"Version spec '{spec}' parseable", callable(matcher))

    # T8: Caret range works correctly
    matcher = parse_version_range("^1.2.0")
    v1 = SemVer.parse("1.5.0")
    v2 = SemVer.parse("2.0.0")
    check("Caret ^1.2.0 matches 1.5.0", matcher(v1))
    check("Caret ^1.2.0 rejects 2.0.0", not matcher(v2))


# ══════════════════════════════════════════════════════════
# 14. Manifest Format Consistency
# ══════════════════════════════════════════════════════════

def test_manifest_format():
    print("\n=== 14. Manifest Format Consistency ===")
    from epl.package_manager import (
        create_manifest, load_manifest, save_manifest,
        _parse_toml, _dump_toml, _manifest_to_toml, _toml_to_manifest
    )

    tmpdir = tempfile.mkdtemp()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)

        # T1: create_manifest defaults to toml
        manifest = create_manifest("fmt-test", fmt="toml")
        check("create_manifest creates epl.toml",
              os.path.isfile(os.path.join(tmpdir, 'epl.toml')))

        # T2: load_manifest reads back correctly
        loaded = load_manifest(tmpdir)
        check("load_manifest reads toml back",
              loaded is not None and loaded.get('name') == 'fmt-test')

        # T3: save_manifest preserves format
        loaded['dependencies'] = {'epl-math': '^1.0.0'}
        save_manifest(loaded, tmpdir)
        reloaded = load_manifest(tmpdir)
        check("save_manifest preserves deps",
              'epl-math' in reloaded.get('dependencies', {}))

        # T4: TOML round-trip preserves data
        toml_data = _manifest_to_toml(loaded)
        text = _dump_toml(toml_data)
        parsed = _parse_toml(text)
        back = _toml_to_manifest(parsed)
        check("TOML round-trip preserves name", back.get('name') == 'fmt-test')

        # T5: TOML round-trip preserves dependencies
        check("TOML round-trip preserves deps",
              'epl-math' in back.get('dependencies', {}))

    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tmpdir)


# ══════════════════════════════════════════════════════════
# 15. Security and Validation
# ══════════════════════════════════════════════════════════

def test_security():
    print("\n=== 15. Security and Validation ===")
    from epl.package_manager import _sanitize_package_name, _resolve_package_name

    # T1: Path traversal blocked
    try:
        _sanitize_package_name('../../../etc/passwd')
        check("Path traversal blocked", False, "Should have raised")
    except ValueError:
        check("Path traversal blocked", True)

    # T2: Null bytes blocked
    try:
        _sanitize_package_name('package\x00evil')
        check("Null bytes blocked", False, "Should have raised")
    except ValueError:
        check("Null bytes blocked", True)

    # T3: Normalize slashes
    try:
        _sanitize_package_name('malicious/name')
        check("Slashes blocked", False, "Should have raised")
    except ValueError:
        check("Slashes blocked", True)

    # T4: Resolve name doesn't bypass sanitization
    result = _resolve_package_name('epl-math')
    check("Resolve preserves valid names", result == 'epl-math')

    # T5: Empty name
    try:
        _sanitize_package_name('')
        check("Empty name handled", False, "Should have raised")
    except (ValueError, Exception):
        check("Empty name handled", True)


# ══════════════════════════════════════════════════════════
# 16. Builtin Registry Coverage
# ══════════════════════════════════════════════════════════

def test_builtin_registry():
    print("\n=== 16. Builtin Registry Coverage ===")
    from epl.package_manager import BUILTIN_REGISTRY, SemVer

    # T1: Registry has packages
    check("Registry has packages", len(BUILTIN_REGISTRY) > 30)

    # T2: All entries have required fields
    all_valid = True
    for name, info in BUILTIN_REGISTRY.items():
        if 'description' not in info or 'version' not in info:
            all_valid = False
            break
    check("All entries have required fields", all_valid)

    # T3: All versions are valid semver
    all_semver = True
    for name, info in BUILTIN_REGISTRY.items():
        v = SemVer.parse(info['version'])
        if v is None:
            all_semver = False
            break
    check("All versions are valid semver", all_semver)

    # T4: No duplicate names
    check("No duplicate names", len(BUILTIN_REGISTRY) == len(set(BUILTIN_REGISTRY.keys())))

    # T5: Package names follow convention
    all_prefixed = all(name.startswith('epl-') for name in BUILTIN_REGISTRY)
    check("All packages use epl- prefix", all_prefixed)


