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

    def test_to_text_uses_epl_formatting(self):
        # to_text must format lists/bools with EPL semantics, not Python repr.
        vm = run_vm('Print to_text([1, 2, 3])\nPrint to_text(1 == 1)')
        self.assertEqual(vm.output_lines, ['[1, 2, 3]', 'true'])

    def test_to_string_alias(self):
        vm = run_vm('Print to_string(42)\nPrint to_string([1, 2])')
        self.assertEqual(vm.output_lines, ['42', '[1, 2]'])

    def test_random_integer_alias_in_range(self):
        vm = run_vm('r = random_integer(1, 6)\nPrint r >= 1 and r <= 6')
        self.assertEqual(vm.output_lines, ['true'])

    def test_random_two_args_is_int_in_range(self):
        vm = run_vm('r = random(1, 100)\nPrint r >= 1 and r <= 100')
        self.assertEqual(vm.output_lines, ['true'])

    def test_slice_with_step(self):
        vm = run_vm(
            'n = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]\n'
            'Print n[0:10:2]\n'
            'Print n[1:10:3]'
        )
        self.assertEqual(vm.output_lines, ['[10, 30, 50, 70, 90]', '[20, 50, 80]'])

    def test_default_parameter_value(self):
        vm = run_vm(
            'Function greet takes name = "World"\n'
            '    Print "Hello " + name\n'
            'End\n'
            'greet()\n'
            'greet("Sam")'
        )
        self.assertEqual(vm.output_lines, ['Hello World', 'Hello Sam'])

    def test_whole_float_keeps_float_form(self):
        vm = run_vm('Print sqrt(16)\nPrint 3.0 + 1.0')
        self.assertEqual(vm.output_lines, ['4.0', '4.0'])

    def test_division_whole_result_is_int(self):
        vm = run_vm('Print 8 / 2\nPrint 7 / 2')
        self.assertEqual(vm.output_lines, ['4', '3.5'])

    def test_none_displays_as_nothing(self):
        vm = run_vm('Function f\n    Return\nEnd\nPrint f()')
        self.assertEqual(vm.output_lines, ['nothing'])


class TestVMErrorHandling(unittest.TestCase):
    """Try/Catch must bind the caught error and propagate across call frames,
    matching the interpreter. Regressions from the parity harness.
    """

    def test_catch_variable_binds_runtime_error(self):
        vm = run_vm('Try\n  x = 10 / 0\nCatch e\n  Print e\nEnd')
        self.assertEqual(
            vm.output_lines, ['EPL Runtime Error on line 2: Cannot divide by zero.']
        )

    def test_reading_undefined_variable_errors(self):
        # Catches typos: an undeclared variable read raises (like the
        # interpreter) instead of silently yielding nothing.
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('Print score')

    def test_catch_variable_binds_thrown_value(self):
        vm = run_vm('Try\n  Throw "boom"\nCatch err\n  Print err\nEnd')
        self.assertEqual(vm.output_lines, ['EPL Runtime Error on line 2: boom'])

    def test_throw_inside_function_propagates_to_caller_catch(self):
        vm = run_vm(
            'Function check takes n\n'
            '    If n < 0 then\n'
            '        Throw "negative!"\n'
            '    End\n'
            '    Return n\n'
            'End\n'
            'Try\n'
            '    check(-5)\n'
            'Catch e\n'
            '    Print "caught: " + e\n'
            'End'
        )
        self.assertEqual(
            vm.output_lines, ['caught: EPL Runtime Error on line 3: negative!']
        )


class TestVMStackHygiene(unittest.TestCase):
    """Functions must restore the operand stack on return, even on an early
    `Return` from inside a loop. Regression: a leaked for-each iterator made an
    enclosing loop iterate the wrong collection.
    """

    def test_early_return_from_loop_does_not_corrupt_outer_loop(self):
        vm = run_vm(
            'Function first_match takes p\n'
            '    Create opts equal to ["x", "y", "z"]\n'
            '    For each o in opts\n'
            '        If p.contains(o) then\n'
            '            Return o\n'
            '        End\n'
            '    End\n'
            '    Return ""\n'
            'End\n'
            'Create words equal to ["ax", "by", "cz"]\n'
            'For each w in words\n'
            '    Create m equal to first_match(w)\n'
            '    Print w\n'
            'End'
        )
        # The outer loop must iterate `words`, not the helper's `opts`.
        self.assertEqual(vm.output_lines, ['ax', 'by', 'cz'])


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
        # Booleans render lowercase (true, not Python's True). Whole floats
        # keep their float form (4.0), matching the interpreter.
        vm = run_vm('flag = true\nratio = 4.0\nPrint "$flag and $ratio"')
        self.assertEqual(vm.output_lines, ['true and 4.0'])

    def test_single_dynamic_part_is_stringified(self):
        # A lone "$flag" must still become the string "true", not the bool.
        vm = run_vm('flag = true\nPrint "$flag"')
        self.assertEqual(vm.output_lines, ['true'])

    def test_undefined_variable_stays_literal(self):
        # "$xK9" where xK9 is undefined must stay literal (matches interpreter),
        # not be replaced with "nothing".
        vm = run_vm('p = "aB3$xK9!mN2@"\nPrint p\nPrint length(p)')
        self.assertEqual(vm.output_lines, ['aB3$xK9!mN2@', '12'])


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
        # sqrt returns a float; whole floats keep their float form (matches
        # the interpreter), so sqrt(16) prints "4.0", not "4".
        vm = run_vm('Display sqrt(16)')
        self.assertEqual(vm.output_lines, ['4.0'])

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
