# EPL Architecture

Technical overview of the EPL compiler and runtime system.

## Pipeline Overview

```
Source Code (.epl)
       │
       ▼
   ┌────────┐
   │ Lexer  │  epl/lexer.py
   └───┬────┘
       │  List[Token]
       ▼
   ┌────────┐
   │ Parser │  epl/parser.py
   └───┬────┘
       │  AST (Program)
       ▼
   ┌────────────────────────────┐
   │      Execution Targets     │
   ├────────┬─────────┬─────────┤
   │Interp. │  VM     │  LLVM   │
   │        │         │Compiler │
   │        │         │         │
   │interp- │  vm.py  │compiler │
   │reter.py│         │  .py    │
   └────────┴─────────┴─────────┘
                │
          ┌─────┴──────┐
          │ Transpilers │
          ├─────────────┤
          │ JS / Kotlin │
          └─────────────┘
```

## Module Descriptions

### Core Pipeline

| Module | File | Purpose |
|--------|------|---------|
| Tokens | `epl/tokens.py` | `TokenType` enum (100+ types) and `Token` dataclass with line/column tracking |
| Lexer | `epl/lexer.py` | Converts source text → token stream. Handles multi-word keywords, string literals, comments (`Note:`), operators |
| Parser | `epl/parser.py` | Recursive-descent parser. Tokens → AST. Produces `Program` containing statement/expression nodes |
| AST Nodes | `epl/ast_nodes.py` | 82 node classes: statements, expressions, classes, GUI, web, async, modules, generics |
| Environment | `epl/environment.py` | Scoped variable storage with parent chain for lexical scoping |
| Errors | `epl/errors.py` | `EPLError` hierarchy: `LexerError`, `ParserError`, `EPLRuntimeError`, `EPLTypeError`, `EPLNameError` |

### Execution Backends

| Backend | File | Description |
|---------|------|-------------|
| Interpreter | `epl/interpreter.py` (~2100+ lines) | Tree-walking interpreter. Visits each AST node, evaluates in `Environment`. Supports the full EPL feature set including classes, closures, file I/O, web, GUI |
| Bytecode VM | `epl/vm.py` (~2400+ lines) | `BytecodeCompiler` compiles AST → opcodes (68 types). `VM` executes stack-based bytecode. 10-50x faster than tree-walking. Includes peephole optimizer, dead code elimination, comparison folding, dict-based builtin dispatch |
| LLVM Compiler | `epl/compiler.py` (~1850 lines) | Compiles AST → LLVM IR via `llvmlite`. Produces native executables. Supports integers, floats, strings, print, conditionals, loops, functions |

### Transpilers

| Transpiler | File | Description |
|------------|------|-------------|
| JavaScript | `epl/js_transpiler.py` | AST → JavaScript source. Supports browser and Node.js targets |
| Kotlin | `epl/kotlin_gen.py` (~2130+ lines) | AST → Kotlin source with Jetpack Compose for Android UI. Full type inference via `SymbolTable`. Generates `build.gradle.kts` and project scaffold |

### Tooling

| Tool | File | Description |
|------|------|-------------|
| Package Manager | `epl/package_manager.py` (~2100+ lines) | SemVer-aware dependency management with transitive resolution, lockfiles, publish workflow |
| Packager | `epl/packager.py` | Cross-platform binary packaging: PyInstaller, Zip, and native (LLVM) packagers |
| Debugger | `epl/debugger.py` | `DebugInterpreter` subclass with breakpoints, stepping, watch expressions |
| LSP Server | `epl/lsp_server.py` | Language Server Protocol implementation for editor integration |
| Profiler | `epl/profiler.py` | Execution profiling and performance analysis |
| Test Framework | `epl/test_framework.py` | Built-in testing: `Assert`, `AssertEqual`, `AssertThrows` |
| Doc/Linter | `epl/doc_linter.py` | Documentation generator and code linter |
| AI Assistant | `epl/ai.py` | Code generation, explanation, and AI-assisted development |
| Type System | `epl/type_system.py` | Optional type annotations and static type checking |
| Standard Library | `epl/stdlib.py` | Built-in math, string, collection, and utility functions |

### Web & GUI

| Module | File | Description |
|--------|------|-------------|
| Web Framework | `epl/web.py` | Route-based web server with templating |
| WSGI | `epl/wsgi.py` | WSGI adapter for production deployment |
| HTML Generator | `epl/html_gen.py` | AST → HTML rendering for web pages |
| GUI | `epl/gui.py` | Desktop GUI via tkinter: windows, widgets, events, canvas |

### Data & I/O

| Module | File | Description |
|--------|------|-------------|
| Database | `epl/database.py`, `epl/database_real.py` | ORM-style database operations with Store/Fetch/Delete |
| Networking | `epl/networking.py` | HTTP client and socket operations |
| Async I/O | `epl/async_io.py` | Async/await support |
| Concurrency | `epl/concurrency.py`, `epl/concurrency_real.py` | Threading and parallel execution |

## AST Node Hierarchy

All nodes inherit from `ASTNode` (base has `line` attribute for error reporting).

**Core Nodes:**
- `Program` → `statements: list`
- `VarDeclaration` → `name`, `value`, `type_annotation`
- `VarAssignment` → `target`, `value`
- `PrintStatement` → `value`
- `IfStatement` → `condition`, `then_body`, `else_body`
- `FunctionDef` → `name`, `params` (3-tuples: name, type, default), `body`, `return_type`
- `FunctionCall` → `name`, `arguments`
- `ClassDef` → `name`, `body`, `parent_class`, `interfaces`
- `BinaryOp` → `left`, `op`, `right`
- `Literal` → `value`
- `Identifier` → `name`

**Collection Nodes:**
- `ListLiteral`, `DictLiteral`, `IndexAccess`, `IndexSet`, `SliceAccess`

**Method/Property Nodes:**
- `MethodCall` → `obj`, `method_name`, `arguments`
- `PropertyAccess` → `obj`, `property_name`
- `PropertySet` → `obj`, `property_name`, `value`

**Control Flow Nodes:**
- `WhileLoop`, `RepeatLoop`, `ForEachLoop`, `ForRange`
- `MatchStatement`, `WhenClause`, `TernaryExpression`
- `BreakStatement`, `ContinueStatement`, `ReturnStatement`

**Advanced Nodes:**
- `LambdaExpression`, `AsyncFunctionDef`, `AwaitExpression`
- `TryCatch`, `TryCatchFinally`, `ThrowStatement`
- `ImportStatement`, `ModuleDef`, `ModuleAccess`, `ExportStatement`
- `GenericClassDef`, `InterfaceDefNode`, `ImplementsClause`
- `SuperCall`, `YieldStatement`, `DestructureAssignment`, `SpreadExpression`

## VM Bytecode Architecture

The VM uses a stack-based architecture with 68 opcodes:

```
┌────────────────────────────────┐
│         Call Stack              │
│  ┌───────────────────────┐     │
│  │ Frame: locals, pc, sp │     │
│  └───────────────────────┘     │
│           ...                   │
├────────────────────────────────┤
│        Operand Stack            │
│  ┌─┬─┬─┬─┬─┬─┬─┬─┬─┬──┐      │
│  │ values pushed/popped  │      │
│  └─┴─┴─┴─┴─┴─┴─┴─┴─┴──┘      │
├────────────────────────────────┤
│       Constant Pool             │
│  [0] 42  [1] "hello" ...       │
├────────────────────────────────┤
│     Bytecode Instructions       │
│  (LOAD_CONST, 0)               │
│  (LOAD_VAR, "x")               │
│  (ADD, None)                    │
│  (STORE_VAR, "result")         │
└────────────────────────────────┘
```

**Opcode Categories:**
- Stack: `LOAD_CONST`, `LOAD_VAR`, `STORE_VAR`, `POP`, `DUP`, `ROT_TWO`
- Arithmetic: `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `POW`, `FLOOR_DIV`, `NEG`
- Comparison: `EQ`, `NEQ`, `LT`, `GT`, `LTE`, `GTE`
- Logic: `AND`, `OR`, `NOT`
- Control: `JUMP`, `JUMP_IF_FALSE`, `JUMP_IF_TRUE`, `CALL`, `RETURN`
- Collections: `BUILD_LIST`, `BUILD_DICT`, `INDEX`, `INDEX_SET`, `SLICE`
- OOP: `NEW_INSTANCE`, `GET_PROP`, `SET_PROP`, `CALL_METHOD`
- Built-ins: `CALL_BUILTIN`, `PRINT`, `INPUT`

**Optimizations:**
1. **Peephole optimizer** — Removes redundant `STORE_VAR`/`LOAD_VAR` pairs, with instruction reindexing
2. **Dead code elimination** — Removes unreachable code after unconditional jumps
3. **Comparison constant folding** — Evaluates constant comparisons at compile time
4. **Dict-based builtin dispatch** — O(1) lookup instead of if/elif chains

## LLVM Compilation Pipeline

```
AST → Compiler → LLVM IR → llvmlite → Object Code → Linker → Native Binary
```

The `Compiler` class (in `compiler.py`) uses `llvmlite` to:
1. Create LLVM module with target triple
2. Declare external C functions (`printf`, `scanf`, `strlen`, etc.)
3. Walk the AST, emitting LLVM IR instructions
4. Optimize with LLVM's built-in pass manager
5. Generate native object code
6. Link with system C library to produce an executable

## Kotlin/Android Pipeline

```
AST → KotlinGenerator → .kt files → build.gradle.kts → Android Project
```

The `KotlinGenerator` uses:
1. `SymbolTable` for type inference across scopes
2. AST traversal emitting idiomatic Kotlin
3. Jetpack Compose mapping for GUI/web nodes
4. Project scaffolding: `AndroidManifest.xml`, Gradle config, directory structure

## Entry Point

`epl/cli.py` is the authoritative CLI implementation.

`main.py` is the source-checkout wrapper that delegates to the same command surface.

Primary commands:

| Command | Action |
|---------|--------|
| `<file.epl>` | Lex → Parse → Interpret |
| `vm <file.epl>` | Lex → Parse → BytecodeCompile → VM Execute |
| `compile <file.epl>` | Lex → Parse → LLVM Compile → Native Binary |
| `kotlin <file.epl>` | Lex → Parse → Kotlin Transpile |
| `android <file.epl>` | Lex → Parse → Full Android Project |
| `js <file.epl>` | Lex → Parse → JavaScript Transpile |
| `init` | Initialize package with `epl.toml` (`epl.json` legacy fallback) |
| `install <pkg>` | Install dependency via package manager |
| `package <file.epl>` | Build standalone binary via packager |

## Test Suite

| Suite | File | Tests | Covers |
|-------|------|-------|--------|
| Core Regression | `tests/test_epl.py` | 271 | Full interpreter: variables, functions, classes, loops, I/O, imports, web |
| v4 Features | `tests/run_tests.py` | 44 | Augmented assignment, ternary, enums, match, super, try/finally, modules |
| LLVM Compiler | `tests/test_llvm.py` | 26 | Native compilation: ints, floats, strings, conditionals, functions, loops |
| Kotlin Transpiler | `tests/test_kotlin.py` | 30 | Kotlin output: types, classes, Compose UI, generics, sealed classes |
| Bytecode VM | `tests/test_vm.py` | 43 | VM execution + all optimizations |
| Package Manager | `tests/test_package_manager.py` | 91 | SemVer, dependencies, lockfiles, publish, validation |
| Stability | `tests/test_stability.py` | 42 | Edge cases, error handling, overflow protection, short-circuit logic |
| **Total** | | **547** | |

## Directory Layout

```
EPL/
├── main.py                  Source-checkout wrapper over the authoritative CLI
├── epl/
│   ├── cli.py               Authoritative CLI entry point
│   ├── tokens.py            Token types
│   ├── lexer.py             Tokenizer
│   ├── parser.py            Recursive-descent parser
│   ├── ast_nodes.py         82 AST node classes
│   ├── environment.py       Scoped variable storage
│   ├── errors.py            Error hierarchy
│   ├── interpreter.py       Tree-walking interpreter
│   ├── vm.py                Bytecode compiler + VM
│   ├── compiler.py          LLVM native compiler
│   ├── kotlin_gen.py        Kotlin/Android transpiler
│   ├── js_transpiler.py     JavaScript transpiler
│   ├── package_manager.py   Package management
│   ├── packager.py          Binary packaging
│   ├── debugger.py          Interactive debugger
│   ├── lsp_server.py        Language server
│   ├── profiler.py          Performance profiler
│   ├── test_framework.py    Built-in test runner
│   ├── stdlib.py            Standard library
│   ├── type_system.py       Type annotations
│   ├── web.py / wsgi.py     Web framework
│   ├── gui.py               Desktop GUI
│   ├── html_gen.py          HTML generation
│   ├── ai.py                AI assistant
│   ├── database.py          Database ORM
│   ├── networking.py        HTTP / sockets
│   ├── async_io.py          Async support
│   └── concurrency.py       Threading
├── docs/                    Documentation
├── tests/                   Test suites
└── examples/                Example programs
```
