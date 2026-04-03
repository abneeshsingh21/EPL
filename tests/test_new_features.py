"""Tests for new EPL features: stdlib, default params, interpolation, multi-line strings."""

import sys, os
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter


def run_epl(source):
    interp = Interpreter()
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp.execute(program)
    return interp.output_lines


PASSED = 0
FAILED = 0

def test(name, source, expected):
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




test.__test__ = False

def test_contains(name, source, substring):
    global PASSED, FAILED
    try:
        result = run_epl(source)
        if any(substring in line for line in result):
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected substring: {substring}")
            print(f"    Got: {result}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
        FAILED += 1




test_contains.__test__ = False

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("=== Default Parameters ===")
    test("default_basic",
         'Function greet takes name, greeting = "Hello"\n'
         '    Print "$greeting, $name!".\n'
         'End Function.\n'
         'Call greet with "World".',
         ['Hello, World!'])
    
    test("default_override",
         'Function greet takes name, greeting = "Hello"\n'
         '    Print "$greeting, $name!".\n'
         'End Function.\n'
         'Call greet with "EPL" and "Hi".',
         ['Hi, EPL!'])
    
    test("default_number",
         'Function add takes a, b = 10\n'
         '    Print a + b.\n'
         'End Function.\n'
         'Call add with 5.\n'
         'Call add with 5 and 20.',
         ['15', '25'])
    
    test("default_multiple",
         'Function f takes a, b = 2, c = 3\n'
         '    Print a + b + c.\n'
         'End Function.\n'
         'Call f with 1.\n'
         'Call f with 1 and 4.\n'
         'Call f with 1 and 4 and 5.',
         ['6', '8', '10'])
    
    
    print("\n=== String Interpolation ${expr} ===")
    test("interp_simple",
         'Create x equal to 5.\nCreate y equal to 10.\nPrint "Sum is ${x + y}".',
         ['Sum is 15'])
    
    test("interp_function",
         'Create s equal to "hello".\nPrint "Length is ${length(s)}".',
         ['Length is 5'])
    
    test("interp_math",
         'Print "Result: ${2 * 3 + 1}".',
         ['Result: 7'])
    
    test("interp_mixed",
         'Create name equal to "World".\nPrint "Hello $name, ${1 + 1} times!".',
         ['Hello World, 2 times!'])
    
    
    print("\n=== Multi-line Strings ===")
    # Multi-line string
    src_ml = 'Create msg equal to """Line 1\nLine 2\nLine 3""".\nPrint msg.'
    test("multiline_with_print",
         src_ml,
         ['Line 1\nLine 2\nLine 3'])
    
    
    print("\n=== Standard Library: DateTime ===")
    test_contains("now",
                  'Print now().',
                  '202')
    
    test_contains("today",
                  'Print today().',
                  '202')
    
    
    print("\n=== Standard Library: Crypto ===")
    test("sha256",
         'Print hash_sha256("hello").',
         ['2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'])
    
    test("md5",
         'Print hash_md5("hello").',
         ['5d41402abc4b2a76b9719d911017c592'])
    
    test("base64_encode",
         'Print base64_encode("Hello World").',
         ['SGVsbG8gV29ybGQ='])
    
    test("base64_decode",
         'Print base64_decode("SGVsbG8gV29ybGQ=").',
         ['Hello World'])
    
    test("uuid_gen",
         'Create id equal to uuid().\nPrint length(id).',
         ['36'])
    
    
    print("\n=== Standard Library: Regex ===")
    test("regex_test_true",
         'Print regex_test("[0-9]+", "abc123").',
         ['true'])
    
    test("regex_test_false",
         'Print regex_test("[0-9]+", "abc").',
         ['false'])
    
    test("regex_find_all",
         'Print regex_find_all("[0-9]+", "a1b22c333").',
         ['[1, 22, 333]'])
    
    test("regex_replace",
         'Print regex_replace("[0-9]+", "X", "a1b22c333").',
         ['aXbXcX'])
    
    test("regex_split",
         'Create parts equal to regex_split(",\\s*", "a, b, c").\nPrint parts.',
         ['[a, b, c]'])
    
    
    print("\n=== Standard Library: File System ===")
    test("file_exists_true",
         'Print file_exists("main.py").',
         ['true'])
    
    test("file_exists_false",
         'Print file_exists("nonexistent.xyz").',
         ['false'])
    
    test("dir_exists",
         'Print dir_exists("epl").',
         ['true'])
    
    test("path_join",
         'Print path_join("a", "b", "c.txt").',
         [os.path.join("a", "b", "c.txt")])
    
    test("path_extension",
         'Print path_extension("hello.txt").',
         ['.txt'])
    
    test("path_basename",
         'Print path_basename("/home/user/file.txt").',
         ['file.txt'])
    
    
    print("\n=== Standard Library: OS ===")
    test_contains("platform",
         'Create p equal to platform().\nPrint p.os.',
         'Windows')
    
    test_contains("cwd",
         'Print cwd().',
         'EPL')
    
    test("pid_positive",
         'Create p equal to pid().\nPrint p > 0.',
         ['true'])
    
    
    print("\n=== Standard Library: Math ===")
    test("pi",
         'Print pi().',
         ['3.141592653589793'])
    
    test("factorial",
         'Print factorial(5).',
         ['120'])
    
    test("gcd",
         'Print gcd(12, 8).',
         ['4'])
    
    test("clamp",
         'Print clamp(15, 0, 10).',
         ['10'])
    
    test("sign",
         'Print sign(-5).\nPrint sign(0).\nPrint sign(3).',
         ['-1', '0', '1'])
    
    
    print("\n=== Standard Library: Collections ===")
    test("zip_lists",
         'Print zip_lists([1, 2, 3], ["a", "b", "c"]).',
         ['[[1, a], [2, b], [3, c]]'])
    
    test("set_create",
         'Create s equal to set_create(1, 2, 3, 2, 1).\nPrint s.',
         ['[1, 2, 3]'])
    
    test("set_union",
         'Print set_union([1, 2], [2, 3]).',
         ['[1, 2, 3]'])
    
    test("dict_from_lists",
         'Create d equal to dict_from_lists(["a", "b"], [1, 2]).\nPrint d.a.',
         ['1'])
    
    
    print("\n=== Standard Library: URL ===")
    test("url_encode",
         'Print url_encode("hello world").',
         ['hello+world'])
    
    test("url_decode",
         'Print url_decode("hello+world").',
         ['hello world'])
    
    
    print("\n=== Standard Library: Format ===")
    test("format_string",
         'Print format("Hello {0}, you are {1}", "EPL", 1).',
         ['Hello EPL, you are 1'])
    
    
    print("\n=== Standard Library: Database (SQLite) ===")
    test("db_crud",
         'Create db equal to db_open(":memory:").\n'
         'db_execute(db, "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)").\n'
         'db_execute(db, "INSERT INTO users (name, age) VALUES (?, ?)", ["Alice", 30]).\n'
         'db_execute(db, "INSERT INTO users (name, age) VALUES (?, ?)", ["Bob", 25]).\n'
         'Create rows equal to db_query(db, "SELECT * FROM users ORDER BY name").\n'
         'Print length(rows).\n'
         'Create first equal to rows[0].\n'
         'Print first.name.\n'
         'Print first.age.\n'
         'db_close(db).',
         ['2', 'Alice', '30'])
    
    test("db_query_one",
         'Create db equal to db_open(":memory:").\n'
         'db_execute(db, "CREATE TABLE test (val TEXT)").\n'
         'db_execute(db, "INSERT INTO test VALUES (?)", ["hello"]).\n'
         'Create row equal to db_query_one(db, "SELECT * FROM test").\n'
         'Print row.val.\n'
         'db_close(db).',
         ['hello'])
    
    test("db_tables",
         'Create db equal to db_open(":memory:").\n'
         'db_execute(db, "CREATE TABLE foo (x INT)").\n'
         'db_execute(db, "CREATE TABLE bar (y INT)").\n'
         'Create t equal to db_tables(db).\n'
         'Print length(t).\n'
         'db_close(db).',
         ['2'])
    
    
    print(f"\n{'='*50}")
    print(f"Results: {PASSED}/{PASSED+FAILED} passed, {FAILED} failed")
    if FAILED:
        print(f"  {FAILED} test(s) failed!")
    else:
        print("All tests passed!")
    return FAILED == 0


def test_new_features_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == "__main__":
    raise SystemExit(0 if run_suite() else 1)
