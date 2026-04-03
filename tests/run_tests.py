"""Quick test runner for EPL v0.2 (simplified syntax, Windows-compatible)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.errors import EPLError


def run(src):
    l = Lexer(src)
    t = l.tokenize()
    p = Parser(t)
    prog = p.parse()
    i = Interpreter()
    i.execute(prog)
    return i.output_lines


def test_err(src, substr):
    try:
        run(src)
        return False
    except EPLError as e:
        return substr.lower() in str(e).lower()
    except Exception:
        return False


tests = [
    # --- Print (no periods!) ---
    ("print_hello", lambda: run('Print "Hello, World!"') == ["Hello, World!"]),
    ("print_int", lambda: run("Print 42") == ["42"]),
    ("print_dec", lambda: run("Print 3.14") == ["3.14"]),
    ("print_bool", lambda: run("Print true") == ["true"]),
    ("print_none", lambda: run("Print nothing") == ["nothing"]),

    # --- Shorthand variables (x = value) ---
    ("short_int", lambda: run("x = 42\nPrint x") == ["42"]),
    ("short_str", lambda: run('msg = "Hello"\nPrint msg') == ["Hello"]),
    ("short_dec", lambda: run("pi = 3.14\nPrint pi") == ["3.14"]),
    ("short_bool", lambda: run("flag = true\nPrint flag") == ["true"]),

    # --- Create still works ---
    ("create_typed", lambda: run('Create integer named x equal to 42\nPrint x') == ["42"]),
    ("create_infer", lambda: run('Create name equal to "EPL"\nPrint name') == ["EPL"]),

    # --- Set variable ---
    ("set_var", lambda: run("x = 1\nSet x to 2\nPrint x") == ["2"]),

    # --- Arithmetic ---
    ("add", lambda: run("Print 5 + 3") == ["8"]),
    ("sub", lambda: run("Print 10 - 4") == ["6"]),
    ("mul", lambda: run("Print 6 * 7") == ["42"]),
    ("div_exact", lambda: run("Print 10 / 2") == ["5"]),
    ("div_dec", lambda: run("Print 7 / 2") == ["3.5"]),
    ("mod", lambda: run("Print 10 % 3") == ["1"]),
    ("precedence", lambda: run("Print 2 + 3 * 4") == ["14"]),
    ("parens", lambda: run("Print (2 + 3) * 4") == ["20"]),
    ("negative", lambda: run("Print -5") == ["-5"]),
    ("str_concat", lambda: run('Print "Hello" + " " + "World"') == ["Hello World"]),
    ("str_num", lambda: run('Print "Age: " + 20') == ["Age: 20"]),

    # --- Comparisons ---
    ("gt_sym", lambda: run('If 10 > 5 then\n    Print "yes"\nEnd') == ["yes"]),
    ("lt_sym", lambda: run('If 3 < 8 then\n    Print "yes"\nEnd') == ["yes"]),
    ("eq_sym", lambda: run('If 5 == 5 then\n    Print "yes"\nEnd') == ["yes"]),
    ("ne_sym", lambda: run('If 5 != 3 then\n    Print "yes"\nEnd') == ["yes"]),
    ("gt_eng", lambda: run('x = 10\nIf x is greater than 5 then\n    Print "yes"\nEnd') == ["yes"]),
    ("lt_eng", lambda: run('x = 3\nIf x is less than 8 then\n    Print "yes"\nEnd') == ["yes"]),
    ("eq_eng", lambda: run('x = 5\nIf x is equal to 5 then\n    Print "yes"\nEnd') == ["yes"]),

    # --- Control Flow ---
    ("if_then", lambda: run('If true then\n    Print "yes"\nEnd') == ["yes"]),
    ("if_else", lambda: run('If false then\n    Print "yes"\nOtherwise\n    Print "no"\nEnd') == ["no"]),
    ("nested_if", lambda: run('x = 85\nIf x > 90 then\n    Print "A"\nOtherwise\n    If x > 80 then\n        Print "B"\n    Otherwise\n        Print "C"\n    End\nEnd') == ["B"]),

    # --- Loops ---
    ("repeat", lambda: run('Repeat 3 times\n    Print "hi"\nEnd') == ["hi", "hi", "hi"]),
    ("while", lambda: run('i = 0\nWhile i < 3\n    Print i\n    Increase i by 1\nEnd') == ["0", "1", "2"]),
    ("foreach", lambda: run('items = [1, 2, 3]\nFor each item in items\n    Print item\nEnd') == ["1", "2", "3"]),
    ("inc_dec", lambda: run('x = 5\nIncrease x by 3\nPrint x\nDecrease x by 2\nPrint x') == ["8", "6"]),

    # --- Functions (short syntax) ---
    ("func_simple", lambda: run('Function hello\n    Print "Hi!"\nEnd\nCall hello') == ["Hi!"]),
    ("func_param", lambda: run('Function greet takes name\n    Print "Hello, " + name + "!"\nEnd\nCall greet with "EPL"') == ["Hello, EPL!"]),
    ("func_return", lambda: run('Function add takes a and b\n    Return a + b\nEnd\nresult = call add with 3 and 4\nPrint result') == ["7"]),
    ("recursive", lambda: run('Function fact takes n\n    If n <= 1 then\n        Return 1\n    End\n    Return n * (call fact with n - 1)\nEnd\nPrint call fact with 5') == ["120"]),

    # --- Old syntax still works (backward compatible) ---
    ("old_period", lambda: run('Print "Hello".') == ["Hello"]),
    ("old_end_if", lambda: run('If true then\n    Print "yes".\nEnd if.') == ["yes"]),
    ("old_create", lambda: run('Create integer named x equal to 5.\nPrint x.') == ["5"]),

    # --- Error handling ---
    ("err_undef", lambda: test_err("Print x", "not been created")),
    ("err_div0", lambda: test_err("Print 10 / 0", "divide by zero")),
    ("err_type", lambda: test_err('Create integer named x equal to 5\nSet x to "hello"', "cannot assign")),

    # === v0.2: Built-in Functions ===
    ("bi_length_str", lambda: run('Print length("Hello")') == ["5"]),
    ("bi_length_list", lambda: run('Print length([1,2,3])') == ["3"]),
    ("bi_type_of", lambda: run('Print type_of(42)') == ["integer"]),
    ("bi_to_int", lambda: run('Print to_integer("42")') == ["42"]),
    ("bi_to_text", lambda: run('Print to_text(3.14)') == ["3.14"]),
    ("bi_to_dec", lambda: run('Print to_decimal("2.5")') == ["2.5"]),
    ("bi_abs", lambda: run('Print absolute(-10)') == ["10"]),
    ("bi_round", lambda: run('Print round(3.7)') == ["4"]),
    ("bi_max", lambda: run('Print max(5, 9)') == ["9"]),
    ("bi_min", lambda: run('Print min(5, 9)') == ["5"]),
    ("bi_upper", lambda: run('Print uppercase("hello")') == ["HELLO"]),
    ("bi_lower", lambda: run('Print lowercase("HELLO")') == ["hello"]),

    # === v0.2: String Methods (dot notation) ===
    ("str_upper", lambda: run('name = "hello"\nPrint name.uppercase') == ["HELLO"]),
    ("str_lower", lambda: run('name = "HELLO"\nPrint name.lowercase') == ["hello"]),
    ("str_len", lambda: run('name = "Hello"\nPrint name.length') == ["5"]),
    ("str_trim", lambda: run('name = "  hi  "\nPrint name.trim') == ["hi"]),
    ("str_contains", lambda: run('name = "Hello World"\nPrint name.contains("World")') == ["true"]),
    ("str_replace", lambda: run('name = "Hello World"\nPrint name.replace("World", "EPL")') == ["Hello EPL"]),
    ("str_starts", lambda: run('name = "Hello"\nPrint name.starts_with("He")') == ["true"]),
    ("str_ends", lambda: run('name = "Hello"\nPrint name.ends_with("lo")') == ["true"]),
    ("str_split", lambda: run('s = "a-b-c"\nPrint s.split("-")') == ["[a, b, c]"]),
    ("str_substr", lambda: run('s = "Hello"\nPrint s.substring(0, 3)') == ["Hel"]),

    # === v0.2: List Methods ===
    ("list_add", lambda: run('x = [1,2]\nx.add(3)\nPrint x') == ["[1, 2, 3]"]),
    ("list_remove", lambda: run('x = [1,2,3]\nx.remove(2)\nPrint x') == ["[1, 3]"]),
    ("list_contains", lambda: run('x = [1,2,3]\nPrint x.contains(2)') == ["true"]),
    ("list_sort", lambda: run('x = [3,1,2]\nx.sort()\nPrint x') == ["[1, 2, 3]"]),
    ("list_reverse", lambda: run('x = [1,2,3]\nx.reverse()\nPrint x') == ["[3, 2, 1]"]),
    ("list_join", lambda: run('x = ["a","b","c"]\nPrint x.join(", ")') == ["a, b, c"]),
    ("list_len", lambda: run('x = [1,2,3]\nPrint x.length') == ["3"]),

    # === v0.2: File I/O ===
    ("file_write_read", lambda: (
        run('Write "test123" to file "test_tmp.txt"\nx = Read file "test_tmp.txt"\nPrint x') == ["test123"]
    )),

    # === v0.2: Classes & OOP ===
    ("class_basic", lambda: run('Class Dog\n    name = "Rex"\nEnd\nd = new Dog\nPrint d.name') == ["Rex"]),
    ("class_set_prop", lambda: run('Class Dog\n    name = ""\nEnd\nd = new Dog\nd.name = "Buddy"\nPrint d.name') == ["Buddy"]),
    ("class_method", lambda: run('Class Calc\n    Function add takes a and b\n        Return a + b\n    End\nEnd\nc = new Calc\nPrint c.add(3, 4)') == ["7"]),
    ("class_state", lambda: run('Class Animal\n    name = ""\n    sound = ""\n    Function speak\n        Print name + " says " + sound\n    End\nEnd\na = new Animal\na.name = "Rex"\na.sound = "Woof"\na.speak()') == ["Rex says Woof"]),

    # === v0.2: Parentheses function call syntax ===
    ("func_paren", lambda: run('Function add takes a and b\n    Return a + b\nEnd\nPrint add(3, 4)') == ["7"]),

    # === v0.3: String Templates ===
    ("tpl_basic", lambda: run('name = "World"\nPrint "Hello, $name"') == ["Hello, World"]),
    ("tpl_multi", lambda: run('name = "EPL"\nver = 3\nPrint "$name version $ver"') == ["EPL version 3"]),
    ("tpl_expr", lambda: run('x = 42\nPrint "Answer: $x"') == ["Answer: 42"]),
    ("tpl_none", lambda: run('Print "No vars here"') == ["No vars here"]),

    # === v0.3: Break ===
    ("break_while", lambda: run('i = 0\nWhile i < 10\n    If i == 3 then\n        Break\n    End\n    Print i\n    Increase i by 1\nEnd') == ["0", "1", "2"]),
    ("break_repeat", lambda: run('i = 0\nRepeat 10 times\n    If i == 2 then\n        Break\n    End\n    Print i\n    Increase i by 1\nEnd') == ["0", "1"]),

    # === v0.3: Continue ===
    ("continue_while", lambda: run('i = 0\nWhile i < 5\n    Increase i by 1\n    If i == 3 then\n        Continue\n    End\n    Print i\nEnd') == ["1", "2", "4", "5"]),

    # === v0.3: Try/Catch ===
    ("try_catch", lambda: run('Try\n    Print 10 / 0\nCatch e\n    Print "caught"\nEnd') == ["caught"]),
    ("try_ok", lambda: run('Try\n    Print "ok"\nCatch e\n    Print "error"\nEnd') == ["ok"]),
    ("try_var", lambda: run('Try\n    x = 10 / 0\nCatch e\n    Print "Error: " + e\nEnd')[0].startswith("Error:")),

    # === v0.3: Match/When ===
    ("match_basic", lambda: run('x = "B"\nMatch x\n    When "A"\n        Print "one"\n    When "B"\n        Print "two"\n    When "C"\n        Print "three"\nEnd') == ["two"]),
    ("match_default", lambda: run('x = "Z"\nMatch x\n    When "A"\n        Print "one"\n    Default\n        Print "other"\nEnd') == ["other"]),
    ("match_int", lambda: run('x = 2\nMatch x\n    When 1\n        Print "one"\n    When 2\n        Print "two"\nEnd') == ["two"]),
    ("match_no_hit", lambda: run('x = 99\nMatch x\n    When 1\n        Print "one"\nEnd') == []),

    # === v0.3: Dictionaries (Map) ===
    ("map_create", lambda: run('p = Map with name = "Abneesh" and age = 20\nPrint p.name') == ["Abneesh"]),
    ("map_set", lambda: run('p = Map with x = 1\np.x = 42\nPrint p.x') == ["42"]),
    ("map_access", lambda: run('p = Map with a = 10 and b = 20\nPrint p.a + p.b') == ["30"]),
    ("map_keys", lambda: run('p = Map with x = 1 and y = 2\nk = p.keys()\nPrint k') == ["[x, y]"]),
    ("map_has", lambda: run('p = Map with name = "test"\nPrint p.has("name")') == ["true"]),
    ("map_length", lambda: run('p = Map with a = 1 and b = 2 and c = 3\nPrint p.length') == ["3"]),
    ("map_foreach", lambda: run('p = Map with a = 1 and b = 2\nFor each key in p\n    Print key\nEnd') == ["a", "b"]),

    # === v0.3: Class Inheritance ===
    ("inherit_basic", lambda: run('Class Animal\n    name = ""\n    Function speak\n        Print name + " makes a sound"\n    End\nEnd\nClass Dog extends Animal\n    Function speak\n        Print name + " says Woof"\n    End\nEnd\nd = new Dog\nd.name = "Rex"\nd.speak()') == ["Rex says Woof"]),
    ("inherit_parent_method", lambda: run('Class Base\n    Function hello\n        Print "Hello from Base"\n    End\nEnd\nClass Child extends Base\nEnd\nc = new Child\nc.hello()') == ["Hello from Base"]),
    ("inherit_prop", lambda: run('Class Base\n    x = 10\nEnd\nClass Child extends Base\n    y = 20\nEnd\nc = new Child\nPrint c.x + c.y') == ["30"]),

    # === v0.3: Index Access ===
    ("idx_read", lambda: run('items = [10, 20, 30]\nPrint items[0]') == ["10"]),
    ("idx_read2", lambda: run('items = [10, 20, 30]\nPrint items[2]') == ["30"]),
    ("idx_set", lambda: run('items = [1, 2, 3]\nitems[1] = 99\nPrint items') == ["[1, 99, 3]"]),
    ("idx_str", lambda: run('name = "Hello"\nPrint name[0]') == ["H"]),
    ("idx_expr", lambda: run('items = [10, 20, 30]\ni = 1\nPrint items[i]') == ["20"]),

    # === v0.3: For Range Loop ===
    ("for_range", lambda: run('For i from 1 to 5\n    Print i\nEnd') == ["1", "2", "3", "4", "5"]),
    ("for_range_sum", lambda: run('total = 0\nFor i from 1 to 10\n    Increase total by i\nEnd\nPrint total') == ["55"]),

    # === v0.3: Otherwise If ===
    ("else_if", lambda: run('x = 85\nIf x > 90 then\n    Print "A"\nOtherwise if x > 80 then\n    Print "B"\nOtherwise\n    Print "C"\nEnd') == ["B"]),
    ("else_if_first", lambda: run('x = 95\nIf x > 90 then\n    Print "A"\nOtherwise if x > 80 then\n    Print "B"\nEnd') == ["A"]),
    ("else_if_last", lambda: run('x = 50\nIf x > 90 then\n    Print "A"\nOtherwise if x > 80 then\n    Print "B"\nOtherwise\n    Print "C"\nEnd') == ["C"]),

    # === v0.3: Import ===
    ("import_file", lambda: run('Import "tests/test_helper.epl"\nPrint square(5)') == ["25"]),

    # === v0.3: Use Python ===
    ("use_math", lambda: run('Use python "math"\nPrint math.sqrt(144)') == ["12.0"]),
    ("use_math_pi", lambda: (
        float(run('Use python "math"\nPrint math.pi')[0]) > 3.14
    )),

    # === v0.3: Constants ===
    ("const_def", lambda: run('Constant PI = 3.14\nPrint PI') == ["3.14"]),
    ("const_err", lambda: test_err('Constant X = 10\nX = 20', "constant")),

    # === v0.3: Assert ===
    ("assert_pass", lambda: run('Assert 1 + 1 == 2') == []),
    ("assert_fail", lambda: test_err('Assert 1 == 2', "assertion")),

    # === v0.3: NoteBlock ===
    ("noteblock", lambda: run('NoteBlock\n    This is ignored\n    So is this\nEnd\nPrint "ok"') == ["ok"]),

    # === v0.3: Exit ===
    ("exit_early", lambda: run('Print "before"\nExit\nPrint "after"') == ["before"]),

    # ═══════════════════════════════════════════════════════
    # === v0.6: Power Features ===
    # ═══════════════════════════════════════════════════════

    # --- Power operator ** ---
    ("power_op", lambda: run('Print 2 ** 3') == ["8"]),
    ("power_op_float", lambda: run('Print 9 ** 0.5') == ["3.0"]),
    ("power_right_assoc", lambda: run('Print 2 ** 3 ** 2') == ["512"]),

    # --- Floor division // ---
    ("floor_div", lambda: run('Print 7 // 2') == ["3"]),
    ("floor_div_neg", lambda: run('Print -7 // 2') == ["-4"]),
    ("floor_div_float", lambda: run('Print 7.5 // 2') == ["3.0"]),

    # --- Augmented assignment +=, -=, *=, /=, %= ---
    ("aug_plus", lambda: run('x = 10\nx += 5\nPrint x') == ["15"]),
    ("aug_minus", lambda: run('x = 10\nx -= 3\nPrint x') == ["7"]),
    ("aug_mul", lambda: run('x = 4\nx *= 3\nPrint x') == ["12"]),
    ("aug_div", lambda: run('x = 20\nx /= 4\nPrint x') == ["5"]),
    ("aug_mod", lambda: run('x = 10\nx %= 3\nPrint x') == ["1"]),
    ("aug_plus_str", lambda: run('x = "Hello"\nx += " World"\nPrint x') == ["Hello World"]),
    ("aug_plus_list", lambda: run('x = [1, 2]\nx += 3\nPrint x') == ["[1, 2, 3]"]),

    # --- Lambda expressions ---
    ("lambda_basic", lambda: run('double = lambda x -> x * 2\nPrint double(5)') == ["10"]),
    ("lambda_multi", lambda: run('add = lambda x, y -> x + y\nPrint add(3, 4)') == ["7"]),
    ("lambda_no_args", lambda: run('greet = lambda -> "Hello"\nPrint greet()') == ["Hello"]),

    # --- Ternary expression ---
    ("ternary_true", lambda: run('x = 10\nresult = "big" if x > 5 otherwise "small"\nPrint result') == ["big"]),
    ("ternary_false", lambda: run('x = 2\nresult = "big" if x > 5 otherwise "small"\nPrint result') == ["small"]),
    ("ternary_inline", lambda: run('Print 1 if true otherwise 0') == ["1"]),

    # --- List slicing ---
    ("slice_basic", lambda: run('nums = [1, 2, 3, 4, 5]\nPrint nums[1:3]') == ["[2, 3]"]),
    ("slice_from_start", lambda: run('nums = [1, 2, 3, 4, 5]\nPrint nums[:3]') == ["[1, 2, 3]"]),
    ("slice_to_end", lambda: run('nums = [1, 2, 3, 4, 5]\nPrint nums[2:]') == ["[3, 4, 5]"]),
    ("slice_with_step", lambda: run('nums = [1, 2, 3, 4, 5]\nPrint nums[0:5:2]') == ["[1, 3, 5]"]),
    ("slice_string", lambda: run('s = "Hello"\nPrint s[1:4]') == ["ell"]),

    # --- For range with step ---
    ("for_step", lambda: run('For i from 0 to 10 step 2\n    Print i\nEnd') == ["0", "2", "4", "6", "8", "10"]),
    ("for_step_down", lambda: run('For i from 5 to 1 step -1\n    Print i\nEnd') == ["5", "4", "3", "2", "1"]),

    # --- Enum ---
    ("enum_def", lambda: run('Enum Color as Red, Green, Blue\nPrint Color.Red') == ["0"]),
    ("enum_access", lambda: run('Enum Status as Open, Closed, Pending\nPrint Status.Pending') == ["2"]),

    # --- Throw ---
    ("throw_basic", lambda: test_err('Throw "Something went wrong"', "Something went wrong")),
    ("throw_catch", lambda: run('Try\n    Throw "oops"\nCatch error\n    Print error\nEnd') == ["EPL Runtime Error on line 2: oops"]),

    # --- Math builtins ---
    ("sqrt_fn", lambda: run('Print sqrt(16)') == ["4.0"]),
    ("power_fn", lambda: run('Print power(2, 10)') == ["1024"]),
    ("floor_fn", lambda: run('Print floor(3.7)') == ["3"]),
    ("ceil_fn", lambda: run('Print ceil(3.2)') == ["4"]),

    # --- Collection builtins ---
    ("range_fn", lambda: run('Print range(5)') == ["[0, 1, 2, 3, 4]"]),
    ("range_fn2", lambda: run('Print range(2, 5)') == ["[2, 3, 4]"]),
    ("sum_fn", lambda: run('Print sum([1, 2, 3, 4])') == ["10"]),
    ("sorted_fn", lambda: run('Print sorted([3, 1, 2])') == ["[1, 2, 3]"]),
    ("reversed_fn", lambda: run('Print reversed([1, 2, 3])') == ["[3, 2, 1]"]),
    ("reversed_str", lambda: run('Print reversed("abc")') == ["cba"]),

    # --- Type checking builtins ---
    ("is_integer", lambda: run('Print is_integer(42)') == ["true"]),
    ("is_integer_false", lambda: run('Print is_integer(3.14)') == ["false"]),
    ("is_decimal", lambda: run('Print is_decimal(3.14)') == ["true"]),
    ("is_text", lambda: run('Print is_text("hi")') == ["true"]),
    ("is_boolean", lambda: run('Print is_boolean(true)') == ["true"]),
    ("is_list", lambda: run('Print is_list([1, 2])') == ["true"]),
    ("is_nothing", lambda: run('Print is_nothing(nothing)') == ["true"]),
    ("is_number_int", lambda: run('Print is_number(42)') == ["true"]),
    ("is_number_dec", lambda: run('Print is_number(3.14)') == ["true"]),

    # --- Utility builtins ---
    ("typeof_fn", lambda: run('Print typeof(42)') == ["integer"]),
    ("char_code_fn", lambda: run('Print char_code("A")') == ["65"]),
    ("from_char_code_fn", lambda: run('Print from_char_code(65)') == ["A"]),
    ("json_parse_fn", lambda: run('data = json_parse("{\\\"x\\\": 1}")\nPrint data.x') == ["1"]),
    ("json_str_fn", lambda: run('m = Map with name = "EPL"\nPrint json_stringify(m)') == ['{"name": "EPL"}']),

    # --- New string methods ---
    ("str_find", lambda: run('Print "Hello World".find("World")') == ["6"]),
    ("str_index_of", lambda: run('Print "abcabc".index_of("bc")') == ["1"]),
    ("str_count", lambda: run('Print "abcabc".count("a")') == ["2"]),
    ("str_repeat", lambda: run('x = "ha"\nPrint x.repeat(3)') == ["hahaha"]),
    ("str_reverse", lambda: run('Print "Hello".reverse()') == ["olleH"]),
    ("str_pad_left", lambda: run('Print "42".pad_left(5, "0")') == ["00042"]),
    ("str_pad_right", lambda: run('Print "Hi".pad_right(5, ".")') == ["Hi..."]),
    ("str_is_number", lambda: run('Print "123".is_number()') == ["true"]),
    ("str_is_alpha", lambda: run('Print "Hello".is_alpha()') == ["true"]),
    ("str_is_empty", lambda: run('Print "".is_empty()') == ["true"]),
    ("str_char_at", lambda: run('Print "Hello".char_at(0)') == ["H"]),
    ("str_to_list", lambda: run('Print "abc".to_list()') == ["[a, b, c]"]),
    ("str_format", lambda: run('Print "Hello {} and {}".format("A", "B")') == ["Hello A and B"]),

    # --- New list methods ---
    ("list_map", lambda: run('nums = [1, 2, 3]\nresult = nums.map(lambda x -> x * 2)\nPrint result') == ["[2, 4, 6]"]),
    ("list_filter", lambda: run('nums = [1, 2, 3, 4, 5]\nresult = nums.filter(lambda x -> x > 3)\nPrint result') == ["[4, 5]"]),
    ("list_reduce", lambda: run('nums = [1, 2, 3, 4]\nresult = nums.reduce(lambda a, b -> a + b, 0)\nPrint result') == ["10"]),
    ("list_find", lambda: run('nums = [1, 2, 3, 4]\nresult = nums.find(lambda x -> x > 2)\nPrint result') == ["3"]),
    ("list_index_of", lambda: run('Print [10, 20, 30].index_of(20)') == ["1"]),
    ("list_count", lambda: run('Print [1, 2, 1, 3, 1].count(1)') == ["3"]),
    ("list_flatten", lambda: run('Print [[1, 2], [3, 4], [5]].flatten()') == ["[1, 2, 3, 4, 5]"]),
    ("list_unique", lambda: run('Print [1, 2, 2, 3, 3, 3].unique()') == ["[1, 2, 3]"]),
    ("list_every", lambda: run('Print [2, 4, 6].every(lambda x -> x % 2 == 0)') == ["true"]),
    ("list_some", lambda: run('Print [1, 2, 3].some(lambda x -> x > 2)') == ["true"]),
    ("list_sum", lambda: run('Print [1, 2, 3].sum()') == ["6"]),
    ("list_min_max", lambda: run('Print [3, 1, 2].min()\nPrint [3, 1, 2].max()') == ["1", "3"]),
    ("list_first_last", lambda: run('Print [10, 20, 30].first()\nPrint [10, 20, 30].last()') == ["10", "30"]),
    ("list_insert", lambda: run('nums = [1, 3]\nnums.insert(1, 2)\nPrint nums') == ["[1, 2, 3]"]),
    ("list_copy", lambda: run('a = [1, 2, 3]\nb = a.copy()\nb.add(4)\nPrint a\nPrint b') == ["[1, 2, 3]", "[1, 2, 3, 4]"]),
    ("list_slice", lambda: run('Print [1, 2, 3, 4, 5].slice(1, 4)') == ["[2, 3, 4]"]),

    # --- New map methods ---
    ("map_entries", lambda: run('m = Map with x = 1 and y = 2\nPrint m.entries()') == ["[[x, 1], [y, 2]]"]),
    ("map_get", lambda: run('m = Map with x = 1\nPrint m.get("x")\nPrint m.get("y", 0)') == ["1", "0"]),
    ("map_set", lambda: run('m = Map with x = 1\nm.set("y", 2)\nPrint m.y') == ["2"]),
    ("map_clear", lambda: run('m = Map with x = 1 and y = 2\nm.clear()\nPrint length(m)') == ["0"]),
    ("map_copy", lambda: run('m = Map with x = 1\nm2 = m.copy()\nm2.set("y", 2)\nPrint m.has("y")\nPrint m2.has("y")') == ["false", "true"]),
    ("map_merge", lambda: run('a = Map with x = 1\nb = Map with y = 2\nc = a.merge(b)\nPrint c.x\nPrint c.y') == ["1", "2"]),

    # --- Higher-order functions ---
    ("higher_order_fn", lambda: run('Define a function named apply that takes fn, value\n    Return fn(value)\nEnd\n\ndouble = lambda x -> x * 2\nPrint apply(double, 5)') == ["10"]),

    # --- Combined power features ---
    ("combined_filter_map", lambda: run('nums = [1, 2, 3, 4, 5, 6]\nresult = nums.filter(lambda x -> x % 2 == 0).map(lambda x -> x ** 2)\nPrint result') == ["[4, 16, 36]"]),

    # ─── v0.7: English Simplicity ──────────────────────────

    # Say (alias for Print)
    ("say_basic", lambda: run('Say "Hello World"') == ["Hello World"]),
    ("say_expr", lambda: run('x = 10\nSay x') == ["10"]),
    ("say_multi", lambda: run('Say "Hi"\nSay "Bye"') == ["Hi", "Bye"]),

    # Remember (alias for Create)
    ("remember_int", lambda: run('Remember age as 25\nPrint age') == ["25"]),
    ("remember_str", lambda: run('Remember name as "Alice"\nSay name') == ["Alice"]),
    ("remember_list", lambda: run('Remember items as [1, 2, 3]\nSay items') == ["[1, 2, 3]"]),

    # raised to (English alias for **)
    ("raised_to_basic", lambda: run('x = 2 raised to 3\nPrint x') == ["8"]),
    ("raised_to_expr", lambda: run('Print 3 raised to 2') == ["9"]),
    ("raised_to_chain", lambda: run('Print 2 raised to 10') == ["1024"]),

    # is between
    ("between_true", lambda: run('x = 5\nIf x is between 1 and 10 then\n  Print "yes"\nEnd') == ["yes"]),
    ("between_false", lambda: run('x = 15\nIf x is between 1 and 10 then\n  Print "yes"\nOtherwise\n  Print "no"\nEnd') == ["no"]),
    ("between_edge_low", lambda: run('x = 1\nIf x is between 1 and 10 then\n  Print "yes"\nEnd') == ["yes"]),
    ("between_edge_high", lambda: run('x = 10\nIf x is between 1 and 10 then\n  Print "yes"\nEnd') == ["yes"]),

    # Add X to list
    ("add_to_list", lambda: run('items = [1, 2]\nAdd 3 to items\nPrint items') == ["[1, 2, 3]"]),
    ("add_str_to_list", lambda: run('names = ["Alice"]\nAdd "Bob" to names\nPrint names') == ['[Alice, Bob]']),

    # Sort list
    ("sort_list", lambda: run('nums = [3, 1, 2]\nSort nums\nPrint nums') == ["[1, 2, 3]"]),
    ("sort_str_list", lambda: run('names = ["Charlie", "Alice", "Bob"]\nSort names\nPrint names') == ['[Alice, Bob, Charlie]']),

    # Reverse list
    ("reverse_list", lambda: run('nums = [1, 2, 3]\nReverse nums\nPrint nums') == ["[3, 2, 1]"]),

    # Combined English features
    ("english_combo", lambda: run('Remember scores as [5, 3, 8, 1]\nAdd 10 to scores\nSort scores\nSay scores') == ["[1, 3, 5, 8, 10]"]),
    ("english_math", lambda: run('Remember base as 2\nRemember result as base raised to 4\nSay result') == ["16"]),

    # Ensure keywords still work as variable names
    ("add_as_var", lambda: run('add = 5\nPrint add') == ["5"]),
    ("sort_as_var", lambda: run('sort = "hello"\nPrint sort') == ["hello"]),
    ("reverse_as_var", lambda: run('reverse = [1, 2]\nPrint reverse') == ["[1, 2]"]),

    # ─── v0.7.1: Simplified Operators ──────────────────────

    # mod (English alias for %)
    ("mod_basic", lambda: run('Print 10 mod 3') == ["1"]),
    ("mod_expr", lambda: run('x = 17\nPrint x mod 5') == ["2"]),
    ("mod_zero", lambda: run('Print 10 mod 2') == ["0"]),

    # equals (English alias for ==)
    ("equals_true", lambda: run('x = 5\nIf x equals 5 then\n  Print "yes"\nEnd') == ["yes"]),
    ("equals_false", lambda: run('x = 3\nIf x equals 5 then\n  Print "yes"\nOtherwise\n  Print "no"\nEnd') == ["no"]),
    ("equals_str", lambda: run('name = "Alice"\nIf name equals "Alice" then\n  Print "hi"\nEnd') == ["hi"]),

    # not equals (English alias for !=)
    ("not_equals_true", lambda: run('x = 3\nIf x not equals 5 then\n  Print "yes"\nEnd') == ["yes"]),
    ("not_equals_false", lambda: run('x = 5\nIf x not equals 5 then\n  Print "yes"\nOtherwise\n  Print "no"\nEnd') == ["no"]),

    # does not equal (English alias for !=)
    ("does_not_equal", lambda: run('x = 10\nIf x does not equal 5 then\n  Print "yes"\nEnd') == ["yes"]),

    # at least (English alias for >=)
    ("at_least_true", lambda: run('age = 18\nIf age at least 18 then\n  Print "adult"\nEnd') == ["adult"]),
    ("at_least_eq", lambda: run('age = 18\nIf age at least 18 then\n  Print "yes"\nEnd') == ["yes"]),
    ("at_least_false", lambda: run('age = 17\nIf age at least 18 then\n  Print "yes"\nOtherwise\n  Print "no"\nEnd') == ["no"]),

    # is at least (with "is" prefix)
    ("is_at_least", lambda: run('score = 90\nIf score is at least 90 then\n  Print "A"\nEnd') == ["A"]),

    # at most (English alias for <=)
    ("at_most_true", lambda: run('tries = 2\nIf tries at most 3 then\n  Print "ok"\nEnd') == ["ok"]),
    ("at_most_false", lambda: run('tries = 5\nIf tries at most 3 then\n  Print "ok"\nOtherwise\n  Print "too many"\nEnd') == ["too many"]),

    # is at most (with "is" prefix)
    ("is_at_most", lambda: run('x = 3\nIf x is at most 5 then\n  Print "ok"\nEnd') == ["ok"]),

    # Multiply X by Y (English *=)
    ("multiply_by", lambda: run('x = 5\nMultiply x by 3\nPrint x') == ["15"]),
    ("multiply_by_dec", lambda: run('x = 10.0\nMultiply x by 0.5\nPrint x') == ["5.0"]),

    # Divide X by Y (English /=)
    ("divide_by", lambda: run('x = 20.0\nDivide x by 4\nPrint x') == ["5.0"]),
    ("divide_by_int", lambda: run('x = 15.0\nDivide x by 3\nPrint x') == ["5.0"]),

    # given ... return (English lambda)
    ("given_basic", lambda: run('double = given x return x * 2\nPrint call double with 5') == ["10"]),
    ("given_multi", lambda: run('add = given x, y return x + y\nPrint call add with 3 and 4') == ["7"]),
    ("given_no_args", lambda: run('greet = given return "Hello"\nPrint call greet') == ["Hello"]),
    ("given_with_arrow", lambda: run('triple = given x -> x * 3\nPrint call triple with 4') == ["12"]),

    # yes/no (English aliases for true/false)
    ("yes_bool", lambda: run('x = yes\nPrint x') == ["true"]),
    ("no_bool", lambda: run('x = no\nPrint x') == ["false"]),
    ("yes_in_if", lambda: run('active = yes\nIf active equals yes then\n  Print "on"\nEnd') == ["on"]),

    # Keywords as variable names (regression tests)
    ("multiply_as_var", lambda: run('multiply = 7\nPrint multiply') == ["7"]),
    ("divide_as_var", lambda: run('divide = 10\nPrint divide') == ["10"]),
    ("given_as_var", lambda: run('given = 42\nPrint given') == ["42"]),
    ("mod_as_var", lambda: run('mod = 3\nPrint mod') == ["3"]),
    ("equals_as_var", lambda: run('equals = "same"\nPrint equals') == ["same"]),
]

passed = 0
failed = 0
fail_names = []

for name, test_fn in tests:
    try:
        result = test_fn()
        if result:
            print(f"  PASS: {name}")
            passed += 1
        else:
            print(f"  FAIL: {name}")
            failed += 1
            fail_names.append(name)
    except Exception as e:
        print(f"  FAIL: {name} -- {type(e).__name__}: {e}")
        failed += 1
        fail_names.append(name)

total = passed + failed
print(f"\nResults: {passed}/{total} passed, {failed} failed")
if fail_names:
    print(f"Failed: {', '.join(fail_names)}")
else:
    print("All tests passed!")
