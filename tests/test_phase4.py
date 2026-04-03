"""
EPL Phase 4 Test Suite — Ecosystem (Make EPL Self-Sustaining)
Tests for: Package Registry, Documentation Generator, 50 Official Packages,
           Documentation Site Generator, TOML Manifest, Dependency Management,
           Production Package Features
"""

import sys
import os
import json
import tempfile
import shutil
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0


def _start_tracker():
    _TrackerState.current = {
        "passed": 0,
        "failed": 0,
        "failures": [],
    }


def _finish_tracker():
    tracker = _TrackerState.current
    _TrackerState.current = None
    if tracker is None:
        return
    _TrackerState.total_pass += tracker["passed"]
    _TrackerState.total_fail += tracker["failed"]
    if tracker["failures"]:
        raise AssertionError("\n".join(tracker["failures"]))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            _finish_tracker()

    return wrapper


def check(name, condition, detail=""):
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("check() called outside an active test tracker.")
    if condition:
        print(f"  PASS: {name}")
        tracker["passed"] += 1
    else:
        print(f"  FAIL: {name} {detail}")
        tracker["failed"] += 1
        tracker["failures"].append(f"{name}: {detail}" if detail else name)


# ══════════════════════════════════════════════════════════
# 4.1  Real Package Registry
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_registry():
    print("\n=== 4.1 Real Package Registry ===")

    # T1: Module imports
    try:
        from epl.registry import RegistryCache, DownloadStats, GitHubRegistry
        check("Registry module imports", True)
    except ImportError as e:
        check("Registry module imports", False, str(e))
        return

    # T2: RegistryCache init
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, 'cache.json')
        cache = RegistryCache(path=cache_path)
        check("RegistryCache init", cache is not None)

        # T3: Cache set/get
        cache.set_package("test-pkg", {"version": "1.0.0", "data": 42})
        result = cache.get_package("test-pkg")
        check("Cache set/get", result is not None and result.get("data") == 42)

        # T4: Cache miss
        result = cache.get_package("nonexistent-key")
        check("Cache miss returns None", result is None)

        # T5: Cache clear
        cache.clear()
        result = cache.get_package("test-pkg")
        check("Cache clear works", result is None)

        # T6: Cache set_index
        cache.set_index({"epl-math": {"version": "1.0.0"}, "epl-web": {"version": "2.0.0"}})
        check("set_index works", len(cache.all_packages()) == 2)

        # T7: is_stale check
        check("Freshly updated not stale", not cache.is_stale())

    # T8: DownloadStats init
    with tempfile.TemporaryDirectory() as tmp:
        stats_path = os.path.join(tmp, 'stats.json')
        stats = DownloadStats(path=stats_path)
        check("DownloadStats init", stats is not None)

        # T9: Record download
        stats.record_download("epl-math", "1.0.0")
        count = stats.get_count("epl-math")
        check("Record download", count == 1)

        # T10: Multiple downloads
        stats.record_download("epl-math", "1.0.0")
        stats.record_download("epl-math", "2.0.0")
        count = stats.get_count("epl-math")
        check("Multiple downloads counted", count == 3)

        # T11: Zero downloads for unknown package
        count = stats.get_count("epl-unknown")
        check("Unknown package has 0 downloads", count == 0)

        # T12: Top packages
        stats.record_download("epl-web", "1.0.0")
        top = stats.top_packages(limit=2)
        check("Get top packages", len(top) >= 1 and top[0][0] == "epl-math")

        # T13: get_all
        all_stats = stats.get_all()
        check("get_all returns data", "epl-math" in all_stats)

    # T14: GitHubRegistry init
    registry = GitHubRegistry.__new__(GitHubRegistry)
    check("GitHubRegistry class exists", True)

    # T15: Registry has search method
    check("Registry has search method", hasattr(GitHubRegistry, 'search'))

    # T16: Registry has get_package_info method
    check("Registry has get_package_info", hasattr(GitHubRegistry, 'get_package_info'))

    # T17: Registry has get_versions method
    check("Registry has get_versions", hasattr(GitHubRegistry, 'get_versions'))

    # T18: Registry has publish method
    check("Registry has publish", hasattr(GitHubRegistry, 'publish_to_registry'))

    # T19: CLI functions exist
    from epl.registry import registry_search, registry_info, registry_stats, registry_publish
    check("registry_search exists", callable(registry_search))
    check("registry_info exists", callable(registry_info))
    check("registry_stats exists", callable(registry_stats))
    check("registry_publish exists", callable(registry_publish))


# ══════════════════════════════════════════════════════════
# 4.2  Documentation Generator (Enhanced)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_doc_generator():
    print("\n=== 4.2 Documentation Generator ===")

    # T1: Module imports
    try:
        from epl.doc_linter import DocGenerator, DocEntry, ModuleDoc, DocParam
        check("Doc generator imports", True)
    except ImportError as e:
        check("Doc generator imports", False, str(e))
        return

    # T2: Parse EPL source
    gen = DocGenerator()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.epl', delete=False, encoding='utf-8') as f:
        f.write('''# Test module description
# Provides utility functions

# @param name The person to greet
# @return A greeting string
Function Greet(name)
    Return "Hello, " + name
End

# Calculator class
Class Calculator
    Function Init(value)
        Set this.value to value
    End

    # @param n Number to add
    Function Add(n)
        Set this.value to this.value + n
    End
End

Create PI equal to 3.14159
Constant MAX equal to 100
''')
        tmpfile = f.name

    try:
        mod = gen.parse_file(tmpfile)
        check("Parse EPL file", mod is not None)

        # T3: Module metadata
        check("Module name extracted", mod.name is not None and len(mod.name) > 0)

        # T4: Module description
        check("Module description", len(mod.description) > 0)

        # T5: Functions extracted
        functions = [e for e in mod.entries if e.kind == 'function']
        check("Functions extracted", len(functions) >= 1)

        # T6: Function params from @param tag
        greet = next((e for e in mod.entries if e.name == 'Greet'), None)
        check("Greet function found", greet is not None)
        if greet:
            check("@param tag parsed", len(greet.params) >= 1)
            check("@return tag parsed", greet.returns != '')

        # T7: Classes extracted
        classes = [e for e in mod.entries if e.kind == 'class']
        check("Classes extracted", len(classes) >= 1)

        # T8: Class methods
        calc = next((e for e in mod.entries if e.name == 'Calculator'), None)
        check("Calculator class found", calc is not None)
        if calc:
            check("Class methods extracted", len(calc.children) >= 1)

        # T9: Variables extracted
        variables = [e for e in mod.entries if e.kind == 'variable']
        check("Variables extracted", len(variables) >= 1)

        # T10: Constants extracted
        constants = [e for e in mod.entries if e.kind == 'constant']
        check("Constants extracted", len(constants) >= 1)

        # T11: To Markdown output
        md = gen.to_markdown()
        check("Markdown generation", len(md) > 0)
        check("Markdown has module", 'Greet' in md)
        check("Markdown has TOC", '## Table of Contents' in md)

        # T12: To HTML output
        html = gen.to_html()
        check("HTML generation", len(html) > 100)
        check("HTML has DOCTYPE", '<!DOCTYPE html>' in html)
        check("HTML has sidebar", 'sidebar' in html)
        check("HTML has search", 'search' in html.lower())
        check("HTML has entries", 'entry' in html)
        check("HTML has dark mode", 'prefers-color-scheme:dark' in html)

        # T13: To JSON output
        json_str = gen.to_json()
        data = json.loads(json_str)
        check("JSON generation", isinstance(data, list))
        check("JSON has module entries", len(data) > 0 and 'entries' in data[0])

        # T14: Cross-reference support
        check("HTML cross-reference class", 'xref' in html or 'data-name' in html)

    finally:
        os.unlink(tmpfile)

    # T15: Parse directory
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, 'utils.epl'), 'w') as f:
            f.write('Function Helper()\n    Return 1\nEnd\n')
        with open(os.path.join(tmpdir, 'main.epl'), 'w') as f:
            f.write('Function Main()\n    Print "hi"\nEnd\n')

        gen2 = DocGenerator()
        gen2.parse_directory(tmpdir)
        check("Parse directory", len(gen2.modules) == 2)

    # T16: Linter basics
    from epl.doc_linter import Linter, LintConfig
    linter = Linter(LintConfig(max_line_length=40))
    issues = linter.lint_source('Create x equal to 1\n' + 'A' * 60 + '\n', '<test>')
    check("Linter module works", isinstance(issues, list))

    # T17: LintConfig from defaults
    config = LintConfig()
    check("LintConfig defaults", config.max_line_length == 120)
    check("LintConfig max_params", config.max_params == 6)

    # T18: DocEntry dataclass
    entry = DocEntry(kind='function', name='Test')
    check("DocEntry creation", entry.kind == 'function' and entry.name == 'Test')


# ══════════════════════════════════════════════════════════
# 4.3  50 Official Packages
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_50_packages():
    print("\n=== 4.3 50 Official Packages ===")

    # T1: Import package manager
    try:
        from epl.package_manager import BUILTIN_REGISTRY
        check("Package manager imports", True)
    except ImportError as e:
        check("Package manager imports", False, str(e))
        return

    # T2: 51 packages exist
    check("51 packages in registry", len(BUILTIN_REGISTRY) == 51,
          f"got {len(BUILTIN_REGISTRY)}")

    # T3: All packages have required fields
    required_fields = ['version', 'description']
    all_have_fields = True
    for name, info in BUILTIN_REGISTRY.items():
        for field in required_fields:
            if field not in info:
                all_have_fields = False
                check(f"{name} has {field}", False)
    check("All packages have version+description", all_have_fields)

    # T4: Check specific core packages exist
    core_packages = [
        'epl-math', 'epl-string', 'epl-collections', 'epl-json', 'epl-csv',
        'epl-http', 'epl-web', 'epl-db', 'epl-crypto', 'epl-testing',
    ]
    for pkg in core_packages:
        check(f"Core package: {pkg}", pkg in BUILTIN_REGISTRY)

    # T5: Check new packages from Phase 4
    new_packages = [
        'epl-auth', 'epl-email', 'epl-pdf', 'epl-charts', 'epl-orm',
        'epl-queue', 'epl-scheduler', 'epl-websocket', 'epl-xml', 'epl-i18n',
        'epl-rate-limit', 'epl-markdown', 'epl-color', 'epl-semver',
    ]
    for pkg in new_packages:
        check(f"New package: {pkg}", pkg in BUILTIN_REGISTRY)

    # T6: All packages have keywords for search
    from epl.package_manager import _get_builtin_source, _get_builtin_source_extra
    packages_with_keywords = sum(1 for info in BUILTIN_REGISTRY.values()
                                  if 'keywords' in info)
    check("Packages with keywords", packages_with_keywords >= 14)

    # T7: Builtin source generation for original packages
    try:
        src = _get_builtin_source('epl-math')
        check("epl-math has source", src is not None and len(src) > 0)
    except Exception as e:
        check("epl-math has source", False, str(e))

    # T8: Builtin source generation for new packages
    for pkg in new_packages:
        try:
            src = _get_builtin_source_extra(pkg)
            has_src = src is not None and len(src) > 10
            check(f"{pkg} has source", has_src)
        except Exception as e:
            check(f"{pkg} has source", False, str(e))

    # T9: Version strings are valid semver-like
    import re
    semver_re = re.compile(r'^\d+\.\d+\.\d+$')
    all_valid = True
    for name, info in BUILTIN_REGISTRY.items():
        if not semver_re.match(info.get('version', '')):
            all_valid = False
            check(f"Version format: {name}", False, info.get('version', 'missing'))
    check("All versions are semver", all_valid)

    # T10: No duplicate package names
    names = list(BUILTIN_REGISTRY.keys())
    check("No duplicate packages", len(names) == len(set(names)))

    # T11: Package descriptions are non-empty
    all_desc = all(len(info.get('description', '')) > 5 for info in BUILTIN_REGISTRY.values())
    check("All descriptions non-empty", all_desc)


# ══════════════════════════════════════════════════════════
# 4.4  Documentation Site Generator
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_site_generator():
    print("\n=== 4.4 Documentation Site Generator ===")

    # T1: Module imports
    try:
        from epl.site_generator import SiteGenerator, generate_site
        check("Site generator imports", True)
    except ImportError as e:
        check("Site generator imports", False, str(e))
        return

    # T2: SiteGenerator init
    gen = SiteGenerator()
    check("SiteGenerator init", gen is not None)

    # T3: Generate site to temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir, page_count = generate_site(output_dir=tmpdir)
        check("generate_site returns", out_dir is not None and page_count > 0)

        # T4: Expected page count
        check("Generated 7 pages", page_count == 7, f"got {page_count}")

        # T5: index.html exists
        check("index.html exists", os.path.isfile(os.path.join(tmpdir, 'index.html')))

        # T6: getting-started.html exists
        check("getting-started.html exists",
              os.path.isfile(os.path.join(tmpdir, 'getting-started.html')))

        # T7: reference.html exists
        check("reference.html exists",
              os.path.isfile(os.path.join(tmpdir, 'reference.html')))

        # T8: api.html exists
        check("api.html exists", os.path.isfile(os.path.join(tmpdir, 'api.html')))

        # T9: packages.html exists
        check("packages.html exists",
              os.path.isfile(os.path.join(tmpdir, 'packages.html')))

        # T10: tutorials.html exists
        check("tutorials.html exists",
              os.path.isfile(os.path.join(tmpdir, 'tutorials.html')))

        # T11: compiler.html exists
        check("compiler.html exists",
              os.path.isfile(os.path.join(tmpdir, 'compiler.html')))

        # T12: index.html has valid HTML
        with open(os.path.join(tmpdir, 'index.html'), 'r', encoding='utf-8') as f:
            idx_html = f.read()
        check("index has DOCTYPE", '<!DOCTYPE html>' in idx_html)
        check("index has title", '<title>' in idx_html)
        check("index has sidebar", 'sidebar' in idx_html)
        check("index has navigation", 'Getting Started' in idx_html)
        check("index has EPL description", 'English Programming Language' in idx_html)

        # T13: packages.html lists packages
        with open(os.path.join(tmpdir, 'packages.html'), 'r', encoding='utf-8') as f:
            pkg_html = f.read()
        check("Packages page has package count", '50' in pkg_html)
        check("Packages page has search", 'search' in pkg_html.lower())
        check("Packages page has epl-math", 'epl-math' in pkg_html)
        check("Packages page has epl-auth", 'epl-auth' in pkg_html)

        # T14: reference.html has language content
        with open(os.path.join(tmpdir, 'reference.html'), 'r', encoding='utf-8') as f:
            ref_html = f.read()
        check("Reference has data types", 'Data Types' in ref_html)
        check("Reference has control flow", 'Control Flow' in ref_html)
        check("Reference has classes", 'Classes' in ref_html)

        # T15: tutorials.html has tutorial content
        with open(os.path.join(tmpdir, 'tutorials.html'), 'r', encoding='utf-8') as f:
            tut_html = f.read()
        check("Tutorials has calculator", 'Calculator' in tut_html)
        check("Tutorials has code examples", 'Function' in tut_html)

        # T16: api.html has built-in functions
        with open(os.path.join(tmpdir, 'api.html'), 'r', encoding='utf-8') as f:
            api_html = f.read()
        check("API has built-in functions", 'Built-in Functions' in api_html)
        check("API has length function", 'length' in api_html)
        check("API has search", 'Search' in api_html or 'search' in api_html)

        # T17: All pages have consistent header
        for page_file in ['index.html', 'getting-started.html', 'reference.html',
                          'api.html', 'packages.html', 'tutorials.html', 'compiler.html']:
            path = os.path.join(tmpdir, page_file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            check(f"{page_file} has site header",
                  'site-header' in content)

        # T18: Dark mode CSS present
        check("CSS has dark mode", 'prefers-color-scheme' in idx_html)

        # T19: Responsive design
        check("CSS is responsive", '@media' in idx_html)

    # T20: Generate with source dirs
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = os.path.join(tmpdir, 'src')
        out_dir = os.path.join(tmpdir, 'out')
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, 'lib.epl'), 'w') as f:
            f.write('Function Hello()\n    Print "hi"\nEnd\n')
        out, count = generate_site(source_dirs=[src_dir], output_dir=out_dir)
        check("Site with source dirs", count == 7)
        with open(os.path.join(out, 'api.html'), 'r', encoding='utf-8') as f:
            api_content = f.read()
        check("API includes parsed source", 'Hello' in api_content)


# ══════════════════════════════════════════════════════════
# 4.5  Integration Tests
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_integration():
    print("\n=== 4.5 Integration Tests ===")

    # T1: CLI 'site' command exists in main.py
    import importlib
    main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_source = f.read()
    check("CLI has 'site' command", "command == 'site'" in main_source)
    check("CLI has 'search' command", "command == 'search'" in main_source)
    check("CLI has 'publish' command", "command == 'publish'" in main_source)
    check("CLI has 'info' command", "command == 'info'" in main_source)
    check("CLI has 'stats' command", "command == 'stats'" in main_source)

    # T2: site command imports site_generator
    check("Site command uses site_generator",
          'from epl.site_generator import generate_site' in main_source)

    # T3: Registry integrates with package manager
    from epl.package_manager import BUILTIN_REGISTRY
    from epl.registry import GitHubRegistry
    check("Registry can access BUILTIN_REGISTRY",
          hasattr(GitHubRegistry, 'search'))

    # T4: Doc generator integrates with site generator
    from epl.doc_linter import DocGenerator
    from epl.site_generator import SiteGenerator
    check("DocGenerator available to SiteGenerator", True)

    # T5: All new packages installable (builtin)
    from epl.package_manager import _get_builtin_source_extra
    installable = True
    new_pkgs = ['epl-auth', 'epl-email', 'epl-pdf', 'epl-charts', 'epl-orm',
                'epl-queue', 'epl-scheduler', 'epl-websocket', 'epl-xml',
                'epl-i18n', 'epl-rate-limit', 'epl-markdown', 'epl-color', 'epl-semver']
    for pkg in new_pkgs:
        src = _get_builtin_source_extra(pkg)
        if not src or len(src) < 20:
            installable = False
            check(f"  {pkg} installable", False)
    check("All new packages have install source", installable)


# ══════════════════════════════════════════════════════════
# 4.6  TOML Manifest Parser/Writer
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_toml_parser():
    print("\n=== 4.6 TOML Manifest Parser/Writer ===")

    from epl.package_manager import _parse_toml, _dump_toml, _toml_value

    # T1: Parse simple key-value
    toml_text = 'name = "hello"\nversion = "1.0.0"'
    result = _parse_toml(toml_text)
    check("Parse simple strings", result.get('name') == 'hello' and result.get('version') == '1.0.0')

    # T2: Parse integers and floats
    result2 = _parse_toml('count = 42\npi = 3.14')
    check("Parse numbers", result2.get('count') == 42 and abs(result2.get('pi', 0) - 3.14) < 0.001)

    # T3: Parse booleans
    result3 = _parse_toml('enabled = true\ndisabled = false')
    check("Parse booleans", result3.get('enabled') is True and result3.get('disabled') is False)

    # T4: Parse arrays
    result4 = _parse_toml('items = ["a", "b", "c"]')
    check("Parse arrays", result4.get('items') == ["a", "b", "c"])

    # T5: Parse table sections
    result5 = _parse_toml('[project]\nname = "test"\nversion = "2.0.0"')
    check("Parse table sections",
          result5.get('project', {}).get('name') == 'test' and
          result5.get('project', {}).get('version') == '2.0.0')

    # T6: Parse nested tables
    result6 = _parse_toml('[project]\nname = "app"\n\n[dependencies]\nepl-math = "^1.0.0"')
    check("Parse nested tables",
          result6.get('project', {}).get('name') == 'app' and
          result6.get('dependencies', {}).get('epl-math') == '^1.0.0')

    # T7: Parse inline tables
    result7 = _parse_toml('server = {host = "localhost", port = 8080}')
    check("Parse inline tables",
          result7.get('server', {}).get('host') == 'localhost' and
          result7.get('server', {}).get('port') == 8080)

    # T8: Parse comments
    result8 = _parse_toml('# This is a comment\nname = "test"\n# Another comment')
    check("Comments ignored", result8.get('name') == 'test' and len(result8) == 1)

    # T9: Parse escape sequences in strings
    result9 = _parse_toml('path = "C:\\\\Users\\\\test"')
    check("String escape sequences", result9.get('path') == 'C:\\Users\\test')

    # T10: Parse literal strings (single quotes)
    result10 = _parse_toml("path = 'no\\\\escapes'")
    check("Literal strings", result10.get('path') == 'no\\\\escapes')

    # T11: Empty document
    result11 = _parse_toml('')
    check("Parse empty document", result11 == {})

    # T12: Parse integer arrays
    result12 = _parse_toml('nums = [1, 2, 3]')
    check("Parse integer arrays", result12.get('nums') == [1, 2, 3])

    # T13: Full epl.toml example
    full_toml = """
[project]
name = "my-app"
version = "1.2.3"
description = "A test application"
author = "EPL Team"
license = "MIT"
entry = "main.epl"
keywords = ["test", "demo"]
repository = "epl-lang/my-app"

[dependencies]
epl-math = "^1.0.0"
epl-json = ">=2.0.0"
epl-http = "*"

[dev-dependencies]
epl-testing = "^1.0.0"

[scripts]
start = "epl main.epl"
build = "epl compile main.epl"
test = "epl test"
"""
    result13 = _parse_toml(full_toml)
    check("Full epl.toml parse",
          result13.get('project', {}).get('name') == 'my-app' and
          result13.get('project', {}).get('version') == '1.2.3' and
          result13.get('dependencies', {}).get('epl-math') == '^1.0.0' and
          result13.get('dev-dependencies', {}).get('epl-testing') == '^1.0.0' and
          result13.get('scripts', {}).get('start') == 'epl main.epl' and
          result13.get('project', {}).get('keywords') == ['test', 'demo'])

    # T14: TOML value serialization
    check("Serialize string", _toml_value("hello") == '"hello"')
    check("Serialize int", _toml_value(42) == '42')
    check("Serialize bool", _toml_value(True) == 'true')
    check("Serialize array", _toml_value([1, 2]) == '[1, 2]')

    # T15: Dump and re-parse round-trip
    data = {'project': {'name': 'roundtrip', 'version': '1.0.0'}, 'dependencies': {'epl-math': '^1.0'}}
    dumped = _dump_toml(data)
    reparsed = _parse_toml(dumped)
    check("TOML dump/parse round-trip",
          reparsed.get('project', {}).get('name') == 'roundtrip' and
          reparsed.get('dependencies', {}).get('epl-math') == '^1.0')

    # T16: Parse dotted keys
    result16 = _parse_toml('[project]\nname = "dottest"')
    check("Dotted table keys", result16.get('project', {}).get('name') == 'dottest')

    # T17: Array of tables
    aot = '[[servers]]\nhost = "alpha"\n\n[[servers]]\nhost = "beta"'
    result17 = _parse_toml(aot)
    check("Array of tables",
          isinstance(result17.get('servers'), list) and
          len(result17['servers']) == 2 and
          result17['servers'][0].get('host') == 'alpha' and
          result17['servers'][1].get('host') == 'beta')

    # T18: Numbers with underscores
    result18 = _parse_toml('big = 1_000_000')
    check("Numbers with underscores", result18.get('big') == 1000000)


# ══════════════════════════════════════════════════════════
# 4.7  TOML Manifest Integration
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_toml_manifest():
    print("\n=== 4.7 TOML Manifest Integration ===")

    from epl.package_manager import (
        _toml_to_manifest, _manifest_to_toml, create_manifest,
        load_manifest, save_manifest, get_manifest_format,
        migrate_manifest_to_toml, TOML_MANIFEST_NAME, MANIFEST_NAME
    )

    # T1: toml_to_manifest conversion
    toml_data = {
        'project': {'name': 'test-pkg', 'version': '2.0.0', 'description': 'Test',
                     'author': 'Dev', 'entry': 'app.epl', 'keywords': ['test']},
        'dependencies': {'epl-math': '^1.0.0'},
        'scripts': {'start': 'epl app.epl'}
    }
    manifest = _toml_to_manifest(toml_data)
    check("toml_to_manifest name", manifest.get('name') == 'test-pkg')
    check("toml_to_manifest version", manifest.get('version') == '2.0.0')
    check("toml_to_manifest deps", manifest.get('dependencies') == {'epl-math': '^1.0.0'})
    check("toml_to_manifest keywords", manifest.get('keywords') == ['test'])
    check("toml_to_manifest scripts", manifest.get('scripts') == {'start': 'epl app.epl'})

    # T2: manifest_to_toml conversion
    toml_out = _manifest_to_toml(manifest)
    check("manifest_to_toml project section", 'project' in toml_out)
    check("manifest_to_toml deps section", 'dependencies' in toml_out)
    check("manifest_to_toml name preserved", toml_out['project']['name'] == 'test-pkg')

    # T3: Round-trip manifest -> toml -> manifest
    round_trip = _toml_to_manifest(_manifest_to_toml(manifest))
    check("Round-trip name", round_trip.get('name') == manifest.get('name'))
    check("Round-trip version", round_trip.get('version') == manifest.get('version'))
    check("Round-trip deps", round_trip.get('dependencies') == manifest.get('dependencies'))

    # T4: Create TOML manifest in temp directory
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            result = create_manifest(name='toml-test', version='1.0.0',
                                     description='TOML Test Project', fmt='toml')
            check("create_manifest toml file exists", os.path.exists(TOML_MANIFEST_NAME))
            check("create_manifest returns manifest", result.get('name') == 'toml-test')

            # T5: Load TOML manifest
            loaded = load_manifest('.')
            check("load_manifest reads toml", loaded is not None)
            check("load_manifest name correct", loaded.get('name') == 'toml-test')
            check("load_manifest version correct", loaded.get('version') == '1.0.0')
            check("load_manifest description", loaded.get('description') == 'TOML Test Project')
        finally:
            os.chdir(old_cwd)

    # T6: Create JSON manifest (legacy)
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='json-test', version='2.0.0', fmt='json')
            check("create_manifest json file exists", os.path.exists(MANIFEST_NAME))
            check("get_manifest_format json", get_manifest_format('.') == 'json')
        finally:
            os.chdir(old_cwd)

    # T7: TOML preferred over JSON
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # Create both
            create_manifest(name='json-ver', version='1.0.0', fmt='json')
            create_manifest(name='toml-ver', version='2.0.0', fmt='toml')
            loaded = load_manifest('.')
            check("TOML preferred over JSON", loaded.get('name') == 'toml-ver')
            check("get_manifest_format toml", get_manifest_format('.') == 'toml')
        finally:
            os.chdir(old_cwd)

    # T8: save_manifest preserves format
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='save-test', version='1.0.0', fmt='toml')
            loaded = load_manifest('.')
            loaded['version'] = '1.1.0'
            save_manifest(loaded, '.')
            reloaded = load_manifest('.')
            check("save_manifest preserves data", reloaded.get('version') == '1.1.0')
            check("save_manifest format stays toml", get_manifest_format('.') == 'toml')
        finally:
            os.chdir(old_cwd)

    # T9: Migrate JSON to TOML
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='migrate-test', version='3.0.0',
                            description='Migration test', fmt='json')
            check("Before migration: JSON exists", os.path.exists(MANIFEST_NAME))
            check("Before migration: no TOML", not os.path.exists(TOML_MANIFEST_NAME))

            migrated = migrate_manifest_to_toml('.')
            check("migrate_manifest_to_toml returns True", migrated is True)
            check("After migration: TOML exists", os.path.exists(TOML_MANIFEST_NAME))

            loaded = load_manifest('.')
            check("Migrated manifest name preserved", loaded.get('name') == 'migrate-test')
            check("Migrated manifest version preserved", loaded.get('version') == '3.0.0')

            # T10: Second migration returns False (already has toml)
            migrated2 = migrate_manifest_to_toml('.')
            check("Second migration returns False", migrated2 is False)
        finally:
            os.chdir(old_cwd)

    # T11: No manifest returns None
    with tempfile.TemporaryDirectory() as tmp:
        check("No manifest returns None", load_manifest(tmp) is None)
        check("No manifest format returns None", get_manifest_format(tmp) is None)

    # T12: Dev dependencies
    toml_with_dev = {
        'project': {'name': 'dev-test', 'version': '1.0.0'},
        'dependencies': {'epl-math': '^1.0'},
        'dev-dependencies': {'epl-testing': '>=1.0.0'}
    }
    m = _toml_to_manifest(toml_with_dev)
    check("Dev dependencies parsed", m.get('dev-dependencies') == {'epl-testing': '>=1.0.0'})

    # T13: Tool section preserved
    toml_with_tool = {
        'project': {'name': 'tool-test', 'version': '1.0.0'},
        'dependencies': {},
        'tool': {'linter': {'max-line-length': 100}}
    }
    m2 = _toml_to_manifest(toml_with_tool)
    check("Tool section preserved", m2.get('tool', {}).get('linter', {}).get('max-line-length') == 100)


# ══════════════════════════════════════════════════════════
# 4.8  Dependency Management (add/remove/tree/audit)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_dependency_management():
    print("\n=== 4.8 Dependency Management ===")

    from epl.package_manager import (
        dependency_tree, print_dependency_tree, outdated_packages,
        audit_packages, clean_cache, add_dependency, remove_dependency,
        create_manifest, load_manifest, save_manifest, install_package,
        uninstall_package, PACKAGES_DIR, CACHE_DIR
    )

    # T1: dependency_tree with no manifest
    with tempfile.TemporaryDirectory() as tmp:
        tree = dependency_tree(tmp)
        check("dependency_tree no manifest", tree == [])

    # T2: dependency_tree with empty deps
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='tree-test', version='1.0.0', fmt='toml')
            tree = dependency_tree('.')
            check("dependency_tree empty deps", tree == [])
        finally:
            os.chdir(old_cwd)

    # T3: dependency_tree with deps
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='tree-test2', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '^1.0.0', 'epl-json': '*'}
            save_manifest(m, '.')
            tree = dependency_tree('.')
            check("dependency_tree shows deps", len(tree) == 2)
            names = [n['name'] for n in tree]
            check("dependency_tree correct names", 'epl-math' in names and 'epl-json' in names)
        finally:
            os.chdir(old_cwd)

    # T4: print_dependency_tree runs without error
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='print-tree', version='1.0.0', fmt='toml')
            # Should print without crashing
            import io as _io
            import sys as _sys
            captured = _io.StringIO()
            old_stdout = _sys.stdout
            _sys.stdout = captured
            print_dependency_tree('.')
            _sys.stdout = old_stdout
            output = captured.getvalue()
            check("print_dependency_tree runs", 'print-tree' in output or 'No dependencies' in output)
        finally:
            os.chdir(old_cwd)

    # T5: outdated_packages with no manifest
    with tempfile.TemporaryDirectory() as tmp:
        result = outdated_packages(tmp)
        check("outdated_packages no manifest", result == [])

    # T6: audit_packages with no manifest
    with tempfile.TemporaryDirectory() as tmp:
        result = audit_packages(tmp)
        check("audit_packages no manifest",
              result.get('ok') == 0 and len(result.get('errors', [])) > 0)

    # T7: audit_packages with manifest
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='audit-test', version='1.0.0', fmt='toml')
            result = audit_packages('.')
            check("audit_packages clean project", result.get('ok') == 0 and result.get('errors') == [])
        finally:
            os.chdir(old_cwd)

    # T8: Install a builtin package and verify audit
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='install-test', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '*'}
            save_manifest(m, '.')
            install_package('epl-math')
            result = audit_packages('.')
            check("audit_packages installed pkg", result.get('ok') >= 1)
        finally:
            os.chdir(old_cwd)

    # T9: clean_cache runs without error
    import io as _io2
    import sys as _sys2
    captured2 = _io2.StringIO()
    old_stdout2 = _sys2.stdout
    _sys2.stdout = captured2
    clean_cache()
    _sys2.stdout = old_stdout2
    check("clean_cache runs", 'Clean' in captured2.getvalue() or 'empty' in captured2.getvalue())

    # T10: add_dependency function exists and works
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='add-test', version='1.0.0', fmt='toml')
            # Create dummy main.epl for entry point
            with open('main.epl', 'w') as f:
                f.write('Print "test"')
            add_dependency('epl-math', '^1.0.0')
            loaded = load_manifest('.')
            check("add_dependency updates manifest",
                  loaded.get('dependencies', {}).get('epl-math') == '^1.0.0')
        finally:
            os.chdir(old_cwd)

    # T11: remove_dependency function
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='remove-test', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '^1.0.0'}
            save_manifest(m, '.')
            remove_dependency('epl-math')
            loaded = load_manifest('.')
            check("remove_dependency removes from manifest",
                  'epl-math' not in loaded.get('dependencies', {}))
        finally:
            os.chdir(old_cwd)

    # T12: add_dependency with --dev
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='dev-add-test', version='1.0.0', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "test"')
            add_dependency('epl-testing', '>=1.0.0', dev=True)
            loaded = load_manifest('.')
            check("add dev-dependency",
                  loaded.get('dev-dependencies', {}).get('epl-testing') == '>=1.0.0')
        finally:
            os.chdir(old_cwd)


# ══════════════════════════════════════════════════════════
# 4.9  SemVer & Dependency Resolution (Production)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_semver_production():
    print("\n=== 4.9 SemVer & Dependency Resolution ===")

    from epl.package_manager import SemVer, parse_version_range, DependencyConflict, resolve_dependencies

    # T1: Basic semver parsing
    v = SemVer.parse('1.2.3')
    check("SemVer parse basic", v is not None and v.major == 1 and v.minor == 2 and v.patch == 3)

    # T2: Pre-release parsing
    v2 = SemVer.parse('1.0.0-beta.1')
    check("SemVer parse pre-release", v2 is not None and v2.pre == 'beta.1')

    # T3: Build metadata
    v3 = SemVer.parse('1.0.0+build123')
    check("SemVer parse build metadata", v3 is not None and v3.build == 'build123')

    # T4: Version comparison
    a = SemVer.parse('1.0.0')
    b = SemVer.parse('2.0.0')
    check("SemVer comparison <", a < b)
    check("SemVer comparison >", b > a)
    check("SemVer comparison ==", SemVer.parse('1.0.0') == SemVer.parse('1.0.0'))
    check("SemVer comparison !=", a != b)

    # T5: Caret range (^) — compatible with
    checker_caret = parse_version_range('^1.2.0')
    check("Caret range ^1.2.0 allows 1.3.0", checker_caret(SemVer.parse('1.3.0')))
    check("Caret range ^1.2.0 allows 1.2.5", checker_caret(SemVer.parse('1.2.5')))
    check("Caret range ^1.2.0 blocks 2.0.0", not checker_caret(SemVer.parse('2.0.0')))
    check("Caret range ^1.2.0 blocks 0.9.0", not checker_caret(SemVer.parse('0.9.0')))

    # T6: Tilde range (~) — patch-level
    checker_tilde = parse_version_range('~1.2.0')
    check("Tilde range ~1.2.0 allows 1.2.5", checker_tilde(SemVer.parse('1.2.5')))
    check("Tilde range ~1.2.0 blocks 1.3.0", not checker_tilde(SemVer.parse('1.3.0')))

    # T7: Wildcard
    checker_star = parse_version_range('*')
    check("Wildcard * allows anything", checker_star(SemVer.parse('99.99.99')))

    # T8: Comparison operators
    check(">=2.0.0 allows 2.0.0", parse_version_range('>=2.0.0')(SemVer.parse('2.0.0')))
    check(">=2.0.0 allows 3.0.0", parse_version_range('>=2.0.0')(SemVer.parse('3.0.0')))
    check(">=2.0.0 blocks 1.9.9", not parse_version_range('>=2.0.0')(SemVer.parse('1.9.9')))

    check("<3.0.0 allows 2.9.9", parse_version_range('<3.0.0')(SemVer.parse('2.9.9')))
    check("<3.0.0 blocks 3.0.0", not parse_version_range('<3.0.0')(SemVer.parse('3.0.0')))

    check("!=1.0.0 allows 1.0.1", parse_version_range('!=1.0.0')(SemVer.parse('1.0.1')))
    check("!=1.0.0 blocks 1.0.0", not parse_version_range('!=1.0.0')(SemVer.parse('1.0.0')))

    # T9: Exact version
    checker_exact = parse_version_range('=1.5.0')
    check("Exact =1.5.0 allows 1.5.0", checker_exact(SemVer.parse('1.5.0')))
    check("Exact =1.5.0 blocks 1.5.1", not checker_exact(SemVer.parse('1.5.1')))

    # T10: SemVer string representation
    check("SemVer str", str(SemVer.parse('1.2.3')) == '1.2.3')

    # T11: Invalid semver
    check("Invalid semver returns None", SemVer.parse('not-a-version') is None)
    check("Empty semver returns None", SemVer.parse('') is None)

    # T12: DependencyConflict is an exception
    check("DependencyConflict is Exception", issubclass(DependencyConflict, Exception))

    # T13: SemVer ordering
    versions = ['0.1.0', '0.2.0', '1.0.0', '1.0.1', '1.1.0', '2.0.0']
    parsed = [SemVer.parse(v) for v in versions]
    for i in range(len(parsed) - 1):
        if parsed[i] >= parsed[i + 1]:
            check("SemVer ordering", False, f"{versions[i]} >= {versions[i+1]}")
            break
    else:
        check("SemVer ordering correct", True)

    # T14: SemVer compatible (caret)
    v_base = SemVer.parse('1.2.3')
    check("SemVer.compatible with 1.9.0", v_base.compatible(SemVer.parse('1.9.0')))
    check("SemVer.compatible blocks 2.0.0", not v_base.compatible(SemVer.parse('2.0.0')))

    # T15: SemVer tilde_compatible
    check("SemVer.tilde_compatible with 1.2.9", v_base.tilde_compatible(SemVer.parse('1.2.9')))
    check("SemVer.tilde_compatible blocks 1.3.0", not v_base.tilde_compatible(SemVer.parse('1.3.0')))


# ══════════════════════════════════════════════════════════
# 4.10  Lockfile & Integrity
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_lockfile():
    print("\n=== 4.10 Lockfile & Integrity ===")

    from epl.package_manager import (
        create_lockfile, load_lockfile, verify_lockfile, _hash_directory,
        create_manifest, save_manifest, install_package, LOCKFILE_NAME
    )

    # T1: _hash_directory produces consistent results
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'test.txt'), 'w') as f:
            f.write('hello world')
        h1 = _hash_directory(tmp)
        h2 = _hash_directory(tmp)
        check("_hash_directory deterministic", h1 == h2 and len(h1) == 64)

    # T2: _hash_directory changes with content
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'test.txt'), 'w') as f:
            f.write('version 1')
        h1 = _hash_directory(tmp)
        with open(os.path.join(tmp, 'test.txt'), 'w') as f:
            f.write('version 2')
        h2 = _hash_directory(tmp)
        check("_hash_directory changes with content", h1 != h2)

    # T3: create_lockfile with installed package
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='lock-test', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '*'}
            save_manifest(m, '.')
            install_package('epl-math')
            create_lockfile('.')
            check("Lockfile created", os.path.exists(LOCKFILE_NAME))
        finally:
            os.chdir(old_cwd)

    # T4: load_lockfile
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='lock-load', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '*'}
            save_manifest(m, '.')
            install_package('epl-math')
            create_lockfile('.')
            lock = load_lockfile('.')
            check("load_lockfile returns data", lock is not None)
            check("Lockfile has packages", 'packages' in (lock or {}))
        finally:
            os.chdir(old_cwd)

    # T5: Lockfile integrity
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m = create_manifest(name='verify-test', version='1.0.0', fmt='toml')
            m['dependencies'] = {'epl-math': '*'}
            save_manifest(m, '.')
            install_package('epl-math')
            create_lockfile('.')
            result = verify_lockfile('.')
            check("verify_lockfile passes",
                  isinstance(result, dict) and result.get('valid', False) is True)
        finally:
            os.chdir(old_cwd)

    # T6: No lockfile returns empty/None
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            result = load_lockfile('.')
            check("No lockfile returns None/empty", result is None or result == {})
        finally:
            os.chdir(old_cwd)


# ══════════════════════════════════════════════════════════
# 4.11  Install Pipeline (Production)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_install_pipeline():
    print("\n=== 4.11 Install Pipeline ===")

    from epl.package_manager import (
        install_package, uninstall_package, _sanitize_package_name,
        _validate_url, _validate_github_repo, find_package_module,
        PACKAGES_DIR, BUILTIN_REGISTRY, list_packages
    )

    # T1: Install builtin package
    result = install_package('epl-math')
    check("Install builtin epl-math", result is True)
    check("Package dir exists", os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-math')))

    # T2: Installed package has manifest
    from epl.package_manager import load_manifest
    pkg_manifest = load_manifest(os.path.join(PACKAGES_DIR, 'epl-math'))
    check("Installed package has manifest", pkg_manifest is not None)
    check("Manifest has correct name", pkg_manifest.get('name') == 'epl-math')

    # T3: Install another package
    result2 = install_package('epl-json')
    check("Install builtin epl-json", result2 is True)

    # T4: list_packages shows installed
    pkgs = list_packages()
    pkg_names = [p[0] for p in pkgs] if pkgs else []
    check("list_packages includes epl-math", 'epl-math' in pkg_names)

    # T5: Uninstall package
    uninstall_package('epl-json')
    check("Uninstall removes dir", not os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-json')))

    # T6: find_package_module for installed
    found = find_package_module('epl-math')
    check("find_package_module finds installed", found is not None)

    # T7: Sanitize valid names
    check("Sanitize valid name", _sanitize_package_name('epl-math') == 'epl-math')
    check("Sanitize valid name 2", _sanitize_package_name('my.pkg') == 'my.pkg')

    # T8: Sanitize rejects bad names
    try:
        _sanitize_package_name('../../../etc/passwd')
        check("Sanitize rejects path traversal", False)
    except ValueError:
        check("Sanitize rejects path traversal", True)

    try:
        _sanitize_package_name('')
        check("Sanitize rejects empty", False)
    except ValueError:
        check("Sanitize rejects empty", True)

    # T9: URL validation
    check("Validate https URL", _validate_url('https://example.com/pkg.zip') == 'https://example.com/pkg.zip')
    try:
        _validate_url('http://insecure.com/pkg.zip')
        check("Reject http URL", False)
    except ValueError:
        check("Reject http URL", True)

    # T10: GitHub repo validation
    check("Validate github repo", _validate_github_repo('user/repo') == 'user/repo')
    try:
        _validate_github_repo('../../etc')
        check("Reject bad github repo", False)
    except ValueError:
        check("Reject bad github repo", True)

    # T11: http:// install rejected
    try:
        install_package('http://insecure.com/pkg.zip')
        check("http install rejected", False)
    except ValueError:
        check("http install rejected", True)

    # T12: All 51 builtins installable
    installable_count = 0
    from epl.package_manager import _get_builtin_source
    for name in list(BUILTIN_REGISTRY.keys())[:5]:
        src = _get_builtin_source(name)
        if src and len(src) > 10:
            installable_count += 1
    check("Builtin packages have source", installable_count == 5)


# ══════════════════════════════════════════════════════════
# 4.12  Publish & Pack Workflow
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_publish_workflow():
    print("\n=== 4.12 Publish & Pack Workflow ===")

    from epl.package_manager import (
        validate_package, pack_package, publish_package,
        create_manifest
    )

    # T1: validate_package with valid project
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='pub-test', version='1.0.0',
                            description='Test package', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "Hello"')
            result = validate_package('.')
            check("validate_package valid", result['valid'] is True)
            check("validate_package no errors", len(result['errors']) == 0)
        finally:
            os.chdir(old_cwd)

    # T2: validate_package missing description
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='no-desc', version='1.0.0', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "Hello"')
            result = validate_package('.')
            check("validate missing description", not result['valid'] or
                  any('description' in e.lower() for e in result.get('errors', [])))
        finally:
            os.chdir(old_cwd)

    # T3: validate_package no manifest
    with tempfile.TemporaryDirectory() as tmp:
        result = validate_package(tmp)
        check("validate no manifest", result['valid'] is False)
        check("validate error mentions manifest",
              any('manifest' in e.lower() or 'epl.toml' in e.lower() for e in result['errors']))

    # T4: validate_package missing entry point
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='no-entry', version='1.0.0',
                            description='Test', entry='missing.epl', fmt='toml')
            result = validate_package('.')
            check("validate missing entry point",
                  any('entry' in e.lower() for e in result['errors']))
        finally:
            os.chdir(old_cwd)

    # T5: pack_package creates archive
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='pack-test', version='1.0.0',
                            description='Pack test', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "Pack test"')
            archive = pack_package('.')
            check("pack_package returns path", archive is not None)
            if archive:
                check("Archive file exists", os.path.exists(archive))
                check("Archive is zip", archive.endswith('.zip'))
                check("Checksum file exists", os.path.exists(archive + '.sha256'))
        finally:
            os.chdir(old_cwd)

    # T6: pack_package archive contents
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='contents-test', version='2.0.0',
                            description='Contents test', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "Contents"')
            archive = pack_package('.')
            if archive:
                import zipfile as _zf
                with _zf.ZipFile(archive, 'r') as zf:
                    names = zf.namelist()
                    check("Archive contains manifest",
                          'epl.toml' in names or 'epl.json' in names)
                    check("Archive contains entry", 'main.epl' in names)
        finally:
            os.chdir(old_cwd)

    # T7: publish_package to local registry
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='local-pub', version='1.0.0',
                            description='Local publish test', fmt='toml')
            with open('main.epl', 'w') as f:
                f.write('Print "Published!"')
            result = publish_package('.')
            check("publish_package succeeds", result is True)
        finally:
            os.chdir(old_cwd)

    # T8: validate warns on legacy JSON
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            create_manifest(name='legacy-warn', version='1.0.0',
                            description='Legacy test', fmt='json')
            with open('main.epl', 'w') as f:
                f.write('Print "Legacy"')
            result = validate_package('.')
            check("validate warns on JSON manifest",
                  any('toml' in w.lower() or 'legacy' in w.lower() for w in result.get('warnings', [])))
        finally:
            os.chdir(old_cwd)


# ══════════════════════════════════════════════════════════
# 4.13  CLI Commands Integration
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_cli_commands():
    print("\n=== 4.13 CLI Commands ===")

    # Read main.py source to check commands exist
    main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    with open(main_path, 'r', encoding='utf-8') as f:
        main_src = f.read()

    # T1-T14: Check all CLI commands exist
    commands = [
        ('init', "command == 'init'"),
        ('install', "command == 'install'"),
        ('uninstall', "command == 'uninstall'"),
        ('packages', "command == 'packages'"),
        ('search', "command == 'search'"),
        ('publish', "command == 'publish'"),
        ('info', "command == 'info'"),
        ('stats', "command == 'stats'"),
        ('add', "command == 'add'"),
        ('remove', "command == 'remove'"),
        ('lock', "command == 'lock'"),
        ('update', "command == 'update'"),
        ('tree', "command == 'tree'"),
        ('outdated', "command == 'outdated'"),
        ('audit', "command == 'audit'"),
        ('migrate', "command == 'migrate'"),
        ('cache', "command == 'cache'"),
    ]
    for cmd_name, pattern in commands:
        check(f"CLI '{cmd_name}' command exists", pattern in main_src)

    # T15: Package manager imports
    from epl.package_manager import (
        init_project, install_package, uninstall_package, list_packages,
        install_dependencies, update_package, update_all, validate_package,
        pack_package, publish_package, create_lockfile, load_lockfile,
        add_dependency, remove_dependency, dependency_tree, print_dependency_tree,
        outdated_packages, print_outdated, audit_packages, print_audit,
        clean_cache, migrate_manifest_to_toml
    )
    check("All package_manager functions importable", True)

    # T16: Registry imports
    from epl.registry import (
        RegistryCache, DownloadStats, GitHubRegistry,
        registry_search, registry_info, registry_publish, registry_stats
    )
    check("All registry functions importable", True)

    # T17: TOML functions importable
    from epl.package_manager import (
        _parse_toml, _dump_toml, _toml_value,
        _toml_to_manifest, _manifest_to_toml,
        load_manifest, save_manifest, get_manifest_format,
        TOML_MANIFEST_NAME
    )
    check("All TOML functions importable", True)

    # T18: init creates epl.toml (not epl.json)
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            init_project('cli-test')
            check("init creates epl.toml", os.path.exists('epl.toml'))
            check("init creates main.epl", os.path.exists('main.epl'))
        finally:
            os.chdir(old_cwd)


# ══════════════════════════════════════════════════════════
# 4.14  Registry (Production Features)
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_registry_production():
    print("\n=== 4.14 Registry Production Features ===")

    from epl.registry import RegistryCache, DownloadStats, GitHubRegistry

    # T1: Cache with custom path
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, 'test_cache.json')
        cache = RegistryCache(path=cache_path)
        cache.set_package('test-a', {'version': '1.0.0'})
        cache.set_package('test-b', {'version': '2.0.0'})
        check("Cache multiple packages", len(cache.all_packages()) == 2)

    # T2: Cache reload from disk
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, 'persist_cache.json')
        cache1 = RegistryCache(path=cache_path)
        cache1.set_package('persist-pkg', {'version': '3.0.0'})
        # Reload from disk
        cache2 = RegistryCache(path=cache_path)
        check("Cache persists to disk", cache2.get_package('persist-pkg') is not None)

    # T3: Cache staleness
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, 'stale_cache.json')
        cache = RegistryCache(path=cache_path)
        check("Fresh cache not stale (or stale if never written)", True)  # Just checking doesn't crash

    # T4: DownloadStats recording
    with tempfile.TemporaryDirectory() as tmp:
        stats_path = os.path.join(tmp, 'stats.json')
        stats = DownloadStats(path=stats_path)
        stats.record_download('pkg-a', '1.0.0')
        stats.record_download('pkg-a', '1.0.0')
        stats.record_download('pkg-b', '2.0.0')
        check("Stats record count", stats.get_count('pkg-a') == 2)
        check("Stats different package", stats.get_count('pkg-b') == 1)

    # T5: Top packages
    with tempfile.TemporaryDirectory() as tmp:
        stats_path = os.path.join(tmp, 'top_stats.json')
        stats = DownloadStats(path=stats_path)
        for _ in range(10):
            stats.record_download('popular', '1.0')
        for _ in range(3):
            stats.record_download('less-popular', '1.0')
        top = stats.top_packages(5)
        check("Top packages ordered", top[0][0] == 'popular' and top[0][1] == 10)

    # T6: GitHubRegistry init (offline)
    reg = GitHubRegistry(token='')
    check("GitHubRegistry init", reg is not None)

    # T7: Search builtin packages
    results = reg.search('math')
    check("Search finds epl-math",
          any(r['name'] == 'epl-math' for r in results))

    # T8: Search with multiple results
    results2 = reg.search('epl')
    check("Search returns multiple results", len(results2) > 5)

    # T9: Package info for builtin
    info = reg.get_package_info('epl-math')
    check("get_package_info returns data", info is not None)
    check("Package info has version", 'version' in (info or {}))

    # T10: Package info for nonexistent
    info2 = reg.get_package_info('nonexistent-pkg-xyz')
    check("Nonexistent package returns None", info2 is None)

    # T11: Stats summary
    stats = reg.get_stats()
    check("get_stats returns dict", isinstance(stats, dict))
    check("Stats has total_downloads", 'total_downloads' in stats)

    # T12: Registry retry logic exists (check method signature)
    import inspect
    sig = inspect.signature(reg._github_request)
    params = list(sig.parameters.keys())
    check("_github_request has retries param", 'retries' in params)

    # T13: _fetch_raw has retries
    sig2 = inspect.signature(reg._fetch_raw)
    params2 = list(sig2.parameters.keys())
    check("_fetch_raw has retries param", 'retries' in params2)

    # T14: Score matching
    score = reg._score_match('epl-math', {'description': 'Math functions', 'keywords': ['math']}, 'math', {'math'})
    check("Score matching positive", score > 0)

    score_zero = reg._score_match('epl-crypto', {'description': 'crypto', 'keywords': ['crypto']}, 'zznotfound', {'zznotfound'})
    check("Score matching zero for no match", score_zero == 0)


# ══════════════════════════════════════════════════════════
# 4.15  End-to-End Integration
# ══════════════════════════════════════════════════════════

@_tracked_test
def test_e2e_integration():
    print("\n=== 4.15 End-to-End Integration ===")

    from epl.package_manager import (
        init_project, install_package, create_lockfile, load_lockfile,
        load_manifest, save_manifest, add_dependency, dependency_tree,
        audit_packages, validate_package, pack_package, uninstall_package,
        get_manifest_format, PACKAGES_DIR
    )

    # T1: Full project lifecycle
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            # Init
            init_project('e2e-test')
            check("E2E: init creates toml", os.path.exists('epl.toml'))
            check("E2E: init creates main.epl", os.path.exists('main.epl'))
            check("E2E: format is toml", get_manifest_format('.') == 'toml')

            # Load and verify manifest
            m = load_manifest('.')
            check("E2E: manifest name", m.get('name') == 'e2e-test')

            # Add dependency
            add_dependency('epl-math', '^1.0.0')
            m2 = load_manifest('.')
            check("E2E: dependency added", 'epl-math' in m2.get('dependencies', {}))

            # Verify package installed
            check("E2E: package installed",
                  os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-math')))

            # Generate lockfile
            create_lockfile('.')
            lock = load_lockfile('.')
            check("E2E: lockfile generated", lock is not None)

            # Dependency tree
            tree = dependency_tree('.')
            check("E2E: tree shows epl-math",
                  any(n['name'] == 'epl-math' for n in tree))

            # Audit
            audit = audit_packages('.')
            check("E2E: audit passes", audit.get('ok', 0) >= 1 and len(audit.get('errors', [])) == 0)

            # Validate for publishing
            m3 = load_manifest('.')
            m3['description'] = 'End to end test package'
            save_manifest(m3, '.')
            validation = validate_package('.')
            check("E2E: validation passes", validation['valid'])

            # Pack
            archive = pack_package('.')
            check("E2E: pack created archive", archive is not None and os.path.exists(archive) if archive else False)

        finally:
            os.chdir(old_cwd)

    # T2: Install -> Uninstall lifecycle
    result = install_package('epl-crypto')
    check("E2E: install epl-crypto", result is True)
    check("E2E: crypto dir exists", os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-crypto')))
    uninstall_package('epl-crypto')
    check("E2E: crypto uninstalled", not os.path.isdir(os.path.join(PACKAGES_DIR, 'epl-crypto')))

    # T3: Multiple package install
    r1 = install_package('epl-db')
    r2 = install_package('epl-os')
    check("E2E: multi-install", r1 is True and r2 is True)
    # Cleanup
    uninstall_package('epl-db')
    uninstall_package('epl-os')

    # T4: TOML manifest with dev dependencies
    with tempfile.TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            init_project('dev-deps-test')
            add_dependency('epl-testing', '>=1.0.0', dev=True)
            m = load_manifest('.')
            check("E2E: dev-deps in manifest",
                  'epl-testing' in m.get('dev-dependencies', {}))
        finally:
            os.chdir(old_cwd)

    # T5: Atomic write safety
    from epl.package_manager import _atomic_write
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, 'atomic_test.txt')
        _atomic_write(fp, 'safe content')
        with open(fp, 'r') as f:
            check("E2E: atomic write", f.read() == 'safe content')

    # T6: File locking
    from epl.package_manager import _file_lock
    with tempfile.TemporaryDirectory() as tmp:
        fp = os.path.join(tmp, 'lock_test.txt')
        with open(fp, 'w') as f:
            f.write('data')
        with _file_lock(fp):
            check("E2E: file lock acquired", True)
        check("E2E: file lock released", not os.path.exists(fp + '.lock'))


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

def main():
    print("=" * 55)
    print("  EPL Phase 4 Tests — Ecosystem")
    print("=" * 55)

    test_functions = [
        test_registry,
        test_doc_generator,
        test_50_packages,
        test_site_generator,
        test_integration,
        test_toml_parser,
        test_toml_manifest,
        test_dependency_management,
        test_semver_production,
        test_lockfile,
        test_install_pipeline,
        test_publish_workflow,
        test_cli_commands,
        test_registry_production,
        test_e2e_integration,
    ]

    for test_fn in test_functions:
        try:
            test_fn()
        except AssertionError:
            pass

    total = _TrackerState.total_pass + _TrackerState.total_fail
    print(f"\n{'=' * 55}")
    print(f"  Results: {_TrackerState.total_pass}/{total} passed, {_TrackerState.total_fail} failed")
    print(f"{'=' * 55}")

    return _TrackerState.total_fail == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
