"""
EPL Comprehensive Interpreter Tests v5.0
Tests: OOP, error handling, expressions, operators, edge cases,
collections, closures, string methods, type coercion, scoping.
"""
import sys, os, io, contextlib, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.interpreter import Interpreter
from epl.lexer import Lexer
from epl.parser import Parser

PASSED = 0
FAILED = 0

def test(name, fn):
    global PASSED, FAILED
    try:
        fn()
        PASSED += 1
    except Exception as e:
        FAILED += 1
        print(f"  FAIL: {name} -> {e}")
test.__test__ = False

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"

def run(src):
    l = Lexer(src)
    tokens = l.tokenize()
    p = Parser(tokens)
    prog = p.parse()
    interp = Interpreter()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        interp.execute(prog)
    return buf.getvalue().strip()

def run_lines(src):
    out = run(src)
    return out.split('\n') if out else []

def run_val(src):
    """Run and return the last printed line."""
    lines = run_lines(src)
    return lines[-1].strip() if lines else ""

def assert_output(src, expected):
    got = run(src)
    assert got == expected, f"Expected output {expected!r}, got {got!r}"

def assert_last_line(src, expected):
    got = run_val(src)
    assert got == expected, f"Expected last line {expected!r}, got {got!r}"

def assert_lines(src, expected_list):
    got = run_lines(src)
    assert got == expected_list, f"Expected {expected_list!r}, got {got!r}"

def assert_raises(src, error_substr=None):
    try:
        run(src)
        raise AssertionError(f"Expected error but got none")
    except AssertionError:
        raise
    except Exception as e:
        if error_substr and error_substr.lower() not in str(e).lower():
            raise AssertionError(f"Expected error containing {error_substr!r}, got {e}")

# ═══════════════════════════════════════════════════════════════
# 1. ARITHMETIC & OPERATORS (60 tests)
# ═══════════════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("\n=== Arithmetic & Operators ===")
    
    test("add_integers", lambda: assert_last_line('Print 2 + 3', '5'))
    test("sub_integers", lambda: assert_last_line('Print 10 - 4', '6'))
    test("mul_integers", lambda: assert_last_line('Print 3 * 7', '21'))
    test("div_integers", lambda: assert_last_line('Print 10 / 2', '5'))
    test("div_decimal", lambda: assert_last_line('Print 7 / 2', '3.5'))
    test("floor_div", lambda: assert_last_line('Print 7 // 2', '3'))
    test("modulo", lambda: assert_last_line('Print 10 % 3', '1'))
    test("power", lambda: assert_last_line('Print 2 ** 10', '1024'))
    test("negative_number", lambda: assert_last_line('Print -5', '-5'))
    test("float_add", lambda: assert_last_line('Print 1.5 + 2.5', '4.0'))
    test("float_sub", lambda: assert_last_line('Print 5.5 - 2.0', '3.5'))
    test("float_mul", lambda: assert_last_line('Print 2.5 * 4.0', '10.0'))
    test("float_div", lambda: assert_last_line('Print 7.5 / 2.5', '3.0'))
    test("mixed_arithmetic", lambda: assert_last_line('Print 2 + 3 * 4', '14'))
    test("paren_precedence", lambda: assert_last_line('Print (2 + 3) * 4', '20'))
    test("nested_parens", lambda: assert_last_line('Print ((2 + 3) * (4 - 1))', '15'))
    test("unary_minus_expr", lambda: assert_last_line('Print -(3 + 2)', '-5'))
    test("chain_add", lambda: assert_last_line('Print 1 + 2 + 3 + 4 + 5', '15'))
    test("chain_mul", lambda: assert_last_line('Print 1 * 2 * 3 * 4', '24'))
    test("zero_multiply", lambda: assert_last_line('Print 999 * 0', '0'))
    test("zero_add", lambda: assert_last_line('Print 0 + 0', '0'))
    test("large_number", lambda: assert_last_line('Print 999999 + 1', '1000000'))
    
    # Comparison operators
    test("gt_true", lambda: assert_last_line('Print 5 > 3', 'true'))
    test("gt_false", lambda: assert_last_line('Print 3 > 5', 'false'))
    test("lt_true", lambda: assert_last_line('Print 3 < 5', 'true'))
    test("lt_false", lambda: assert_last_line('Print 5 < 3', 'false'))
    test("gte_true", lambda: assert_last_line('Print 5 >= 5', 'true'))
    test("gte_false", lambda: assert_last_line('Print 4 >= 5', 'false'))
    test("lte_true", lambda: assert_last_line('Print 5 <= 5', 'true'))
    test("lte_false", lambda: assert_last_line('Print 6 <= 5', 'false'))
    test("eq_true", lambda: assert_last_line('Print 5 == 5', 'true'))
    test("eq_false", lambda: assert_last_line('Print 5 == 6', 'false'))
    test("neq_true", lambda: assert_last_line('Print 5 != 6', 'true'))
    test("neq_false", lambda: assert_last_line('Print 5 != 5', 'false'))
    
    # Logical operators
    test("and_tt", lambda: assert_last_line('Print true and true', 'true'))
    test("and_tf", lambda: assert_last_line('Print true and false', 'false'))
    test("and_ff", lambda: assert_last_line('Print false and false', 'false'))
    test("or_tt", lambda: assert_last_line('Print true or true', 'true'))
    test("or_tf", lambda: assert_last_line('Print true or false', 'true'))
    test("or_ff", lambda: assert_last_line('Print false or false', 'false'))
    test("not_true", lambda: assert_last_line('Print not true', 'false'))
    test("not_false", lambda: assert_last_line('Print not false', 'true'))
    test("complex_logical", lambda: assert_last_line('Print (true and false) or (not false)', 'true'))
    test("short_circuit_and", lambda: assert_last_line('Print false and true', 'false'))
    test("short_circuit_or", lambda: assert_last_line('Print true or false', 'true'))
    
    # Augmented assignment
    test("plus_assign", lambda: assert_last_line('x = 5\nx += 3\nPrint x', '8'))
    test("minus_assign", lambda: assert_last_line('x = 10\nx -= 4\nPrint x', '6'))
    test("mul_assign", lambda: assert_last_line('x = 3\nx *= 5\nPrint x', '15'))
    test("div_assign", lambda: assert_last_line('x = 20\nx /= 4\nPrint x', '5'))
    test("increase_by", lambda: assert_last_line('x = 10\nIncrease x by 5\nPrint x', '15'))
    test("decrease_by", lambda: assert_last_line('x = 10\nDecrease x by 3\nPrint x', '7'))
    
    # String operators
    test("str_concat", lambda: assert_last_line('Print "hello" + " " + "world"', 'hello world'))
    test("str_repeat", lambda: assert_last_line('Print "ab" * 3', 'ababab'))
    test("str_eq", lambda: assert_last_line('Print "abc" == "abc"', 'true'))
    test("str_neq", lambda: assert_last_line('Print "abc" != "def"', 'true'))
    test("int_to_str_concat", lambda: assert_last_line('Print "val=" + 42', 'val=42'))
    test("str_compare_gt", lambda: assert_last_line('Print "b" > "a"', 'true'))
    test("str_compare_lt", lambda: assert_last_line('Print "a" < "b"', 'true'))
    
    # Division by zero
    test("div_by_zero", lambda: assert_raises('Print 10 / 0', 'zero'))
    test("mod_by_zero", lambda: assert_raises('Print 10 % 0', 'zero'))
    test("floor_div_by_zero", lambda: assert_raises('Print 10 // 0', 'zero'))
    
    # ═══════════════════════════════════════════════════════════════
    # 2. VARIABLES & ASSIGNMENT (30 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Variables & Assignment ===")
    
    test("create_int", lambda: assert_last_line('Create x equal to 42\nPrint x', '42'))
    test("create_float", lambda: assert_last_line('Create x equal to 3.14\nPrint x', '3.14'))
    test("create_string", lambda: assert_last_line('Create x equal to "hello"\nPrint x', 'hello'))
    test("create_bool_true", lambda: assert_last_line('Create x equal to true\nPrint x', 'true'))
    test("create_bool_false", lambda: assert_last_line('Create x equal to false\nPrint x', 'false'))
    test("create_none", lambda: assert_last_line('Create x equal to nothing\nPrint x', 'nothing'))
    test("short_int", lambda: assert_last_line('x = 42\nPrint x', '42'))
    test("short_str", lambda: assert_last_line('msg = "Hello"\nPrint msg', 'Hello'))
    test("short_bool", lambda: assert_last_line('flag = true\nPrint flag', 'true'))
    test("set_variable", lambda: assert_last_line('x = 1\nSet x to 2\nPrint x', '2'))
    test("set_to_expr", lambda: assert_last_line('x = 1\nSet x to x + 10\nPrint x', '11'))
    test("multiple_vars", lambda: assert_last_line('x = 1\ny = 2\nPrint x + y', '3'))
    test("constant_value", lambda: assert_last_line('Constant PI = 3\nPrint PI', '3'))
    test("constant_float", lambda: assert_last_line('Constant TAU = 6.28\nPrint TAU', '6.28'))
    test("constant_string", lambda: assert_last_line('Constant MSG = "hi"\nPrint MSG', 'hi'))
    test("constant_reassign_fails", lambda: assert_raises('Constant X = 5\nSet X to 10', 'constant'))
    test("var_in_expr", lambda: assert_last_line('x = 5\ny = x * 2 + 1\nPrint y', '11'))
    test("swap_vars", lambda: assert_lines(
        'x = 1\ny = 2\ntmp = x\nSet x to y\nSet y to tmp\nPrint x\nPrint y',
        ['2', '1']))
    test("var_scope_global", lambda: assert_last_line('x = 10\nIf true then\nSet x to 20\nEnd\nPrint x', '20'))
    test("nested_expr_var", lambda: assert_last_line('x = (2 + 3) * (4 - 1)\nPrint x', '15'))
    test("chain_vars", lambda: assert_lines('x = 1\ny = 2\nz = 3\nPrint x\nPrint y\nPrint z', ['1', '2', '3']))
    test("var_bool_expr", lambda: assert_last_line('x = 5 > 3\nPrint x', 'true'))
    test("typed_create", lambda: assert_last_line('Create integer named x equal to 42\nPrint x', '42'))
    test("typed_reassign_fails", lambda: assert_raises(
        'Create integer named x equal to 5\nSet x to "hello"', 'cannot assign'))
    
    # ═══════════════════════════════════════════════════════════════
    # 3. CONTROL FLOW (40 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Control Flow ===")
    
    # If/Otherwise
    test("if_true", lambda: assert_output('If true then\nPrint "yes"\nEnd', 'yes'))
    test("if_false", lambda: assert_output('If false then\nPrint "yes"\nEnd', ''))
    test("if_otherwise", lambda: assert_output(
        'If false then\nPrint "no"\nOtherwise\nPrint "yes"\nEnd', 'yes'))
    test("if_nested", lambda: assert_output(
        'If true then\nIf true then\nPrint "deep"\nEnd\nEnd', 'deep'))
    test("if_with_expr", lambda: assert_output('x = 10\nIf x > 5 then\nPrint "big"\nEnd', 'big'))
    test("if_and", lambda: assert_output('If true and true then\nPrint "both"\nEnd', 'both'))
    test("if_or", lambda: assert_output('If false or true then\nPrint "one"\nEnd', 'one'))
    test("if_not", lambda: assert_output('If not false then\nPrint "negated"\nEnd', 'negated'))
    test("if_complex_cond", lambda: assert_output(
        'x = 5\nIf x >= 1 and x <= 10 then\nPrint "range"\nEnd', 'range'))
    test("if_no_then", lambda: assert_output('If true\nPrint "yes"\nEnd', 'yes'))
    
    # While loops
    test("while_basic", lambda: assert_last_line('i = 0\nWhile i < 3\nIncrease i by 1\nEnd\nPrint i', '3'))
    test("while_never_runs", lambda: assert_output('While false\nPrint "no"\nEnd', ''))
    test("while_break", lambda: assert_last_line(
        'i = 0\nWhile true\nIf i >= 5 then\nBreak\nEnd\nIncrease i by 1\nEnd\nPrint i', '5'))
    test("while_continue", lambda: assert_lines(
        'i = 0\nWhile i < 5\nIncrease i by 1\nIf i == 3 then\nContinue\nEnd\nPrint i\nEnd',
        ['1', '2', '4', '5']))
    
    # For loops
    test("for_basic", lambda: assert_lines('For i from 1 to 3\nPrint i\nEnd', ['1', '2', '3']))
    test("for_step", lambda: assert_lines('For i from 0 to 10 step 3\nPrint i\nEnd', ['0', '3', '6', '9']))
    test("for_with_break", lambda: assert_last_line(
        'last = 0\nFor i from 1 to 100\nIf i > 5 then\nBreak\nEnd\nSet last to i\nEnd\nPrint last', '5'))
    test("for_nested", lambda: assert_lines(
        'For i from 1 to 2\nFor j from 1 to 2\nPrint i * 10 + j\nEnd\nEnd',
        ['11', '12', '21', '22']))
    
    # Repeat loops
    test("repeat_basic", lambda: assert_lines('Repeat 3 times\nPrint "go"\nEnd', ['go', 'go', 'go']))
    test("repeat_zero", lambda: assert_output('Repeat 0 times\nPrint "no"\nEnd', ''))
    test("repeat_with_counter", lambda: assert_last_line(
        'count = 0\nRepeat 5 times\nIncrease count by 1\nEnd\nPrint count', '5'))
    
    # Match/When
    test("match_when_basic", lambda: assert_lines(
        'x = "B"\nMatch x\nWhen "A"\nPrint "one"\nWhen "B"\nPrint "two"\nWhen "C"\nPrint "three"\nEnd',
        ['two']))
    test("match_when_default", lambda: assert_lines(
        'x = "Z"\nMatch x\nWhen "A"\nPrint "one"\nDefault\nPrint "other"\nEnd',
        ['other']))
    test("match_int", lambda: assert_lines(
        'x = 2\nMatch x\nWhen 1\nPrint "one"\nWhen 2\nPrint "two"\nEnd', ['two']))
    test("match_no_hit", lambda: assert_output(
        'x = 99\nMatch x\nWhen 1\nPrint "one"\nEnd', ''))
    
    # for-each
    test("for_each_list", lambda: assert_lines(
        'items = [10, 20, 30]\nFor each item in items\nPrint item\nEnd',
        ['10', '20', '30']))
    
    # ═══════════════════════════════════════════════════════════════
    # 4. FUNCTIONS (40 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Functions ===")
    
    test("fn_no_args", lambda: assert_output(
        'Function hello\nPrint "hello"\nEnd\nCall hello', 'hello'))
    test("fn_one_arg", lambda: assert_last_line(
        'Function double takes n\nReturn n * 2\nEnd\nPrint double(5)', '10'))
    test("fn_two_args", lambda: assert_last_line(
        'Function add takes a and b\nReturn a + b\nEnd\nPrint add(3, 7)', '10'))
    test("fn_three_args", lambda: assert_last_line(
        'Function addThree takes x and y and z\nReturn x + y + z\nEnd\nPrint addThree(1, 2, 3)', '6'))
    test("fn_return_string", lambda: assert_last_line(
        'Function getName takes nothing\nReturn "Alice"\nEnd\nPrint getName()', 'Alice'))
    test("fn_return_bool", lambda: assert_last_line(
        'Function isEven takes n\nReturn n % 2 == 0\nEnd\nPrint isEven(4)', 'true'))
    test("fn_return_nothing", lambda: assert_last_line(
        'Function doStuff takes nothing\nx = 1\nEnd\nPrint doStuff()', 'nothing'))
    test("fn_recursive_factorial", lambda: assert_last_line(
        'Function fact takes n\nIf n <= 1 then\nReturn 1\nEnd\nReturn n * fact(n - 1)\nEnd\nPrint fact(5)', '120'))
    test("fn_recursive_fib", lambda: assert_last_line(
        'Function fib takes n\nIf n <= 1 then\nReturn n\nEnd\nReturn fib(n - 1) + fib(n - 2)\nEnd\nPrint fib(10)', '55'))
    test("fn_local_scope", lambda: assert_lines(
        'x = 10\nFunction setX takes nothing\nx = 99\nPrint x\nEnd\nCall setX\nPrint x',
        ['99', '10']))
    test("fn_closure_read", lambda: assert_last_line(
        'x = 42\nFunction getX takes nothing\nReturn x\nEnd\nPrint getX()', '42'))
    test("fn_call_in_expr", lambda: assert_last_line(
        'Function double takes n\nReturn n * 2\nEnd\nPrint double(3) + double(4)', '14'))
    test("fn_nested_calls", lambda: assert_last_line(
        'Function double takes n\nReturn n * 2\nEnd\nFunction quad takes n\nReturn double(double(n))\nEnd\nPrint quad(3)', '12'))
    test("fn_call_syntax", lambda: assert_output(
        'Function hello\nPrint "hi"\nEnd\nCall hello', 'hi'))
    test("fn_call_with", lambda: assert_last_line(
        'Function greet takes name\nPrint "Hello, " + name + "!"\nEnd\nCall greet with "EPL"', 'Hello, EPL!'))
    test("fn_return_call_with", lambda: assert_last_line(
        'Function add takes a and b\nReturn a + b\nEnd\nresult = call add with 3 and 4\nPrint result', '7'))
    test("fn_multiple_returns", lambda: assert_last_line(
        'Function absVal takes n\nIf n < 0 then\nReturn -n\nEnd\nReturn n\nEnd\nPrint absVal(-5)', '5'))
    test("fn_string_ops", lambda: assert_last_line(
        'Function greetName takes nm\nReturn "Hello " + nm\nEnd\nPrint greetName("World")', 'Hello World'))
    test("fn_bool_param", lambda: assert_last_line(
        'Function toggle takes b\nReturn not b\nEnd\nPrint toggle(true)', 'false'))
    test("fn_chain_results", lambda: assert_last_line(
        'Function inc takes n\nReturn n + 1\nEnd\nPrint inc(inc(inc(0)))', '3'))
    test("fn_with_loop", lambda: assert_last_line(
        'Function sumTo takes n\ntotal = 0\nFor i from 1 to n\nSet total to total + i\nEnd\nReturn total\nEnd\nPrint sumTo(10)', '55'))
    
    # Lambda
    test("lambda_basic", lambda: assert_last_line('double = lambda x -> x * 2\nPrint double(5)', '10'))
    test("lambda_multi", lambda: assert_last_line('add = lambda x, y -> x + y\nPrint add(3, 4)', '7'))
    test("lambda_no_args", lambda: assert_last_line('greet = lambda -> "Hello"\nPrint greet()', 'Hello'))
    test("given_basic", lambda: assert_last_line(
        'double = given x return x * 2\nPrint call double with 5', '10'))
    test("given_multi", lambda: assert_last_line(
        'add = given x, y return x + y\nPrint call add with 3 and 4', '7'))
    test("given_no_args", lambda: assert_last_line(
        'greet = given return "Hello"\nPrint call greet', 'Hello'))
    
    # ═══════════════════════════════════════════════════════════════
    # 5. CLASSES & OOP (45 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Classes & OOP ===")
    
    test("class_basic", lambda: assert_last_line(
        'Class Dog\nname = "Rex"\nEnd\nd = new Dog\nPrint d.name', 'Rex'))
    test("class_set_prop", lambda: assert_last_line(
        'Class Dog\nname = ""\nEnd\nd = new Dog\nd.name = "Buddy"\nPrint d.name', 'Buddy'))
    test("class_method", lambda: assert_last_line(
        'Class Calc\nFunction add takes a and b\nReturn a + b\nEnd\nEnd\nc = new Calc\nPrint c.add(3, 4)', '7'))
    test("class_constructor", lambda: assert_last_line(
        'Class Point\npx = 0\npy = 0\nFunction init takes x, y\nSet px to x\nSet py to y\nEnd\nEnd\npt = new Point(3, 4)\nPrint pt.px + pt.py', '7'))
    test("class_method_return", lambda: assert_last_line(
        'Class Holder\nval = 10\nFunction getVal takes nothing\nReturn val\nEnd\nEnd\nh = new Holder\nPrint h.getVal()', '10'))
    test("class_method_with_args", lambda: assert_last_line(
        'Class MathHelper\nbase = 0\nFunction init takes b\nSet base to b\nEnd\nFunction addTo takes n\nReturn base + n\nEnd\nEnd\nhelper = new MathHelper(10)\nPrint helper.addTo(5)', '15'))
    test("class_property_set", lambda: assert_last_line(
        'Class Box\nwidth = 0\nEnd\nbox = new Box\nbox.width = 50\nPrint box.width', '50'))
    test("class_multiple_instances", lambda: assert_lines(
        'Class Animal\nkind = ""\nFunction init takes k\nSet kind to k\nEnd\nEnd\ncat = new Animal("cat")\ndog = new Animal("dog")\nPrint cat.kind\nPrint dog.kind',
        ['cat', 'dog']))
    test("class_inheritance", lambda: assert_last_line(
        'Class Base\nFunction hello\nPrint "Hello from Base"\nEnd\nEnd\nClass Child extends Base\nEnd\nc = new Child\nc.hello()', 'Hello from Base'))
    test("class_override_method", lambda: assert_last_line(
        'Class Base\nFunction speak takes nothing\nReturn "base"\nEnd\nEnd\nClass Child extends Base\nFunction speak takes nothing\nReturn "child"\nEnd\nEnd\nobj = new Child\nPrint obj.speak()', 'child'))
    test("class_inherit_prop", lambda: assert_last_line(
        'Class Base\nx = 10\nEnd\nClass Child extends Base\ny = 20\nEnd\nc = new Child\nPrint c.x + c.y', '30'))
    test("class_this_in_method", lambda: assert_last_line(
        'Class Greeter\ngreeting = "Hi"\nFunction greet takes nm\nReturn greeting + " " + nm\nEnd\nEnd\ng = new Greeter\nPrint g.greet("World")', 'Hi World'))
    test("class_instance_independent", lambda: assert_lines(
        'Class Holder\nval = 0\nEnd\nh1 = new Holder\nh2 = new Holder\nh1.val = 10\nh2.val = 20\nPrint h1.val\nPrint h2.val',
        ['10', '20']))
    test("class_method_with_params", lambda: assert_last_line(
        'Class Adder\nFunction compute takes x and y\nReturn x + y\nEnd\nEnd\nadder = new Adder\nPrint adder.compute(7, 3)', '10'))
    test("class_empty", lambda: assert_last_line(
        'Class Empty\nEnd\nobj = new Empty\nPrint "ok"', 'ok'))
    
    # ═══════════════════════════════════════════════════════════════
    # 6. COLLECTIONS (35 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Collections ===")
    
    # Lists
    test("list_create", lambda: assert_last_line('items = [1, 2, 3]\nPrint items', '[1, 2, 3]'))
    test("list_empty", lambda: assert_last_line('items = []\nPrint items', '[]'))
    test("list_access", lambda: assert_last_line('items = [10, 20, 30]\nPrint items[0]', '10'))
    test("list_access_last", lambda: assert_last_line('items = [10, 20, 30]\nPrint items[2]', '30'))
    test("list_length", lambda: assert_last_line('Print length([1,2,3])', '3'))
    test("list_length_dot", lambda: assert_last_line('x = [1,2,3]\nPrint x.length', '3'))
    test("list_add", lambda: assert_last_line('items = [1, 2]\nAdd 3 to items\nPrint items', '[1, 2, 3]'))
    test("list_remove", lambda: assert_last_line('x = [1,2,3]\nx.remove(2)\nPrint x', '[1, 3]'))
    test("list_contains_true", lambda: assert_last_line('x = [1,2,3]\nPrint x.contains(2)', 'true'))
    test("list_contains_false", lambda: assert_last_line('x = [1,2,3]\nPrint x.contains(5)', 'false'))
    test("list_mixed_types", lambda: assert_last_line('items = [1, "hello", true]\nPrint items[1]', 'hello'))
    test("list_nested", lambda: assert_last_line('items = [[1, 2], [3, 4]]\nPrint items[0]', '[1, 2]'))
    test("list_for_each", lambda: assert_lines(
        'items = [10, 20, 30]\nFor each item in items\nPrint item\nEnd', ['10', '20', '30']))
    test("list_set_index", lambda: assert_last_line('items = [1, 2, 3]\nitems[1] = 99\nPrint items[1]', '99'))
    test("list_strings", lambda: assert_last_line('names = ["Alice", "Bob"]\nPrint names[0]', 'Alice'))
    test("list_booleans", lambda: assert_last_line('flags = [true, false, true]\nPrint flags[1]', 'false'))
    test("list_single", lambda: assert_last_line('items = [42]\nPrint items[0]', '42'))
    test("list_in_function", lambda: assert_last_line(
        'Function getList takes nothing\nReturn [1, 2, 3]\nEnd\nitems = getList()\nPrint items[2]', '3'))
    test("list_empty_length", lambda: assert_last_line('x = []\nPrint x.length', '0'))
    test("list_map_lambda", lambda: assert_last_line(
        'nums = [1, 2, 3]\nresult = nums.map(lambda x -> x * 2)\nPrint result', '[2, 4, 6]'))
    test("list_filter_lambda", lambda: assert_last_line(
        'nums = [1, 2, 3, 4, 5]\nresult = nums.filter(lambda x -> x > 3)\nPrint result', '[4, 5]'))
    test("list_reduce_lambda", lambda: assert_last_line(
        'nums = [1, 2, 3, 4]\nresult = nums.reduce(lambda a, b -> a + b, 0)\nPrint result', '10'))
    test("list_find_lambda", lambda: assert_last_line(
        'nums = [1, 2, 3, 4]\nresult = nums.find(lambda x -> x > 2)\nPrint result', '3'))
    test("list_sort", lambda: assert_last_line(
        'x = [3, 1, 4, 1, 5]\nx.sort()\nPrint x', '[1, 1, 3, 4, 5]'))
    test("list_reverse", lambda: assert_last_line(
        'x = [1, 2, 3]\nx.reverse()\nPrint x', '[3, 2, 1]'))
    test("list_every", lambda: assert_last_line('Print [2, 4, 6].every(lambda x -> x % 2 == 0)', 'true'))
    test("list_some", lambda: assert_last_line('Print [1, 2, 3].some(lambda x -> x > 2)', 'true'))
    
    # Maps
    test("map_create", lambda: assert_last_line(
        'p = Map with name = "Alice"\nPrint p.name', 'Alice'))
    test("map_set", lambda: assert_last_line(
        'p = Map with val = 0\np.val = 42\nPrint p.val', '42'))
    test("map_multiple_keys", lambda: assert_last_line(
        'p = Map with x = 1 and y = 2\nPrint p.x + p.y', '3'))
    test("map_length", lambda: assert_last_line(
        'p = Map with a = 1 and b = 2 and c = 3\nPrint p.length', '3'))
    
    # ═══════════════════════════════════════════════════════════════
    # 7. ERROR HANDLING (20 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Error Handling ===")
    
    test("try_catch_basic", lambda: assert_last_line(
        'Try\nPrint 10 / 0\nCatch e\nPrint "caught"\nEnd', 'caught'))
    test("try_no_error", lambda: assert_output(
        'Try\nPrint "ok"\nCatch e\nPrint "error"\nEnd', 'ok'))
    test("try_error_var", lambda: assert_true(
        run_val('Try\nx = 10 / 0\nCatch e\nPrint "Error: " + e\nEnd').startswith('Error:')))
    test("try_finally", lambda: assert_lines(
        'Try\nPrint "try"\nCatch e\nPrint "catch"\nFinally\nPrint "finally"\nEnd',
        ['try', 'finally']))
    test("try_catch_finally_error", lambda: assert_lines(
        'Try\nThrow "oops"\nCatch e\nPrint "caught"\nFinally\nPrint "done"\nEnd',
        ['caught', 'done']))
    test("nested_try_catch", lambda: assert_true(
        'outer ok' in run('Try\nTry\nPrint 10/0\nCatch e\nPrint "inner caught"\nEnd\nPrint "outer ok"\nCatch e\nPrint "outer catch"\nEnd')))
    test("throw_custom_message", lambda: assert_raises(
        'Throw "Something went wrong"', 'Something went wrong'))
    test("assert_true_passes", lambda: assert_output('Assert 1 + 1 == 2', ''))
    test("assert_false_fails", lambda: assert_raises('Assert 1 == 2', 'assertion'))
    test("assert_expr", lambda: assert_output('Assert 5 > 3', ''))
    test("assert_eq_pass", lambda: assert_output('Assert 1 + 1 == 2', ''))
    test("undefined_var_error", lambda: assert_raises('Print undefined_xyz', ''))
    test("type_error_arith", lambda: assert_raises(
        'Create integer named x equal to 5\nSet x to "hello"', ''))
    
    # ═══════════════════════════════════════════════════════════════
    # 8. STRING METHODS (20 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== String Methods ===")
    
    test("str_length_fn", lambda: assert_last_line('Print length("hello")', '5'))
    test("str_length_dot", lambda: assert_last_line('name = "hello"\nPrint name.length', '5'))
    test("str_upper", lambda: assert_last_line('name = "hello"\nPrint name.uppercase', 'HELLO'))
    test("str_lower", lambda: assert_last_line('name = "HELLO"\nPrint name.lowercase', 'hello'))
    test("str_upper_fn", lambda: assert_last_line('Print uppercase("hello")', 'HELLO'))
    test("str_lower_fn", lambda: assert_last_line('Print lowercase("HELLO")', 'hello'))
    test("str_contains", lambda: assert_last_line('name = "Hello World"\nPrint name.contains("World")', 'true'))
    test("str_not_contains", lambda: assert_last_line('name = "Hello"\nPrint name.contains("xyz")', 'false'))
    test("str_empty", lambda: assert_last_line('x = ""\nPrint x.length', '0'))
    test("str_index", lambda: assert_last_line('Print "hello"[0]', 'h'))
    test("str_index_last", lambda: assert_last_line('Print "hello"[4]', 'o'))
    test("str_multiword", lambda: assert_last_line('Print "hello" + " " + "world"', 'hello world'))
    test("str_number_concat", lambda: assert_last_line('Print "count: " + 42', 'count: 42'))
    test("str_repeat_op", lambda: assert_last_line('Print "ab" * 3', 'ababab'))
    test("str_equality", lambda: assert_last_line('Print "abc" == "abc"', 'true'))
    test("str_inequality", lambda: assert_last_line('Print "abc" != "xyz"', 'true'))
    test("str_bool_concat", lambda: assert_last_line('Print "val: " + true', 'val: true'))
    test("str_in_list", lambda: assert_last_line('items = ["a", "b", "c"]\nPrint items[1]', 'b'))
    
    # ═══════════════════════════════════════════════════════════════
    # 9. SPECIAL FEATURES (25 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Special Features ===")
    
    # Type checking via function
    test("type_of_int", lambda: assert_last_line('Print type_of(42)', 'integer'))
    test("type_of_str", lambda: assert_last_line('Print type_of("hello")', 'text'))
    test("type_of_bool", lambda: assert_last_line('Print type_of(true)', 'boolean'))
    test("type_of_list", lambda: assert_last_line('x = [1,2]\nPrint type_of(x)', 'list'))
    
    # Ternary
    test("ternary_true", lambda: assert_last_line('x = 10 if true otherwise 20\nPrint x', '10'))
    test("ternary_false", lambda: assert_last_line('x = 10 if false otherwise 20\nPrint x', '20'))
    test("ternary_with_expr", lambda: assert_last_line(
        'n = 5\nPrint "big" if n > 3 otherwise "small"', 'big'))
    
    # Print format
    test("print_format", lambda: assert_last_line('Print "Result: " + (2 + 3)', 'Result: 5'))
    
    # NoteBlock (comments)
    test("noteblock", lambda: assert_lines(
        'NoteBlock\nThis is ignored\nSo is this\nEnd\nPrint "ok"', ['ok']))
    
    # Multiline programs
    test("complex_program_1", lambda: assert_last_line(
        'total = 0\nFor i from 1 to 10\nSet total to total + i\nEnd\nPrint total', '55'))
    test("complex_program_2", lambda: assert_last_line(
        'Function isPrime takes n\nIf n < 2 then\nReturn false\nEnd\ni = 2\nWhile i * i <= n\nIf n % i == 0 then\nReturn false\nEnd\nIncrease i by 1\nEnd\nReturn true\nEnd\nPrint isPrime(7)', 'true'))
    test("complex_program_prime_false", lambda: assert_last_line(
        'Function isPrime takes n\nIf n < 2 then\nReturn false\nEnd\ni = 2\nWhile i * i <= n\nIf n % i == 0 then\nReturn false\nEnd\nIncrease i by 1\nEnd\nReturn true\nEnd\nPrint isPrime(4)', 'false'))
    test("complex_sort", lambda: assert_last_line(
        'x = [5, 3, 1, 4, 2]\nx.sort()\nPrint x', '[1, 2, 3, 4, 5]'))
    test("complex_map_doubled", lambda: assert_last_line(
        'items = [1, 2, 3, 4, 5]\ndoubled = items.map(lambda x -> x * 2)\nPrint doubled', '[2, 4, 6, 8, 10]'))
    
    # Enum (inline)
    test("enum_basic", lambda: assert_last_line('Enum Color as Red, Green, Blue\nPrint Color.Red', '0'))
    test("enum_access", lambda: assert_last_line('Enum Status as Open, Closed, Pending\nPrint Status.Pending', '2'))
    
    # Higher-order functions
    test("higher_order_fn", lambda: assert_last_line(
        'Define a function named apply that takes fn, value\nReturn fn(value)\nEnd\ndouble = lambda x -> x * 2\nPrint apply(double, 5)', '10'))
    test("combined_filter_map", lambda: assert_last_line(
        'nums = [1, 2, 3, 4, 5, 6]\nresult = nums.filter(lambda x -> x % 2 == 0).map(lambda x -> x ** 2)\nPrint result', '[4, 16, 36]'))
    
    # ═══════════════════════════════════════════════════════════════
    # 10. EDGE CASES (20 tests)
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Edge Cases ===")
    
    test("empty_string_var", lambda: assert_last_line('x = ""\nPrint x.length', '0'))
    test("zero_value", lambda: assert_last_line('x = 0\nPrint x', '0'))
    test("negative_var", lambda: assert_last_line('x = -42\nPrint x', '-42'))
    test("bool_in_arithmetic", lambda: assert_last_line('Print true + true', '2'))
    test("float_precision", lambda: assert_true(
        '0.3' in run_val('Print 0.1 + 0.2') or '0.300' in run_val('Print 0.1 + 0.2')))
    test("large_loop", lambda: assert_last_line(
        'total = 0\nFor i from 1 to 1000\nSet total to total + 1\nEnd\nPrint total', '1000'))
    test("deeply_nested_if", lambda: assert_output(
        'If true then\nIf true then\nIf true then\nIf true then\nPrint "deep"\nEnd\nEnd\nEnd\nEnd', 'deep'))
    test("string_with_spaces", lambda: assert_last_line('Print "hello   world"', 'hello   world'))
    test("print_nothing", lambda: assert_last_line('Print nothing', 'nothing'))
    test("print_multiple_lines", lambda: assert_lines('Print 1\nPrint 2\nPrint 3', ['1', '2', '3']))
    test("power_of_zero", lambda: assert_last_line('Print 0 ** 0', '1'))
    test("power_of_one", lambda: assert_last_line('Print 5 ** 0', '1'))
    test("string_of_numbers", lambda: assert_last_line('Print "123"', '123'))
    test("bool_comparison", lambda: assert_last_line('Print true == true', 'true'))
    test("nested_function_calls", lambda: assert_last_line(
        'Function inc takes n\nReturn n + 1\nEnd\nFunction double takes n\nReturn n * 2\nEnd\nPrint double(inc(4))', '10'))
    test("list_in_condition", lambda: assert_last_line(
        'items = [1, 2, 3]\nIf items.length > 0 then\nPrint "nonempty"\nEnd', 'nonempty'))
    test("old_period_syntax", lambda: assert_lines('Print "Hello".', ['Hello']))
    test("string_number_val", lambda: assert_last_line('Print "Age: " + 20', 'Age: 20'))
    
    # ═══════════════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"Comprehensive Interpreter Tests: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    print(f"{'='*60}")
    return FAILED == 0


def test_interpreter_comprehensive_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Interpreter comprehensive suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
