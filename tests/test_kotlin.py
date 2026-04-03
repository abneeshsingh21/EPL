"""
Test suite for EPL Kotlin Code Generator v3.0
Tests: symbol table, type inference, visibility, companion objects, Compose, etc.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.kotlin_gen import KotlinGenerator, SymbolTable


def parse(source):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def gen(source, **kwargs):
    program = parse(source)
    g = KotlinGenerator(**kwargs)
    return g.generate(program)


def gen_compose(source, **kwargs):
    program = parse(source)
    g = KotlinGenerator(**kwargs)
    return g.generate_compose_activity(program)


# ─── Symbol Table Tests ──────────────────────────────

def test_symbol_table_scoping():
    st = SymbolTable()
    st.define('x', 'Int')
    child = st.child()
    child.define('y', 'String')
    assert child.lookup('x') == 'Int', "Child should see parent symbol"
    assert child.lookup('y') == 'String', "Child should see own symbol"
    assert st.lookup('y') is None, "Parent should NOT see child symbol"
    print("  PASS: symbol_table_scoping")


def test_symbol_table_function():
    st = SymbolTable()
    st.define_function('add', [('a', 'Int'), ('b', 'Int')], 'Int')
    info = st.lookup_function('add')
    assert info['return'] == 'Int'
    assert len(info['params']) == 2
    print("  PASS: symbol_table_function")


def test_symbol_table_class():
    st = SymbolTable()
    st.define_class('Dog', {'properties': {'name': 'String'}, 'methods': {'bark': 'String'}, 'parent': None})
    info = st.lookup_class('Dog')
    assert info['properties']['name'] == 'String'
    assert info['methods']['bark'] == 'String'
    print("  PASS: symbol_table_class")


# ─── Type Inference Tests ────────────────────────────

def test_type_infer_int():
    code = gen('Create x equal to 42.')
    assert 'var x: Int = 42' in code, f"Expected Int type, got: {code}"
    print("  PASS: type_infer_int")


def test_type_infer_string():
    code = gen('Create x equal to "hello".')
    assert 'var x: String = "hello"' in code
    print("  PASS: type_infer_string")


def test_type_infer_double():
    code = gen('Create x equal to 3.14.')
    assert 'var x: Double = 3.14' in code
    print("  PASS: type_infer_double")


def test_type_infer_bool():
    code = gen('Create x equal to true.')
    assert 'var x: Boolean = true' in code
    print("  PASS: type_infer_bool")


def test_type_infer_list_homogeneous():
    code = gen('Create items equal to [1, 2, 3].')
    assert 'MutableList<Int>' in code, f"Expected MutableList<Int>, got: {code}"
    print("  PASS: type_infer_list_homogeneous")


def test_type_infer_const():
    code = gen('Constant PI = 3.14')
    assert 'val PI: Double = 3.14' in code
    print("  PASS: type_infer_const")


# ─── Function Return Type Inference ──────────────────

def test_return_type_int():
    code = gen('Function double takes x\n  Return x * 2.\nEnd Function.')
    assert 'fun double(x: Any): Int' in code or 'fun double(x: Any): Any' in code
    print("  PASS: return_type_inference")


def test_return_type_string():
    code = gen('Function greet takes name\n  Return "Hello " + name.\nEnd Function.')
    assert 'String' in code
    print("  PASS: return_type_string")


def test_return_type_unit():
    code = gen('Function doStuff takes nothing\n  Print "hi".\nEnd Function.')
    assert 'Unit' in code
    print("  PASS: return_type_unit")


def test_typed_params():
    code = gen('Function add takes integer a and integer b\n  Return a + b.\nEnd Function.')
    assert 'a: Int' in code and 'b: Int' in code
    print("  PASS: typed_params")


# ─── Visibility Modifier ─────────────────────────────

def test_visibility_private():
    code = gen('Private Create secret equal to 42.')
    assert 'private' in code.lower()
    print("  PASS: visibility_private")


# ─── Class Generation ────────────────────────────────

def test_class_basic():
    code = gen('Class Dog\n    name = "Rex"\nEnd')
    assert 'class Dog' in code
    assert 'var name: String = "Rex"' in code
    print("  PASS: class_basic")


def test_class_method_no_self():
    code = gen('Class Dog\n    name = "Rex"\n    Function bark takes self\n        Return "Woof"\n    End\nEnd')
    # Should NOT have 'self' in Kotlin params
    assert 'fun bark()' in code or 'fun bark():' in code
    assert 'self' not in code.split('fun bark')[1].split(')')[0]
    print("  PASS: class_method_no_self")


def test_class_inheritance():
    code = gen('Class Animal\n    species = "unknown"\nEnd\nClass Dog extends Animal\n    breed = "lab"\nEnd')
    assert 'class Dog : Animal()' in code or 'Dog : Animal' in code
    print("  PASS: class_inheritance")


# ─── Kotlin Constructs ───────────────────────────────

def test_for_range():
    code = gen('For i from 1 to 10\n  Print i.\nEnd For.')
    assert 'for (i in 1..10)' in code
    print("  PASS: for_range")


def test_while_loop():
    code = gen('Create x equal to 0.\nWhile x < 5\n  Set x to x + 1.\nEnd While.')
    assert 'while (' in code
    print("  PASS: while_loop")


def test_match_stmt():
    code = gen('x = 2\nMatch x\n    When 1\n        Print "one"\n    When 2\n        Print "two"\nEnd')
    assert 'when (' in code
    print("  PASS: match_stmt")


def test_lambda():
    code = gen('double = lambda x -> x * 2')
    assert '->' in code
    print("  PASS: lambda")


def test_ternary():
    code = gen('x = 5\nresult = "big" if x > 3 otherwise "small"')
    assert 'if (' in code and 'else' in code
    print("  PASS: ternary")


def test_try_catch():
    code = gen('Try\n    Print "ok"\nCatch e\n    Print e\nEnd')
    assert 'try {' in code and 'catch' in code
    print("  PASS: try_catch")


def test_enum():
    code = gen('Enum Color as Red, Green, Blue')
    assert 'enum class Color' in code
    assert 'Red' in code and 'Green' in code
    print("  PASS: enum")


def test_throw():
    code = gen('Throw "error".')
    assert 'throw Exception' in code
    print("  PASS: throw")


def test_map_literal():
    code = gen('m = Map with name = "EPL" and version = "4"')
    assert 'mutableMapOf(' in code or 'Map' in code
    print("  PASS: map_literal")


# ─── Jetpack Compose Tests ──────────────────────────

def test_compose_basic():
    code = gen_compose('Print "Hello Compose".')
    assert 'ComponentActivity' in code
    assert 'setContent' in code
    assert 'MaterialTheme' in code
    assert '@Composable' in code
    print("  PASS: compose_basic")


def test_compose_print_as_text():
    code = gen_compose('Print "Hello".')
    assert 'Text(text = "Hello")' in code
    print("  PASS: compose_print_as_text")


# ─── Method Mapping Tests ────────────────────────────

def test_expr_binary_ops():
    code = gen('Create x equal to 2 ** 3.')
    assert '.pow(' in code
    print("  PASS: expr_binary_power")


def test_builtin_sqrt():
    code = gen('Create x equal to call sqrt with 16.')
    assert 'kotlin.math.sqrt' in code
    print("  PASS: builtin_sqrt")


# ─── Run All ─────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        test_symbol_table_scoping,
        test_symbol_table_function,
        test_symbol_table_class,
        test_type_infer_int,
        test_type_infer_string,
        test_type_infer_double,
        test_type_infer_bool,
        test_type_infer_list_homogeneous,
        test_type_infer_const,
        test_return_type_int,
        test_return_type_string,
        test_return_type_unit,
        test_typed_params,
        test_visibility_private,
        test_class_basic,
        test_class_method_no_self,
        test_class_inheritance,
        test_for_range,
        test_while_loop,
        test_match_stmt,
        test_lambda,
        test_ternary,
        test_try_catch,
        test_enum,
        test_throw,
        test_map_literal,
        test_compose_basic,
        test_compose_print_as_text,
        test_expr_binary_ops,
        test_builtin_sqrt,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} — {e}")
            failed += 1

    print(f"\nResults: {passed}/{passed + failed} Kotlin transpiler tests passed")
    if failed == 0:
        print("ALL KOTLIN TESTS PASSED!")
    else:
        print(f"FAILED: {failed} tests")
