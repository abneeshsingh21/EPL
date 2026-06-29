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


def compile_only(code):
    """Helper: lex, parse, and compile (no execution) — returns the compiled dict."""
    return BytecodeCompiler().compile(Parser(Lexer(code).tokenize()).parse())


class TestVMFunctionBodyOptimization(unittest.TestCase):
    """The optimization passes (const-fold / peephole / dead-code) run on function
    and method bodies, not just the top-level stream (regression: they used to be
    skipped entirely for anything compiled into its own instruction list).

    Note: these assert *dead-code elimination* rather than constant folding. A
    literal*literal like ``2 * 3`` is folded at AST-compile time (in
    ``_compile_expr``) regardless of the per-callable pipeline, so a "MUL absent"
    check would pass even with ``_optimize_callables`` removed. Dropping code after
    a ``Return`` is a bytecode-level pass (``_dead_code_eliminate``) that ONLY runs
    via the per-callable pipeline — so these fail loudly if that wiring regresses."""

    def test_dead_code_removed_after_return_in_function(self):
        compiled = compile_only(
            'Function f takes n\n    Return n\n    Say "dead"\n    Say "also dead"\nEnd\nSay f(1)\n'
        )
        fn = compiled['functions']['f']
        # The two unreachable Says compile to PRINT ops; the pipeline must drop them.
        self.assertNotIn(Op.PRINT, [i.op for i in fn.code], 'dead code after Return not eliminated')
        ret_positions = [idx for idx, i in enumerate(fn.code) if i.op == Op.RETURN]
        # Everything after the first reachable RETURN (the explicit one) is dead and dropped;
        # only the auto-appended fallthrough RETURN may remain at the tail.
        self.assertTrue(ret_positions)
        self.assertLessEqual(len(fn.code) - 1, ret_positions[0] + 1)

    def test_dead_code_removed_after_return_in_method(self):
        compiled = compile_only(
            'Class C\n    Function m takes x\n        Return x\n        Say "dead"\n    End\nEnd\n'
        )
        method = compiled['classes']['C'].methods['m']
        # Unreachable Say inside a *method* body — only optimized because
        # _optimize_callables reaches into cls.methods, not just top-level code.
        self.assertNotIn(Op.PRINT, [i.op for i in method.code], 'method dead code not eliminated')

    def test_function_optimization_preserves_behavior(self):
        vm = run_vm(
            'Function fib takes n\n'
            '    If n < 2\n        Return n\n    End\n'
            '    Return fib(n - 1) + fib(n - 2)\n'
            'End\n'
            'Say fib(10)\n'
        )
        self.assertEqual(vm.output_lines, ['55'])

    def test_method_optimization_preserves_behavior(self):
        vm = run_vm(
            'Class Calc\n'
            '    Function double takes x\n        Return x * 2\n        Say "dead"\n    End\n'
            'End\n'
            'Create c equal to new Calc()\n'
            'Say c.double(21)\n'
        )
        self.assertEqual(vm.output_lines, ['42'])


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
        vm = run_vm('nums = [3, 1, 2]\nnums.sort()\nPrint nums\nnums.reverse()\nPrint nums')
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
            'n = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]\nPrint n[0:10:2]\nPrint n[1:10:3]'
        )
        self.assertEqual(vm.output_lines, ['[10, 30, 50, 70, 90]', '[20, 50, 80]'])

    def test_omitted_bound_step_slices(self):
        """Slices with omitted start/end around a `::` step — `[::2]`, `[::-1]`,
        `[1::2]` — must parse and match Python semantics. The lexer emits `::` as
        a single DOUBLE_COLON, so these once silently mis-parsed as module access.
        """
        n = '[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]'
        vm = run_vm(
            f'n = {n}\n'
            'Print n[::2]\n'  # every other from start
            'Print n[::-1]\n'  # full reverse
            'Print n[1::2]\n'  # odd indices
            'Print n[:5]\n'  # first five (single-colon, end only)
            'Print n[5:]\n'  # from five (single-colon, start only)
        )
        self.assertEqual(
            vm.output_lines,
            [
                '[0, 2, 4, 6, 8]',
                '[9, 8, 7, 6, 5, 4, 3, 2, 1, 0]',
                '[1, 3, 5, 7, 9]',
                '[0, 1, 2, 3, 4]',
                '[5, 6, 7, 8, 9]',
            ],
        )

    def test_module_access_still_parses_after_slice_fix(self):
        """The `::` slice fix must not break real `Module::member` access: `::` is
        module access only when a member name follows, a slice separator otherwise
        (both forms share the single DOUBLE_COLON token). End-to-end proof via the
        interpreter that `Str::capitalize` still resolves rather than mis-parsing.
        """
        from epl.interpreter import Interpreter

        code = 'Import "string" as Str\nPrint Str::capitalize("hello")'
        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        self.assertEqual(interp.output_lines, ['Hello'])

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
        self.assertEqual(vm.output_lines, ['EPL Runtime Error on line 2: Cannot divide by zero.'])

    def test_reading_undefined_variable_errors(self):
        # Catches typos: an undeclared variable read raises (like the
        # interpreter) instead of silently yielding nothing.
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('Print score')

    def test_caught_undefined_variable_has_name_category(self):
        vm = run_vm('Try\n  Print score\nCatch e\n  Print e\nEnd')
        self.assertEqual(
            vm.output_lines,
            ['EPL Name Error on line 2: Variable "score" has not been created yet.'],
        )

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
        self.assertEqual(vm.output_lines, ['caught: EPL Runtime Error on line 3: negative!'])


class TestVMTopLevelScope(unittest.TestCase):
    """Top-level variables are globals visible inside functions (matching the
    interpreter), and a loop variable shares the one top-level binding.
    """

    def test_function_reads_top_level_variable(self):
        vm = run_vm(
            'config = "prod"\nFunction where\n    Return "running in " + config\nEnd\nPrint where()'
        )
        self.assertEqual(vm.output_lines, ['running in prod'])

    def test_loop_var_and_create_same_name_consistent(self):
        # `amount` is a foreach var, then re-Created in an indexed loop; both
        # must refer to the same top-level binding (regression: indexed reads
        # returned the stale foreach value).
        vm = run_vm(
            'amounts = [10, 20, 30]\n'
            'For each amount in amounts\n'
            '    Print amount\n'
            'End\n'
            'For i from 0 to 2\n'
            '    Create amount equal to amounts[i]\n'
            '    Print amount\n'
            'End'
        )
        self.assertEqual(vm.output_lines, ['10', '20', '30', '10', '20', '30'])


class TestVMModuleImports(unittest.TestCase):
    """`Import "mod" as M` then `M::func(args)` must run on the VM, not only the
    interpreter. Imports are inlined into the same compilation unit (one shared
    constant pool), so module functions resolve by bare name and the constant
    indices stay valid. Regression: the old runtime-merge path compiled the
    module separately and its constant indices pointed into the wrong pool, so
    every import silently crashed the VM (and de-optimised `epl run` to the
    interpreter fallback).
    """

    def _interp_lines(self, code):
        from epl.interpreter import Interpreter

        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        return interp.output_lines

    def test_aliased_member_call_runs_on_vm(self):
        code = 'Import "string" as Str\nPrint Str::capitalize("hello")'
        self.assertEqual(run_vm(code).output_lines, ['Hello'])

    def test_member_call_with_multiple_args(self):
        code = 'Import "string" as Str\nPrint Str::pad_left("7", 4, "0")'
        self.assertEqual(run_vm(code).output_lines, ['0007'])

    def test_two_modules_do_not_collide(self):
        code = (
            'Import "string" as Str\n'
            'Print Str::word_count("the quick brown fox")\n'
            'Print Str::pad_right("x", 3, ".")'
        )
        self.assertEqual(run_vm(code).output_lines, ['4', 'x..'])

    def test_vm_matches_interpreter(self):
        code = (
            'Import "string" as Str\nPrint Str::capitalize("epl")\nPrint Str::pad_left("9", 3, "0")'
        )
        self.assertEqual(run_vm(code).output_lines, self._interp_lines(code))

    def test_repeat_import_inlined_once(self):
        # Importing the same module twice must not double-define or error.
        code = 'Import "string" as Str\nImport "string" as Str2\nPrint Str::capitalize("ok")'
        self.assertEqual(run_vm(code).output_lines, ['Ok'])

    def test_unknown_member_raises(self):
        from epl.vm import VMError

        code = 'Import "string" as Str\nPrint Str::does_not_exist("x")'
        with self.assertRaises(VMError):
            run_vm(code)


class TestVMFirstClassFunctions(unittest.TestCase):
    """The VM can call a function value held in a variable — a lambda passed as
    a parameter (`Call f With x`) or stored in a global — not only functions
    referenced by their declared name. Regression: such calls silently returned
    `nothing`, which made every higher-order stdlib function (map/reduce/filter)
    produce wrong results once imports started running on the VM.
    """

    def test_call_lambda_passed_as_parameter(self):
        vm = run_vm(
            'Function apply takes f, x\n'
            '    Return Call f With x\n'
            'End\n'
            'Print apply(lambda n -> n * 2, 5)'
        )
        self.assertEqual(vm.output_lines, ['10'])

    def test_call_lambda_stored_in_global(self):
        vm = run_vm('double = lambda x -> x * 2\nPrint double(21)')
        self.assertEqual(vm.output_lines, ['42'])

    def test_higher_order_map_over_list(self):
        vm = run_vm(
            'Function map_list takes items, transform\n'
            '    Create result equal to []\n'
            '    For Each item In items\n'
            '        Add (Call transform With item) to result\n'
            '    End\n'
            '    Return result\n'
            'End\n'
            'Print map_list([1, 2, 3], lambda x -> x * 10)'
        )
        self.assertEqual(vm.output_lines, ['[10, 20, 30]'])

    def test_top_level_constant_visible_inside_function(self):
        # Regression: a top-level `Constant` was stored as a main-frame local,
        # so functions couldn't see it (the interpreter could).
        vm = run_vm(
            'Constant PI = 3.14\nFunction area takes r\n    Return PI * r * r\nEnd\nPrint area(2)'
        )
        self.assertEqual(vm.output_lines, ['12.56'])


class TestVMClosureCaptureGuard(unittest.TestCase):
    """The VM has no working closure capture, so a lambda that closes over an
    enclosing function's locals must raise at compile time rather than silently
    compute nonsense — that makes `epl run` fall back to the interpreter, which
    does support closures. A lambda that only uses its own params or globals is
    fine and stays on the VM.
    """

    def test_capturing_lambda_raises(self):
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm(
                'Function compose takes f, g\n'
                '    Return lambda x -> Call f With (Call g With x)\n'
                'End\n'
                'h = compose(lambda a -> a + 1, lambda b -> b * 2)\n'
                'Print Call h With 3'
            )

    def test_non_capturing_lambda_inside_function_is_fine(self):
        vm = run_vm(
            'Function run\n'
            '    Create g equal to lambda x -> x + 1\n'
            '    Return Call g With 9\n'
            'End\n'
            'Print run()'
        )
        self.assertEqual(vm.output_lines, ['10'])


class TestVMSoftKeywordIdentifiers(unittest.TestCase):
    """GUI/web/style words (`label`, `menu`, `grid`, `start`, `row`, ...) are
    soft keywords: they head a statement only in their statement form. Used as a
    bare variable target — `label = 5`, `grid += 1` — they must be plain
    assignments, not a misfired widget/layout statement.
    """

    def test_label_as_variable(self):
        vm = run_vm('label = 5\nPrint label')
        self.assertEqual(vm.output_lines, ['5'])

    def test_menu_as_variable(self):
        vm = run_vm('menu = "File"\nPrint menu')
        self.assertEqual(vm.output_lines, ['File'])

    def test_soft_keyword_augmented_assignment(self):
        vm = run_vm('start = 0\nstart += 3\ngrid = 10\ngrid *= 2\nPrint start\nPrint grid')
        self.assertEqual(vm.output_lines, ['3', '20'])

    def test_multiple_soft_keyword_vars_in_expression(self):
        vm = run_vm('row = 1\ncolumn = 2\nPrint row + column')
        self.assertEqual(vm.output_lines, ['3'])

    def test_soft_keyword_var_matches_interpreter(self):
        from epl.interpreter import Interpreter

        code = 'label = 7\nmenu = "x"\nstyle = label * 2\nPrint style\nPrint menu'
        vm = run_vm(code)
        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        self.assertEqual(vm.output_lines, ['14', 'x'])
        self.assertEqual(vm.output_lines, interp.output_lines)


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
        vm = run_vm('Function greet takes who\n    Print "Hi $who"\nEnd\ngreet("Sam")')
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


class TestVMCountedLoopControlFlow(unittest.TestCase):
    """Counted loops (for-range, repeat) advance the counter *after* the body, so
    a `Continue` must jump to the increment, not back to the condition. The VM
    previously pointed `continue` at the condition, leaving the counter unchanged
    and spinning forever (this hung `examples/constants_and_loops.epl`). Negative
    steps were also always compiled with a `<=` test, so countdown loops never
    ran a single iteration.
    """

    def test_for_continue_does_not_infinite_loop(self):
        vm = run_vm('For i from 1 to 6\n  If i % 3 == 0 Then\n    Continue\n  End\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['1', '2', '4', '5'])

    def test_repeat_continue_does_not_infinite_loop(self):
        vm = run_vm(
            'i = 0\nRepeat 5 times\n  Increase i by 1\n  If i == 3 Then\n    Continue\n  End\n  Print i\nEnd'
        )
        self.assertEqual(vm.output_lines, ['1', '2', '4', '5'])

    def test_for_negative_step_counts_down(self):
        vm = run_vm('For i from 5 to 1 step -1\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['5', '4', '3', '2', '1'])

    def test_for_positive_step_still_works(self):
        vm = run_vm('For i from 0 to 6 step 2\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['0', '2', '4', '6'])

    def test_for_break_still_works(self):
        vm = run_vm('For i from 1 to 10\n  If i > 3 Then\n    Break\n  End\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['1', '2', '3'])

    def test_for_continue_matches_interpreter(self):
        """VM and tree-walking interpreter must agree on counted-loop control flow."""
        from epl.interpreter import Interpreter

        code = (
            'For i from 10 to 1 step -1\n  If i % 2 == 0 Then\n    Continue\n  End\n  Print i\nEnd'
        )
        vm = run_vm(code)
        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        self.assertEqual(vm.output_lines, [str(n) for n in (9, 7, 5, 3, 1)])
        self.assertEqual(vm.output_lines, interp.output_lines)

    def test_for_runtime_positive_step_counts_up(self):
        """A step given by a variable (not a literal) must derive direction at runtime."""
        vm = run_vm('s = 2\nFor i from 0 to 6 step s\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['0', '2', '4', '6'])

    def test_for_runtime_negative_step_counts_down(self):
        """A negative runtime step must count down, mirroring the interpreter."""
        vm = run_vm('s = 0 - 1\nFor i from 5 to 1 step s\n  Print i\nEnd')
        self.assertEqual(vm.output_lines, ['5', '4', '3', '2', '1'])

    def test_for_constant_zero_step_raises(self):
        """A compile-time-constant zero step would spin forever; reject it instead."""
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('For i from 1 to 5 step 0\n  Print i\nEnd')

    def test_for_runtime_zero_step_raises(self):
        """A runtime zero step must be rejected at execution time, not hang."""
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('s = 0\nFor i from 1 to 5 step s\n  Print i\nEnd')

    def test_for_constant_fractional_step_raises(self):
        """A fractional constant step must be rejected (interpreter wants an integer)."""
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('For i from 1 to 5 step 0.5\n  Print i\nEnd')

    def test_for_runtime_fractional_step_raises(self):
        """A fractional runtime step must be rejected at execution time."""
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('s = 0.5\nFor i from 1 to 5 step s\n  Print i\nEnd')

    def test_for_whole_number_float_step_raises_like_interpreter(self):
        """The interpreter rejects any non-int step via isinstance, so even a
        whole-number float like 2.0 must be rejected by the VM for parity —
        both as a constant literal and as a runtime variable."""
        from epl.errors import EPLError
        from epl.interpreter import Interpreter
        from epl.vm import VMError

        for code in (
            'For i from 1 to 5 step 2.0\n  Print i\nEnd',
            's = 2.0\nFor i from 1 to 5 step s\n  Print i\nEnd',
        ):
            with self.assertRaises(VMError):
                run_vm(code)
            interp = Interpreter()
            with self.assertRaises(EPLError):
                interp.execute(Parser(Lexer(code).tokenize()).parse())

    def test_for_end_bound_snapshotted_like_interpreter(self):
        """The end bound is evaluated once up front; mutating it in the body must
        not change the loop's extent (matches the interpreter, avoids a hang)."""
        from epl.interpreter import Interpreter

        code = 'e = 3\nFor i from 1 to e\n  Print i\n  e = 10\nEnd'
        vm = run_vm(code)
        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        self.assertEqual(vm.output_lines, ['1', '2', '3'])
        self.assertEqual(vm.output_lines, interp.output_lines)

    def test_for_runtime_step_matches_interpreter(self):
        """VM and interpreter must agree when the step is a runtime expression."""
        from epl.interpreter import Interpreter

        code = 's = 0 - 2\nFor i from 10 to 0 step s\n  Print i\nEnd'
        vm = run_vm(code)
        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        self.assertEqual(vm.output_lines, [str(n) for n in (10, 8, 6, 4, 2, 0)])
        self.assertEqual(vm.output_lines, interp.output_lines)


class TestBareConstantParity(unittest.TestCase):
    """Bare constant identifiers (pi, euler, infinity, on, off) must resolve to the
    same value in the VM and the interpreter. Regression: the VM had a constants
    dict but the interpreter did not, so `Say pi` printed 3.14159 on the default VM
    yet "pi" (or errored) under --interpret. Both now share stdlib.BARE_CONSTANTS.
    """

    def _interp(self, code):
        from epl.interpreter import Interpreter

        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        return interp.output_lines

    def test_math_and_boolean_constants_match(self):
        for name in ('pi', 'euler', 'infinity', 'on', 'off', 'yes', 'no'):
            code = f'Say {name}'
            with self.subTest(constant=name):
                vm = run_vm(code)
                self.assertEqual(vm.output_lines, self._interp(code))

    def test_pi_is_numeric_not_string(self):
        # The whole point of the fix: bare `pi` is the number, usable in arithmetic.
        vm = run_vm('Say pi > 3')
        self.assertEqual(vm.output_lines, ['true'])
        self.assertEqual(vm.output_lines, self._interp('Say pi > 3'))

    def test_user_variable_shadows_constant(self):
        code = 'Create pi equal to 42\nSay pi'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['42'])
        self.assertEqual(vm.output_lines, self._interp(code))


class TestVMParityWithInterpreter(unittest.TestCase):
    """Regression tests for VM compile bugs that crashed `epl vm` on basic
    features (Ternary, Match, file I/O) and a division-semantics divergence.

    Before these fixes the VM compiler read AST attributes that don't exist
    (node.true_value, node.value, node.path), so `epl vm` raised AttributeError
    and only `epl run` worked — via the silent interpreter fallback. Each test
    here forces the VM and, where output is deterministic, cross-checks it
    against the interpreter so the two engines can't silently drift again.
    """

    def _interp(self, code):
        from epl.interpreter import Interpreter

        interp = Interpreter()
        interp.execute(Parser(Lexer(code).tokenize()).parse())
        return interp.output_lines

    def test_ternary_true_and_false_branches(self):
        # `expr if condition otherwise other` — VM read .true_value/.false_value,
        # the real fields are .true_expr/.false_expr.
        for x, expected in ((9, 'big'), (2, 'small')):
            code = f'x = {x}\nPrint "big" if x > 5 otherwise "small"'
            vm = run_vm(code)
            self.assertEqual(vm.output_lines, [expected])
            self.assertEqual(vm.output_lines, self._interp(code))

    def test_match_single_value_and_default(self):
        code = (
            'd = "Tue"\nMatch d\n  When "Mon"\n    Print "start"\n  Default\n    Print "other"\nEnd'
        )
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['other'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_match_multi_value_clause(self):
        # A clause matches if the subject equals ANY of its values. The current
        # surface parser folds `When 1 or 2 or 3` into one boolean expression
        # (a separate limitation affecting both engines), so build the AST
        # directly to exercise the multi-value path the old VM code ignored.
        from epl import ast_nodes as ast
        from epl.interpreter import Interpreter

        def build(n):
            return ast.Program(
                [
                    ast.VarDeclaration('n', ast.Literal(n)),
                    ast.MatchStatement(
                        ast.Identifier('n'),
                        [
                            ast.WhenClause(
                                [ast.Literal(1), ast.Literal(2), ast.Literal(3)],
                                [ast.PrintStatement(ast.Literal('low'))],
                            )
                        ],
                        default_body=[ast.PrintStatement(ast.Literal('high'))],
                    ),
                ]
            )

        for n, expected in ((2, 'low'), (5, 'high')):
            program = build(n)
            vm = VM()
            vm.execute(BytecodeCompiler().compile(program))
            interp = Interpreter()
            interp.execute(build(n))
            self.assertEqual(vm.output_lines, [expected])
            self.assertEqual(vm.output_lines, interp.output_lines)

    def test_division_preserves_float_operand(self):
        # 200.0 / 4 must stay 50.0 (float operand) — the old VM collapsed any
        # whole-valued result to int, diverging from the interpreter.
        code = 'p = 100.0\np = p * 2\nPrint p / 4'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['50.0'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_division_int_operands_still_collapse(self):
        # Both operands int and evenly divisible -> int, matching interpreter.
        code = 'Print 8 / 2\nPrint 7 / 2'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['4', '3.5'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_division_constant_folded_paths(self):
        # Literal operands hit the compile-time constant-folding path (distinct
        # from the runtime _op_div path). A float operand must keep the float;
        # two evenly-dividing ints collapse to int — same rule, both paths.
        code = 'Print 200.0 / 4\nPrint 9 / 3\nPrint 9 / 2'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['50.0', '3', '4.5'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_division_large_int_keeps_precision(self):
        # Even-int division uses `//`, not int(a / b): the float round-trip
        # loses precision for large divisible ints. A variable operand forces
        # the runtime _op_div path (literals would constant-fold). Both engines
        # must agree on the exact integer — this would diverge if only one used
        # `//` (int((10**18 + 1) / 1) drops the +1).
        code = 'n = 1000000000000000001\nPrint (n * 7) / 7'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['1000000000000000001'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_augmented_division_large_int_parity(self):
        # `/=` must follow the same exact-int rule. The VM routes `/=` through
        # Op.DIV (now `//`); the interpreter's `/=` previously used
        # int(current / rhs) and lost precision, diverging from the VM.
        code = 'n = 1000000000000000001\nn = n * 7\nn /= 7\nPrint n'
        vm = run_vm(code)
        self.assertEqual(vm.output_lines, ['1000000000000000001'])
        self.assertEqual(vm.output_lines, self._interp(code))

    def test_file_write_append_read_roundtrip(self):
        import tempfile

        # Non-ASCII payload so this actually exercises the utf-8 fix — with the
        # old platform-default encoding this would mojibake or raise on a
        # non-utf-8 system (e.g. cp1252 Windows) instead of round-tripping.
        path = os.path.join(tempfile.mkdtemp(), 'vm_io.txt')
        epl_path = path.replace('\\', '/')
        code = (
            f'Write "café ☕" to file "{epl_path}"\n'
            f'Append "日本語 ñ" to file "{epl_path}"\n'
            f'c = Read file "{epl_path}"\n'
            f'Print c'
        )
        vm = run_vm(code)
        # Append adds a trailing newline (matching the interpreter), so the
        # read-back is "café ☕日本語 ñ\n" -> two printed lines.
        self.assertEqual(vm.output_lines, self._interp(code))
        with open(path, encoding='utf-8') as f:
            self.assertEqual(f.read(), 'café ☕日本語 ñ\n')

    def test_constant_fold_peephole_division_rule(self):
        # The bytecode-level _constant_fold pass (distinct from the AST fold) has
        # its own DIV branch. Exercise it directly — the AST fold front-runs it
        # for simple literals, so a black-box program wouldn't reach it. It must
        # follow the same exact-int rule: float operand keeps the float; large
        # divisible ints use `//` (no precision loss); non-divisible stays float.
        from epl.vm import Instruction, Op

        def fold_div(a, b):
            comp = BytecodeCompiler()
            ia, ib = comp._add_const(a), comp._add_const(b)
            code = [
                Instruction(Op.LOAD_CONST, ia, 1),
                Instruction(Op.LOAD_CONST, ib, 1),
                Instruction(Op.DIV, None, 1),
            ]
            folded = comp._constant_fold(code)
            self.assertEqual(len(folded), 1)
            self.assertEqual(folded[0].op, Op.LOAD_CONST)
            return comp.constants[folded[0].arg]

        self.assertEqual(fold_div(200.0, 4), 50.0)  # float operand -> float
        self.assertEqual(fold_div(9, 2), 4.5)  # not divisible -> float
        big = fold_div(1000000000000000001 * 7, 7)  # even ints -> exact //
        self.assertEqual(big, 1000000000000000001)

    def test_use_python_declines_at_compile_time(self):
        # The VM has no foreign-language bridge; it must raise at compile time
        # so `epl run` falls back to the interpreter (which does bridge), rather
        # than failing mid-run with a cryptic error.
        from epl.vm import VMError

        with self.assertRaises(VMError):
            run_vm('Use python "math"\nPrint "after"')


if __name__ == '__main__':
    unittest.main()
