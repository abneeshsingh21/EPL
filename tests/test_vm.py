"""Tests for VM bytecode compiler and execution (performance & correctness)."""
import unittest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.vm import BytecodeCompiler, VM, Op, VMClosure


def run_vm(code):
    """Helper: lex, parse, compile, and execute EPL code in the VM."""
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    compiler = BytecodeCompiler()
    compiled = compiler.compile(ast)
    vm = VM()
    vm.execute(compiled)
    return vm


class TestVMBasicOps(unittest.TestCase):
    """Test basic VM operations."""

    def test_arithmetic(self):
        vm = run_vm("Print 2 + 3")
        self.assertEqual(vm.output_lines, ["5"])

    def test_string_concat(self):
        vm = run_vm('Print "hello" + " world"')
        self.assertEqual(vm.output_lines, ["hello world"])

    def test_variables(self):
        vm = run_vm('x = 10\nPrint x')
        self.assertEqual(vm.output_lines, ["10"])

    def test_comparison(self):
        vm = run_vm('If 5 > 3 Then\n    Print "yes"\nEnd')
        self.assertEqual(vm.output_lines, ["yes"])

    def test_list_creation(self):
        vm = run_vm('items = [1, 2, 3]\nPrint items')
        self.assertIn("1", vm.output_lines[0])

    def test_if_else(self):
        vm = run_vm('If 5 > 3 Then\n    Print "yes"\nOtherwise\n    Print "no"\nEnd')
        self.assertEqual(vm.output_lines, ["yes"])

    def test_while_loop(self):
        vm = run_vm('i = 0\nWhile i < 3\n    Increase i by 1\nEnd\nPrint i')
        self.assertEqual(vm.output_lines, ["3"])

    def test_for_each_loop(self):
        vm = run_vm('items = [10, 20, 30]\nFor each item in items\n    Print item\nEnd')
        self.assertEqual(vm.output_lines, ["10", "20", "30"])

    def test_function_def_and_call(self):
        vm = run_vm('Function add takes a, b\n    Return a + b\nEnd\nPrint add(3, 4)')
        self.assertEqual(vm.output_lines, ["7"])

    def test_string_method(self):
        vm = run_vm('name = "hello"\nPrint upper(name)')
        self.assertEqual(vm.output_lines, ["HELLO"])

    def test_list_method_append(self):
        vm = run_vm('items = [1, 2, 3]\nPrint length(items)')
        self.assertEqual(vm.output_lines, ["3"])

    def test_class_basic(self):
        vm = run_vm('Class Dog\n    name = "Rex"\nEnd\nPrint "ok"')
        self.assertEqual(vm.output_lines, ["ok"])

    def test_try_catch(self):
        vm = run_vm('Try\n    Throw "oops"\nCatch e\n    Print "caught"\nEnd')
        self.assertEqual(vm.output_lines, ["caught"])

    def test_repeat_loop(self):
        vm = run_vm('Repeat 3 times\n    Print "hi"\nEnd')
        self.assertEqual(vm.output_lines, ["hi", "hi", "hi"])


class TestVMConstantFolding(unittest.TestCase):
    """Test that constant folding works correctly."""

    def test_numeric_fold(self):
        """2 + 3 should fold to 5 at compile time."""
        code = "Print 2 + 3"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn(5, compiled['constants'])
        vm = VM()
        vm.execute(compiled)
        self.assertEqual(vm.output_lines, ["5"])

    def test_string_fold(self):
        """String concat of literals should fold."""
        code = 'Print "hello" + " world"'
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn("hello world", compiled['constants'])

    def test_multiply_fold(self):
        vm = run_vm("Print 6 * 7")
        self.assertEqual(vm.output_lines, ["42"])

    def test_no_fold_with_variables(self):
        """Variables should not be folded."""
        vm = run_vm("x = 5\nPrint x + 3")
        self.assertEqual(vm.output_lines, ["8"])


class TestVMPeepholeOptimizer(unittest.TestCase):
    """Test peephole optimizations produce correct results."""

    def test_complex_program_after_peephole(self):
        """Ensure complex programs still work after peephole optimization."""
        code = 'total = 0\ni = 0\nWhile i < 10\n    Set total to total + i\n    Increase i by 1\nEnd\nPrint total'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ["45"])

    def test_jump_reindexing(self):
        """Verify jumps are reindexed correctly after instruction removal."""
        code = 'Set x to 10\nIf x > 5 Then\n    Display "big"\nOtherwise\n    Display "small"\nEnd'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ["big"])

    def test_nested_if_after_peephole(self):
        """Nested ifs with jump targets must survive peephole."""
        code = 'Set x to 3\nIf x > 1 Then\n    If x < 5 Then\n        Display "mid"\n    End\nEnd'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ["mid"])


class TestVMComparisonFolding(unittest.TestCase):
    """Test comparison constant folding."""

    def test_fold_gt_true(self):
        code = "Print 5 > 3"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn(True, compiled['constants'])

    def test_fold_eq(self):
        vm = run_vm("Print 5 == 5")
        self.assertEqual(vm.output_lines, ["true"])

    def test_fold_lt_false(self):
        vm = run_vm("Print 10 < 3")
        self.assertEqual(vm.output_lines, ["false"])


class TestVMDeadCodeElimination(unittest.TestCase):
    """Test dead code elimination pass."""

    def test_code_after_return(self):
        """Code after Return in a function should be eliminated."""
        code = 'Function F\n    Return 42\n    Display "dead"\nEnd\nDisplay F()'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ["42"])

    def test_conditional_return_both_paths(self):
        """Both conditional paths should work after DCE."""
        code = 'Function G takes x\n    If x > 0 Then\n        Return "pos"\n    End\n    Return "neg"\nEnd\nDisplay G(5)\nDisplay G(-1)'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ["pos", "neg"])


class TestVMBuiltinDictDispatch(unittest.TestCase):
    """Test O(1) dict-based builtin dispatch."""

    def test_builtin_sqrt(self):
        vm = run_vm("Display sqrt(16)")
        self.assertEqual(vm.output_lines, ["4"])

    def test_builtin_abs(self):
        vm = run_vm("Display abs(-7)")
        self.assertEqual(vm.output_lines, ["7"])

    def test_builtin_round(self):
        vm = run_vm("Display round(3.7)")
        self.assertEqual(vm.output_lines, ["4"])

    def test_builtin_range(self):
        vm = run_vm("Display range(4)")
        self.assertEqual(vm.output_lines, ["[0, 1, 2, 3]"])

    def test_builtin_sum(self):
        vm = run_vm("Display sum([1, 2, 3])")
        self.assertEqual(vm.output_lines, ["6"])

    def test_builtin_reverse_list(self):
        vm = run_vm("Display reverse([1, 2, 3])")
        self.assertEqual(vm.output_lines, ["[3, 2, 1]"])

    def test_builtin_upper(self):
        vm = run_vm('Display upper("hello")')
        self.assertEqual(vm.output_lines, ["HELLO"])

    def test_builtin_type_of(self):
        vm = run_vm('Display type_of(42)')
        self.assertEqual(vm.output_lines, ["Integer"])


class TestVMDispatch(unittest.TestCase):
    """Test that list-indexed dispatch works for all opcodes."""

    def test_dispatch_table_complete(self):
        """Every Op that could be generated should have a handler."""
        vm = VM()
        dispatch = vm._dispatch
        basic_ops = [Op.LOAD_CONST, Op.LOAD_VAR, Op.STORE_VAR, Op.ADD, Op.SUB,
                     Op.MUL, Op.DIV, Op.JUMP, Op.CALL, Op.RETURN, Op.PRINT,
                     Op.BUILD_LIST, Op.BUILD_DICT, Op.BUILD_CLASS, Op.MAKE_CLOSURE,
                     Op.LOAD_FREE, Op.STORE_FREE, Op.ADD_ASSIGN, Op.UNPACK_SEQ]
        for op in basic_ops:
            self.assertIsNotNone(dispatch[op.value],
                                 f"Missing handler for {op.name}")


class TestVMMethodDispatch(unittest.TestCase):
    """Test optimized method dispatch on built-in types."""

    def test_str_length(self):
        vm = run_vm('name = "hello"\nPrint length(name)')
        self.assertEqual(vm.output_lines, ["5"])

    def test_str_upper(self):
        vm = run_vm('name = "abc"\nPrint upper(name)')
        self.assertEqual(vm.output_lines, ["ABC"])

    def test_list_length(self):
        vm = run_vm('items = [1, 2, 3]\nPrint length(items)')
        self.assertEqual(vm.output_lines, ["3"])

    def test_map_keys(self):
        vm = run_vm('p = Map with a = 1 and b = 2\nPrint keys(p)')
        out = vm.output_lines[0]
        self.assertIn("a", out)
        self.assertIn("b", out)

    def test_num_abs(self):
        vm = run_vm('Print abs(-5)')
        self.assertEqual(vm.output_lines, ["5"])


class TestVMPerformance(unittest.TestCase):
    """Performance sanity checks — ensuring the VM can handle moderate workloads."""

    def test_loop_performance(self):
        """10000 iterations should complete quickly."""
        code = 'total = 0\ni = 0\nWhile i < 10000\n    Set total to total + i\n    Increase i by 1\nEnd\nPrint total'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ["49995000"])
        self.assertLess(elapsed, 10.0, f"Loop took {elapsed:.2f}s — too slow")

    def test_function_call_performance(self):
        """Many function calls should execute reasonably fast."""
        code = 'Function add_one takes x\n    Return x + 1\nEnd\nresult = 0\ni = 0\nWhile i < 1000\n    result = add_one(result)\n    Increase i by 1\nEnd\nPrint result'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ["1000"])
        self.assertLess(elapsed, 10.0, f"Function calls took {elapsed:.2f}s — too slow")

    def test_string_method_performance(self):
        """String method calls in loop should be fast."""
        code = 's = "hello world"\ni = 0\nWhile i < 1000\n    x = upper(s)\n    Increase i by 1\nEnd\nPrint "done"'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ["done"])
        self.assertLess(elapsed, 10.0)


if __name__ == '__main__':
    unittest.main()
