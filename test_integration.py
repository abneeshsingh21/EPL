"""
EPL Production Integration Test Suite
Tests all subsystem connections are production-grade.
"""
import os
import sys

PASS = 0
FAIL = 0

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  [PASS] {name}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        FAIL += 1

# ═══════════════════════════════════════════════════
# TEST 1: Core imports
# ═══════════════════════════════════════════════════
print("=" * 60)
print("SECTION 1: Core Imports")
print("=" * 60)

def test_type_checker_imports():
    from epl.type_checker import TypeChecker, type_check, type_check_file, TypeWarning
    assert callable(TypeChecker)
    assert callable(type_check)
    assert callable(type_check_file)

def test_lsp_imports():
    from epl.lsp_server import EPLLanguageServer, JSONRPC, EPLAnalyzer
    assert callable(EPLLanguageServer)
    assert callable(EPLAnalyzer)

def test_package_manager_imports():
    from epl.package_manager import load_manifest, create_manifest, install_package
    assert callable(load_manifest)
    assert callable(create_manifest)

def test_type_system_imports():
    from epl.type_checker import EPLType, T_INTEGER, T_TEXT, T_BOOLEAN, T_LIST, T_ANY
    assert T_INTEGER.name == "integer"
    assert T_TEXT.name == "text"
    assert T_BOOLEAN.name == "boolean"

def test_lexer_parser_imports():
    from epl.lexer import Lexer
    from epl.parser import Parser
    assert callable(Lexer)
    assert callable(Parser)

test("TypeChecker imports", test_type_checker_imports)
test("LSP Server imports", test_lsp_imports)
test("Package Manager imports", test_package_manager_imports)
test("Type System imports", test_type_system_imports)
test("Lexer + Parser imports", test_lexer_parser_imports)

# ═══════════════════════════════════════════════════
# TEST 2: Pipeline Integration
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 2: Lexer → Parser → TypeChecker Pipeline")
print("=" * 60)

def test_pipeline_basic():
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.type_checker import TypeChecker
    source = 'Set x To 10\nSet y To 20\nSay x + y\n'
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    checker = TypeChecker(strict=False)
    warnings = checker.check(program)
    assert isinstance(warnings, list)

def test_pipeline_strict():
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl.type_checker import TypeChecker
    source = 'Set x To 10\nSay x\n'
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    checker = TypeChecker(strict=True)
    warnings = checker.check(program)
    assert isinstance(warnings, list)

def test_typewarning_to_dict():
    from epl.type_checker import TypeWarning
    tw = TypeWarning("test error", 5, "error", "fix it", "E001")
    d = tw.to_dict()
    assert d["severity"] == 1
    assert d["source"] == "epl-typecheck"
    assert d["code"] == "E001"
    assert d["range"]["start"]["line"] == 4  # 0-indexed
    assert "test error" in d["message"]

def test_checker_helpers():
    from epl.type_checker import TypeChecker
    c = TypeChecker()
    assert hasattr(c, "has_errors")
    assert hasattr(c, "format_report")
    assert hasattr(c, "to_lsp_diagnostics")

test("Basic pipeline (Lexer→Parser→TypeChecker)", test_pipeline_basic)
test("Strict mode pipeline", test_pipeline_strict)
test("TypeWarning.to_dict() LSP format", test_typewarning_to_dict)
test("TypeChecker helper methods", test_checker_helpers)

# ═══════════════════════════════════════════════════
# TEST 3: type_check_file() on real files
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 3: type_check_file() on real .epl files")
print("=" * 60)

test_files = [
    "examples/hello.epl",
    "examples/advanced.epl",
    "examples/classes.epl",
    "examples/builtins.epl",
]

for f in test_files:
    def make_test(filepath):
        def t():
            from epl.type_checker import type_check_file
            checker = type_check_file(filepath)
            assert not checker.has_errors(), f"Type errors found: {checker.format_report()}"
        return t
    if os.path.isfile(f):
        test(f"type_check_file({f})", make_test(f))
    else:
        print(f"  [SKIP] {f} not found")

# ═══════════════════════════════════════════════════
# TEST 4: LSP + Type Checker integration
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 4: LSP Analyzer + Type Checker Integration")
print("=" * 60)

def test_lsp_type_integration():
    from epl.lsp_server import EPLAnalyzer
    analyzer = EPLAnalyzer()
    source = 'Set x To 10\nSet y To 20\nSay x + y\n'
    analyzer.update_document("file:///test.epl", source)
    diagnostics = analyzer.diagnostics.get("file:///test.epl", [])
    # Should be a list of dicts
    assert isinstance(diagnostics, list)
    for d in diagnostics:
        assert "range" in d
        assert "severity" in d
        assert "message" in d

def test_lsp_completions():
    from epl.lsp_server import EPLAnalyzer
    analyzer = EPLAnalyzer()
    source = 'Set x To 10\nSa'
    analyzer.update_document("file:///test2.epl", source)
    items = analyzer.get_completions("file:///test2.epl", 1, 2)
    assert isinstance(items, list)

def test_lsp_hover():
    from epl.lsp_server import EPLAnalyzer
    analyzer = EPLAnalyzer()
    source = 'Set counter To 42\nSay counter\n'
    analyzer.update_document("file:///test3.epl", source)
    result = analyzer.get_hover("file:///test3.epl", 0, 5)
    # result can be None or dict

def test_lsp_symbols():
    from epl.lsp_server import EPLAnalyzer
    analyzer = EPLAnalyzer()
    source = 'Define function greet()\n  Say "Hi"\nEnd\n'
    analyzer.update_document("file:///test4.epl", source)
    symbols = analyzer.symbols.get("file:///test4.epl", [])
    assert isinstance(symbols, list)

test("LSP type checking integration", test_lsp_type_integration)
test("LSP completions", test_lsp_completions)
test("LSP hover", test_lsp_hover)
test("LSP document symbols", test_lsp_symbols)

# ═══════════════════════════════════════════════════
# TEST 5: Package Manager integration
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 5: Package Manager Integration")
print("=" * 60)

def test_pm_load_manifest():
    from epl.package_manager import load_manifest
    # Should handle missing manifest gracefully
    try:
        m = load_manifest("nonexistent_dir")
    except Exception:
        pass  # expected

def test_pm_create_manifest():
    from epl.package_manager import create_manifest
    assert callable(create_manifest)

def test_pm_version_parsing():
    from epl.package_manager import parse_version
    v = parse_version("1.2.3")
    assert v == (1, 2, 3)

def test_pm_toml():
    from epl.package_manager import _dump_toml, _manifest_to_toml
    data = {"name": "test", "version": "1.0.0"}
    toml = _manifest_to_toml(data)
    result = _dump_toml(toml)
    assert "test" in result
    assert "1.0.0" in result

test("Package Manager load_manifest", test_pm_load_manifest)
test("Package Manager create_manifest", test_pm_create_manifest)
test("Package Manager version parsing", test_pm_version_parsing)
test("Package Manager TOML generation", test_pm_toml)

# ═══════════════════════════════════════════════════
# TEST 6: CLI integration
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 6: CLI Command Integration")
print("=" * 60)

def test_cli_check():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "epl.cli", "check", "examples/hello.epl"],
        capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, f"Exit code {r.returncode}: {r.stderr}"
    assert "Type Check Summary" in r.stdout

def test_cli_help():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "epl.cli", "--help"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0
    assert "check" in r.stdout

def test_cli_version():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "epl.cli", "--version"],
        capture_output=True, text=True, timeout=10
    )
    assert r.returncode == 0
    assert "epl" in r.stdout.lower()

test("CLI: epl check examples/hello.epl", test_cli_check)
test("CLI: epl --help includes 'check'", test_cli_help)
test("CLI: epl --version", test_cli_version)

# ═══════════════════════════════════════════════════
# TEST 7: Cross-system integration
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SECTION 7: Cross-System Integration")
print("=" * 60)

def test_type_checker_lsp_roundtrip():
    """TypeChecker warnings → LSP diagnostics → valid format"""
    from epl.type_checker import type_check_file
    checker = type_check_file("examples/advanced.epl")
    lsp_diags = checker.to_lsp_diagnostics()
    for d in lsp_diags:
        assert "range" in d
        assert "start" in d["range"]
        assert "end" in d["range"]
        assert isinstance(d["severity"], int)
        assert d["source"] == "epl-typecheck"

def test_full_pipeline():
    """Full: read file → lex → parse → type check → format report"""
    from epl.type_checker import type_check_file
    checker = type_check_file("examples/advanced.epl")
    report = checker.format_report()
    assert isinstance(report, str)
    assert "Summary" in report or "No type issues" in report

test("TypeChecker → LSP diagnostic roundtrip", test_type_checker_lsp_roundtrip)
test("Full pipeline: file → lex → parse → check → report", test_full_pipeline)

# ═══════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} tests passed, {FAIL} failed")
print("=" * 60)
if FAIL > 0:
    sys.exit(1)
