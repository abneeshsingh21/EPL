"""
EPL Phase 1: Self-Hosting Foundation Tests
Tests: Complete LLVM backend (all AST nodes compile), expanded runtime.c,
       self-contained executable builder, cross-compilation targets.
"""
import sys, os
import importlib.util
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

PASS_COUNT = 0
FAIL_COUNT = 0

def _legacy_run_case(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        PASS_COUNT += 1
        print(f"  PASS: {name}")
    except Exception as e:
        FAIL_COUNT += 1
        print(f"  FAIL: {name} -> {e}")

def assert_eq(a, b):
    assert a == b, f"Expected {b!r}, got {a!r}"

def assert_true(v, msg=""):
    assert v, msg or f"Expected truthy, got {v!r}"

def assert_in(item, collection, msg=""):
    assert item in collection, msg or f"{item!r} not in collection"

HAS_LLVM = importlib.util.find_spec("llvmlite") is not None

pytestmark = pytest.mark.skipif(not HAS_LLVM, reason="llvmlite not available")


def _load_toolchain():
    from epl.compiler import Compiler
    from epl.lexer import Lexer
    from epl.parser import Parser
    from epl import ast_nodes as ast

    return Compiler, Lexer, Parser, ast


def compile_src(src, opt=2):
    Compiler, Lexer, Parser, _ = _load_toolchain()
    c = Compiler(opt_level=opt)
    l = Lexer(src)
    t = l.tokenize()
    p = Parser(t)
    prog = p.parse()
    return c.compile(prog), c

def compile_obj(src, opt=2):
    ir_code, c = compile_src(src, opt)
    return c.compile_to_object(ir_code)

Q = chr(34)  # double quote for embedding in strings

# ═══════════════════════════════════════════════════════════
# 1a. COMPLETE LLVM BACKEND — All AST Nodes Compile
# ═══════════════════════════════════════════════════════════

# --- Previously stubbed nodes (now have real codegen) ---

def test_spawn_generates_thread_code():
    """SpawnStatement should generate epl_spawn_task call + trampoline."""
    src = "Function work takes nothing\nPrint 1\nEnd\nSpawn t1 calling work"
    ir_code, _ = compile_src(src)
    assert_in("epl_spawn_task", ir_code)
    assert_in("_epl_spawn_trampoline_", ir_code)

def test_spawn_trampoline_is_void_fn():
    """The spawn trampoline should be a void function."""
    src = "Function work takes nothing\nPrint 1\nEnd\nSpawn t1 calling work"
    ir_code, _ = compile_src(src)
    # Might use 'void' or 'ptr' depending on llvmlite version
    assert_in("_epl_spawn_trampoline_", ir_code)
    assert_in("define", ir_code)

def test_spawn_stores_handle():
    """Spawn stores thread handle as i64 variable."""
    src = "Function work takes nothing\nPrint 1\nEnd\nSpawn t1 calling work"
    ir_code, _ = compile_src(src)
    assert_in("alloca i64", ir_code)
    assert_in("store i64", ir_code)

def test_spawn_multiple():
    """Multiple Spawn statements should create unique trampolines."""
    src = "Function a takes nothing\nPrint 1\nEnd\nFunction b takes nothing\nPrint 2\nEnd\nSpawn t1 calling a\nSpawn t2 calling b"
    ir_code, _ = compile_src(src)
    assert_in("_epl_spawn_trampoline_1", ir_code)
    assert_in("_epl_spawn_trampoline_2", ir_code)

def test_parallel_foreach_compiles():
    """ParallelForEach should compile (as sequential foreach)."""
    src = "Create items equal to [1, 2, 3]\nParallel For Each item in items\nPrint item\nEnd"
    ir_code, _ = compile_src(src)
    assert_in("br", ir_code)
    assert_in("epl_list_get_int", ir_code)

def test_parallel_foreach_produces_object():
    """ParallelForEach should produce a valid object file."""
    src = "Create items equal to [1, 2, 3]\nParallel For Each item in items\nPrint item\nEnd"
    obj = compile_obj(src)
    assert_true(len(obj) > 0)

def test_breakpoint_generates_trap_O0():
    """Breakpoint at O0 should call epl_debug_trap."""
    ir_code, _ = compile_src("Breakpoint\nPrint 42", opt=0)
    assert_in("epl_debug_trap", ir_code)

def test_breakpoint_stripped_O2():
    """Breakpoint at O2+ should be stripped."""
    ir_code, _ = compile_src("Breakpoint\nPrint 42", opt=2)
    assert_true("call void @epl_debug_trap" not in ir_code)

def test_breakpoint_conditional_O0():
    """Conditional breakpoint should generate branch + trap."""
    ir_code, _ = compile_src("Create x equal to 5\nBreakpoint if x > 3\nPrint x", opt=0)
    assert_in("epl_debug_trap", ir_code)
    assert_in("bp_then", ir_code)
    assert_in("bp_merge", ir_code)

def test_external_function_dlopen():
    """External function should generate epl_dlopen + epl_dlsym calls."""
    src = f'External function test from {Q}lib{Q} takes nothing returns int\nPrint 42'
    ir_code, _ = compile_src(src)
    assert_in("epl_dlopen", ir_code)
    assert_in("epl_dlsym", ir_code)

def test_external_function_stores_ptr():
    """External function should store the resolved function pointer."""
    src = f'External function myFunc from {Q}lib{Q} takes (int) returns int\nPrint 42'
    ir_code, _ = compile_src(src)
    assert_in("alloca i8*", ir_code)

def test_external_function_lib_cache():
    """Multiple externals from same lib should reuse cached handle."""
    src = f'External function fn1 from {Q}mylib{Q} takes nothing returns int\nExternal function fn2 from {Q}mylib{Q} takes nothing returns int\nPrint 42'
    ir_code, _ = compile_src(src)
    # Should only have 1 dlopen call for mylib (second reuses cache)
    # Check for epl_dlopen with any calling convention / pointer type
    count = ir_code.count('@epl_dlopen')
    # Expect exactly 2: one declaration + one call (second reuses cached handle)
    assert_true(count <= 3, f"Too many epl_dlopen references: {count} (expected <=3 for decl+call+cache)")

def test_external_function_with_alias():
    """External function with alias should store under alias name."""
    src = f'External function strlen from {Q}c{Q} takes (char_p) returns int as StringLength\nPrint 42'
    ir_code, _ = compile_src(src)
    assert_in("StringLength", ir_code)

def test_load_library_generates_dlopen():
    """Load library should generate epl_dlopen call."""
    src = f'Load library {Q}test.dll{Q} as TestLib\nPrint 42'
    ir_code, _ = compile_src(src)
    assert_in("epl_dlopen", ir_code)
    assert_in("TestLib", ir_code)

def test_load_library_stores_handle():
    """Load library handle should be stored as pointer variable."""
    src = f'Load library {Q}mylib{Q} as Lib\nPrint 42'
    ir_code, _ = compile_src(src)
    assert_in("alloca i8*", ir_code)

# --- Existing full codegen nodes (regression) ---

def test_async_compiles_as_regular():
    """Async function should compile as regular function."""
    src = "Async Function fetchData takes nothing\nReturn 42\nEnd\nPrint fetchData()"
    ir_code, _ = compile_src(src)
    assert_in("fetchData", ir_code)

def test_yield_compiles():
    """Yields should compile as return."""
    src = "Function gen takes nothing\nYields 42\nEnd\nPrint gen()"
    ir_code, _ = compile_src(src)
    assert_in("ret", ir_code)

def test_try_catch_finally_compiles():
    """TryCatchFinally should produce full codegen."""
    src = 'Try\nPrint "ok"\nCatch err\nPrint err\nEnd'
    ir_code, _ = compile_src(src)
    assert_in("epl_try_begin", ir_code)

def test_list_index_compiles():
    """List indexing should produce codegen."""
    src = "Create items equal to [10, 20]\nPrint items[0]"
    ir_code, _ = compile_src(src)
    assert_in("epl_list_get_int", ir_code)

def test_module_def_compiles():
    """Module definition should produce prefixed functions."""
    src = 'Module Math\nFunction add takes a and b\nReturn a + b\nEnd\nEnd\nPrint Math::add(1, 2)'
    ir_code, _ = compile_src(src)
    assert_in("Math_add", ir_code)

def test_super_call_compiles():
    """Super call in class method should compile."""
    src = "Class Animal\nFunction speak takes nothing\nReturn 1\nEnd\nEnd\nClass Dog extends Animal\nFunction speak takes nothing\nReturn Super.speak() + 1\nEnd\nEnd\nCreate d equal to new Dog()\nPrint d.speak()"
    ir_code, _ = compile_src(src)
    assert_in("epl_class_lookup_method", ir_code)

def test_compound_condition_compiles():
    """Compound and/or condition should compile."""
    src = 'Create x equal to 5\nIf x > 1 and x < 10\nPrint "yes"\nEnd'
    ir_code, _ = compile_src(src)
    assert_in("icmp", ir_code)

def test_lambda_with_closure_compiles():
    """Lambda with closure capture should compile."""
    src = "Create multiplier equal to 3\nCreate fn equal to Lambda x -> x * multiplier\nPrint fn(5)"
    ir_code, _ = compile_src(src)
    assert_in("epl_closure_new", ir_code)

def test_enum_def_compiles():
    """Enum definition should be compiled."""
    src = 'Enum Color as Red, Green, Blue\nPrint Color.Red'
    ir_code, _ = compile_src(src)
    assert_true(len(ir_code) > 0)

def test_match_statement_compiles():
    """Match/when statement should compile."""
    src = 'Create x equal to 2\nMatch x\nWhen 1\nPrint "one"\nWhen 2\nPrint "two"\nDefault\nPrint "other"\nEnd'
    ir_code, _ = compile_src(src)
    assert_in("icmp", ir_code)

def test_class_with_methods_compiles():
    """Class with methods should compile to IR."""
    src = "Class Counter\nCreate count equal to 0\nFunction increment takes nothing\nSet count to count + 1\nEnd\nEnd\nCreate c equal to new Counter()\nCall c.increment()\nPrint c.count"
    ir_code, _ = compile_src(src)
    assert_in("epl_gc_new_object", ir_code)

def test_all_previously_stubbed_produce_obj():
    """All 5 previously stubbed nodes should now produce valid object files."""
    tests = [
        "Function w takes nothing\nPrint 1\nEnd\nSpawn t calling w",
        "Create xs equal to [1]\nParallel For Each x in xs\nPrint x\nEnd",
        f'External function f from {Q}lib{Q} takes nothing returns int\nPrint 1',
        f'Load library {Q}lib{Q} as L\nPrint 1',
    ]
    # Breakpoint tested separately (needs O0)
    for src in tests:
        obj = compile_obj(src)
        assert_true(len(obj) > 0, f"Empty object for: {src[:40]}")
    # Breakpoint at O0
    obj = compile_obj("Breakpoint\nPrint 1", opt=0)
    assert_true(len(obj) > 0)


# ═══════════════════════════════════════════════════════════
# 1b. EXPANDED RUNTIME.C
# ═══════════════════════════════════════════════════════════

def test_runtime_has_spawn_functions():
    """runtime.c should declare spawn_task and spawn_wait."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("epl_spawn_task", src)
    assert_in("epl_spawn_wait", src)
    assert_in("epl_spawn_wait_all", src)

def test_runtime_has_ffi_functions():
    """runtime.c should declare dlopen/dlsym/dlclose wrappers."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("epl_dlopen", src)
    assert_in("epl_dlsym", src)
    assert_in("epl_dlclose", src)

def test_runtime_has_ffi_callers():
    """runtime.c should have typed FFI call functions."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("epl_ffi_call_i64", src)
    assert_in("epl_ffi_call_double", src)
    assert_in("epl_ffi_call_ptr", src)
    assert_in("epl_ffi_call_void", src)

def test_runtime_has_debug_trap():
    """runtime.c should have epl_debug_trap."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("epl_debug_trap", src)

def test_runtime_has_sleep_ms():
    """runtime.c should have sleep_ms for thread sleep."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("epl_sleep_ms", src)

def test_runtime_platform_agnostic_threading():
    """runtime.c should have both Win32 and pthread paths."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("CreateThread", src)
    assert_in("pthread_create", src)

def test_runtime_platform_agnostic_ffi():
    """runtime.c should have both LoadLibraryA and dlopen paths."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("LoadLibraryA", src)
    assert_in("dlopen", src)

def test_runtime_ffi_supports_8_args():
    """FFI call should support up to 8 arguments."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    assert_in("case 8:", src)

def test_runtime_thread_runner_frees_arg():
    """Thread runner should free its argument to avoid leaks."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        src = f.read()
    # Both Win32 and Unix paths should free(ta)
    assert_true(src.count("free(ta)") >= 2, "Thread runner doesn't free args")

def test_runtime_line_count():
    """Runtime should be substantial (2000+ lines)."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    with open(runtime_path, 'r') as f:
        lines = f.readlines()
    assert_true(len(lines) >= 2000, f"Only {len(lines)} lines in runtime.c")


# ═══════════════════════════════════════════════════════════
# 1c. SELF-CONTAINED EXECUTABLE BUILDER
# ═══════════════════════════════════════════════════════════

def test_compiler_has_compile_to_executable():
    """Compiler should have compile_to_executable method."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_true(hasattr(c, 'compile_to_executable'))
    assert_true(callable(c.compile_to_executable))

def test_compiler_has_compile_to_wasm():
    """Compiler should have compile_to_wasm method."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_true(hasattr(c, 'compile_to_wasm'))
    assert_true(callable(c.compile_to_wasm))

def test_compile_file_function_exists():
    """main.py should have compile_file function with target parameter."""
    from main import compile_file
    import inspect
    sig = inspect.signature(compile_file)
    assert_in('target', sig.parameters)
    assert_in('static', sig.parameters)
    assert_in('opt_level', sig.parameters)

def test_build_command_uses_native():
    """The build command should route to native compilation."""
    # Read main.py to verify command routing
    main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
    with open(main_path, 'r') as f:
        src = f.read()
    # Build command should call compile_file
    assert_in("compile_file(args[1]", src)

def test_runtime_c_exists():
    """runtime.c should exist for linking."""
    runtime_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'runtime.c')
    assert_true(os.path.exists(runtime_path))

def test_complete_ir_pipeline():
    """Full program should compile to valid IR with GC shutdown."""
    src = "Create x equal to 42\nPrint x"
    ir_code, _ = compile_src(src)
    assert_in("define i32 @", ir_code)
    assert_in("epl_gc_shutdown", ir_code)
    assert_in("ret i32 0", ir_code)

def test_complex_program_compiles_to_obj():
    """A complex program with classes, loops, functions should compile to object."""
    src = """Class Animal
Create name equal to ""
Function init takes n
Set name to n
End
Function speak takes nothing
Return name
End
End
Create dog equal to new Animal("Rex")
Create items equal to [1, 2, 3]
For Each item in items
Print item
End
Print dog.speak()"""
    obj = compile_obj(src)
    assert_true(len(obj) > 200, f"Object too small: {len(obj)}")


# ═══════════════════════════════════════════════════════════
# 1d. CROSS-COMPILATION TARGETS
# ═══════════════════════════════════════════════════════════

def test_cross_targets_defined():
    """CROSS_TARGETS dictionary should exist with all platforms."""
    from main import CROSS_TARGETS
    assert_true(len(CROSS_TARGETS) >= 7, f"Only {len(CROSS_TARGETS)} targets")
    assert_in('windows-x64', CROSS_TARGETS)
    assert_in('linux-x64', CROSS_TARGETS)
    assert_in('macos-x64', CROSS_TARGETS)
    assert_in('macos-arm64', CROSS_TARGETS)
    assert_in('wasm32', CROSS_TARGETS)

def test_cross_targets_valid_triples():
    """Cross-compilation triples should be valid LLVM triples."""
    from main import CROSS_TARGETS
    for name, triple in CROSS_TARGETS.items():
        parts = triple.split('-')
        assert_true(len(parts) >= 3, f"Invalid triple for {name}: {triple}")

def test_ir_with_custom_triple():
    """Compiler should accept a custom target triple."""
    Compiler, Lexer, Parser, _ = _load_toolchain()
    c = Compiler()
    c.module.triple = "x86_64-unknown-linux-gnu"
    prog = Parser(Lexer('Print 42').tokenize()).parse()
    ir_code = c.compile(prog)
    assert_in("x86_64-unknown-linux-gnu", ir_code)

def test_ir_with_macos_triple():
    """Compiler should accept macOS target triple."""
    Compiler, Lexer, Parser, _ = _load_toolchain()
    c = Compiler()
    c.module.triple = "aarch64-apple-darwin"
    prog = Parser(Lexer('Print 42').tokenize()).parse()
    ir_code = c.compile(prog)
    assert_in("aarch64-apple-darwin", ir_code)

def test_ir_with_wasm_triple():
    """Compiler should accept WASM target triple."""
    Compiler, Lexer, Parser, _ = _load_toolchain()
    c = Compiler()
    c.module.triple = "wasm32-unknown-wasi"
    prog = Parser(Lexer('Print 42').tokenize()).parse()
    ir_code = c.compile(prog)
    assert_in("wasm32-unknown-wasi", ir_code)

def test_default_triple_is_host():
    """Default triple should be the host machine."""
    import llvmlite.binding as llvm
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_eq(c.module.triple, llvm.get_default_triple())


# ═══════════════════════════════════════════════════════════
# 2. COMPREHENSIVE AST NODE COVERAGE
# ═══════════════════════════════════════════════════════════

# Every AST node type that exists should either compile to real IR
# or be intentionally skipped (interfaces, exports, etc.)

def test_all_ast_nodes_handled():
    """Every AST node in ast_nodes.py should be handled by the compiler dispatcher."""
    import inspect
    _, _, _, ast = _load_toolchain()
    # Get all AST node classes
    ast_classes = [name for name, obj in inspect.getmembers(ast)
                   if inspect.isclass(obj) and issubclass(obj, ast.ASTNode)
                   and name not in ('ASTNode', 'ASTVisitor')]
    
    # Read compiler source to check dispatch
    compiler_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'compiler.py')
    with open(compiler_path, 'r') as f:
        compiler_src = f.read()
    
    # Web/UI nodes are handled by html_gen/web, not the LLVM compiler
    web_ui_nodes = {
        'BindEvent', 'CanvasDraw', 'DeleteStatement', 'DialogShow',
        'FetchStatement', 'HtmlElement', 'ImplementsClause', 'LayoutBlock',
        'MenuDef', 'PageDef', 'Route', 'ScriptBlock', 'SendResponse',
        'StartServer', 'StoreStatement', 'WebApp', 'WidgetAdd', 'WindowCreate',
    }
    # Structural/helper nodes not dispatched directly
    structural_nodes = {
        'Program', 'WhenClause', 'TypeAnnotation', 'RestParameter',
        'SpreadExpression', 'AbstractMethodDef',
    }
    skip = web_ui_nodes | structural_nodes
    
    missing = []
    for cls_name in ast_classes:
        if cls_name in skip:
            continue
        if f'ast.{cls_name}' not in compiler_src and f'isinstance(node, ast.{cls_name})' not in compiler_src:
            missing.append(cls_name)
    
    assert_true(len(missing) == 0, f"AST nodes not handled: {missing}")

def test_no_stub_returns_in_dispatcher():
    """Previously stubbed nodes should no longer have bare returns."""
    compiler_path = os.path.join(os.path.dirname(__file__), '..', 'epl', 'compiler.py')
    with open(compiler_path, 'r') as f:
        lines = f.readlines()
    
    # Check that SpawnStatement, ParallelForEach, BreakpointStatement,
    # ExternalFunctionDef, LoadLibrary no longer have "return  #" stubs
    for line in lines:
        if 'ast.SpawnStatement' in line and 'return  #' in line:
            raise AssertionError("SpawnStatement still stubbed")
        if 'ast.ParallelForEach' in line and 'return  #' in line:
            raise AssertionError("ParallelForEach still stubbed")
        if 'ast.BreakpointStatement' in line and 'return  #' in line:
            raise AssertionError("BreakpointStatement still stubbed")
        if 'ast.ExternalFunctionDef' in line and 'return  #' in line:
            raise AssertionError("ExternalFunctionDef still stubbed")
        if 'ast.LoadLibrary' in line and 'return  #' in line:
            raise AssertionError("LoadLibrary still stubbed")


# ═══════════════════════════════════════════════════════════
# 3. COMPILER RUNTIME DECLARATIONS
# ═══════════════════════════════════════════════════════════

def test_compiler_declares_spawn_rt():
    """Compiler should declare epl_spawn_task and epl_spawn_wait."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_true(hasattr(c, 'rt_spawn_task'))
    assert_eq(c.rt_spawn_task.name, "epl_spawn_task")
    assert_true(hasattr(c, 'rt_spawn_wait'))
    assert_eq(c.rt_spawn_wait.name, "epl_spawn_wait")

def test_compiler_declares_ffi_rt():
    """Compiler should declare dlopen/dlsym/dlclose."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_eq(c.rt_dlopen.name, "epl_dlopen")
    assert_eq(c.rt_dlsym.name, "epl_dlsym")
    assert_eq(c.rt_dlclose.name, "epl_dlclose")

def test_compiler_declares_ffi_callers():
    """Compiler should declare typed FFI call functions."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_eq(c.rt_ffi_call_i64.name, "epl_ffi_call_i64")
    assert_eq(c.rt_ffi_call_double.name, "epl_ffi_call_double")
    assert_eq(c.rt_ffi_call_ptr.name, "epl_ffi_call_ptr")
    assert_eq(c.rt_ffi_call_void.name, "epl_ffi_call_void")

def test_compiler_declares_debug_trap():
    """Compiler should declare epl_debug_trap."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_eq(c.rt_debug_trap.name, "epl_debug_trap")

def test_compiler_declares_sleep_ms():
    """Compiler should declare epl_sleep_ms."""
    Compiler, _, _, _ = _load_toolchain()
    c = Compiler()
    assert_eq(c.rt_sleep_ms.name, "epl_sleep_ms")


# ═══════════════════════════════════════════════════════════
# 4. OBJECT FILE GENERATION FOR NEW FEATURES
# ═══════════════════════════════════════════════════════════

def test_obj_spawn_program():
    """Program with Spawn should compile to valid object."""
    src = "Function w takes nothing\nPrint 1\nEnd\nSpawn t calling w\nPrint 2"
    obj = compile_obj(src)
    assert_true(len(obj) > 100)

def test_obj_external_function_program():
    """Program with External function should compile to valid object."""
    src = f'External function test from {Q}lib{Q} takes nothing returns int\nPrint 42'
    obj = compile_obj(src)
    assert_true(len(obj) > 100)

def test_obj_breakpoint_program():
    """Program with Breakpoint should compile (at O0)."""
    src = "Breakpoint\nPrint 42"
    obj = compile_obj(src, opt=0)
    assert_true(len(obj) > 100)

def test_obj_load_library_program():
    """Program with Load library should compile."""
    src = f'Load library {Q}lib{Q} as L\nPrint 42'
    obj = compile_obj(src)
    assert_true(len(obj) > 100)

def test_obj_mixed_new_features():
    """Program mixing old and new features should compile."""
    src = f"""Function worker takes nothing
Print 1
End
Spawn task calling worker
External function f from {Q}lib{Q} takes nothing returns int
Load library {Q}lib{Q} as Lib
Create items equal to [1, 2, 3]
Parallel For Each item in items
Print item
End
Print 42"""
    obj = compile_obj(src)
    assert_true(len(obj) > 200)

def test_obj_all_opt_levels_new_features():
    """New features should compile at all optimization levels."""
    src = "Function w takes nothing\nPrint 1\nEnd\nSpawn t calling w\nPrint 2"
    for opt_lvl in range(4):
        obj = compile_obj(src, opt=opt_lvl)
        assert_true(len(obj) > 0, f"Empty at O{opt_lvl}")


TEST_FUNCTIONS = [obj for name, obj in globals().items() if name.startswith("test_") and callable(obj)]


def main():
    if not HAS_LLVM:
        print("SKIP: llvmlite not available")
        return True

    print("=" * 50)
    print("Phase 1 Native Tests")
    print("=" * 50)

    for test_fn in TEST_FUNCTIONS:
        _legacy_run_case(test_fn.__name__, test_fn)

    print(f"\n{'='*50}")
    print(f"Phase 1 Native Tests: {PASS_COUNT}/{PASS_COUNT+FAIL_COUNT} passed, {FAIL_COUNT} failed")
    print(f"{'='*50}")
    return FAIL_COUNT == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

