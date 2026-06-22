"""Tests for VM bytecode compiler and execution (performance & correctness)."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.vm import VM, BytecodeCompiler, Op


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
        vm = run_vm('Print 2 + 3')
        self.assertEqual(vm.output_lines, ['5'])

    def test_string_concat(self):
        vm = run_vm('Print "hello" + " world"')
        self.assertEqual(vm.output_lines, ['hello world'])

    def test_variables(self):
        vm = run_vm('x = 10\nPrint x')
        self.assertEqual(vm.output_lines, ['10'])

    def test_comparison(self):
        vm = run_vm('If 5 > 3 Then\n    Print "yes"\nEnd')
        self.assertEqual(vm.output_lines, ['yes'])

    def test_list_creation(self):
        vm = run_vm('items = [1, 2, 3]\nPrint items')
        self.assertIn('1', vm.output_lines[0])

    def test_if_else(self):
        vm = run_vm('If 5 > 3 Then\n    Print "yes"\nOtherwise\n    Print "no"\nEnd')
        self.assertEqual(vm.output_lines, ['yes'])

    def test_while_loop(self):
        vm = run_vm('i = 0\nWhile i < 3\n    Increase i by 1\nEnd\nPrint i')
        self.assertEqual(vm.output_lines, ['3'])

    def test_for_each_loop(self):
        vm = run_vm('items = [10, 20, 30]\nFor each item in items\n    Print item\nEnd')
        self.assertEqual(vm.output_lines, ['10', '20', '30'])

    def test_function_def_and_call(self):
        vm = run_vm('Function add takes a, b\n    Return a + b\nEnd\nPrint add(3, 4)')
        self.assertEqual(vm.output_lines, ['7'])

    def test_string_method(self):
        vm = run_vm('name = "hello"\nPrint upper(name)')
        self.assertEqual(vm.output_lines, ['HELLO'])

    def test_list_method_append(self):
        vm = run_vm('items = [1, 2, 3]\nPrint length(items)')
        self.assertEqual(vm.output_lines, ['3'])

    def test_class_basic(self):
        vm = run_vm('Class Dog\n    name = "Rex"\nEnd\nPrint "ok"')
        self.assertEqual(vm.output_lines, ['ok'])

    def test_try_catch(self):
        vm = run_vm('Try\n    Throw "oops"\nCatch e\n    Print "caught"\nEnd')
        self.assertEqual(vm.output_lines, ['caught'])

    def test_repeat_loop(self):
        vm = run_vm('Repeat 3 times\n    Print "hi"\nEnd')
        self.assertEqual(vm.output_lines, ['hi', 'hi', 'hi'])


class TestVMImplicitThis(unittest.TestCase):
    """Bare instance-field access inside a method must resolve to `this.field`
    (matching the interpreter), not a global. Regression: the VM previously
    compiled bare field names to LOAD_GLOBAL, yielding `none`.
    """

    def test_read_instance_field_in_method(self):
        vm = run_vm(
            'Class Animal\n'
            '    name = "Unknown"\n'
            '    sound = "..."\n'
            '    Function speak\n'
            '        Print name + " says " + sound\n'
            '    End\n'
            'End\n'
            'dog = new Animal\n'
            'dog.name = "Rex"\n'
            'dog.sound = "Woof!"\n'
            'dog.speak()'
        )
        self.assertEqual(vm.output_lines, ['Rex says Woof!'])

    def test_write_instance_field_bare_assignment(self):
        vm = run_vm(
            'Class Box\n'
            '    amount = 0\n'
            '    Function bump\n'
            '        amount = amount + 1\n'
            '    End\n'
            'End\n'
            'b = new Box\n'
            'b.bump()\n'
            'b.bump()\n'
            'Print b.amount'
        )
        self.assertEqual(vm.output_lines, ['2'])

    def test_write_instance_field_set_keyword(self):
        vm = run_vm(
            'Class Box\n'
            '    amount = 0\n'
            '    Function addv takes v\n'
            '        Set amount to amount + v\n'
            '    End\n'
            'End\n'
            'b = new Box\n'
            'b.addv(10)\n'
            'Print b.amount'
        )
        self.assertEqual(vm.output_lines, ['10'])

    def test_param_shadows_field(self):
        # A method parameter named like a field must win over the field.
        vm = run_vm(
            'Class Box\n'
            '    amount = 99\n'
            '    Function echo takes amount\n'
            '        Print amount\n'
            '    End\n'
            'End\n'
            'b = new Box\n'
            'b.echo(7)'
        )
        self.assertEqual(vm.output_lines, ['7'])


class TestVMMethodsAndFormatting(unittest.TestCase):
    """Parity with the interpreter for built-in methods and concatenation
    formatting. Regressions found via the interpreter-vs-VM parity harness.
    """

    def test_property_style_string_methods(self):
        vm = run_vm(
            'name = "Hello"\n'
            'Print name.uppercase\n'
            'Print name.lowercase\n'
            'Print name.length\n'
            'Print "  hi  ".trim'
        )
        self.assertEqual(vm.output_lines, ['HELLO', 'hello', '5', 'hi'])

    def test_method_call_string_aliases(self):
        vm = run_vm('name = "Hi"\nPrint name.uppercase()\nPrint name.lowercase()')
        self.assertEqual(vm.output_lines, ['HI', 'hi'])

    def test_list_sort_reverse_mutate_in_place(self):
        vm = run_vm(
            'nums = [3, 1, 2]\n'
            'nums.sort()\n'
            'Print nums\n'
            'nums.reverse()\n'
            'Print nums'
        )
        self.assertEqual(vm.output_lines, ['[1, 2, 3]', '[3, 2, 1]'])

    def test_concat_formats_bool_lowercase(self):
        vm = run_vm('Print "valid: " + (1 == 1)')
        self.assertEqual(vm.output_lines, ['valid: true'])

    def test_concat_formats_list_without_quotes(self):
        vm = run_vm('words = ["a", "b", "c"]\nPrint "words: " + words')
        self.assertEqual(vm.output_lines, ['words: [a, b, c]'])

    def test_dict_entries_alias(self):
        vm = run_vm('m = Map with a = 1\nPrint m.entries()')
        self.assertEqual(vm.output_lines, ['[[a, 1]]'])

    def test_string_find_alias(self):
        vm = run_vm('s = "the fox"\nPrint s.find("fox")')
        self.assertEqual(vm.output_lines, ['4'])


class TestVMStringInterpolation(unittest.TestCase):
    """$name / ${expr} interpolation must match the interpreter & compiler.

    Regression guard: the VM previously keyed off bare ``{expr}`` and did a
    naive global load, so EPL's documented ``$name``/``${expr}`` syntax printed
    literally under the default ``epl run`` (VM) path.
    """

    def test_simple_variable(self):
        vm = run_vm('name = "World"\nPrint "Hello, $name!"')
        self.assertEqual(vm.output_lines, ['Hello, World!'])

    def test_expression_braces(self):
        vm = run_vm('Print "Sum: ${1 + 2}"')
        self.assertEqual(vm.output_lines, ['Sum: 3'])

    def test_mixed_variable_and_expression(self):
        vm = run_vm('x = 10\ny = 5\nPrint "$x and ${x * y}"')
        self.assertEqual(vm.output_lines, ['10 and 50'])

    def test_local_variable_in_function(self):
        vm = run_vm(
            'Function greet takes who\n'
            '    Print "Hi $who"\n'
            'End\n'
            'greet("Sam")'
        )
        self.assertEqual(vm.output_lines, ['Hi Sam'])

    def test_dollar_followed_by_digit_is_literal(self):
        # "$5" is not a valid template (digits can't start an identifier).
        vm = run_vm('Print "cost is $5 today"')
        self.assertEqual(vm.output_lines, ['cost is $5 today'])

    def test_no_interpolation_plain_string(self):
        vm = run_vm('Print "just a plain string"')
        self.assertEqual(vm.output_lines, ['just a plain string'])

    def test_interpolated_value_uses_epl_formatting(self):
        # Booleans/floats must render with EPL semantics (true, whole-float as
        # int) — not Python repr (True, 4.0) — matching the interpreter.
        vm = run_vm('flag = true\nratio = 4.0\nPrint "$flag and $ratio"')
        self.assertEqual(vm.output_lines, ['true and 4'])

    def test_single_dynamic_part_is_stringified(self):
        # A lone "$flag" must still become the string "true", not the bool.
        vm = run_vm('flag = true\nPrint "$flag"')
        self.assertEqual(vm.output_lines, ['true'])


class TestVMConstantFolding(unittest.TestCase):
    """Test that constant folding works correctly."""

    def test_numeric_fold(self):
        """2 + 3 should fold to 5 at compile time."""
        code = 'Print 2 + 3'
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn(5, compiled['constants'])
        vm = VM()
        vm.execute(compiled)
        self.assertEqual(vm.output_lines, ['5'])

    def test_string_fold(self):
        """String concat of literals should fold."""
        code = 'Print "hello" + " world"'
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn('hello world', compiled['constants'])

    def test_multiply_fold(self):
        vm = run_vm('Print 6 * 7')
        self.assertEqual(vm.output_lines, ['42'])

    def test_no_fold_with_variables(self):
        """Variables should not be folded."""
        vm = run_vm('x = 5\nPrint x + 3')
        self.assertEqual(vm.output_lines, ['8'])


class TestVMPeepholeOptimizer(unittest.TestCase):
    """Test peephole optimizations produce correct results."""

    def test_complex_program_after_peephole(self):
        """Ensure complex programs still work after peephole optimization."""
        code = 'total = 0\ni = 0\nWhile i < 10\n    Set total to total + i\n    Increase i by 1\nEnd\nPrint total'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['45'])

    def test_jump_reindexing(self):
        """Verify jumps are reindexed correctly after instruction removal."""
        code = 'Set x to 10\nIf x > 5 Then\n    Display "big"\nOtherwise\n    Display "small"\nEnd'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['big'])

    def test_nested_if_after_peephole(self):
        """Nested ifs with jump targets must survive peephole."""
        code = 'Set x to 3\nIf x > 1 Then\n    If x < 5 Then\n        Display "mid"\n    End\nEnd'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['mid'])


class TestVMComparisonFolding(unittest.TestCase):
    """Test comparison constant folding."""

    def test_fold_gt_true(self):
        code = 'Print 5 > 3'
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()
        compiler = BytecodeCompiler()
        compiled = compiler.compile(ast)
        self.assertIn(True, compiled['constants'])

    def test_fold_eq(self):
        vm = run_vm('Print 5 == 5')
        self.assertEqual(vm.output_lines, ['true'])

    def test_fold_lt_false(self):
        vm = run_vm('Print 10 < 3')
        self.assertEqual(vm.output_lines, ['false'])


class TestVMDeadCodeElimination(unittest.TestCase):
    """Test dead code elimination pass."""

    def test_code_after_return(self):
        """Code after Return in a function should be eliminated."""
        code = 'Function F\n    Return 42\n    Display "dead"\nEnd\nDisplay F()'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['42'])

    def test_conditional_return_both_paths(self):
        """Both conditional paths should work after DCE."""
        code = 'Function G takes x\n    If x > 0 Then\n        Return "pos"\n    End\n    Return "neg"\nEnd\nDisplay G(5)\nDisplay G(-1)'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['pos', 'neg'])


class TestVMBuiltinDictDispatch(unittest.TestCase):
    """Test O(1) dict-based builtin dispatch."""

    def test_builtin_sqrt(self):
        vm = run_vm('Display sqrt(16)')
        self.assertEqual(vm.output_lines, ['4'])

    def test_builtin_abs(self):
        vm = run_vm('Display abs(-7)')
        self.assertEqual(vm.output_lines, ['7'])

    def test_builtin_round(self):
        vm = run_vm('Display round(3.7)')
        self.assertEqual(vm.output_lines, ['4'])

    def test_builtin_range(self):
        vm = run_vm('Display range(4)')
        self.assertEqual(vm.output_lines, ['[0, 1, 2, 3]'])

    def test_builtin_sum(self):
        vm = run_vm('Display sum([1, 2, 3])')
        self.assertEqual(vm.output_lines, ['6'])

    def test_builtin_reverse_list(self):
        vm = run_vm('Display reverse([1, 2, 3])')
        self.assertEqual(vm.output_lines, ['[3, 2, 1]'])

    def test_builtin_upper(self):
        vm = run_vm('Display upper("hello")')
        self.assertEqual(vm.output_lines, ['HELLO'])

    def test_builtin_type_of(self):
        vm = run_vm('Display type_of(42)')
        self.assertEqual(vm.output_lines, ['integer'])


class TestVMDispatch(unittest.TestCase):
    """Test that list-indexed dispatch works for all opcodes."""

    def test_dispatch_table_complete(self):
        """Every Op that could be generated should have a handler."""
        vm = VM()
        dispatch = vm._dispatch
        basic_ops = [
            Op.LOAD_CONST,
            Op.LOAD_VAR,
            Op.STORE_VAR,
            Op.ADD,
            Op.SUB,
            Op.MUL,
            Op.DIV,
            Op.JUMP,
            Op.CALL,
            Op.RETURN,
            Op.PRINT,
            Op.BUILD_LIST,
            Op.BUILD_DICT,
            Op.BUILD_CLASS,
            Op.MAKE_CLOSURE,
            Op.LOAD_FREE,
            Op.STORE_FREE,
            Op.ADD_ASSIGN,
            Op.UNPACK_SEQ,
        ]
        for op in basic_ops:
            self.assertIsNotNone(dispatch[op.value], f'Missing handler for {op.name}')


class TestVMMethodDispatch(unittest.TestCase):
    """Test optimized method dispatch on built-in types."""

    def test_str_length(self):
        vm = run_vm('name = "hello"\nPrint length(name)')
        self.assertEqual(vm.output_lines, ['5'])

    def test_str_upper(self):
        vm = run_vm('name = "abc"\nPrint upper(name)')
        self.assertEqual(vm.output_lines, ['ABC'])

    def test_list_length(self):
        vm = run_vm('items = [1, 2, 3]\nPrint length(items)')
        self.assertEqual(vm.output_lines, ['3'])

    def test_map_keys(self):
        vm = run_vm('p = Map with a = 1 and b = 2\nPrint keys(p)')
        out = vm.output_lines[0]
        self.assertIn('a', out)
        self.assertIn('b', out)

    def test_num_abs(self):
        vm = run_vm('Print abs(-5)')
        self.assertEqual(vm.output_lines, ['5'])


class TestVMPerformance(unittest.TestCase):
    """Performance sanity checks — ensuring the VM can handle moderate workloads."""

    def test_loop_performance(self):
        """10000 iterations should complete quickly."""
        code = 'total = 0\ni = 0\nWhile i < 10000\n    Set total to total + i\n    Increase i by 1\nEnd\nPrint total'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ['49995000'])
        self.assertLess(elapsed, 10.0, f'Loop took {elapsed:.2f}s — too slow')

    def test_function_call_performance(self):
        """Many function calls should execute reasonably fast."""
        code = 'Function add_one takes x\n    Return x + 1\nEnd\nresult = 0\ni = 0\nWhile i < 1000\n    result = add_one(result)\n    Increase i by 1\nEnd\nPrint result'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ['1000'])
        self.assertLess(elapsed, 10.0, f'Function calls took {elapsed:.2f}s — too slow')

    def test_string_method_performance(self):
        """String method calls in loop should be fast."""
        code = 's = "hello world"\ni = 0\nWhile i < 1000\n    x = upper(s)\n    Increase i by 1\nEnd\nPrint "done"'
        start = time.perf_counter()
        vm = run_vm(code)
        elapsed = time.perf_counter() - start
        self.assertEqual(vm.output_lines, ['done'])
        self.assertLess(elapsed, 10.0)


if __name__ == '__main__':
    unittest.main()
