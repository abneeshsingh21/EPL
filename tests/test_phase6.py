"""
EPL Phase 6 Test Suite — Mobile & Desktop
Tests for: Desktop GUI (6a), Android (6b), Web/WASM (6c)
Target: 300+ tests covering all three targets.
"""

import sys
import os
import shutil
import tempfile
from functools import wraps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from epl.lexer import Lexer
from epl.parser import Parser
from epl import ast_nodes as ast

# ─── Test Infrastructure ─────────────────────────────────


class _TrackerState:
    current = None
    total_pass = 0
    total_fail = 0
    total_count = 0


def _start_tracker():
    _TrackerState.current = {
        "passed": 0,
        "failed": 0,
        "count": 0,
        "failures": [],
    }


def _finish_tracker():
    tracker = _TrackerState.current
    _TrackerState.current = None
    if tracker is None:
        return
    _TrackerState.total_pass += tracker["passed"]
    _TrackerState.total_fail += tracker["failed"]
    _TrackerState.total_count += tracker["count"]
    if tracker["failures"]:
        raise AssertionError("\n".join(tracker["failures"]))


def _tracked_test(fn):
    @wraps(fn)
    def wrapper():
        _start_tracker()
        try:
            fn()
        finally:
            cleanup()
            _finish_tracker()

    return wrapper


def _parse(source):
    """Parse EPL source into AST."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def _check(name, condition):
    """Assert a condition."""
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("_check() called outside an active test tracker.")
    tracker["count"] += 1
    if condition:
        tracker["passed"] += 1
        print(f"  PASS: {name}")
    else:
        tracker["failed"] += 1
        tracker["failures"].append(name)
        print(f"  FAIL: {name}")


def _check_contains(name, text, *substrings):
    """Assert text contains all substrings."""
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("_check_contains() called outside an active test tracker.")
    tracker["count"] += 1
    missing = [s for s in substrings if s not in text]
    if not missing:
        tracker["passed"] += 1
        print(f"  PASS: {name}")
    else:
        tracker["failed"] += 1
        tracker["failures"].append(f"{name}: missing {', '.join(repr(m) for m in missing)}")
        print(f"  FAIL: {name}")
        for m in missing:
            print(f"    Missing: {m!r}")


def _check_file_exists(name, path):
    """Assert a file exists."""
    tracker = _TrackerState.current
    if tracker is None:
        raise RuntimeError("_check_file_exists() called outside an active test tracker.")
    tracker["count"] += 1
    if os.path.exists(path):
        tracker["passed"] += 1
        print(f"  PASS: {name}")
    else:
        tracker["failed"] += 1
        tracker["failures"].append(f"{name}: file not found: {path}")
        print(f"  FAIL: {name} — file not found: {path}")


def section(title):
    print(f"\n--- {title} ---")


# ─── Cleanup Helper ─────────────────────────────────────

_TEMP_DIRS = []

def make_temp_dir():
    d = tempfile.mkdtemp(prefix='epl_test_')
    _TEMP_DIRS.append(d)
    return d

def cleanup():
    for d in _TEMP_DIRS:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# 6a — Desktop GUI Tests
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_desktop_import():
    section("6a Desktop — Module Import")
    from epl.desktop import (
        DesktopProjectGenerator, DesktopComposeGenerator,
        generate_desktop_project, generate_desktop_kotlin
    )
    _check("DesktopProjectGenerator importable", DesktopProjectGenerator is not None)
    _check("DesktopComposeGenerator importable", DesktopComposeGenerator is not None)
    _check("generate_desktop_project importable", callable(generate_desktop_project))
    _check("generate_desktop_kotlin importable", callable(generate_desktop_kotlin))


@_tracked_test
def test_desktop_generator_init():
    section("6a Desktop — Generator Initialization")
    from epl.desktop import DesktopProjectGenerator, DesktopComposeGenerator

    gen = DesktopProjectGenerator("MyApp", "com.test.app", 1024, 768)
    _check("app_name set", gen.app_name == "MyApp")
    _check("package set", gen.package == "com.test.app")
    _check("width set", gen.width == 1024)
    _check("height set", gen.height == 768)
    _check("package_path set", gen.package_path == "com/test/app")
    _check("version default", gen.version == "1.0.0")

    cg = DesktopComposeGenerator("com.test.app", "Test App", 800, 600)
    _check("compose gen package", cg.package == "com.test.app")
    _check("compose gen title", cg.app_title == "Test App")
    _check("compose gen width", cg.width == 800)
    _check("compose gen height", cg.height == 600)


@_tracked_test
def test_desktop_simple_program():
    section("6a Desktop — Simple Program Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('Display "Hello Desktop"')
    gen = DesktopComposeGenerator("com.epl.test", "Test App")
    code = gen.generate(program)

    _check_contains("has package", code, "package com.epl.test")
    _check_contains("has imports", code, "import androidx.compose")
    _check_contains("has fun main()", code, "fun main()")
    _check_contains("has application block", code, "application {")
    _check_contains("has Window composable", code, "Window(")
    _check_contains("has MaterialTheme", code, "MaterialTheme")
    _check_contains("has AppContent", code, "AppContent()")
    _check_contains("has @Composable", code, "@Composable")
    _check_contains("has Text", code, "Text(")


@_tracked_test
def test_desktop_variables():
    section("6a Desktop — Variables in Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Set x to 42
Set name to "Desktop"
Display x
Display name
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has Text for x", code, "Text(")
    _check("has multiple Text widgets", code.count("Text(") >= 2)


@_tracked_test
def test_desktop_function():
    section("6a Desktop — Function Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Function greet takes name
    Display "Hello " + name
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has fun greet", code, "fun greet(")
    _check_contains("has println", code, "println(")


@_tracked_test
def test_desktop_class():
    section("6a Desktop — Class Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Class Animal
    Set species to "Unknown"
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has open class", code, "open class Animal")


@_tracked_test
def test_desktop_conditionals():
    section("6a Desktop — Conditionals in Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Set x to 10
If x > 5 Then
    Display "big"
Otherwise
    Display "small"
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has if block", code, "if (")
    _check_contains("has else block", code, "} else {")


@_tracked_test
def test_desktop_loops():
    section("6a Desktop — Loops in Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
For Each item In [1, 2, 3]
    Display item
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has for loop", code, "for (item in")


@_tracked_test
def test_desktop_while_loop():
    section("6a Desktop — While Loop Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Set i to 0
While i < 5
    Display i
    Set i to i + 1
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has while loop", code, "while (")


@_tracked_test
def test_desktop_try_catch():
    section("6a Desktop — Try/Catch Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Try
    Display "trying"
Catch e
    Display "caught"
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has try block", code, "try {")
    _check_contains("has catch block", code, "catch (")


@_tracked_test
def test_desktop_gui_widgets():
    section("6a Desktop — GUI Widget Codegen")
    from epl.desktop import DesktopComposeGenerator

    program = _parse('''
Window "My App"
    Label "Welcome!"
    Button "Click Me" called btn1
    TextBox called txtName
    Checkbox "Agree" called chk1
End
''')
    gen = DesktopComposeGenerator()
    code = gen.generate(program)

    _check_contains("has Text for label", code, "Text(")
    _check_contains("has Button composable", code, "Button(onClick")
    _check_contains("has TextField", code, "TextField(")
    _check_contains("has Checkbox composable", code, "Checkbox(")
    _check_contains("has remember state", code, "remember {")
    _check_contains("has mutableStateOf", code, "mutableStateOf")


@_tracked_test
def test_desktop_runtime():
    section("6a Desktop — Runtime Generation")
    from epl.desktop import DesktopComposeGenerator

    gen = DesktopComposeGenerator("com.test.app")
    runtime = gen.generate_runtime()

    _check_contains("has package", runtime, "package com.test.app")
    _check_contains("has EPLRuntime object", runtime, "object EPLRuntime")
    _check_contains("has print function", runtime, "fun print(")
    _check_contains("has input function", runtime, "fun input(")
    _check_contains("has toInteger", runtime, "fun toInteger(")
    _check_contains("has toDecimal", runtime, "fun toDecimal(")
    _check_contains("has toText", runtime, "fun toText(")
    _check_contains("has length", runtime, "fun length(")
    _check_contains("has uppercase", runtime, "fun uppercase(")
    _check_contains("has lowercase", runtime, "fun lowercase(")
    _check_contains("has absolute", runtime, "fun absolute(")
    _check_contains("has power", runtime, "fun power(")
    _check_contains("has squareRoot", runtime, "fun squareRoot(")
    _check_contains("has random", runtime, "fun random()")
    _check_contains("has readFile", runtime, "fun readFile(")
    _check_contains("has writeFile", runtime, "fun writeFile(")
    _check_contains("has now", runtime, "fun now()")
    _check_contains("has showMessage dialog", runtime, "fun showMessage(")
    _check_contains("has showError dialog", runtime, "fun showError(")
    _check_contains("has askYesNo dialog", runtime, "fun askYesNo(")
    _check_contains("has askText dialog", runtime, "fun askText(")
    _check_contains("has openFileDialog", runtime, "fun openFileDialog(")
    _check_contains("has saveFileDialog", runtime, "fun saveFileDialog(")
    _check_contains("has sleep", runtime, "fun sleep(")
    _check_contains("has exit", runtime, "fun exit(")
    _check_contains("has env", runtime, "fun env(")
    _check_contains("has execute", runtime, "fun execute(")
    _check_contains("has toJson", runtime, "fun toJson(")


@_tracked_test
def test_desktop_project_generation():
    section("6a Desktop — Full Project Generation")
    from epl.desktop import generate_desktop_project

    program = _parse('Display "Hello Desktop"')
    out = make_temp_dir()
    result = generate_desktop_project(program, out, app_name="TestApp",
                                       package="com.test.desktop")

    _check("returns output dir", result == out)

    # Check all project files exist
    _check_file_exists("build.gradle.kts", f"{out}/build.gradle.kts")
    _check_file_exists("settings.gradle.kts", f"{out}/settings.gradle.kts")
    _check_file_exists("gradle.properties", f"{out}/gradle.properties")
    _check_file_exists("gradlew", f"{out}/gradlew")
    _check_file_exists("gradlew.bat", f"{out}/gradlew.bat")
    _check_file_exists("gradle-wrapper.properties", f"{out}/gradle/wrapper/gradle-wrapper.properties")
    _check_file_exists(".gitignore", f"{out}/.gitignore")
    _check_file_exists("README.md", f"{out}/README.md")
    _check_file_exists("Main.kt", f"{out}/src/main/kotlin/com/test/desktop/Main.kt")
    _check_file_exists("EPLRuntime.kt", f"{out}/src/main/kotlin/com/test/desktop/EPLRuntime.kt")

    # Check build.gradle.kts content
    with open(f"{out}/build.gradle.kts", 'r') as f:
        bg = f.read()
    _check_contains("gradle has compose plugin", bg, "org.jetbrains.compose")
    _check_contains("gradle has kotlin jvm", bg, 'kotlin("jvm")')
    _check_contains("gradle has compose desktop", bg, "compose.desktop")
    _check_contains("gradle has mainClass", bg, "mainClass")
    _check_contains("gradle has nativeDistributions", bg, "nativeDistributions")
    _check_contains("gradle has Msi format", bg, "TargetFormat.Msi")
    _check_contains("gradle has Dmg format", bg, "TargetFormat.Dmg")
    _check_contains("gradle has Deb format", bg, "TargetFormat.Deb")
    _check_contains("gradle has package name", bg, "TestApp")

    # Check Main.kt content
    with open(f"{out}/src/main/kotlin/com/test/desktop/Main.kt", 'r') as f:
        mk = f.read()
    _check_contains("main.kt has package", mk, "package com.test.desktop")
    _check_contains("main.kt has fun main", mk, "fun main()")
    _check_contains("main.kt has Window", mk, "Window(")

    # Check README
    with open(f"{out}/README.md", 'r') as f:
        readme = f.read()
    _check_contains("readme has app name", readme, "TestApp")
    _check_contains("readme has gradlew run", readme, "./gradlew run")


@_tracked_test
def test_desktop_build_gradle_details():
    section("6a Desktop — Build Gradle Details")
    from epl.desktop import DesktopProjectGenerator

    gen = DesktopProjectGenerator("MyDesktop", "com.my.app")
    bg = gen._build_gradle()

    _check_contains("has compose import", bg, "import org.jetbrains.compose")
    _check_contains("has material3", bg, "compose.material3")
    _check_contains("has coroutines", bg, "kotlinx-coroutines-core")
    _check_contains("has mavenCentral", bg, "mavenCentral()")
    _check_contains("has jetbrains repo", bg, "maven.pkg.jetbrains.space")
    _check_contains("has windows config", bg, "windows {")
    _check_contains("has macOS config", bg, "macOS {")
    _check_contains("has linux config", bg, "linux {")
    _check_contains("has Rpm format", bg, "TargetFormat.Rpm")
    _check_contains("has JUnit", bg, "useJUnitPlatform")


@_tracked_test
def test_desktop_settings_gradle():
    section("6a Desktop — Settings Gradle")
    from epl.desktop import DesktopProjectGenerator

    gen = DesktopProjectGenerator("MyApp")
    sg = gen._settings_gradle()

    _check_contains("has pluginManagement", sg, "pluginManagement")
    _check_contains("has compose dev repo", sg, "maven.pkg.jetbrains.space")
    _check_contains("has root project name", sg, "MyApp")


@_tracked_test
def test_desktop_expression_codegen():
    section("6a Desktop — Expression Codegen")
    from epl.desktop import DesktopComposeGenerator

    gen = DesktopComposeGenerator()

    # Literal expressions
    lit_int = ast.Literal(42)
    _check("int literal", gen._expr(lit_int) == "42")

    lit_str = ast.Literal("hello")
    _check("string literal", gen._expr(lit_str) == '"hello"')

    lit_bool_t = ast.Literal(True)
    _check("bool true", gen._expr(lit_bool_t) == "true")

    lit_bool_f = ast.Literal(False)
    _check("bool false", gen._expr(lit_bool_f) == "false")

    lit_none = ast.Literal(None)
    _check("null literal", gen._expr(lit_none) == "null")

    # Identifier
    ident = ast.Identifier("myVar")
    _check("identifier", gen._expr(ident) == "myVar")

    # BinaryOp
    binop = ast.BinaryOp(ast.Literal(1), '+', ast.Literal(2))
    result = gen._expr(binop)
    _check("binary add", '1' in result and '2' in result and '+' in result)

    # UnaryOp  
    unary = ast.UnaryOp('not', ast.Literal(True))
    result = gen._expr(unary)
    _check("unary not", '!' in result)

    # ListLiteral
    lst = ast.ListLiteral([ast.Literal(1), ast.Literal(2), ast.Literal(3)])
    result = gen._expr(lst)
    _check("list literal", 'mutableListOf' in result)

    # DictLiteral
    dct = ast.DictLiteral([(ast.Literal("a"), ast.Literal(1))])
    result = gen._expr(dct)
    _check("dict literal", 'mutableMapOf' in result)


@_tracked_test
def test_desktop_widget_types():
    section("6a Desktop — All Widget Types")
    from epl.desktop import DesktopComposeGenerator

    widget_tests = [
        ('button', {'text': 'Click', 'action': None}),
        ('label', {'text': 'Info'}),
        ('input', {'properties': {'placeholder': 'Enter'}}),
        ('textarea', {'properties': {'placeholder': 'Write'}}),
        ('checkbox', {'text': 'Enable'}),
        ('slider', {'properties': {'max': 200}}),
        ('progress', {}),
        ('dropdown', {'properties': {'options': ['A', 'B']}}),
        ('canvas', {'properties': {'width': 500, 'height': 400}}),
        ('image', {'text': 'logo.png'}),
        ('separator', {}),
        ('listbox', {}),
    ]

    for wtype, props in widget_tests:
        gen = DesktopComposeGenerator()
        gen.output = []
        gen.indent = 0
        gen.widget_counter += 1
        widget = {
            'id': f'test_{wtype}',
            'type': wtype,
            'text': props.get('text'),
            'properties': props.get('properties', {}),
            'action': props.get('action'),
        }
        gen._emit_compose_widget(widget)
        code = '\n'.join(gen.output)
        _check(f"widget {wtype} emits code", len(code.strip()) > 0)


# ═══════════════════════════════════════════════════════════
# 6b — Android Tests
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_android_import():
    section("6b Android — Module Import")
    from epl.kotlin_gen import (
        KotlinGenerator, AndroidProjectGenerator,
        transpile_to_kotlin, generate_android_project
    )
    _check("KotlinGenerator importable", KotlinGenerator is not None)
    _check("AndroidProjectGenerator importable", AndroidProjectGenerator is not None)
    _check("transpile_to_kotlin importable", callable(transpile_to_kotlin))
    _check("generate_android_project importable", callable(generate_android_project))


@_tracked_test
def test_android_kotlin_transpile():
    section("6b Android — Kotlin Transpilation")
    from epl.kotlin_gen import transpile_to_kotlin

    program = _parse('Display "Hello Android"')
    kt = transpile_to_kotlin(program, package="com.test.android")

    _check_contains("has package", kt, "package com.test.android")
    _check_contains("has fun main", kt, "fun main()")
    _check_contains("has println", kt, "println(")


@_tracked_test
def test_android_variables():
    section("6b Android — Variable Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Set x to 42
Set name to "test"
Set pi to 3.14
Set flag to True
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has x assignment", code, "x = ")
    _check_contains("has name assignment", code, "name = ")
    _check_contains("has pi assignment", code, "pi = ")


@_tracked_test
def test_android_functions():
    section("6b Android — Function Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Function add takes a and b
    Return a + b
End

Function greet takes name
    Display "Hello " + name
End
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has fun add", code, "fun add(")
    _check_contains("has fun greet", code, "fun greet(")
    _check_contains("has return", code, "return")


@_tracked_test
def test_android_classes():
    section("6b Android — Class Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Class Vehicle
    Set speed to 0
    Function accelerate
        Set speed to speed + 10
    End
End
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has class Vehicle", code, "class Vehicle")
    _check_contains("has speed property", code, "speed")


@_tracked_test
def test_android_conditionals():
    section("6b Android — Conditional Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Set age to 20
If age >= 18 Then
    Display "adult"
Otherwise
    Display "minor"
End
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has if", code, "if (")
    _check_contains("has else", code, "else")


@_tracked_test
def test_android_loops():
    section("6b Android — Loop Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
For Each item In [1, 2, 3]
    Display item
End

Set i to 0
While i < 10
    Set i to i + 1
End
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has for loop", code, "for (")
    _check_contains("has while loop", code, "while (")


@_tracked_test
def test_android_collections():
    section("6b Android — Collection Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Set myList to [1, 2, 3]
Set myDict to Map with key = "value"
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has list creation", code, "mutableListOf(")
    _check_contains("has map creation", code, "mutableMapOf(")


@_tracked_test
def test_android_try_catch():
    section("6b Android — Try/Catch Transpilation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Try
    Display "test"
Catch e
    Display "error"
End
''')
    gen = KotlinGenerator("com.test")
    code = gen.generate(program)

    _check_contains("has try", code, "try {")
    _check_contains("has catch", code, "catch (")


@_tracked_test
def test_android_project_generation():
    section("6b Android — Full Project Generation")
    from epl.kotlin_gen import generate_android_project

    program = _parse('Display "Hello Android"')
    out = make_temp_dir()
    result = generate_android_project(program, out, app_name="TestAndroid",
                                       package="com.test.android")

    _check("returns output dir", result == out)

    # Core files
    _check_file_exists("AndroidManifest.xml", f"{out}/app/src/main/AndroidManifest.xml")
    _check_file_exists("MainActivity.kt", f"{out}/app/src/main/java/com/test/android/MainActivity.kt")
    _check_file_exists("EPLRuntime.kt", f"{out}/app/src/main/java/com/test/android/EPLRuntime.kt")
    _check_file_exists("EPLApplication.kt", f"{out}/app/src/main/java/com/test/android/EPLApplication.kt")
    _check_file_exists("app build.gradle.kts", f"{out}/app/build.gradle.kts")
    _check_file_exists("root build.gradle.kts", f"{out}/build.gradle.kts")
    _check_file_exists("settings.gradle.kts", f"{out}/settings.gradle.kts")
    _check_file_exists("gradle.properties", f"{out}/gradle.properties")
    _check_file_exists("gradlew", f"{out}/gradlew")
    _check_file_exists("proguard-rules.pro", f"{out}/app/proguard-rules.pro")

    # Data layer
    _check_file_exists("Repository.kt", f"{out}/app/src/main/java/com/test/android/data/Repository.kt")
    _check_file_exists("EPLEntity.kt", f"{out}/app/src/main/java/com/test/android/data/model/EPLEntity.kt")
    _check_file_exists("EPLDao.kt", f"{out}/app/src/main/java/com/test/android/data/local/EPLDao.kt")
    _check_file_exists("EPLDatabase.kt", f"{out}/app/src/main/java/com/test/android/data/local/EPLDatabase.kt")
    _check_file_exists("ApiService.kt", f"{out}/app/src/main/java/com/test/android/data/remote/ApiService.kt")
    _check_file_exists("RetrofitClient.kt", f"{out}/app/src/main/java/com/test/android/data/remote/RetrofitClient.kt")

    # UI layer
    _check_file_exists("MainViewModel.kt", f"{out}/app/src/main/java/com/test/android/ui/MainViewModel.kt")
    _check_file_exists("ItemAdapter.kt", f"{out}/app/src/main/java/com/test/android/ui/ItemAdapter.kt")

    # Resources
    _check_file_exists("activity_main.xml", f"{out}/app/src/main/res/layout/activity_main.xml")
    _check_file_exists("strings.xml", f"{out}/app/src/main/res/values/strings.xml")
    _check_file_exists("themes.xml", f"{out}/app/src/main/res/values/themes.xml")
    _check_file_exists("colors.xml", f"{out}/app/src/main/res/values/colors.xml")
    _check_file_exists("nav_graph.xml", f"{out}/app/src/main/res/navigation/nav_graph.xml")
    _check_file_exists("main_menu.xml", f"{out}/app/src/main/res/menu/main_menu.xml")

    # Tests
    _check_file_exists("unit test", f"{out}/app/src/test/java/com/test/android/EPLRuntimeTest.kt")
    _check_file_exists("instrumented test", f"{out}/app/src/androidTest/java/com/test/android/MainActivityTest.kt")

    # Check manifest content
    with open(f"{out}/app/src/main/AndroidManifest.xml", 'r') as f:
        manifest = f.read()
    _check_contains("manifest has package", manifest, "com.test.android")
    _check_contains("manifest has INTERNET permission", manifest, "android.permission.INTERNET")
    _check_contains("manifest has MainActivity", manifest, ".MainActivity")


@_tracked_test
def test_android_manifest_details():
    section("6b Android — Manifest Details")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator("TestApp", "com.epl.test")
    manifest = gen._manifest()

    _check("omits deprecated package attribute", 'package="com.epl.test"' not in manifest)
    _check_contains("has INTERNET", manifest, "android.permission.INTERNET")
    _check_contains("has ACCESS_NETWORK_STATE", manifest, "android.permission.ACCESS_NETWORK_STATE")
    _check_contains("has icon", manifest, "@mipmap/ic_launcher")
    _check_contains("has theme", manifest, "@style/Theme.EPLApp")
    _check_contains("has application name", manifest, "com.epl.test.EPLApplication")
    _check_contains("has exported=true", manifest, 'android:exported="true"')


@_tracked_test
def test_android_strings_xml():
    section("6b Android — Strings XML")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator("MyAndroidApp", "com.epl.app")
    strings = gen._strings()

    _check_contains("has app_name", strings, "app_name")
    _check("is valid XML", strings.strip().startswith('<?xml') or strings.strip().startswith('<resources'))


@_tracked_test
def test_android_themes():
    section("6b Android — Themes")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator("TestApp", "com.epl.app")
    themes = gen._themes()
    themes_night = gen._themes_night()

    _check_contains("has style tag", themes, "<style")
    _check_contains("has Theme.EPLApp", themes, "Theme.EPLApp")
    _check_contains("night has style", themes_night, "<style")


@_tracked_test
def test_android_colors():
    section("6b Android — Colors")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator()
    colors = gen._colors()

    _check_contains("has color tag", colors, "<color")
    _check("has multiple colors", colors.count("<color") >= 3)


@_tracked_test
def test_android_gradle():
    section("6b Android — Gradle Files")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator("TestApp", "com.epl.app")
    app_gradle = gen._app_gradle()
    root_gradle = gen._root_gradle()
    settings = gen._settings()

    _check_contains("app gradle has android block", app_gradle, "android {")
    _check_contains("app gradle has compileSdk", app_gradle, "compileSdk")
    _check_contains("app gradle has defaultConfig", app_gradle, "defaultConfig")
    _check_contains("app gradle has dependencies", app_gradle, "dependencies")
    _check_contains("app gradle has applicationId", app_gradle, "com.epl.app")

    _check_contains("root gradle has plugins", root_gradle, "plugins")

    _check_contains("settings has app", settings, ":app")


@_tracked_test
def test_android_proguard():
    section("6b Android — ProGuard")
    from epl.kotlin_gen import AndroidProjectGenerator

    gen = AndroidProjectGenerator()
    rules = gen._proguard_rules()

    _check("proguard not empty", len(rules.strip()) > 0)


@_tracked_test
def test_android_symbol_table():
    section("6b Android — Symbol Table")
    from epl.kotlin_gen import SymbolTable

    st = SymbolTable()
    st.define("x", "Int")
    _check("lookup defined var", st.lookup("x") == "Int")
    _check("lookup undefined var", st.lookup("y") is None)

    st.define_function("add", [("a", "Int"), ("b", "Int")], "Int")
    fn = st.lookup_function("add")
    _check("lookup function", fn is not None)
    _check("function return type", fn['return'] == "Int")

    st.define_class("Foo", {'properties': {}, 'methods': {}, 'parent': None})
    cls = st.lookup_class("Foo")
    _check("lookup class", cls is not None)

    # Child scope
    child = st.child()
    child.define("y", "String")
    _check("child defines own", child.lookup("y") == "String")
    _check("child sees parent", child.lookup("x") == "Int")
    _check("parent doesn't see child", st.lookup("y") is None)


@_tracked_test
def test_android_gui_activity():
    section("6b Android — GUI Activity Generation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Window "My App"
    Label "Welcome"
    Button "Go" called btnGo
End
''')
    gen = KotlinGenerator("com.test")
    activity = gen.generate_android_activity(program)

    _check_contains("has package", activity, "package com.test")
    _check_contains("has AppCompatActivity", activity, "AppCompatActivity")
    _check_contains("has onCreate", activity, "onCreate")
    _check_contains("has setContentView", activity, "setContentView")


@_tracked_test
def test_android_compose_activity():
    section("6b Android — Compose Activity Generation")
    from epl.kotlin_gen import KotlinGenerator

    program = _parse('''
Window "Compose App"
    Button "Hello" called btn1
    Label "World"
End
''')
    gen = KotlinGenerator("com.test")
    compose = gen.generate_compose_activity(program)

    _check_contains("has package", compose, "package com.test")
    _check_contains("has ComponentActivity", compose, "ComponentActivity")
    _check_contains("has setContent", compose, "setContent")
    _check_contains("has @Composable", compose, "@Composable")


# ═══════════════════════════════════════════════════════════
# 6c — Web / WASM Tests
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_web_import():
    section("6c Web — Module Import")
    from epl.wasm_web import (
        WebProjectGenerator, WebCodeGenerator,
        generate_web_project, transpile_to_web_js, generate_wasm_glue
    )
    _check("WebProjectGenerator importable", WebProjectGenerator is not None)
    _check("WebCodeGenerator importable", WebCodeGenerator is not None)
    _check("generate_web_project importable", callable(generate_web_project))
    _check("transpile_to_web_js importable", callable(transpile_to_web_js))
    _check("generate_wasm_glue importable", callable(generate_wasm_glue))


@_tracked_test
def test_web_js_transpile():
    section("6c Web — JS Transpilation")
    from epl.wasm_web import transpile_to_web_js

    program = _parse('Display "Hello Web"')
    js = transpile_to_web_js(program, app_title="Test")

    _check_contains("has strict mode", js, "'use strict'")
    _check_contains("has EPL runtime object", js, "const EPL = {")
    _check_contains("has EPL.print call", js, "EPL.print(")
    _check_contains("has DOMContentLoaded", js, "DOMContentLoaded")


@_tracked_test
def test_web_js_variables():
    section("6c Web — JS Variable Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Set x to 42
Set name to "web"
Constant PI = 3.14
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has x assignment", js, "x = 42")
    _check_contains("has name assignment", js, 'name = "web"')
    _check_contains("has const PI", js, "const PI =")


@_tracked_test
def test_web_js_functions():
    section("6c Web — JS Function Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Function add takes a and b
    Return a + b
End

Function greet takes name
    Display "Hello " + name
End
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has function add", js, "function add(")
    _check_contains("has function greet", js, "function greet(")
    _check_contains("has return", js, "return")
    _check_contains("has EPL.print", js, "EPL.print(")


@_tracked_test
def test_web_js_conditionals():
    section("6c Web — JS Conditional Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Set x to 10
If x > 5 Then
    Display "big"
Otherwise
    Display "small"
End
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has if block", js, "if (")
    _check_contains("has else block", js, "} else {")


@_tracked_test
def test_web_js_loops():
    section("6c Web — JS Loop Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
For Each item In [1, 2, 3]
    Display item
End

Set i to 0
While i < 10
    Set i to i + 1
End
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has for...of", js, "for (const item of")
    _check_contains("has while", js, "while (")


@_tracked_test
def test_web_js_classes():
    section("6c Web — JS Class Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Class Shape
    Set sides to 0
End
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has class Shape", js, "class Shape")


@_tracked_test
def test_web_js_try_catch():
    section("6c Web — JS Try/Catch Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Try
    Display "testing"
Catch err
    Display "caught"
End
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has try", js, "try {")
    _check_contains("has catch", js, "catch (err)")


@_tracked_test
def test_web_js_collections():
    section("6c Web — JS Collection Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Set myList to [1, 2, 3]
Set myDict to Map with a = 1 and b = 2
''')
    gen = WebCodeGenerator()
    js = gen.transpile_js(program)

    _check_contains("has array literal", js, "[1, 2, 3]")
    _check_contains("has object literal", js, "{")


@_tracked_test
def test_web_js_builtins():
    section("6c Web — JS Builtin Mapping")
    from epl.wasm_web import WebCodeGenerator

    # Test each builtin maps to EPL.xxx
    builtins_to_test = [
        ('Display length("hello")', 'EPL.length('),
        ('Display toInteger("42")', 'EPL.toInteger('),
        ('Display uppercase("hi")', 'EPL.uppercase('),
        ('Display random()', 'EPL.random('),
        ('Display floor(3.7)', 'EPL.floor('),
        ('Display absolute(-5)', 'EPL.absolute('),
    ]

    for source, expected in builtins_to_test:
        gen = WebCodeGenerator()
        js = gen.transpile_js(_parse(source))
        _check(f"builtin {expected.split('(')[0]}", expected in js)


@_tracked_test
def test_web_js_runtime_functions():
    section("6c Web — JS Runtime Object")
    from epl.wasm_web import WebCodeGenerator

    gen = WebCodeGenerator()
    program = _parse('Display "hi"')
    js = gen.transpile_js(program)

    runtime_funcs = [
        'print', 'input', 'toInteger', 'toDecimal', 'toText',
        'length', 'uppercase', 'lowercase', 'trim', 'contains',
        'replace', 'split', 'substring', 'indexOf', 'startsWith',
        'endsWith', 'random', 'randomInt', 'absolute', 'power',
        'squareRoot', 'floor', 'ceil', 'round', 'sin', 'cos', 'tan',
        'now', 'timestamp', 'toJson', 'fromJson', 'keys', 'values',
        'hasKey', 'append', 'join', 'sorted', 'reversed',
    ]
    for fn in runtime_funcs:
        _check(f"runtime has {fn}", fn in js)


@_tracked_test
def test_web_html_generation():
    section("6c Web — HTML Generation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('Display "Hello"')
    gen = WebCodeGenerator("My Web App")
    html = gen.generate_html(program, mode='js')

    _check_contains("has DOCTYPE", html, "<!DOCTYPE html>")
    _check_contains("has html lang", html, '<html lang="en">')
    _check_contains("has charset", html, "UTF-8")
    _check_contains("has viewport", html, "viewport")
    _check_contains("has title", html, "My Web App")
    _check_contains("has stylesheet link", html, "style.css")
    _check_contains("has script tag", html, "app.js")
    _check_contains("has manifest link", html, "manifest.json")
    _check_contains("has header", html, "<header>")
    _check_contains("has main#app", html, 'id="app"')
    _check_contains("has footer", html, "<footer>")


@_tracked_test
def test_web_html_widgets():
    section("6c Web — HTML Widget Generation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Window "Widget App"
    Label "Welcome"
    Button "Click" called btn1
    TextBox called txt1
    Checkbox "Agree" called chk1
    Slider called sld1
End
''')
    gen = WebCodeGenerator("Widget App")
    html = gen.generate_html(program, mode='js')

    _check_contains("has button element", html, '<button id="btn1"')
    _check_contains("has span for label", html, "epl-label")
    _check_contains("has input element", html, '<input id="txt1"')
    _check_contains("has checkbox", html, 'type="checkbox"')
    _check_contains("has slider", html, 'type="range"')


@_tracked_test
def test_web_css_generation():
    section("6c Web — CSS Generation")
    from epl.wasm_web import WebCodeGenerator

    gen = WebCodeGenerator()
    css = gen.generate_css()

    _check_contains("has CSS variables", css, ":root {")
    _check_contains("has --primary", css, "--primary:")
    _check_contains("has body style", css, "body {")
    _check_contains("has header style", css, "header {")
    _check_contains("has .epl-btn", css, ".epl-btn")
    _check_contains("has .epl-input", css, ".epl-input")
    _check_contains("has .epl-textarea", css, ".epl-textarea")
    _check_contains("has .epl-checkbox", css, ".epl-checkbox")
    _check_contains("has .epl-slider", css, ".epl-slider")
    _check_contains("has .epl-select", css, ".epl-select")
    _check_contains("has .epl-canvas", css, ".epl-canvas")
    _check_contains("has .epl-listbox", css, ".epl-listbox")
    _check_contains("has responsive media query", css, "@media")
    _check("css is substantial", len(css) > 500)


@_tracked_test
def test_web_wasm_loader():
    section("6c Web — WASM Loader")
    from epl.wasm_web import WebCodeGenerator

    gen = WebCodeGenerator()
    loader = gen.generate_wasm_loader()

    _check_contains("has EPLWasm object", loader, "const EPLWasm =")
    _check_contains("has init function", loader, "async init(")
    _check_contains("has WebAssembly.instantiate", loader, "WebAssembly.instantiate")
    _check_contains("has WASI polyfill", loader, "wasi_snapshot_preview1")
    _check_contains("has epl_print_str import", loader, "epl_print_str")
    _check_contains("has epl_print_int import", loader, "epl_print_int")
    _check_contains("has memory access", loader, "EPLWasm.memory")
    _check_contains("has readString", loader, "readString(")
    _check_contains("has writeString", loader, "writeString(")
    _check_contains("has call function", loader, "call(name")
    _check_contains("has auto-init", loader, "DOMContentLoaded")
    _check_contains("has export default", loader, "export default EPLWasm")


@_tracked_test
def test_web_wasm_runtime():
    section("6c Web — WASM Runtime")
    from epl.wasm_web import WebCodeGenerator

    gen = WebCodeGenerator()
    runtime = gen.generate_wasm_runtime()

    _check_contains("has EPLRuntime", runtime, "const EPLRuntime =")
    _check_contains("has createElement", runtime, "createElement(")
    _check_contains("has getElementById", runtime, "getElementById(")
    _check_contains("has setText", runtime, "setText(")
    _check_contains("has getValue", runtime, "getValue(")
    _check_contains("has addClass", runtime, "addClass(")
    _check_contains("has canvas getCanvas", runtime, "getCanvas(")
    _check_contains("has drawRect", runtime, "drawRect(")
    _check_contains("has drawCircle", runtime, "drawCircle(")
    _check_contains("has drawText", runtime, "drawText(")
    _check_contains("has httpGet", runtime, "httpGet(")
    _check_contains("has httpPost", runtime, "httpPost(")
    _check_contains("has local storage store", runtime, "store(key")
    _check_contains("has local storage load", runtime, "load(key")
    _check_contains("has notify", runtime, "notify(")
    _check_contains("has copyToClipboard", runtime, "copyToClipboard(")
    _check_contains("has animate", runtime, "animate(")
    _check_contains("exports to window", runtime, "window.EPLRuntime")


@_tracked_test
def test_web_wasm_glue():
    section("6c Web — WASM Glue Convenience")
    from epl.wasm_web import generate_wasm_glue

    glue = generate_wasm_glue("Test App")
    _check("returns dict", isinstance(glue, dict))
    _check("has loader.js key", 'loader.js' in glue)
    _check("has runtime.js key", 'runtime.js' in glue)
    _check("loader has content", len(glue['loader.js']) > 100)
    _check("runtime has content", len(glue['runtime.js']) > 100)


@_tracked_test
def test_web_js_project_generation():
    section("6c Web — JS Project Generation")
    from epl.wasm_web import generate_web_project

    program = _parse('Display "Hello Web"')
    out = make_temp_dir()
    result = generate_web_project(program, out, app_name="TestWeb", mode="js")

    _check("returns output dir", result == out)
    _check_file_exists("index.html", f"{out}/public/index.html")
    _check_file_exists("app.js", f"{out}/src/js/app.js")
    _check_file_exists("style.css", f"{out}/src/css/style.css")
    _check_file_exists("package.json", f"{out}/package.json")
    _check_file_exists("manifest.json", f"{out}/public/manifest.json")
    _check_file_exists("sw.js (service worker)", f"{out}/public/sw.js")
    _check_file_exists("README.md", f"{out}/README.md")
    _check_file_exists(".gitignore", f"{out}/.gitignore")

    # Check index.html
    with open(f"{out}/public/index.html", 'r') as f:
        html = f.read()
    _check_contains("html has title", html, "TestWeb")
    _check_contains("html has app.js", html, "app.js")

    # Check app.js
    with open(f"{out}/src/js/app.js", 'r') as f:
        js = f.read()
    _check_contains("js has EPL runtime", js, "const EPL =")

    # Check package.json
    with open(f"{out}/package.json", 'r') as f:
        pkg = f.read()
    _check_contains("package.json has name", pkg, "testweb")

    # Check service worker
    with open(f"{out}/public/sw.js", 'r') as f:
        sw = f.read()
    _check_contains("sw has cache", sw, "CACHE_NAME")
    _check_contains("sw has install event", sw, "install")
    _check_contains("sw has fetch event", sw, "fetch")


@_tracked_test
def test_web_wasm_project_generation():
    section("6c Web — WASM Project Generation")
    from epl.wasm_web import generate_web_project

    program = _parse('Display "Hello WASM"')
    out = make_temp_dir()
    result = generate_web_project(program, out, app_name="TestWasm", mode="wasm")

    _check("returns output dir", result == out)
    _check_file_exists("index.html", f"{out}/public/index.html")
    _check_file_exists("loader.js", f"{out}/src/loader.js")
    _check_file_exists("runtime.js", f"{out}/src/runtime.js")
    _check_file_exists("style.css", f"{out}/src/style.css")
    _check_file_exists("package.json", f"{out}/package.json")
    _check_file_exists("build.sh", f"{out}/build.sh")
    _check_file_exists("README.md", f"{out}/README.md")

    with open(f"{out}/public/index.html", 'r') as f:
        html = f.read()
    _check_contains("wasm html has loader script", html, "loader.js")


@_tracked_test
def test_web_kotlin_js_project_generation():
    section("6c Web — Kotlin/JS Project Generation")
    from epl.wasm_web import generate_web_project

    program = _parse('Display "Hello Kotlin/JS"')
    out = make_temp_dir()
    result = generate_web_project(program, out, app_name="TestKotlinJS", mode="kotlin_js")

    _check("returns output dir", result == out)
    pkg_path = "com/epl/web"
    _check_file_exists("Main.kt", f"{out}/src/main/kotlin/{pkg_path}/Main.kt")
    _check_file_exists("index.html", f"{out}/src/main/resources/index.html")
    _check_file_exists("style.css", f"{out}/src/main/resources/style.css")
    _check_file_exists("build.gradle.kts", f"{out}/build.gradle.kts")
    _check_file_exists("settings.gradle.kts", f"{out}/settings.gradle.kts")
    _check_file_exists("gradle.properties", f"{out}/gradle.properties")

    with open(f"{out}/build.gradle.kts", 'r') as f:
        bg = f.read()
    _check_contains("kt/js gradle has kotlin js", bg, 'kotlin("js")')
    _check_contains("kt/js gradle has browser", bg, "browser {")
    _check_contains("kt/js gradle has kotlinx-html", bg, "kotlinx-html-js")

    with open(f"{out}/src/main/kotlin/{pkg_path}/Main.kt", 'r') as f:
        kt = f.read()
    _check_contains("kt/js has package", kt, "package com.epl.web")
    _check_contains("kt/js has document import", kt, "import kotlinx.browser.document")
    _check_contains("kt/js has fun main()", kt, "fun main()")


@_tracked_test
def test_web_kotlin_js_transpile():
    section("6c Web — Kotlin/JS Transpilation")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('''
Set x to 42
Display "Hello Kotlin/JS"
''')
    gen = WebCodeGenerator("Test")
    kt = gen.transpile_kotlin_js(program, 'com.test.web')

    _check_contains("has package", kt, "package com.test.web")
    _check_contains("has import document", kt, "import kotlinx.browser.document")
    _check_contains("has fun main()", kt, "fun main()")
    _check_contains("has console.log", kt, "console.log(")
    _check_contains("has x assignment", kt, "x = 42")


@_tracked_test
def test_web_html_modes():
    section("6c Web — HTML Generation Modes")
    from epl.wasm_web import WebCodeGenerator

    program = _parse('Display "Test"')

    # JS mode
    gen1 = WebCodeGenerator("Test")
    html_js = gen1.generate_html(program, mode='js')
    _check_contains("js mode has app.js", html_js, "app.js")

    # WASM mode
    gen2 = WebCodeGenerator("Test")
    html_wasm = gen2.generate_html(program, mode='wasm')
    _check_contains("wasm mode has loader.js", html_wasm, "loader.js")

    # Kotlin/JS mode
    gen3 = WebCodeGenerator("Test")
    html_kt = gen3.generate_html(program, mode='kotlin_js')
    _check("kotlin_js mode produces html", len(html_kt) > 100)


@_tracked_test
def test_web_pwa_support():
    section("6c Web — PWA Support")
    from epl.wasm_web import WebProjectGenerator

    gen = WebProjectGenerator("PWAApp")
    manifest = gen._pwa_manifest()

    _check_contains("manifest has name", manifest, "PWAApp")
    _check_contains("manifest has display", manifest, "standalone")
    _check_contains("manifest has theme_color", manifest, "theme_color")
    _check_contains("manifest has start_url", manifest, "start_url")

    sw = gen._service_worker()
    _check_contains("sw has CACHE_NAME", sw, "CACHE_NAME")
    _check_contains("sw has install handler", sw, "install")
    _check_contains("sw has fetch handler", sw, "fetch")
    _check_contains("sw has caches", sw, "caches")


# ═══════════════════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_integration_all_targets():
    section("Integration — All Targets from Same Source")

    source = '''
Set greeting to "Hello from EPL"
Display greeting

Function double takes n
    Return n * 2
End

Display double(21)
'''
    program = _parse(source)

    from epl.desktop import generate_desktop_kotlin
    from epl.wasm_web import transpile_to_web_js
    from epl.kotlin_gen import transpile_to_kotlin

    desktop_kt = generate_desktop_kotlin(program)
    web_js = transpile_to_web_js(program)
    android_kt = transpile_to_kotlin(program)

    _check("desktop generates code", len(desktop_kt) > 100)
    _check("web generates code", len(web_js) > 100)
    _check("android generates code", len(android_kt) > 50)

    _check_contains("desktop has greeting", desktop_kt, "greeting")
    _check_contains("web has greeting", web_js, "greeting")
    _check_contains("android has greeting", android_kt, "greeting")


@_tracked_test
def test_integration_gui_all_targets():
    section("Integration — GUI Across Targets")

    source = '''
Window "Test App"
    Label "Welcome"
    Button "OK" called btnOK
    TextBox called txtInput
End
'''
    program = _parse(source)

    from epl.desktop import DesktopComposeGenerator
    from epl.wasm_web import WebCodeGenerator

    dg = DesktopComposeGenerator()
    dk = dg.generate(program)
    _check_contains("desktop has Button", dk, "Button(")
    _check_contains("desktop has TextField", dk, "TextField(")

    wg = WebCodeGenerator()
    wh = wg.generate_html(program, mode='js')
    _check_contains("web has button HTML", wh, "<button")
    _check_contains("web has input HTML", wh, "<input")


@_tracked_test
def test_integration_complex_program():
    section("Integration — Complex Program")

    source = '''
Constant VERSION = "1.0"
Set items to ["apple", "banana", "cherry"]

Function findItem takes collection and target
    For Each item In collection
        If item == target Then
            Return True
        End
    End
    Return False
End

Set found to findItem(items, "banana")
If found Then
    Display "Found banana!"
Otherwise
    Display "Not found"
End

Try
    Display "Processing..."
Catch e
    Display "Error: " + e
End
'''
    program = _parse(source)

    from epl.desktop import generate_desktop_kotlin
    from epl.wasm_web import transpile_to_web_js

    dk = generate_desktop_kotlin(program)
    wj = transpile_to_web_js(program)

    _check("desktop complex output", len(dk) > 200)
    _check("web complex output", len(wj) > 200)
    _check_contains("desktop has VERSION", dk, "VERSION")
    _check_contains("web has VERSION", wj, "VERSION")
    _check_contains("desktop has findItem", dk, "findItem")
    _check_contains("web has findItem", wj, "findItem")


@_tracked_test
def test_integration_project_dirs():
    section("Integration — Full Project Directory Structures")

    from epl.desktop import generate_desktop_project
    from epl.wasm_web import generate_web_project
    from epl.kotlin_gen import generate_android_project

    program = _parse('Display "Multi-target"')

    # Desktop
    d_out = make_temp_dir()
    generate_desktop_project(program, d_out, app_name="DesktopApp")

    # Count files
    d_files = []
    for root, dirs, files in os.walk(d_out):
        d_files.extend(files)
    _check("desktop has 10+ files", len(d_files) >= 10)

    # Web JS
    w_out = make_temp_dir()
    generate_web_project(program, w_out, app_name="WebApp", mode="js")

    w_files = []
    for root, dirs, files in os.walk(w_out):
        w_files.extend(files)
    _check("web js has 7+ files", len(w_files) >= 7)

    # Web WASM
    ww_out = make_temp_dir()
    generate_web_project(program, ww_out, app_name="WasmApp", mode="wasm")

    ww_files = []
    for root, dirs, files in os.walk(ww_out):
        ww_files.extend(files)
    _check("web wasm has 6+ files", len(ww_files) >= 6)

    # Android
    a_out = make_temp_dir()
    generate_android_project(program, a_out)

    a_files = []
    for root, dirs, files in os.walk(a_out):
        a_files.extend(files)
    _check("android has 30+ files", len(a_files) >= 30)


@_tracked_test
def test_version_check():
    section("Version Check")
    from epl import __version__
    _check("version is 7.0.0", __version__ == "7.0.0")


# ═══════════════════════════════════════════════════════════
# Expression Edge Cases
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_desktop_expression_edge_cases():
    section("6a Desktop — Expression Edge Cases")
    from epl.desktop import DesktopComposeGenerator

    gen = DesktopComposeGenerator()

    # String concatenation via BinaryOp
    concat = ast.BinaryOp(ast.Literal("Hello "), '+', ast.Identifier("name"))
    result = gen._expr(concat)
    _check("string concat", "Hello" in result and "name" in result)

    # Float literal
    fl = ast.Literal(3.14)
    _check("float literal", gen._expr(fl) == "3.14")

    # Nested binary
    nested = ast.BinaryOp(
        ast.BinaryOp(ast.Literal(1), '+', ast.Literal(2)),
        '*',
        ast.Literal(3)
    )
    result = gen._expr(nested)
    _check("nested binary", '1' in result and '2' in result and '3' in result)

    # Boolean operators
    and_op = ast.BinaryOp(ast.Literal(True), 'and', ast.Literal(False))
    _check("and operator", '&&' in gen._expr(and_op))

    or_op = ast.BinaryOp(ast.Literal(True), 'or', ast.Literal(False))
    _check("or operator", '||' in gen._expr(or_op))


@_tracked_test
def test_web_js_expression_edge_cases():
    section("6c Web — JS Expression Edge Cases")
    from epl.wasm_web import WebCodeGenerator

    gen = WebCodeGenerator()

    # Power operator
    power = ast.BinaryOp(ast.Literal(2), '**', ast.Literal(10))
    result = gen._js_expr(power)
    _check("power maps to Math.pow", "Math.pow" in result)

    # Floor division
    fdiv = ast.BinaryOp(ast.Literal(7), '//', ast.Literal(2))
    result = gen._js_expr(fdiv)
    _check("floor div", "Math.floor" in result)

    # And/Or
    and_op = ast.BinaryOp(ast.Identifier("a"), 'and', ast.Identifier("b"))
    _check("and to &&", '&&' in gen._js_expr(and_op))

    or_op = ast.BinaryOp(ast.Identifier("a"), 'or', ast.Identifier("b"))
    _check("or to ||", '||' in gen._js_expr(or_op))

    # Not
    not_op = ast.UnaryOp('not', ast.Identifier("x"))
    _check("not to !", '!' in gen._js_expr(not_op))

    # None/null
    _check("null literal", gen._js_expr(ast.Literal(None)) == "null")

    # String escaping
    esc = ast.Literal('hello "world"')
    result = gen._js_expr(esc)
    _check("string escaping", '\\"' in result)


# ═══════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════

@_tracked_test
def test_cli_functions_exist():
    section("CLI — Functions Exist")
    import main as epl_main

    _check("generate_desktop exists", hasattr(epl_main, 'generate_desktop'))
    _check("generate_web exists", hasattr(epl_main, 'generate_web'))
    _check("generate_android exists", hasattr(epl_main, 'generate_android'))




# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  EPL Phase 6 Test Suite — Mobile & Desktop")
    print("  Version: 7.0.0")
    print("=" * 60)

    test_functions = [
        test_desktop_import,
        test_desktop_generator_init,
        test_desktop_simple_program,
        test_desktop_variables,
        test_desktop_function,
        test_desktop_class,
        test_desktop_conditionals,
        test_desktop_loops,
        test_desktop_while_loop,
        test_desktop_try_catch,
        test_desktop_gui_widgets,
        test_desktop_runtime,
        test_desktop_project_generation,
        test_desktop_build_gradle_details,
        test_desktop_settings_gradle,
        test_desktop_expression_codegen,
        test_desktop_widget_types,
        test_desktop_expression_edge_cases,
        test_android_import,
        test_android_kotlin_transpile,
        test_android_variables,
        test_android_functions,
        test_android_classes,
        test_android_conditionals,
        test_android_loops,
        test_android_collections,
        test_android_try_catch,
        test_android_project_generation,
        test_android_manifest_details,
        test_android_strings_xml,
        test_android_themes,
        test_android_colors,
        test_android_gradle,
        test_android_proguard,
        test_android_symbol_table,
        test_android_gui_activity,
        test_android_compose_activity,
        test_web_import,
        test_web_js_transpile,
        test_web_js_variables,
        test_web_js_functions,
        test_web_js_conditionals,
        test_web_js_loops,
        test_web_js_classes,
        test_web_js_try_catch,
        test_web_js_collections,
        test_web_js_builtins,
        test_web_js_runtime_functions,
        test_web_html_generation,
        test_web_html_widgets,
        test_web_css_generation,
        test_web_wasm_loader,
        test_web_wasm_runtime,
        test_web_wasm_glue,
        test_web_js_project_generation,
        test_web_wasm_project_generation,
        test_web_kotlin_js_project_generation,
        test_web_kotlin_js_transpile,
        test_web_html_modes,
        test_web_pwa_support,
        test_integration_all_targets,
        test_integration_gui_all_targets,
        test_integration_complex_program,
        test_integration_project_dirs,
        test_version_check,
        test_web_js_expression_edge_cases,
        test_cli_functions_exist,
    ]
    failed_sections = 0

    for fn in test_functions:
        try:
            fn()
        except AssertionError as exc:
            failed_sections += 1
            print(str(exc))

    print("\n" + "=" * 60)
    print(
        f"  Results: {_TrackerState.total_pass} passed, "
        f"{_TrackerState.total_fail} failed, {_TrackerState.total_count} total"
    )
    print("=" * 60)

    if failed_sections > 0:
        sys.exit(1)
    else:
        print("  ALL PHASE 6 TESTS PASSED!")


if __name__ == '__main__':
    main()



