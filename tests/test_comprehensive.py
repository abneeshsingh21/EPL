"""Comprehensive tests for JS transpiler, web framework, and additional stdlib coverage."""

import sys, os, tempfile, json, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter
from epl.js_transpiler import JSTranspiler, transpile_to_js, transpile_to_node

PASSED = 0
FAILED = 0

def run_epl(source):
    interp = Interpreter()
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp.execute(program)
    return interp.output_lines

def parse_epl(source):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()

def transpile(source):
    return transpile_to_js(parse_epl(source))

def test(name, actual, expected):
    global PASSED, FAILED
    try:
        if actual == expected:
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {actual}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
        FAILED += 1
test.__test__ = False

def test_contains(name, text, substring):
    global PASSED, FAILED
    if substring in text:
        print(f"  PASS: {name}")
        PASSED += 1
    else:
        print(f"  FAIL: {name}")
        print(f"    Expected substring: {substring}")
        print(f"    Got: {text[:200]}")
        FAILED += 1
test_contains.__test__ = False

def test_epl(name, source, expected):
    global PASSED, FAILED
    try:
        result = run_epl(source)
        if result == expected:
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {result}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
        FAILED += 1
test_epl.__test__ = False


# ═══════════════════════════════════════════════════════
# JS Transpiler Tests
# ═══════════════════════════════════════════════════════

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("=== JS Transpiler - Basic ===")
    
    test_contains("js_var_decl", transpile('Create x equal to 5.'), 'let x = 5;')
    test("js_var_assign", 'x = 10;' in transpile('x = 5.\nx = 10.'), True)
    test_contains("js_print", transpile('Print "hello".'), 'console.log("hello");')
    test("js_if",
         'if' in transpile('If x > 5 then\n    Print "yes".\nEnd.'),
         True)
    test("js_while",
         'while' in transpile('While x > 0\n    x = x - 1.\nEnd.'),
         True)
    test("js_for_range",
         'for' in transpile('For i from 1 to 10\n    Print i.\nEnd.'),
         True)
    test("js_for_each",
         'for' in transpile('For each item in items\n    Print item.\nEnd.'),
         True)
    
    print("\n=== JS Transpiler - Functions ===")
    
    js_func = transpile('Function add takes a and b\n    Return a + b.\nEnd Function.')
    test_contains("js_func_def", js_func, "function add(a, b)")
    test_contains("js_func_return", js_func, "return (a + b)")
    
    # Default parameters
    js_default = transpile('Function greet takes name, greeting = "Hello"\n    Print greeting.\nEnd Function.')
    test_contains("js_default_param", js_default, 'greeting = "Hello"')
    
    js_default2 = transpile('Function calc takes a, b = 10, c = 20\n    Return a + b + c.\nEnd Function.')
    test_contains("js_multi_defaults", js_default2, 'b = 10')
    test_contains("js_multi_defaults2", js_default2, 'c = 20')
    
    print("\n=== JS Transpiler - Classes ===")
    
    js_class = transpile(
        'Class Animal\n'
        '    name = "unknown"\n'
        '    Function speak\n'
        '        Print name.\n'
        '    End\n'
        'End'
    )
    test_contains("js_class_def", js_class, "class Animal")
    test_contains("js_class_constructor", js_class, "constructor()")
    test_contains("js_class_prop", js_class, 'this.name = "unknown"')
    test_contains("js_class_method", js_class, "speak()")
    
    print("\n=== JS Transpiler - Expressions ===")
    
    test_contains("js_binary_op", transpile('Print 1 + 2.'), "(1 + 2)")
    test_contains("js_and_op", transpile('Print true and false.'), "&&")
    test_contains("js_or_op", transpile('Print true or false.'), "||")
    test_contains("js_eq_op", transpile('If x == 5 then\n    Print x.\nEnd.'), "===")
    test_contains("js_neq_op", transpile('If x != 5 then\n    Print x.\nEnd.'), "!==")
    
    # String interpolation -> template literals
    js_interp = transpile('Create name equal to "World".\nPrint "Hello $name".')
    test_contains("js_interpolation", js_interp, "`Hello ${name}`")
    
    print("\n=== JS Transpiler - Builtins ===")
    
    test_contains("js_length", transpile('Print length("hello").'), ".length")
    test_contains("js_to_integer", transpile('Print to_integer("5").'), "parseInt")
    test_contains("js_to_text", transpile('Print to_text(5).'), "String(")
    test_contains("js_sqrt", transpile('Print sqrt(9).'), "Math.sqrt(")
    test_contains("js_floor", transpile('Print floor(3.7).'), "Math.floor(")
    test_contains("js_ceil", transpile('Print ceil(3.2).'), "Math.ceil(")
    test_contains("js_power", transpile('Print power(2, 3).'), "Math.pow(")
    test_contains("js_random", transpile('Print random().'), "Math.random()")
    test_contains("js_sorted", transpile('Print sorted(items).'), ".sort(")
    test_contains("js_range", transpile('Create r equal to range(5).'), "Array.from(")
    
    print("\n=== JS Transpiler - Stdlib Mappings ===")
    
    test_contains("js_now", transpile('Print now().'), "new Date().toISOString()")
    test_contains("js_today", transpile('Print today().'), "new Date().toISOString().slice(0, 10)")
    test_contains("js_uuid", transpile('Print uuid().'), "crypto.randomUUID()")
    test_contains("js_base64_encode", transpile('Print base64_encode("hi").'), "btoa(")
    test_contains("js_base64_decode", transpile('Print base64_decode("aGk=").'), "atob(")
    test_contains("js_regex_test", transpile('Print regex_test("a", "abc").'), "new RegExp(")
    test_contains("js_pi", transpile('Print pi().'), "Math.PI")
    test_contains("js_euler", transpile('Print euler().'), "Math.E")
    test_contains("js_sign", transpile('Print sign(-1).'), "Math.sign(")
    test_contains("js_is_finite", transpile('Print is_finite(5).'), "Number.isFinite(")
    test_contains("js_url_encode", transpile('Print url_encode("hi there").'), "encodeURIComponent(")
    test_contains("js_url_decode", transpile('Print url_decode("hi%20there").'), "decodeURIComponent(")
    test_contains("js_print_error", transpile('print_error("oops").'), "console.error(")
    test_contains("js_platform", transpile('Print platform().'), "process.platform")
    
    print("\n=== JS Transpiler - Control Flow ===")
    
    # Match/switch
    js_match = transpile(
        'x = 1\n'
        'Match x\n'
        '    When 1\n'
        '        Print "one"\n'
        '    When 2\n'
        '        Print "two"\n'
        '    Default\n'
        '        Print "other"\n'
        'End'
    )
    test_contains("js_match_switch", js_match, "switch")
    test_contains("js_match_case", js_match, "case 1")
    test_contains("js_match_default", js_match, "default:")
    
    # Try/Catch
    js_try = transpile(
        'Try\n'
        '    Print "try".\n'
        'Catch e\n'
        '    Print e.\n'
        'End.'
    )
    test_contains("js_try_catch", js_try, "try {")
    test_contains("js_catch_var", js_try, "catch (e)")
    
    # Throw
    js_throw = transpile('Throw "error message".')
    test_contains("js_throw", js_throw, "throw new Error(")
    
    # Break/Continue
    js_break = transpile('While true\n    Break.\nEnd.')
    test_contains("js_break", js_break, "break;")
    js_cont = transpile('While true\n    Continue.\nEnd.')
    test_contains("js_continue", js_cont, "continue;")
    
    print("\n=== JS Transpiler - Methods ===")
    
    # Method calls
    js_method = transpile('Create items equal to [1, 2, 3].\nitems.add(4).')
    test_contains("js_method_add", js_method, ".push(4)")
    
    # The remove fix
    js_remove = transpile('Create items equal to [1, 2, 3].\nitems.remove(2).')
    test_contains("js_method_remove_indexOf", js_remove, ".indexOf(2)")
    
    # Property access
    js_prop = transpile('Create n equal to items.length.')
    test_contains("js_prop_length", js_prop, ".length")
    
    print("\n=== JS Transpiler - Special ===")
    
    # Node.js target
    js_node = transpile_to_node(parse_epl('Print "hello".'))
    test_contains("js_node_header", js_node, "Node.js target")
    test_contains("js_node_generated", js_node, "Generated by EPL Compiler v3.0")
    
    # Enum
    js_enum = transpile('Enum Color as RED, GREEN, BLUE')
    test_contains("js_enum", js_enum, "Object.freeze")
    test_contains("js_enum_member", js_enum, "RED: 0")
    
    # Lambda
    js_lambda = transpile('Create fn equal to lambda x -> x + 1.')
    test_contains("js_lambda", js_lambda, "(x) =>")
    
    # Const
    js_const = transpile('Constant PI = 3.14.')
    test_contains("js_const", js_const, "const PI = 3.14")
    
    # File ops
    js_fwrite = transpile_to_node(parse_epl('Write "hello" to file "test.txt".'))
    test_contains("js_file_write", js_fwrite, 'writeFileSync')
    js_fappend = transpile_to_node(parse_epl('Append "line" to file "test.txt".'))
    test_contains("js_file_append", js_fappend, 'appendFileSync')
    
    # Assert
    js_assert = transpile('Assert 1 == 1.')
    test_contains("js_assert", js_assert, "console.assert")
    
    # Augmented assignment
    js_aug = transpile('x = 5.\nx += 3.')
    test_contains("js_aug_assign", js_aug, "+= 3")
    
    # Wait
    js_wait = transpile('Wait 1 seconds.')
    test_contains("js_wait", js_wait, "setTimeout")
    
    # Index set/get
    js_idx = transpile('Create items equal to [1,2,3].\nitems[0] = 99.')
    test_contains("js_index_set", js_idx, "[0] = 99")
    
    
    # ═══════════════════════════════════════════════════════
    # Additional Stdlib Tests
    # ═══════════════════════════════════════════════════════
    print("\n=== Stdlib - DateTime ===")
    
    test_epl("date_format",
        'Create t equal to "2024-01-15T10:30:00".\n'
        'Create d equal to date_format(t, "%Y-%m-%d").\n'
        'Print d.',
        ['2024-01-15'])
    
    test_epl("date_year",
        'Create y equal to year("2024-06-15T10:00:00").\nPrint y.',
        ['2024'])
    
    test_epl("date_month",
        'Create m equal to month("2024-06-15T10:00:00").\nPrint m.',
        ['6'])
    
    test_epl("date_day",
        'Create d equal to day("2024-06-15T10:00:00").\nPrint d.',
        ['15'])
    
    test_epl("is_leap_year_true",
        'Print is_leap_year(2024).',
        ['true'])
    
    test_epl("is_leap_year_false",
        'Print is_leap_year(2023).',
        ['false'])
    
    test_epl("days_in_month",
        'Print days_in_month(2024, 2).',
        ['29'])
    
    print("\n=== Stdlib - Crypto ===")
    
    test_epl("hash_md5",
        'Create h equal to hash_md5("hello").\nPrint h.',
        ['5d41402abc4b2a76b9719d911017c592'])
    
    test_epl("hash_sha512_contains",
        'Create h equal to hash_sha512("hello").\nPrint length(h).',
        ['128'])
    
    print("\n=== Stdlib - FileSystem ===")
    
    test_epl("temp_file",
        'Create f equal to temp_file().\nPrint file_exists(f).',
        ['true'])
    
    test_epl("path_split",
        'Create parts equal to path_split("/home/user/file.txt").\n'
        'Print parts.',
        ['[/home/user, file.txt]'])
    
    test_epl("path_absolute",
        'Create p equal to path_absolute(".").\nPrint length(p) > 0.',
        ['true'])
    
    print("\n=== Stdlib - Collections ===")
    
    test_epl("set_create",
        'Create s equal to set_create(1, 2, 2, 3, 3).\nPrint length(s).',
        ['3'])
    
    test_epl("set_add",
        'Create s equal to set_create(1, 2).\n'
        'Create s2 equal to set_add(s, 3).\n'
        'Print length(s2).',
        ['3'])
    
    test_epl("set_contains_true",
        'Create s equal to set_create(1, 2, 3).\nPrint set_contains(s, 2).',
        ['true'])
    
    test_epl("set_contains_false",
        'Create s equal to set_create(1, 2, 3).\nPrint set_contains(s, 5).',
        ['false'])
    
    test_epl("set_intersection",
        'Create s1 equal to set_create(1, 2, 3).\n'
        'Create s2 equal to set_create(2, 3, 4).\n'
        'Create s3 equal to set_intersection(s1, s2).\n'
        'Print length(s3).',
        ['2'])
    
    test_epl("set_difference",
        'Create s1 equal to set_create(1, 2, 3).\n'
        'Create s2 equal to set_create(2, 3, 4).\n'
        'Create s3 equal to set_difference(s1, s2).\n'
        'Print length(s3).',
        ['1'])
    
    print("\n=== Stdlib - Math ===")
    
    test_epl("atan",
        'Create r equal to atan(1).\nPrint r > 0.',
        ['true'])
    
    test_epl("asin",
        'Create r equal to asin(0.5).\nPrint r > 0.',
        ['true'])
    
    test_epl("acos",
        'Create r equal to acos(0.5).\nPrint r > 0.',
        ['true'])
    
    test_epl("degrees",
        'Print degrees(pi()).',
        ['180.0'])
    
    test_epl("radians",
        'Create r equal to radians(180).\nPrint r > 3.',
        ['true'])
    
    test_epl("lcm",
        'Print lcm(4, 6).',
        ['12'])
    
    test_epl("lerp",
        'Print lerp(0, 10, 0.5).',
        ['5.0'])
    
    test_epl("is_finite_true",
        'Print is_finite(42).',
        ['true'])
    
    test_epl("factorial_zero",
        'Print factorial(0).',
        ['1'])
    
    test_epl("factorial_large",
        'Print factorial(12).',
        ['479001600'])
    
    print("\n=== Stdlib - Strings & Encoding ===")
    
    test_epl("hex_encode",
        'Create h equal to hex_encode("AB").\nPrint h.',
        ['4142'])
    
    test_epl("hex_decode",
        'Create d equal to hex_decode("4142").\nPrint d.',
        ['AB'])
    
    test_epl("regex_escape",
        'Create e equal to regex_escape("hello.world").\nPrint e.',
        ['hello\\.world'])
    
    print("\n=== Stdlib - URL ===")
    
    test_epl("url_parse",
        'Create u equal to url_parse("https://example.com:8080/path?q=1").\n'
        'Print u.',
        ['{scheme: https, host: example.com, port: 8080, path: /path, query: q=1, fragment: }'])
    
    print("\n=== Stdlib - System ===")
    
    test_epl("timer",
        'Create t equal to timer_start("test").\n'
        'Create elapsed equal to timer_stop("test").\n'
        'Print elapsed >= 0.',
        ['true'])
    
    test_epl("memory_usage",
        'Create m equal to memory_usage().\nPrint m > 0.',
        ['true'])
    
    print("\n=== Stdlib - CSV ===")
    
    test_epl("csv_parse",
        'Create data equal to csv_parse("a,b,c\\n1,2,3").\n'
        'Print length(data).',
        ['1'])
    
    print("\n=== Stdlib - Database Advanced ===")
    
    test_epl("db_create_table_string",
        'Create db equal to db_open(":memory:").\n'
        'db_create_table(db, "users", Map with name = "TEXT" and age = "INTEGER").\n'
        'db_execute(db, "INSERT INTO users VALUES (?, ?)", ["Alice", 30]).\n'
        'Create row equal to db_query_one(db, "SELECT * FROM users").\n'
        'Print row.\n'
        'db_close(db).',
        ['{name: Alice, age: 30}'])
    
    test_epl("db_insert_func",
        'Create db equal to db_open(":memory:").\n'
        'db_execute(db, "CREATE TABLE t (a TEXT, b INT)").\n'
        'Create id equal to db_insert(db, "t", Map with a = "hello" and b = 42).\n'
        'Print id.',
        ['1'])
    
    # ═══════════════════════════════════════════════════════
    # Edge Cases
    # ═══════════════════════════════════════════════════════
    print("\n=== Edge Cases ===")
    
    test_epl("default_param_expr",
        'Function f takes a, b = 2 + 3\n'
        '    Print a + b.\n'
        'End Function.\n'
        'Call f with 10.',
        ['15'])
    
    test_epl("interp_nested",
        'Create x equal to 3.\n'
        'Create y equal to 4.\n'
        'Print "Result: ${x * y + 1}".',
        ['Result: 13'])
    
    test_epl("multiline_preserve_newlines",
        'Create s equal to """line1\nline2\nline3""".\n'
        'Print s.',
        ['line1\nline2\nline3'])
    
    test_epl("escape_dollar",
        'Print "Price: \\$5".',
        ['Price: $5'])
    
    test_epl("empty_list_ops",
        'Create items equal to [].\nPrint length(items).',
        ['0'])
    
    test_epl("nested_function_default",
        'Function outer takes x = 1\n'
        '    Function inner takes y = 2\n'
        '        Return x + y.\n'
        '    End Function.\n'
        '    Return inner().\n'
        'End Function.\n'
        'Print outer().',
        ['3'])
    
    
    # ═══════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    print(f"Results: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    if FAILED:
        print(f"  {FAILED} test(s) failed!")
    else:
        print("All tests passed!")
    return FAILED == 0


def test_comprehensive_suite():
    result = subprocess.run(
        [sys.executable, __file__],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise AssertionError(f"Comprehensive suite failed:\n{output}")


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
