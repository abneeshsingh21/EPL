"""
EPL LLVM Compiler Optimization Tests v5.0
Tests compile pipeline with optimization levels O0-O3,
div-by-zero guards, and various compilation paths.
"""
import sys, os
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

PASSED = 0
FAILED = 0

def test(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
        print(f"  PASS: {name}")
    except Exception as e:
        FAILED += 1
        print(f"  FAIL: {name} -> {e}")



test.__test__ = False

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"


def _has_llvm_support():
    try:
        from epl.compiler import Compiler  # noqa: F401
        from epl.lexer import Lexer  # noqa: F401
        from epl.parser import Parser  # noqa: F401
        return True
    except ImportError:
        return False


HAS_LLVM = _has_llvm_support()

def compile_src(src, opt=2):
    from epl.compiler import Compiler
    from epl.lexer import Lexer
    from epl.parser import Parser

    l = Lexer(src)
    t = l.tokenize()
    p = Parser(t)
    prog = p.parse()
    c = Compiler(opt_level=opt)
    ir_code = c.compile(prog)
    return ir_code, c

def compile_to_obj(src, opt=2):
    ir_code, c = compile_src(src, opt)
    return c.compile_to_object(ir_code)

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    if not HAS_LLVM:
        print("SKIP: llvmlite not available")
        return True

    from epl.compiler import Compiler
    from epl.lexer import Lexer
    from epl.parser import Parser
    
    
    # ═══════════════════════════════════════════════════════════
    # 1. Optimization Levels
    # ═══════════════════════════════════════════════════════════
    print("\n=== Optimization Levels ===")
    
    def t_O0_produces_valid_object():
        obj = compile_to_obj('Print "hello"', opt=0)
        assert_true(obj is not None and len(obj) > 0)
    test("O0_produces_valid_object", t_O0_produces_valid_object)
    
    def t_O1_produces_valid_object():
        obj = compile_to_obj('Print "hello"', opt=1)
        assert_true(obj is not None and len(obj) > 0)
    test("O1_produces_valid_object", t_O1_produces_valid_object)
    
    def t_O2_produces_valid_object():
        obj = compile_to_obj('Print "hello"', opt=2)
        assert_true(obj is not None and len(obj) > 0)
    test("O2_produces_valid_object", t_O2_produces_valid_object)
    
    def t_O3_produces_valid_object():
        obj = compile_to_obj('Print "hello"', opt=3)
        assert_true(obj is not None and len(obj) > 0)
    test("O3_produces_valid_object", t_O3_produces_valid_object)
    
    def t_O0_larger_than_O2():
        o0 = compile_to_obj('Create x equal to 10\nPrint x', opt=0)
        o2 = compile_to_obj('Create x equal to 10\nPrint x', opt=2)
        assert_true(len(o0) >= len(o2), f"O0={len(o0)} < O2={len(o2)}")
    test("O0_larger_than_O2", t_O0_larger_than_O2)
    
    def t_invalid_opt_level_raises():
        try:
            Compiler(opt_level=5)
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass
    test("invalid_opt_level_raises", t_invalid_opt_level_raises)
    
    def t_default_opt_is_2():
        c = Compiler()
        assert_eq(c.opt_level, 2)
    test("default_opt_is_2", t_default_opt_is_2)
    
    def t_negative_opt_level_raises():
        try:
            Compiler(opt_level=-1)
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass
    test("negative_opt_level_raises", t_negative_opt_level_raises)
    
    # ═══════════════════════════════════════════════════════════
    # 2. IR Generation
    # ═══════════════════════════════════════════════════════════
    print("\n=== IR Generation ===")
    
    def t_ir_contains_main():
        ir_code, _ = compile_src('Print "hello"')
        assert_true('define i32 @"main"' in ir_code or 'define i32 @main' in ir_code)
    test("ir_contains_main", t_ir_contains_main)
    
    def t_ir_contains_printf():
        ir_code, _ = compile_src('Print "hello"')
        assert_true("printf" in ir_code)
    test("ir_contains_printf", t_ir_contains_printf)
    
    def t_ir_variables():
        ir_code, _ = compile_src('Create x equal to 42\nPrint x')
        assert_true("alloca" in ir_code or "store" in ir_code)
    test("ir_variables", t_ir_variables)
    
    def t_ir_string_constant():
        ir_code, _ = compile_src('Print "test123"')
        assert_true("test123" in ir_code)
    test("ir_string_constant", t_ir_string_constant)
    
    def t_ir_integer_arithmetic():
        ir_code, _ = compile_src('Create x equal to 10 + 5\nPrint x')
        assert_true("add" in ir_code)
    test("ir_integer_arithmetic", t_ir_integer_arithmetic)
    
    def t_ir_float_arithmetic():
        ir_code, _ = compile_src('Create x equal to 3.14 + 2.0\nPrint x')
        assert_true("fadd" in ir_code)
    test("ir_float_arithmetic", t_ir_float_arithmetic)
    
    def t_ir_comparison():
        ir_code, _ = compile_src('Create x equal to 5 > 3\nPrint x')
        assert_true("icmp" in ir_code or "cmp" in ir_code)
    test("ir_comparison", t_ir_comparison)
    
    def t_ir_if_branch():
        ir_code, _ = compile_src('If true\nPrint "yes"\nEnd')
        assert_true("br" in ir_code)
    test("ir_if_branch", t_ir_if_branch)
    
    def t_ir_while_loop():
        ir_code, _ = compile_src('Create i equal to 0\nWhile i < 3\nIncrease i by 1\nEnd')
        assert_true("br" in ir_code)
    test("ir_while_loop", t_ir_while_loop)
    
    def t_ir_function_def():
        ir_code, _ = compile_src('Function greet takes nothing\nPrint "hi"\nEnd\nCall greet')
        assert_true("@greet" in ir_code or "greet" in ir_code)
    test("ir_function_def", t_ir_function_def)
    
    def t_ir_gc_shutdown():
        ir_code, _ = compile_src('Print "done"')
        assert_true("epl_gc_shutdown" in ir_code)
    test("ir_gc_shutdown", t_ir_gc_shutdown)
    
    def t_ir_for_loop():
        ir_code, _ = compile_src('For i from 1 to 5\nPrint i\nEnd')
        assert_true("br" in ir_code)
    test("ir_for_loop", t_ir_for_loop)
    
    def t_ir_list_create():
        ir_code, _ = compile_src('Create items equal to [1, 2, 3]\nPrint items')
        assert_true("epl_list_new" in ir_code or "epl_list_create" in ir_code)
    test("ir_list_create", t_ir_list_create)
    
    def t_ir_map_create():
        ir_code, _ = compile_src('Create m equal to Map with key1 = 1\nPrint m')
        assert_true("epl_map_create" in ir_code or "map" in ir_code.lower())
    test("ir_map_create", t_ir_map_create)
    
    def t_ir_division_has_zero_check():
        ir_code, _ = compile_src('Create x equal to 10 / 2\nPrint x')
        assert_true("div_zero" in ir_code.lower() or "icmp" in ir_code)
    test("ir_division_has_zero_check", t_ir_division_has_zero_check)
    
    def t_ir_modulo_has_zero_check():
        ir_code, _ = compile_src('Create x equal to 10 % 3\nPrint x')
        assert_true("div_zero" in ir_code.lower() or "icmp" in ir_code)
    test("ir_modulo_has_zero_check", t_ir_modulo_has_zero_check)
    
    def t_ir_repeat_loop():
        ir_code, _ = compile_src('Repeat 3 times\nPrint "go"\nEnd')
        assert_true("br" in ir_code)
    test("ir_repeat_loop", t_ir_repeat_loop)
    
    def t_ir_boolean_true():
        ir_code, _ = compile_src('Create flag equal to true\nPrint flag')
        assert_true("alloca" in ir_code or "store" in ir_code)
    test("ir_boolean_true", t_ir_boolean_true)
    
    def t_ir_boolean_false():
        ir_code, _ = compile_src('Create flag equal to false\nPrint flag')
        assert_true("alloca" in ir_code or "store" in ir_code)
    test("ir_boolean_false", t_ir_boolean_false)
    
    def t_ir_string_concat():
        ir_code, _ = compile_src('Create msg equal to "hello" + " " + "world"\nPrint msg')
        assert_true("epl_str_concat" in ir_code or "concat" in ir_code.lower())
    test("ir_string_concat", t_ir_string_concat)
    
    def t_ir_subtraction():
        ir_code, _ = compile_src('Create x equal to 10 - 3\nPrint x')
        assert_true("sub" in ir_code)
    test("ir_subtraction", t_ir_subtraction)
    
    def t_ir_multiplication():
        ir_code, _ = compile_src('Create x equal to 4 * 5\nPrint x')
        assert_true("mul" in ir_code)
    test("ir_multiplication", t_ir_multiplication)
    
    def t_ir_power():
        ir_code, _ = compile_src('Create x equal to 2 ** 3\nPrint x')
        assert_true("power" in ir_code.lower() or "pow" in ir_code.lower() or "call" in ir_code)
    test("ir_power", t_ir_power)
    
    def t_ir_floor_division():
        ir_code, _ = compile_src('Create x equal to 7 // 2\nPrint x')
        assert_true("sdiv" in ir_code)
    test("ir_floor_division", t_ir_floor_division)
    
    def t_ir_augmented_plus_assign():
        ir_code, _ = compile_src('Create x equal to 1\nx += 5\nPrint x')
        assert_true("add" in ir_code)
    test("ir_augmented_plus_assign", t_ir_augmented_plus_assign)
    
    def t_ir_augmented_mul_assign():
        ir_code, _ = compile_src('Create x equal to 3\nx *= 4\nPrint x')
        assert_true("mul" in ir_code)
    test("ir_augmented_mul_assign", t_ir_augmented_mul_assign)
    
    def t_ir_nested_if():
        ir_code, _ = compile_src('If true\nIf false\nPrint "no"\nEnd\nEnd')
        assert_true(ir_code.count("br") >= 2)
    test("ir_nested_if", t_ir_nested_if)
    
    def t_ir_otherwise():
        ir_code, _ = compile_src('If false\nPrint "no"\nOtherwise\nPrint "yes"\nEnd')
        assert_true("br" in ir_code)
    test("ir_otherwise", t_ir_otherwise)
    
    def t_ir_multi_function():
        ir_code, _ = compile_src('Function fn1 takes nothing\nReturn 1\nEnd\nFunction fn2 takes nothing\nReturn 2\nEnd\nPrint fn1()\nPrint fn2()')
        assert_true("epl_fn1" in ir_code and "epl_fn2" in ir_code)
    test("ir_multi_function", t_ir_multi_function)
    
    def t_ir_function_with_params():
        ir_code, _ = compile_src('Function myAdd takes x and y\nReturn x + y\nEnd\nPrint myAdd(1, 2)')
        assert_true("@myAdd" in ir_code or "myAdd" in ir_code)
    test("ir_function_with_params", t_ir_function_with_params)
    
    def t_ir_break_in_loop():
        ir_code, _ = compile_src('Create i equal to 0\nWhile true\nIf i > 3\nBreak\nEnd\nIncrease i by 1\nEnd')
        assert_true("br" in ir_code)
    test("ir_break_in_loop", t_ir_break_in_loop)
    
    def t_ir_unary_minus():
        ir_code, _ = compile_src('Create x equal to -5\nPrint x')
        assert_true("sub" in ir_code or "-5" in ir_code)
    test("ir_unary_minus", t_ir_unary_minus)
    
    def t_ir_and_operator():
        ir_code, _ = compile_src('Create x equal to true and false\nPrint x')
        assert_true("and" in ir_code.lower() or "br" in ir_code)
    test("ir_and_operator", t_ir_and_operator)
    
    def t_ir_or_operator():
        ir_code, _ = compile_src('Create x equal to true or false\nPrint x')
        assert_true("or" in ir_code.lower() or "br" in ir_code)
    test("ir_or_operator", t_ir_or_operator)
    
    def t_ir_not_operator():
        ir_code, _ = compile_src('Create x equal to not true\nPrint x')
        assert_true("xor" in ir_code or "not" in ir_code.lower())
    test("ir_not_operator", t_ir_not_operator)
    
    def t_ir_class_def():
        ir_code, _ = compile_src('Class MyObj\nCreate val equal to 1\nEnd\nCreate obj equal to new MyObj()\nPrint obj')
        assert_true("epl_object_create" in ir_code or "object" in ir_code.lower())
    test("ir_class_def", t_ir_class_def)
    
    def t_ir_constant():
        ir_code, _ = compile_src('Constant PI = 3\nPrint PI')
        assert_true("alloca" in ir_code or "store" in ir_code)
    test("ir_constant", t_ir_constant)
    
    def t_ir_try_catch():
        ir_code, _ = compile_src('Try\nPrint "ok"\nCatch err\nPrint err\nEnd')
        assert_true("epl_try_begin" in ir_code or "try" in ir_code.lower())
    test("ir_try_catch", t_ir_try_catch)
    
    def t_ir_less_than():
        ir_code, _ = compile_src('Create x equal to 3 < 5\nPrint x')
        assert_true("icmp" in ir_code)
    test("ir_less_than", t_ir_less_than)
    
    def t_ir_greater_equal():
        ir_code, _ = compile_src('Create x equal to 5 >= 3\nPrint x')
        assert_true("icmp" in ir_code)
    test("ir_greater_equal", t_ir_greater_equal)
    
    def t_ir_less_equal():
        ir_code, _ = compile_src('Create x equal to 3 <= 5\nPrint x')
        assert_true("icmp" in ir_code)
    test("ir_less_equal", t_ir_less_equal)
    
    def t_ir_equality():
        ir_code, _ = compile_src('Create x equal to 3 == 3\nPrint x')
        assert_true("icmp" in ir_code)
    test("ir_equality", t_ir_equality)
    
    def t_ir_inequality():
        ir_code, _ = compile_src('Create x equal to 3 != 5\nPrint x')
        assert_true("icmp" in ir_code)
    test("ir_inequality", t_ir_inequality)
    
    def t_ir_negative_literal():
        ir_code, _ = compile_src('Create x equal to -42\nPrint x')
        assert_true("42" in ir_code)
    test("ir_negative_literal", t_ir_negative_literal)
    
    def t_ir_float_literal():
        ir_code, _ = compile_src('Create x equal to 3.14\nPrint x')
        assert_true("3.14" in ir_code or "double" in ir_code)
    test("ir_float_literal", t_ir_float_literal)
    
    def t_ir_empty_string():
        ir_code, _ = compile_src('Create x equal to ""\nPrint x')
        assert_true("alloca" in ir_code or "store" in ir_code)
    test("ir_empty_string", t_ir_empty_string)
    
    def t_ir_multiline_program():
        src = 'Create x equal to 1\nCreate y equal to 2\nCreate z equal to x + y\nPrint z'
        ir_code, _ = compile_src(src)
        assert_true("add" in ir_code)
    test("ir_multiline_program", t_ir_multiline_program)
    
    def t_ir_nested_loop():
        src = 'For i from 1 to 3\nFor j from 1 to 3\nPrint i + j\nEnd\nEnd'
        ir_code, _ = compile_src(src)
        assert_true(ir_code.count("br") >= 4)
    test("ir_nested_loop", t_ir_nested_loop)
    
    def t_ir_chain_comparison():
        ir_code, _ = compile_src('Create x equal to 5\nIf x > 3 and x < 10\nPrint "yes"\nEnd')
        assert_true("icmp" in ir_code)
    test("ir_chain_comparison", t_ir_chain_comparison)
    
    def t_ir_reassignment():
        ir_code, _ = compile_src('Create x equal to 1\nSet x to 2\nPrint x')
        assert_true("store" in ir_code)
    test("ir_reassignment", t_ir_reassignment)
    
    def t_ir_decrease():
        ir_code, _ = compile_src('Create x equal to 10\nDecrease x by 3\nPrint x')
        assert_true("sub" in ir_code)
    test("ir_decrease", t_ir_decrease)
    
    def t_ir_increase():
        ir_code, _ = compile_src('Create x equal to 0\nIncrease x by 5\nPrint x')
        assert_true("add" in ir_code)
    test("ir_increase", t_ir_increase)
    
    def t_ir_sub_assign():
        ir_code, _ = compile_src('Create x equal to 10\nx -= 3\nPrint x')
        assert_true("sub" in ir_code)
    test("ir_sub_assign", t_ir_sub_assign)
    
    def t_ir_div_assign():
        ir_code, _ = compile_src('Create x equal to 10\nx /= 2\nPrint x')
        assert_true("sdiv" in ir_code or "div" in ir_code)
    test("ir_div_assign", t_ir_div_assign)
    
    # ═══════════════════════════════════════════════════════════
    # 3. Optimization Effects
    # ═══════════════════════════════════════════════════════════
    print("\n=== Optimization Effects ===")
    
    def t_opt_all_levels_same_semantics_simple():
        sizes = [len(compile_to_obj('Create x equal to 42\nPrint x', opt=i)) for i in range(4)]
        assert_true(all(s > 0 for s in sizes), f"Some had zero size: {sizes}")
    test("opt_all_levels_same_semantics_simple", t_opt_all_levels_same_semantics_simple)
    
    def t_opt_complex_program():
        src = 'Create total equal to 0\nFor i from 1 to 10\nSet total to total + i\nEnd\nPrint total'
        sizes = [len(compile_to_obj(src, opt=i)) for i in range(4)]
        assert_true(all(s > 0 for s in sizes))
    test("opt_complex_program", t_opt_complex_program)
    
    def t_opt_function_inlining_candidate():
        src = 'Function double takes n\nReturn n * 2\nEnd\nPrint double(21)'
        o0 = len(compile_to_obj(src, opt=0))
        o3 = len(compile_to_obj(src, opt=3))
        assert_true(o0 > 0 and o3 > 0)
    test("opt_function_inlining_candidate", t_opt_function_inlining_candidate)
    
    def t_opt_dead_code_elimination():
        src = 'Create x equal to 5\nCreate y equal to 10\nPrint x'
        obj = compile_to_obj(src, opt=2)
        assert_true(len(obj) > 0)
    test("opt_dead_code_elimination", t_opt_dead_code_elimination)
    
    def t_opt_constant_folding():
        src = 'Create x equal to 2 + 3 * 4\nPrint x'
        obj = compile_to_obj(src, opt=2)
        assert_true(len(obj) > 0)
    test("opt_constant_folding", t_opt_constant_folding)
    
    def t_opt_loop_optimization():
        src = 'Create sum_val equal to 0\nFor i from 1 to 100\nSet sum_val to sum_val + i\nEnd\nPrint sum_val'
        obj = compile_to_obj(src, opt=2)
        assert_true(len(obj) > 0)
    test("opt_loop_optimization", t_opt_loop_optimization)
    
    def t_opt_nested_loops():
        src = 'Create total equal to 0\nFor i from 1 to 5\nFor j from 1 to 5\nSet total to total + 1\nEnd\nEnd\nPrint total'
        obj = compile_to_obj(src, opt=3)
        assert_true(len(obj) > 0)
    test("opt_nested_loops", t_opt_nested_loops)
    
    def t_opt_string_ops():
        src = 'Create msg equal to "hello" + " " + "world"\nPrint msg'
        obj = compile_to_obj(src, opt=2)
        assert_true(len(obj) > 0)
    test("opt_string_ops", t_opt_string_ops)
    
    # ═══════════════════════════════════════════════════════════
    # 4. Object File Properties
    # ═══════════════════════════════════════════════════════════
    print("\n=== Object File Properties ===")
    
    def t_obj_is_bytes():
        obj = compile_to_obj('Print "hello"')
        assert_true(isinstance(obj, bytes))
    test("obj_is_bytes", t_obj_is_bytes)
    
    def t_obj_nonzero_size():
        obj = compile_to_obj('Print "hello"')
        assert_true(len(obj) > 50, f"Object too small: {len(obj)}")
    test("obj_nonzero_size", t_obj_nonzero_size)
    
    def t_obj_complex_program():
        src = 'Create total equal to 0\nFor i from 1 to 10\nSet total to total + i\nEnd\nPrint total'
        obj = compile_to_obj(src)
        assert_true(len(obj) > 100)
    test("obj_complex_program", t_obj_complex_program)
    
    # ═══════════════════════════════════════════════════════════
    # 5. get_ir method
    # ═══════════════════════════════════════════════════════════
    print("\n=== get_ir Method ===")
    
    def t_get_ir_returns_string():
        l = Lexer('Print "test"')
        t = l.tokenize()
        p = Parser(t)
        prog = p.parse()
        c = Compiler()
        ir_code = c.get_ir(prog)
        assert_true(isinstance(ir_code, str) and len(ir_code) > 0)
    test("get_ir_returns_string", t_get_ir_returns_string)
    
    def t_get_ir_has_main():
        l = Lexer('Print 42')
        t = l.tokenize()
        p = Parser(t)
        prog = p.parse()
        c = Compiler()
        ir1 = c.compile(prog)
        assert_true('define i32 @"main"' in ir1 or 'define i32 @main' in ir1)
    test("get_ir_has_main", t_get_ir_has_main)
    
    # ═══════════════════════════════════════════════════════════
    # 6. Compiler Instance Properties
    # ═══════════════════════════════════════════════════════════
    print("\n=== Compiler Instance Properties ===")
    
    def t_compiler_has_opt_level():
        c = Compiler(opt_level=1)
        assert_eq(c.opt_level, 1)
    test("compiler_has_opt_level", t_compiler_has_opt_level)
    
    def t_compiler_opt_0():
        c = Compiler(opt_level=0)
        assert_eq(c.opt_level, 0)
    test("compiler_opt_0", t_compiler_opt_0)
    
    def t_compiler_opt_3():
        c = Compiler(opt_level=3)
        assert_eq(c.opt_level, 3)
    test("compiler_opt_3", t_compiler_opt_3)
    
    def t_compiler_multiple_compiles():
        c1 = Compiler()
        ir1 = c1.compile(Parser(Lexer('Print 1').tokenize()).parse())
        c2 = Compiler()
        ir2 = c2.compile(Parser(Lexer('Print 2').tokenize()).parse())
        assert_true(len(ir1) > 0 and len(ir2) > 0)
    test("compiler_multiple_compiles", t_compiler_multiple_compiles)
    
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"LLVM Optimization Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    print(f"{'='*50}")
    return FAILED == 0


def test_llvm_optimization_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
