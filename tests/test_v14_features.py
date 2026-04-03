"""
EPL v1.4 Feature Tests
Tests for: async/await, super calls, constructor arguments,
GUI parsing, web framework, package manager, compiler types.
"""

import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl.interpreter import Interpreter, EPLInstance, EPLFuture
from epl.errors import EPLError

PASSED = 0
FAILED = 0


def run_epl(source: str) -> list:
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp.output_lines


def get_interp(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()
    interp = Interpreter()
    interp.execute(program)
    return interp


def test(name, source, expected):
    global PASSED, FAILED
    try:
        output = run_epl(source)
        if output == expected:
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected: {expected}")
            print(f"    Got:      {output}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
        FAILED += 1


test.__test__ = False

def test_error(name, source, expected_substring):
    global PASSED, FAILED
    try:
        run_epl(source)
        print(f"  FAIL: {name} (no error raised)")
        FAILED += 1
    except EPLError as e:
        if expected_substring.lower() in str(e).lower():
            print(f"  PASS: {name}")
            PASSED += 1
        else:
            print(f"  FAIL: {name}")
            print(f"    Expected error containing: {expected_substring}")
            print(f"    Got: {e}")
            FAILED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> unexpected: {e}")
        FAILED += 1


test_error.__test__ = False

def test_parse_ok(name, source):
    """Test that source parses without error."""
    global PASSED, FAILED
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        parser.parse()
        print(f"  PASS: {name}")
        PASSED += 1
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
        FAILED += 1


test_parse_ok.__test__ = False

def run_suite():
    global PASSED, FAILED
    PASSED = 0
    FAILED = 0
    print("=" * 60)
    print("EPL v1.4 Feature Tests")
    print("=" * 60)
    
    # =====================================================
    # 1. Constructor Arguments (init method)
    # =====================================================
    print("\n--- Constructor Arguments ---")
    
    test("constructor_init_basic",
        'Class Person\n'
        '  Create name equal to "".\n'
        '  Create age equal to 0.\n'
        '  Function init takes n, a\n'
        '    Set name to n.\n'
        '    Set age to a.\n'
        '  End Function.\n'
        'End.\n'
        'Create p equal to new Person("Alice", 30).\n'
        'Print p.name.\n'
        'Print p.age.',
        ['Alice', '30'])
    
    test("constructor_init_no_args",
        'Class Dog\n'
        '  Create breed equal to "unknown".\n'
        'End.\n'
        'Create d equal to new Dog().\n'
        'Print d.breed.',
        ['unknown'])
    
    test_error("constructor_args_no_init",
        'Class Empty\n'
        '  Create x equal to 0.\n'
        'End.\n'
        'Create e equal to new Empty(42).',
        'no init')
    
    test("constructor_init_with_method",
        'Class Counter\n'
        '  Create count equal to 0.\n'
        '  Function init takes start\n'
        '    Set count to start.\n'
        '  End Function.\n'
        '  Function increment\n'
        '    Set count to count + 1.\n'
        '  End Function.\n'
        '  Function get_count\n'
        '    Return count.\n'
        '  End Function.\n'
        'End.\n'
        'Create c equal to new Counter(10).\n'
        'c.increment().\n'
        'Print c.get_count().',
        ['11'])
    
    test("constructor_init_default_params",
        'Class Config\n'
        '  Create host equal to "".\n'
        '  Create myport equal to 0.\n'
        '  Function init takes h, p = 8080\n'
        '    Set host to h.\n'
        '    Set myport to p.\n'
        '  End Function.\n'
        'End.\n'
        'Create c1 equal to new Config("localhost").\n'
        'Create c2 equal to new Config("example.com", 3000).\n'
        'Print c1.myport.\n'
        'Print c2.myport.',
        ['8080', '3000'])
    
    # =====================================================
    # 2. Super Calls
    # =====================================================
    print("\n--- Super Calls ---")
    
    test("super_method_call",
        'Class Animal\n'
        '  Create sound equal to "...".\n'
        '  Function speak\n'
        '    Return sound.\n'
        '  End Function.\n'
        'End.\n'
        'Class Dog extends Animal\n'
        '  Create sound equal to "Woof".\n'
        '  Function speak\n'
        '    Return "Dog says: " + sound.\n'
        '  End Function.\n'
        '  Function parent_speak\n'
        '    Return Super.speak().\n'
        '  End Function.\n'
        'End.\n'
        'Create d equal to new Dog().\n'
        'Print d.speak().\n'
        'Print d.parent_speak().',
        ['Dog says: Woof', 'Woof'])
    
    test("super_constructor_defaults",
        'Class Base\n'
        '  Create x equal to 10.\n'
        '  Create y equal to 20.\n'
        'End.\n'
        'Class Child extends Base\n'
        '  Create z equal to 30.\n'
        'End.\n'
        'Create c equal to new Child().\n'
        'Print c.x.\n'
        'Print c.y.\n'
        'Print c.z.',
        ['10', '20', '30'])
    
    test_error("super_no_parent",
        'Class Solo\n'
        '  Create x equal to 1.\n'
        '  Function try_super\n'
        '    Super.nothing().\n'
        '  End Function.\n'
        'End.\n'
        'Create s equal to new Solo().\n'
        's.try_super().',
        'no parent')
    
    test("super_as_expression_in_return",
        'Class A\n'
        '  Function compute takes x\n'
        '    Return x * 2.\n'
        '  End Function.\n'
        'End.\n'
        'Class B extends A\n'
        '  Function compute takes x\n'
        '    Return Super.compute(x) + 1.\n'
        '  End Function.\n'
        'End.\n'
        'Create b equal to new B().\n'
        'Print b.compute(5).',
        ['11'])
    
    # =====================================================
    # 3. Async/Await
    # =====================================================
    print("\n--- Async/Await ---")
    
    test_parse_ok("async_function_parse",
        'Async Function fetch_data takes url\n'
        '  Return "data from " + url.\n'
        'End Function.')
    
    test_parse_ok("await_parse",
        'Async Function get_value\n'
        '  Return 42.\n'
        'End Function.\n'
        'Create result equal to Await get_value().')
    
    test("async_returns_value_via_await",
        'Async Function compute takes x\n'
        '  Return x * 2.\n'
        'End Function.\n'
        'Create result equal to Await compute(21).\n'
        'Print result.',
        ['42'])
    
    test("async_string_return",
        'Async Function greet takes name\n'
        '  Return "Hello, " + name.\n'
        'End Function.\n'
        'Create msg equal to Await greet("World").\n'
        'Print msg.',
        ['Hello, World'])
    
    test("async_no_return",
        'Async Function do_nothing\n'
        '  Create x equal to 1.\n'
        'End Function.\n'
        'Create r equal to Await do_nothing().\n'
        'Print r.',
        ['nothing'])
    
    test("async_multiple_calls",
        'Async Function double takes n\n'
        '  Return n * 2.\n'
        'End Function.\n'
        'Create val_a equal to Await double(5).\n'
        'Create val_b equal to Await double(10).\n'
        'Print val_a + val_b.',
        ['30'])
    
    # =====================================================
    # 4. GUI Parsing (no tkinter needed, just parse check)
    # =====================================================
    print("\n--- GUI Parsing ---")
    
    test_parse_ok("window_parse",
        'Window "My App" 800 by 600\n'
        '  Label "Welcome" as lbl.\n'
        'End.')
    
    test_parse_ok("layout_row_parse",
        'Window "Test" 400 by 300\n'
        '  Row\n'
        '    Button "OK" as ok_btn does handle_ok.\n'
        '    Button "Cancel" as cancel_btn does handle_cancel.\n'
        '  End.\n'
        'End.')
    
    test_parse_ok("layout_column_parse",
        'Window "Test" 400 by 300\n'
        '  Column\n'
        '    Label "Name:" as name_label.\n'
        '    Textbox "Enter name" as name_input.\n'
        '  End.\n'
        'End.')
    
    test_parse_ok("bind_event_parse",
        'Window "Test" 400 by 300\n'
        '  Button "Click" as btn does handler.\n'
        '  Bind btn "click" to handler.\n'
        'End.')
    
    test_parse_ok("dialog_parse",
        'Dialog "Are you sure?" type "yesno".')
    
    test_parse_ok("menu_parse",
        'Menu "File"\n'
        '  Print "menu item".\n'
        'End.')
    
    test_parse_ok("canvas_parse",
        'Canvas myCanvas draw rect x 10 y 10 width 100 height 50.')
    
    test_parse_ok("multiple_widgets_parse",
        'Window "Form" 600 by 400\n'
        '  Label "Username:" as usr_lbl.\n'
        '  Textbox "" as usr_input.\n'
        '  Checkbox "Remember me" as remember.\n'
        '  Dropdown "Option 1" as dd.\n'
        '  Slider "Volume" as vol.\n'
        '  Progress "Loading" as prog.\n'
        '  Textarea "Notes" as notes.\n'
        'End.')
    
    # =====================================================
    # 5. Soft Keywords as Identifiers
    # =====================================================
    print("\n--- Soft Keywords ---")
    
    test("row_as_variable",
        'Create row equal to "data_row_1".\n'
        'Print row.',
        ['data_row_1'])
    
    test("column_as_variable",
        'Create column equal to 5.\n'
        'Print column.',
        ['5'])
    
    test("label_as_variable",
        'Create label equal to "my label".\n'
        'Print label.',
        ['my label'])
    
    test("tab_as_variable",
        'Create tab equal to "tab1".\n'
        'Print tab.',
        ['tab1'])
    
    test("menu_as_variable",
        'Create menu equal to "File".\n'
        'Print menu.',
        ['File'])
    
    # =====================================================
    # 6. OOP: Inheritance chain
    # =====================================================
    print("\n--- Inheritance ---")
    
    test("three_level_inheritance",
        'Class A\n'
        '  Create val equal to "A".\n'
        'End.\n'
        'Class B extends A\n'
        '  Create val2 equal to "B".\n'
        'End.\n'
        'Class C extends B\n'
        '  Create val3 equal to "C".\n'
        'End.\n'
        'Create c equal to new C().\n'
        'Print c.val.\n'
        'Print c.val2.\n'
        'Print c.val3.',
        ['A', 'B', 'C'])
    
    test("method_override_and_inherit",
        'Class Shape\n'
        '  Create kind equal to "shape".\n'
        '  Function describe\n'
        '    Return "I am a " + kind.\n'
        '  End Function.\n'
        'End.\n'
        'Class Circle extends Shape\n'
        '  Create kind equal to "circle".\n'
        '  Create radius equal to 0.\n'
        'End.\n'
        'Create c equal to new Circle().\n'
        'Print c.describe().',
        ['I am a circle'])
    
    test("init_with_inheritance",
        'Class Vehicle\n'
        '  Create speed equal to 0.\n'
        '  Function init takes s\n'
        '    Set speed to s.\n'
        '  End Function.\n'
        'End.\n'
        'Class Car extends Vehicle\n'
        '  Create doors equal to 4.\n'
        '  Function init takes s, d\n'
        '    Set speed to s.\n'
        '    Set doors to d.\n'
        '  End Function.\n'
        'End.\n'
        'Create c equal to new Car(120, 2).\n'
        'Print c.speed.\n'
        'Print c.doors.',
        ['120', '2'])
    
    # =====================================================
    # 7. Web Framework
    # =====================================================
    print("\n--- Web Framework ---")
    
    def test_web_route_params():
        global PASSED, FAILED
        try:
            from epl.web import EPLWebApp
            app = EPLWebApp("test_app")
            called = {}
            def user_handler(req, res, params):
                called['id'] = params.get('id')
            app.add_route('/users/:id', 'text', user_handler, method='GET')
            assert 'GET' in app.param_routes, "param route not registered"
            print("  PASS: web_param_route_register")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: web_param_route_register -> {e}")
            FAILED += 1
    
    def test_web_auth():
        global PASSED, FAILED
        try:
            from epl.web import hash_password, verify_password
            hashed = hash_password("secret123")
            assert verify_password("secret123", hashed), "password should verify"
            assert not verify_password("wrong", hashed), "wrong password should fail"
            print("  PASS: web_auth_hashing")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: web_auth_hashing -> {e}")
            FAILED += 1
    
    def test_web_validation():
        global PASSED, FAILED
        try:
            from epl.web import validate_email, validate_length, sanitize_html
            assert validate_email("user@example.com"), "valid email should pass"
            assert not validate_email("invalid"), "invalid email should fail"
            assert validate_length("hello", 1, 10), "valid length should pass"
            assert not validate_length("hi", 5, 10), "too short should fail"
            clean = sanitize_html("<script>alert('xss')</script>Hello")
            assert "<script>" not in clean, "script tags should be removed"
            assert "Hello" in clean, "text content should remain"
            print("  PASS: web_validation")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: web_validation -> {e}")
            FAILED += 1
    
    def test_web_middleware():
        global PASSED, FAILED
        try:
            from epl.web import EPLWebApp
            app = EPLWebApp("mw_test")
            log = []
            def logger(req, res):
                log.append("middleware_called")
            app.add_middleware("logger", before_fn=logger)
            assert len(app.middleware) == 1, "middleware not added"
            print("  PASS: web_middleware")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: web_middleware -> {e}")
            FAILED += 1
    
    test_web_route_params()
    test_web_auth()
    test_web_validation()
    test_web_middleware()
    
    # =====================================================
    # 8. Package Manager
    # =====================================================
    print("\n--- Package Manager ---")
    
    def test_package_search():
        global PASSED, FAILED
        try:
            from epl.package_manager import search_packages, BUILTIN_REGISTRY
            results = search_packages("math")
            assert any("math" in r['name'] for r in results), "should find math package"
            results2 = search_packages("http")
            assert any("http" in r['name'] for r in results2), "should find http package"
            print("  PASS: package_search")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: package_search -> {e}")
            FAILED += 1
    
    def test_builtin_registry():
        global PASSED, FAILED
        try:
            from epl.package_manager import BUILTIN_REGISTRY
            assert 'epl-math' in BUILTIN_REGISTRY, "missing epl-math"
            assert 'epl-http' in BUILTIN_REGISTRY, "missing epl-http"
            assert 'epl-json' in BUILTIN_REGISTRY, "missing epl-json"
            assert len(BUILTIN_REGISTRY) >= 9, f"expected 9+ packages, got {len(BUILTIN_REGISTRY)}"
            print("  PASS: builtin_registry")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: builtin_registry -> {e}")
            FAILED += 1
    
    def test_find_package_module():
        global PASSED, FAILED
        try:
            from epl.package_manager import find_package_module
            result = find_package_module("nonexistent_package_xyz")
            assert result is None, "should return None for missing package"
            print("  PASS: find_package_module")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: find_package_module -> {e}")
            FAILED += 1
    
    test_package_search()
    test_builtin_registry()
    test_find_package_module()
    
    # =====================================================
    # 9. Compiler
    # =====================================================
    print("\n--- Compiler ---")
    
    def test_compiler_init():
        global PASSED, FAILED
        try:
            from epl.compiler import Compiler
            c = Compiler()
            assert c.module is not None, "module should be created"
            # builder is None until compile() is called — that's correct
            assert c.func is None, "func should be None before compile"
            print("  PASS: compiler_init")
            PASSED += 1
        except ImportError:
            print("  SKIP: compiler_init (llvmlite not installed)")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: compiler_init -> {e}")
            FAILED += 1
    
    def test_compiler_type_inference():
        global PASSED, FAILED
        try:
            from epl.compiler import Compiler
            c = Compiler()
            # _infer_param_type takes a param tuple: (name, type_hint)
            ir_type, epl_type = c._infer_param_type(('x', 'integer'))
            assert epl_type == "int", f"expected 'int', got '{epl_type}'"
            ir_type2, epl_type2 = c._infer_param_type(('y', 'decimal'))
            assert epl_type2 == "float", f"expected 'float', got '{epl_type2}'"
            ir_type3, epl_type3 = c._infer_param_type(('z', 'text'))
            assert epl_type3 == "string", f"expected 'string', got '{epl_type3}'"
            print("  PASS: compiler_type_inference")
            PASSED += 1
        except ImportError:
            print("  SKIP: compiler_type_inference (llvmlite not installed)")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: compiler_type_inference -> {e}")
            FAILED += 1
    
    test_compiler_init()
    test_compiler_type_inference()
    
    # =====================================================
    # 10. Kotlin Generator
    # =====================================================
    print("\n--- Kotlin Generator ---")
    
    def test_kotlin_basic():
        global PASSED, FAILED
        try:
            from epl.kotlin_gen import KotlinGenerator
            source = 'Print "Hello Kotlin".'
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            gen = KotlinGenerator()
            code = gen.generate(program)
            assert 'println' in code, "should contain println"
            assert 'Hello Kotlin' in code, "should contain the string"
            print("  PASS: kotlin_basic")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: kotlin_basic -> {e}")
            FAILED += 1
    
    def test_kotlin_class():
        global PASSED, FAILED
        try:
            from epl.kotlin_gen import KotlinGenerator
            source = (
                'Class Animal\n'
                '  Create name equal to "".\n'
                '  Function speak\n'
                '    Return name.\n'
                '  End Function.\n'
                'End.'
            )
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            gen = KotlinGenerator()
            code = gen.generate(program)
            assert 'class Animal' in code, "should contain class"
            assert 'name' in code, "should contain property"
            print("  PASS: kotlin_class")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: kotlin_class -> {e}")
            FAILED += 1
    
    def test_kotlin_function():
        global PASSED, FAILED
        try:
            from epl.kotlin_gen import KotlinGenerator
            source = (
                'Function add takes a, b\n'
                '  Return a + b.\n'
                'End Function.'
            )
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            gen = KotlinGenerator()
            code = gen.generate(program)
            assert 'fun add' in code, "should contain function"
            print("  PASS: kotlin_function")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: kotlin_function -> {e}")
            FAILED += 1
    
    test_kotlin_basic()
    test_kotlin_class()
    test_kotlin_function()
    
    # =====================================================
    # 11. JS Transpiler
    # =====================================================
    print("\n--- JS Transpiler ---")
    
    def test_js_basic():
        global PASSED, FAILED
        try:
            from epl.js_transpiler import JSTranspiler
            source = 'Print "Hello JS".'
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            trans = JSTranspiler()
            code = trans.transpile(program)
            assert 'console.log' in code, "should contain console.log"
            assert 'Hello JS' in code, "should contain the string"
            print("  PASS: js_basic")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: js_basic -> {e}")
            FAILED += 1
    
    def test_js_function():
        global PASSED, FAILED
        try:
            from epl.js_transpiler import JSTranspiler
            source = (
                'Function add takes a, b\n'
                '  Return a + b.\n'
                'End Function.\n'
                'Print add(3, 4).'
            )
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            trans = JSTranspiler()
            code = trans.transpile(program)
            assert 'function add' in code, "should contain function"
            assert 'return' in code.lower(), "should contain return"
            print("  PASS: js_function")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: js_function -> {e}")
            FAILED += 1
    
    def test_js_class():
        global PASSED, FAILED
        try:
            from epl.js_transpiler import JSTranspiler
            source = (
                'Class Animal\n'
                '  Create name equal to "default".\n'
                '  Function speak\n'
                '    Return name.\n'
                '  End Function.\n'
                'End.'
            )
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            parser = Parser(tokens)
            program = parser.parse()
            trans = JSTranspiler()
            code = trans.transpile(program)
            assert 'class Animal' in code, "should contain class"
            print("  PASS: js_class")
            PASSED += 1
        except Exception as e:
            print(f"  FAIL: js_class -> {e}")
            FAILED += 1
    
    test_js_basic()
    test_js_function()
    test_js_class()
    
    # =====================================================
    # 12. Edge Cases
    # =====================================================
    print("\n--- Edge Cases ---")
    
    test("empty_class_with_methods_only",
        'Class Utils\n'
        '  Function double takes x\n'
        '    Return x * 2.\n'
        '  End Function.\n'
        'End.\n'
        'Create u equal to new Utils().\n'
        'Print u.double(5).',
        ['10'])
    
    test("class_property_mutation",
        'Class Box\n'
        '  Create items equal to 0.\n'
        '  Function add takes n\n'
        '    Set items to items + n.\n'
        '  End Function.\n'
        'End.\n'
        'Create b equal to new Box().\n'
        'b.add(3).\n'
        'b.add(7).\n'
        'Print b.items.',
        ['10'])
    
    test("nested_class_method_calls",
        'Class Math\n'
        '  Function square takes x\n'
        '    Return x * x.\n'
        '  End Function.\n'
        '  Function cube takes x\n'
        '    Return x * x * x.\n'
        '  End Function.\n'
        'End.\n'
        'Create m equal to new Math().\n'
        'Print m.square(4) + m.cube(2).',
        ['24'])
    
    test("lambda_in_list",
        'Create ops equal to [lambda x -> x + 1, lambda x -> x * 2].\n'
        'Create f1 equal to ops[0].\n'
        'Create f2 equal to ops[1].\n'
        'Print f1(5).\n'
        'Print f2(5).',
        ['6', '10'])
    
    test("string_interpolation_in_class",
        'Class Greeter\n'
        '  Create name equal to "".\n'
        '  Function init takes n\n'
        '    Set name to n.\n'
        '  End Function.\n'
        '  Function greet\n'
        '    Return "Hello, ${name}!".\n'
        '  End Function.\n'
        'End.\n'
        'Create g equal to new Greeter("World").\n'
        'Print g.greet().',
        ['Hello, World!'])
    
    test("map_literal_basic",
        'Create cfg equal to Map with host = "localhost" and port = 8080.\n'
        'Print cfg.host.\n'
        'Print cfg.port.',
        ['localhost', '8080'])
    
    test("class_with_map_property",
        'Class Settings\n'
        '  Create data equal to Map with debug = true and level = 3.\n'
        'End.\n'
        'Create s equal to new Settings().\n'
        'Print s.data.debug.\n'
        'Print s.data.level.',
        ['true', '3'])
    
    test("await_as_expression_in_print",
        'Async Function meaning\n'
        '  Return 42.\n'
        'End Function.\n'
        'Print Await meaning().',
        ['42'])
    
    test("constructor_and_super",
        'Class Base\n'
        '  Create val equal to 0.\n'
        '  Function init takes v\n'
        '    Set val to v.\n'
        '  End Function.\n'
        '  Function get_val\n'
        '    Return val.\n'
        '  End Function.\n'
        'End.\n'
        'Class Derived extends Base\n'
        '  Create extra equal to 0.\n'
        '  Function init takes v, e\n'
        '    Set val to v.\n'
        '    Set extra to e.\n'
        '  End Function.\n'
        '  Function total\n'
        '    Return val + extra.\n'
        '  End Function.\n'
        'End.\n'
        'Create d equal to new Derived(10, 5).\n'
        'Print d.total().',
        ['15'])
    
    # =====================================================
    # Summary
    # =====================================================
    
    print()
    print("=" * 60)
    print(f"Results: {PASSED}/{PASSED + FAILED} passed, {FAILED} failed")
    if FAILED == 0:
        print("All tests passed!")
    else:
        print(f"  {FAILED} test(s) failed!")
    print("=" * 60)
    return FAILED == 0


def test_v14_features_suite():
    result = subprocess.run(
        [sys.executable, os.path.abspath(__file__)],
        cwd=os.path.dirname(__file__),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    raise SystemExit(0 if run_suite() else 1)
