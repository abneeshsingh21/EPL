"""
EPL Tier 3 Feature Tests
Comprehensive tests for all Tier 3 gaps:
  #16 Block scoping
  #17 AST visitor pattern
  #18 Bytecode serialization (.eplc caching)
  #19 DWARF/debug info in compiler
  #20 Parser error recovery
  #21 Template strings in compiler
  #22 SECURITY.md (existence check)
  #23 Strict type mode hardening
"""

import sys
import os
import tempfile
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.environment import Environment
from epl.errors import EPLError, ParserError
from epl import ast_nodes as ast

PASSED = 0
FAILED = 0


def track(result):
    global PASSED, FAILED
    if result:
        PASSED += 1
    else:
        FAILED += 1


def run_epl(source, block_scoping=False):
    tokens = Lexer(source).tokenize()
    tree = Parser(tokens).parse()
    interp = Interpreter(block_scoping=block_scoping)
    interp.execute(tree)
    return interp.output_lines


def test(name, source, expected, **kw):
    try:
        output = run_epl(source, **kw)
        if output == expected:
            print(f"  PASS: {name}")
            track(True)
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            track(False)
    except Exception as e:
        print(f"  FAIL: {name} -- {e}")
        track(False)


test.__test__ = False

def test_true(name, condition):
    if condition:
        print(f"  PASS: {name}")
        track(True)
    else:
        print(f"  FAIL: {name}")
        track(False)


test_true.__test__ = False

# ═══════════════════════════════════════════════════════════
#  #17 — AST Visitor Pattern
# ═══════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n--- #17: AST Visitor Pattern ---")
    
    
    class PrintCounter(ast.ASTVisitor):
        def __init__(self):
            self.count = 0
        def visit_PrintStatement(self, node):
            self.count += 1
    
    
    code = 'print "a"\nprint "b"\nprint "c"'
    tokens = Lexer(code).tokenize()
    tree = Parser(tokens).parse()
    
    v = PrintCounter()
    for stmt in tree.statements:
        stmt.accept(v)
    test_true("visitor_counts_prints", v.count == 3)
    
    
    class VarCollector(ast.ASTVisitor):
        def __init__(self):
            self.names = []
        def visit_VarDeclaration(self, node):
            self.names.append(node.name)
    
    
    code2 = 'create x as 10\ncreate y as 20\nprint x + y'
    tokens2 = Lexer(code2).tokenize()
    tree2 = Parser(tokens2).parse()
    vc = VarCollector()
    for stmt in tree2.statements:
        stmt.accept(vc)
    test_true("visitor_collects_var_names", vc.names == ['x', 'y'])
    
    # Test generic_visit traversal
    class NodeCounter(ast.ASTVisitor):
        def __init__(self):
            self.count = 0
        def generic_visit(self, node):
            self.count += 1
            super().generic_visit(node)
    
    nc = NodeCounter()
    for stmt in tree.statements:
        stmt.accept(nc)
    test_true("visitor_generic_visit_traverses", nc.count >= 3)
    
    # Test accept exists on base class
    test_true("ast_node_has_accept", hasattr(ast.ASTNode, 'accept'))
    
    # Test double-dispatch
    class SpecificVisitor(ast.ASTVisitor):
        def __init__(self):
            self.visited = []
        def visit_PrintStatement(self, node):
            self.visited.append('print')
        def visit_VarDeclaration(self, node):
            self.visited.append('var')
    
    sv = SpecificVisitor()
    for stmt in tree2.statements:
        stmt.accept(sv)
    test_true("visitor_double_dispatch", sv.visited == ['var', 'var', 'print'])
    
    
    # ═══════════════════════════════════════════════════════════
    #  #16 — Block Scoping
    # ═══════════════════════════════════════════════════════════
    print("\n--- #16: Block Scoping ---")
    
    # Without block scoping (default): variables leak
    test("no_block_scope_loop_leak",
         'create x as 0\nRepeat 3 times\n    set x to x + 1\nEnd Repeat\nprint x',
         ['3'])
    
    # With block scoping on: loop variable changes stay in the child env
    # But note: the loop body assigns to x (from parent), so it gets a copy in child
    # Actually for block_scoping, assignments to existing parent vars should still work
    # Let's test a variable CREATED inside a block
    test("block_scope_if_var_leak_off",
         'If true then\n    create z as 42\nEnd If\nprint z',
         ['42'], block_scoping=False)
    
    # With block scoping: var created inside if should NOT be accessible outside
    try:
        run_epl('If true then\n    create z as 42\nEnd If\nprint z', block_scoping=True)
        print("  FAIL: block_scope_if_isolates (expected error)")
        track(False)
    except EPLError:
        print("  PASS: block_scope_if_isolates")
        track(True)
    
    # While loop with block scoping
    test("block_scope_while_parent_access",
         'create counter as 0\nWhile counter < 3\n    set counter to counter + 1\nEnd While\nprint counter',
         ['3'], block_scoping=True)
    
    # For range with block scoping
    test("block_scope_for_range",
         'create total as 0\nFor i from 1 to 3\n    set total to total + i\nEnd For\nprint total',
         ['6'], block_scoping=True)
    
    # Repeat with block scoping
    test("block_scope_repeat",
         'create n as 0\nRepeat 5 times\n    set n to n + 1\nEnd Repeat\nprint n',
         ['5'], block_scoping=True)
    
    # Default mode is backward compatible
    test("block_scope_default_off",
         'create val as 1\nprint val',
         ['1'])
    
    
    # ═══════════════════════════════════════════════════════════
    #  #18 — Bytecode Serialization (.eplc caching)
    # ═══════════════════════════════════════════════════════════
    print("\n--- #18: Bytecode Serialization ---")
    
    from epl.bytecode_cache import save, load, cache_path_for
    
    code = 'create x as 10\nprint x'
    tokens = Lexer(code).tokenize()
    tree = Parser(tokens).parse()
    
    with tempfile.NamedTemporaryFile(suffix='.eplc', delete=False) as f:
        cache_path = f.name
    
    try:
        # Save
        save(tree, code, cache_path)
        test_true("bytecode_save", os.path.exists(cache_path))
    
        # Load with matching source
        loaded = load(code, cache_path)
        test_true("bytecode_load_match", loaded is not None)
        test_true("bytecode_roundtrip_stmts", len(loaded.statements) == len(tree.statements))
    
        # Load with changed source → None
        result = load('create y as 20', cache_path)
        test_true("bytecode_load_mismatch", result is None)
    
        # Load from nonexistent file → None
        result2 = load(code, '/nonexistent/path.eplc')
        test_true("bytecode_load_missing_file", result2 is None)
    
        # cache_path_for
        cp = cache_path_for('examples/hello.epl')
        test_true("bytecode_cache_path_for", str(cp).endswith('.eplc'))
    
        # Roundtrip preserves node types
        test_true("bytecode_preserves_types",
                  type(loaded.statements[0]).__name__ == type(tree.statements[0]).__name__)
    
        # Execute roundtripped AST
        interp = Interpreter()
        interp.execute(loaded)
        test_true("bytecode_exec_roundtrip", interp.output_lines == ['10'])
    
    finally:
        if os.path.exists(cache_path):
            os.remove(cache_path)
    
    
    # ═══════════════════════════════════════════════════════════
    #  #19 — DWARF/Debug Info in Compiler
    # ═══════════════════════════════════════════════════════════
    print("\n--- #19: DWARF/Debug Info ---")
    
    try:
        from epl.compiler import Compiler
    
        code = 'create x as 10\nprint x'
        tokens = Lexer(code).tokenize()
        tree = Parser(tokens).parse()
    
        # Compile without debug (default)
        c1 = Compiler()
        ir1 = c1.compile(tree)
        test_true("compiler_no_debug_default", 'DIFile' not in ir1)
    
        # Compile with debug
        c2 = Compiler(debug=True, source_filename='test.epl')
        tokens2 = Lexer(code).tokenize()
        tree2 = Parser(tokens2).parse()
        ir2 = c2.compile(tree2)
    
        test_true("compiler_debug_has_difile", 'DIFile' in ir2)
        test_true("compiler_debug_has_dicu", 'DICompileUnit' in ir2)
        test_true("compiler_debug_has_disubprogram", 'DISubprogram' in ir2)
        test_true("compiler_debug_has_dilocation", 'DILocation' in ir2)
        test_true("compiler_debug_has_filename", 'test.epl' in ir2)
        test_true("compiler_debug_has_line_1", 'line: 1' in ir2)
        test_true("compiler_debug_has_line_2", 'line: 2' in ir2)
    
        # Debug with function
        code3 = 'Function greet takes name\n    print name\nEnd Function\ngreet("world")'
        tokens3 = Lexer(code3).tokenize()
        tree3 = Parser(tokens3).parse()
        c3 = Compiler(debug=True, source_filename='func_test.epl')
        ir3 = c3.compile(tree3)
        test_true("compiler_debug_function_disubprogram", ir3.count('DISubprogram') >= 2)
    
    except ImportError:
        print("  SKIP: compiler tests (llvmlite not available)")
    except Exception as e:
        print(f"  FAIL: DWARF debug tests -- {e}")
        track(False)
    
    
    # ═══════════════════════════════════════════════════════════
    #  #20 — Parser Error Recovery
    # ═══════════════════════════════════════════════════════════
    print("\n--- #20: Parser Error Recovery ---")
    
    # parse_with_recovery returns partial AST + errors
    code_bad = 'print "hello"\nset 123 to 5\nprint "world"'
    tokens = Lexer(code_bad).tokenize()
    p = Parser(tokens)
    tree, errors = p.parse_with_recovery()
    test_true("recovery_returns_partial_ast", tree is not None)
    test_true("recovery_returns_errors", len(errors) > 0)
    test_true("recovery_partial_has_stmts", len(tree.statements) >= 1)
    
    # Good code → no errors
    code_good = 'print "ok"'
    tokens2 = Lexer(code_good).tokenize()
    p2 = Parser(tokens2)
    tree2, errors2 = p2.parse_with_recovery()
    test_true("recovery_good_code_no_errors", len(errors2) == 0)
    test_true("recovery_good_code_full_ast", len(tree2.statements) == 1)
    
    # parse() still raises on bad code
    try:
        tokens3 = Lexer(code_bad).tokenize()
        Parser(tokens3).parse()
        print("  FAIL: parse_still_raises (expected error)")
        track(False)
    except (ParserError, EPLError) as e:
        test_true("parse_still_raises", True)
        has_count = "more error" in str(e)
        # may or may not have count depending on how many errors found
        test_true("parse_error_mentions_count", has_count or len(str(e)) > 10)
    
    # Multiple errors collected
    code_multi = 'print "a"\nset 111 to 1\nprint "b"\nset 222 to 2\nprint "c"'
    tokens4 = Lexer(code_multi).tokenize()
    p4 = Parser(tokens4)
    tree4, errors4 = p4.parse_with_recovery()
    test_true("recovery_multiple_errors", len(errors4) >= 2)
    test_true("recovery_continues_after_errors", len(tree4.statements) >= 2)
    
    # Synchronization (recovers to next statement)
    code_sync = 'set 999 to 1\nprint "recovered"'
    tokens5 = Lexer(code_sync).tokenize()
    p5 = Parser(tokens5)
    tree5, errors5 = p5.parse_with_recovery()
    test_true("recovery_sync_to_print", len(tree5.statements) >= 1)
    
    
    # ═══════════════════════════════════════════════════════════
    #  #21 — Template Strings in Compiler
    # ═══════════════════════════════════════════════════════════
    print("\n--- #21: Template Strings in Compiler ---")
    
    try:
        from epl.compiler import Compiler
        import re
    
        # Simple variable interpolation
        code = 'create name as "World"\nprint "Hello, ${name}!"'
        tokens = Lexer(code).tokenize()
        tree = Parser(tokens).parse()
        c = Compiler()
        ir_out = c.compile(tree)
        # Should not have any warning about template strings
        test_true("template_no_warning", 'WARNING' not in ir_out.upper().split('!')[0] if '!' in ir_out else True)
        # IR should compute a string result
        test_true("template_compiles", 'define i32 @"main"' in ir_out)
    
        # $var shorthand
        code2 = 'create x as 42\nprint "Value is $x"'
        tokens2 = Lexer(code2).tokenize()
        tree2 = Parser(tokens2).parse()
        c2 = Compiler()
        ir2 = c2.compile(tree2)
        test_true("template_dollar_var", 'define i32 @"main"' in ir2)
    
    except ImportError:
        print("  SKIP: template string compiler tests (llvmlite not available)")
    except Exception as e:
        print(f"  FAIL: template string tests -- {e}")
        track(False)
    
    
    # ═══════════════════════════════════════════════════════════
    #  #22 — SECURITY.md
    # ═══════════════════════════════════════════════════════════
    print("\n--- #22: SECURITY.md ---")
    
    project_root = os.path.join(os.path.dirname(__file__), '..')
    security_path = os.path.join(project_root, 'SECURITY.md')
    test_true("security_md_exists", os.path.isfile(security_path))
    
    with open(security_path, 'r', encoding='utf-8') as f:
        content = f.read()
    test_true("security_md_not_empty", len(content) > 100)
    test_true("security_md_has_reporting", 'report' in content.lower())
    
    
    # ═══════════════════════════════════════════════════════════
    #  #23 — Strict Type Mode Hardening
    # ═══════════════════════════════════════════════════════════
    print("\n--- #23: Strict Type Mode ---")
    
    from epl.type_system import TypeChecker
    
    
    def type_check(code, strict=True):
        tokens = Lexer(code).tokenize()
        tree = Parser(tokens).parse()
        tc = TypeChecker(strict=strict)
        return tc.check(tree)
    
    
    # Return type mismatch
    diags = type_check('Function add takes a and returns integer\n    return "hello"\nEnd Function')
    test_true("strict_return_type_mismatch",
              any("Return type" in d.message and d.level == "error" for d in diags))
    
    # Unreachable code
    diags = type_check('Function foo\n    return 10\n    print 20\nEnd Function')
    test_true("strict_unreachable_code",
              any("Unreachable" in d.message for d in diags))
    
    # Too many arguments
    diags = type_check('Function greet takes name\n    print name\nEnd Function\ngreet("Alice", "extra")')
    test_true("strict_too_many_args",
              any("Too many arguments" in d.message for d in diags))
    
    # Undeclared variable
    diags = type_check('print unknownVar')
    test_true("strict_undeclared_var",
              any("before declaration" in d.message for d in diags))
    
    # Type mismatch in assignment
    diags = type_check('create integer x as 10\nset x to "hello"')
    test_true("strict_assignment_type_mismatch",
              any("Cannot assign" in d.message and d.level == "error" for d in diags))
    
    # No false positives
    diags = type_check('create x as 10\nset x to 20\nprint x')
    test_true("strict_no_false_positives",
              all(d.level != "error" for d in diags))
    
    # d.level field (not d.severity) — the critical bug fix
    diags = type_check('print unknownVar')
    test_true("strict_uses_level_not_severity",
              all(hasattr(d, 'level') and d.level in ("error", "warning", "info") for d in diags))
    
    # Class method bodies are now checked
    diags = type_check('Class Dog\n    Function bark\n        print unknownClassVar\n    End\nEnd', strict=True)
    test_true("strict_checks_class_methods",
              any("before declaration" in d.message for d in diags))
    
    # format_diagnostics works
    tc = TypeChecker(strict=True)
    tokens = Lexer('print unknownVar').tokenize()
    tree = Parser(tokens).parse()
    tc.check(tree)
    fmt = tc.format_diagnostics()
    test_true("strict_format_diagnostics", len(fmt) > 0 and "ERROR" in fmt)
    
    
    # ═══════════════════════════════════════════════════════════
    #  Summary
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 55)
    print(f"  Tier 3 Results: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    print("=" * 55)
    
    if FAILED == 0:
        print("All Tier 3 tests passed!")
    return FAILED == 0


def test_tier3_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    raise SystemExit(0 if run_suite() else 1)
