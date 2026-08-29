<div align="center">

# Changelog

All notable changes to the **English Programming Language (EPL)** are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

</div>

---

## [Unreleased]

## [11.0.0] — 2026-08-29

### Added — Phase 5 (Deep) HIR Transpilation & Semantic Parity
- **SSA CFG Direct Lowering**: Native transpilation directly from SSA Control Flow Graphs (`epl/hir_transpiler.py`) targeting Python 3, JavaScript ES2020, and Kotlin.
- **Cross-Runtime Semantic Parity**: Uniform Unicode scalar indexing/slicing, 64-bit signed integer overflow wrapping, and lexical closure variable reference cells (`epl/semantic_parity.py`).
- **Differential Parity Test Suite**: Comprehensive golden testing locking cross-runtime execution semantics (`tests/test_phase5_transpiler_parity.py`).

### Added — Phase 6 Security, Formal Foundations & Governance
- **Zero-Trust Package Signing**: Asymmetric Ed25519 / SHA-256 cryptographic signing and manifest verification engine (`epl/crypto_signing.py`).
- **Kernel-Level OS Sandboxing**: POSIX resource limits (`rlimit`), Linux `prctl(PR_SET_NO_NEW_PRIVS)`, `seccomp-bpf` syscall filters, and Windows restricted token containment (`epl/sandbox_os.py`).
- **Formal Operational Semantics**: Mechanized Big-Step / Small-Step structural operational semantics with determinism proof validation (`epl/formal_semantics.py`, `docs/operational_semantics.md`).
- **Differential Fuzzing Engine**: Automated generative differential fuzzer testing AST Interpreter vs SSA HIR vs Formal Semantics (`tests/test_differential_fuzzing.py`).
- **Production Governance Quality Gates**: Automated release verification and test suites (`tests/test_phase6_governance.py`, `tests/test_phase6_security_formal.py`).

### Changed — Kotlin runtime extracted to a single source of truth (+ console/JVM target)

The inline `EPLRuntime` Kotlin shim moved out of `kotlin_gen.py` into
`epl/kotlin_runtime.py`, assembled per target from one semantic core plus
platform slots (base64 / json / db / file):

- `android_runtime()` stays **byte-identical** to the historically verified APK
  runtime (SQLite `db_*`, `android.util.Base64`, `org.json`); a golden-file test
  (`tests/test_kotlin_runtime_golden.py`) locks it against drift.
- `console_runtime()` fills the slots with plain-JVM equivalents plus a
  dependency-free `JsonMini`, so a standalone `epl kotlin` transpile compiles and
  runs with only `kotlin-stdlib` on the classpath. `transpile_to_kotlin` now
  appends this shim by default (`include_runtime=True`).

### Fixed — Kotlin/Android transpiler correctness (compiler-verified, real-APK)

A further batch surfaced by compiling the example corpus through the real Kotlin
toolchain (`compileDebugKotlin` + `assembleDebug` → installable APK):

- **`for each` over a list-of-maps emitted `.keys`** — the iterable type check
  matched the substring `Map` inside `MutableList<Map<…>>`, so a list of rows
  (e.g. a `db_query` result) iterated a Map-only member and failed to compile. It
  now matches on the type prefix in the correct order.
- **`Display`/`Say` of a dynamic value** hit Kotlin's `println(Any?)` overload
  ambiguity and wouldn't match EPL's display formatting; dynamic values now print
  through `EPLRuntime.toText` (string literals still print directly).
- **Reassigning a function parameter** (`Set n to n / 2`) redeclared it as a
  fresh `var` and violated Kotlin's immutable `val` parameters. Reassigned params
  now get a mutable shadow (`var n = n`) at function top.
- **Math builtins on dynamic arguments** — `floor`/`sqrt`/`ceil`/`log`/`sin`/`cos`
  emitted `.toDouble()` on an `eplDiv`/`eplMul` result typed `Any` (unresolved
  reference). They coerce through `EPLRuntime.toDecimal`; `abs`/`absolute` keep
  integer-vs-decimal parity via a new `EPLRuntime.absNum`.
- **Top-level constants were unreachable** — a `Constant` (e.g. stdlib `ALPHABET`)
  was emitted inside `fun main()`, so file-scope inlined stdlib functions couldn't
  see it. Constants are now emitted at file scope.
- **`not` on a dynamic operand** routed to Kotlin's `!` (which needs `Boolean`);
  a dynamic operand now goes through `EPLRuntime.truthy`. An `Any?` value passed
  into a non-null `Any` parameter gets a non-null assertion so the call type-checks.
- **`regex_replace` / `regex_split`** were unresolved; added native
  `EPLRuntime.regexReplace`/`regexSplit` bridges with interpreter arg-order parity.

Verified: 63 Kotlin/native unit tests; 47 of 55 example programs compile clean on
real `kotlinc` (the rest are legitimately non-portable — Python interop, `gui_*`,
server-only `real_db_*`/`web_*`, `csv_read` — surfaced by the porting report).

### Fixed — Kotlin/Android transpiler correctness (real-APK hardening)

Verified by compiling generated projects with the actual Kotlin/Gradle toolchain
and building installable debug APKs. Six defects the real compiler rejected:

- **db/file builtins unresolved** — `db_create_table`, `db_tables`, and the
  `file_*` family passed through as raw snake_case (unresolved references). Added
  their `EPLRuntime` bridge methods (SQLite `CREATE TABLE` with interpreter-parity
  identifier/type validation; sandboxed `filesDir` file ops) and call mappings.
- **`Any + Any` didn't compile** — untyped params default to `Any`, but EPL `+`
  emitted raw Kotlin `+`. Now lowers to an `eplAdd` runtime helper (numeric add
  when both sides are numbers, string concat otherwise — matching EPL semantics).
- **Integer division gave wrong values** — `10 / 4` emitted `(10 / 4)` = `2`.
  EPL `/` is float division that raises on a zero divisor, so it now lowers to an
  `eplDiv` helper (2.5, and a divide-by-zero exception).
- **Class-method call return types** — a call on a user-class instance resolved
  the generic builtin `.add ⇒ Unit` map, poisoning `var x = obj.method()`. It now
  resolves the receiver class's declared method return type.
- **Symbols unregistered on the Android path** — `generate_android_activity`
  never ran the symbol pre-pass, so class/function type lookups failed there.
- **Duplicate `var` on reassignment** — `x = 5` then `x = 10` emitted two
  conflicting `var x` declarations; emission now tracks declared names per scope.

Also: the native portability checker now flags `Use python` / `Use javascript`
interop as unportable instead of silently emitting uncompilable references.

### Fixed — Kotlin/Android transpiler correctness (second compiler-verified pass)

A further batch surfaced by compiling more of the example corpus through the real
Kotlin toolchain. Each fix is verified against `compileDebugKotlin`:

- **Map methods didn't compile** — `keys()`, `values()`, `entries()`, `has()`,
  `get(k, default)`, `merge()`, `set()`, `copy()`, `remove()` collided with
  Kotlin's `MutableMap` API (properties vs. methods, missing overloads). They now
  route through `EPLRuntime` map helpers that mirror the interpreter's dict
  methods, plus map-key field assignment (`person.email = …`) and map iteration
  (EPL iterates keys, not entries).
- **Slicing was emitted as `null`** — `list[a:b:c]` / `text[a:b]` had no codegen.
  Added an `EPLRuntime.slice` helper with CPython-faithful start/stop/step and
  negative-index semantics.
- **Missing builtins** — `round`, `type_of`/`typeof`, `abs` were unresolved
  references; added mappings and `EPLRuntime` helpers. `length()` now dispatches
  on the runtime value instead of assuming `.length`.
- **Local enum classes rejected** — top-level enums were emitted inside `onCreate`
  (Kotlin forbids local enum classes); they are now hoisted to file level.
- **Mixed Int/Double arithmetic and calls** — `b == 0` where `b: Double`, and
  `divide(10, 2)` into `Double` params failed (Kotlin won't auto-promote). Integer
  operands are now widened at comparison/arithmetic sites and function-call args.
- **Function-scoped variables lost across blocks** — a variable first assigned
  inside a `try`/`if`/loop but used after it became an unresolved reference under
  Kotlin's block scoping. Such locals are now hoisted to the top of their function
  scope (EPL variables are function-scoped), with float reassignment coercion.

### Fixed — Kotlin/Android transpiler correctness (lambdas & functional programming)

Fourth compiler-verified pass, covering the `lambdas` example (closures, `.map`/
`.filter`/`.reduce`, higher-order functions, ternaries):

- **Lambdas are now emitted as fully dynamic** `(Any?...) -> Any?` with `Any?`-annotated
  params, matching EPL's dynamic typing. Previously concrete param/return types made
  bodies like `x * 2` fail (`Any * Int`) and clashed with `reduce`'s return type.
- **Dynamic operators route through `EPLRuntime`** — `*`, `-`, `%`, `**`, `+`, `//`,
  the comparisons, and `==`/`!=` on `Any?` operands (e.g. lambda params) lower to
  `eplMul`/`eplSub`/`eplAdd`/`eplLt`/`eplEq`/… which mirror EPL's numeric and
  truthiness semantics, instead of Kotlin operators that don't apply to `Any?`.
- **Higher-order list methods** — `map`, `filter`, `reduce`, `find`, `every`, `some`
  route through `EPLRuntime` helpers taking `(Any?)->Any?`, rather than Kotlin's typed
  `List` methods whose element/return types clash with dynamic lambdas.
- **Invoking a dynamic callable** — calling a value held in an `Any` param (a lambda
  passed to a higher-order function) now casts to a function type of matching arity.

### Fixed — Kotlin/Android transpiler correctness (string & builtin coverage)

Third compiler-verified pass, covering the string and math example programs:

- **String methods diverged from Kotlin's `CharSequence` API** — `find`, `count`,
  and `reverse` bind to predicate overloads on `CharSequence`; `pad_left`,
  `pad_right`, `char_at`, `to_list`, `is_number`, `is_alpha`, `format` have no
  member at all. String receivers now dispatch through a dedicated map plus
  `EPLRuntime` helpers mirroring the interpreter's `_call_string_method`.
- **Property-style accessors** — `text.uppercase`/`.lowercase`/`.trim` emitted as
  property reads (Kotlin wanted `()`); `list.length` was unresolved. Now emit the
  method call / `.size` as appropriate.
- **List mutation methods were non-mutating** — `list.sort()`/`reverse()` mapped
  to Kotlin's `sorted()`/`reversed()` (which return new lists and dropped the
  mutation); `list.remove(x)` mapped to `removeAt` (index) instead of by-value.
  Fixed to in-place `sort()`/`reverse()` and by-value `remove()`. `split()` now
  yields a `MutableList`.
- **Missing free-function builtins** — `range`, `sum`, `sorted`, `reversed`,
  `is_integer`/`is_decimal`/`is_text`/`is_boolean`/`is_list`/`is_map`/`is_nothing`/
  `is_number`, `char_code`, `from_char_code`, `json_parse`, `json_stringify` were
  unresolved references. Added mappings and `EPLRuntime` implementations (JSON via
  `org.json`).

### Fixed — Kotlin/Android transpiler correctness (dynamic dispatch & stdlib inlining)

Fourth compiler-verified pass, driven by compiling the `killer_*`, `text_analyzer`,
and data-processing examples through the real Kotlin toolchain. Every fix is
verified against `compileDebugKotlin`.

- **Stdlib imports were silently dropped** — the native targets have no runtime
  import loader, so `Import "string"` etc. left calls like `word_count` as
  unresolved references. A new `stdlib_inliner` resolves plain stdlib imports and
  splices only the *reachable* definitions into the program (callee-before-caller
  ordering, unused imports dropped, aliased/namespaced imports left untouched).
- **Dynamic-receiver methods didn't compile** — a loop variable bound from
  `EPLRuntime.iterate` has static type `Any`, so `char.lowercase()`,
  `str.contains(char)`, and the string transforms rejected it. String-only methods
  now coerce a dynamic receiver/argument to `String`; shared methods
  (`reverse`/`count`/`replace`/`contains`/`length`) route through `EPLRuntime`.
- **Value-returning functions got a spurious `return Unit`** — the trailing-return
  check only looked for a top-level `return`, so a function whose returns are all
  inside `if/else` branches emitted `return Unit` under a `String` signature. Now
  an all-paths-return analysis recurses through `if/else`.
- **Kotlin hard keywords as identifiers** — an EPL parameter named `val`/`var`/etc.
  produced un-parseable Kotlin. Colliding identifiers are now backtick-escaped at
  every emission site (`this`/`super` pass through with their Kotlin meaning).
- **Dynamic values into typed contexts** — `Any` values flowing into `Int`/`Double`/
  `String` params, `Int`/`Double`/`String`-typed reassignments, and `From..To`
  range bounds are now coerced (`as Number`, `.toString()`) instead of failing type
  inference. `+`-expression type inference now mirrors the emitter exactly (a
  dynamic left lowers to `eplAdd ⇒ Any?`, so it no longer mis-infers `String`).

### Added — enforced VM↔interpreter parity gate over the example corpus

Phase 4 of the enterprise-hardening pass. `epl run` defaults to the bytecode VM,
while the docs and most of the suite validate against the tree-walking
interpreter — so a program that behaves differently across the two backends is a
divergence bug that nothing caught. `tests/parity_check.py` diffed the backends
but always returned `0`, so it never gated CI.

- **`tests/test_parity_corpus.py`** — walks the real corpus (`examples/` +
  `benchmarks/`, recursively) and runs every eligible program through BOTH
  backends via the actual CLI, asserting each exits `0` with byte-identical
  stdout (54 programs, 0 divergences today). Ineligible programs are excluded by
  a documented, directory-agnostic content filter (servers, interactive,
  socket/GUI loops, the Node-dependent JS bridge, the `Test … End Test` DSL, and
  nondeterministic `random`/`uuid` output). Everything else is included by
  default (fail-closed): a new compute example is auto-covered, and a program
  that hangs **fails** on a per-program timeout instead of being silently
  skipped — the exact failure mode the advisory harness used to swallow.

### Added — dedicated tests for previously under-covered core modules

Phase 3 of the enterprise-hardening pass. Five core modules were exercised only
indirectly (as pipeline stages) or under legacy `__main__` harnesses; each now
has a dedicated, declarative pytest module (126 new tests) pinning its public
API contract:

- **`tests/test_lexer.py`** — token-stream assertions the parser-level tests
  never made: numeric decoding (`int`/`float`/hex/binary/`_` separators),
  string escape resolution, case-insensitive keyword-vs-identifier resolution,
  two-character and multi-word operators, comment skipping, 1-based positions,
  the `Token` equality model, and loud `LexerError`s on bad input.
- **`tests/test_type_system.py`** — the primitives under `TypeChecker`: type
  `str()`/equality/hashing, the `is_assignable` subtyping table (incl.
  integer→decimal promotion, `any`/`never`/optional rules), `infer_type_from_value`,
  `make_union_type` collapse, `TypeScope` lookups, and `PRIMITIVE_MAP` aliases.
- **`tests/test_python_transpiler.py`** — emitted-code shape: `+`/`/` routing
  through `_epl_*` helpers, the split between idiomatic `builtin_map`
  (`maximum`→`max`, `absolute`→`abs`, `floor`→`math.floor`) and the faithful
  `_epl_call` shim (`max`/`gcd`/`factorial`/`type_of`/`trim`), conditional
  prelude emission, and the `TranspileError` guards.
- **`tests/test_copilot.py`** — the offline generator/analyzer: every generated
  template re-parses as valid EPL, `analyze_code` never executes code, and
  `assist_request` fix-mode repairs (`Else`→`Otherwise`).
- **`tests/test_ios_gen.py`** — SwiftUI app/runtime scaffolding, the pure
  color/type/op helpers, the empty-program fallback, and the on-disk
  `IOSProjectGenerator` project tree (now hermetic via `tmp_path`).

### Changed — JS transpiler: correct-or-loud + wider builtin coverage

Phase 2 of the enterprise-hardening pass. The JavaScript target now matches the
Python target's correct-or-loud contract, so it can no longer silently emit code
that throws `ReferenceError` at runtime.

- **Fail-loud on unmapped builtins** — a call to a real EPL builtin that has no
  faithful JS mapping now raises `TranspileError` at transpile time (naming the
  builtin) instead of emitting `name(args)` — a call to a nonexistent JS
  identifier. Genuine user-function calls still emit a bare `name(args)`. The
  authoritative builtin set is sourced from the interpreter so it can never
  drift. A node-less regression test locks the contract on every CI image.
- **More builtins mapped faithfully** — `abs`, `to_string`, `trim`, `exp`,
  `log10`, `log2`, `hypot`, `gcd`, `factorial`, `contains`, `keys`, `values`,
  `has_key`, `is_text`, `is_boolean`, `is_map`. Each mirrors the interpreter
  exactly: `contains` is a string-coercion substring test (`str(needle) in
  str(hay)`, so `contains([12], 2)` is true), not typed membership; `trim`
  coerces to text first (`trim(123)` → `123`); `gcd`/`factorial` truncate their
  operands and `factorial` raises on a negative input (correct-or-loud rather
  than returning `1`). `max`/`min` accept either a single list or varargs
  (previously `Math.max([..])` → `NaN`) via a fold that can't overflow the
  call stack, and raise the interpreter's exact error on empty input
  (`max([])`/`min([])`) instead of returning `undefined`.
- **Python transpiler fixes** — `contains` was mapped to `operator.contains`
  without importing `operator`; `trim` was mapped to `str.strip`, which raised
  on non-text input. Both now route through the faithful `_epl_call` shim.
- **Fidelity corpus grown 18 → 30** — new deterministic programs covering the
  added builtins, nested data, string ops, map iteration, closures, decimal
  math, and control flow. Each auto-gates BOTH transpilers byte-for-byte.

### Changed — reliability: no more silently-swallowed errors

Phase 1 of the enterprise-hardening pass. Previously-silent `except …: pass`
sites that could hide real failures now either surface under `EPL_DEBUG` (routed
through `epl._debug_log.suppressed`) or, for operator misconfigurations, emit a
visible warning. Behavior is otherwise unchanged. Regression coverage in
`tests/test_silent_except_hardening.py`, including a guard that fails if a broad
`except Exception: pass` is reintroduced.

- **Operator misconfigurations now warn** — an invalid `EPL_WEB_PORT`/`PORT` or
  `EPL_WEB_WORKERS` logs a warning and falls back to the default instead of
  silently ignoring the value; a corrupt AI config file warns instead of being
  treated as "no config".
- **Diagnosable-under-debug** — dropped LLM stream chunks (`ai`), failed ML
  scaler transforms that fall back to raw input (`stdlib`), corrupt
  registry/index/update caches, HTTP/Lambda JSON-decode fallbacks, and Node/JS
  bridge teardown now record the swallowed exception under `EPL_DEBUG`.

### Fixed — type checker, Python bridge, and dot-notation defects

A code-level audit surfaced five confirmed defects across the type checker,
parser, and Python bridge; all are now fixed with regression coverage in
`tests/test_access_and_bridge_fixes.py`:

- **False "unused variable" (W002)** — the type checker never visited the object
  of a `PropertyAccess`/`IndexAccess`, and had no case at all for `MethodCall`,
  `SliceAccess`, or `FunctionCall` arguments. A variable used *only* via
  `user.status`, `data[0]`, `items.count()`, `list[0:2]`, or `f(x)` was reported
  as declared-but-never-used. `_infer_type` now recurses into every such
  sub-expression, so the inner variable read is counted.
- **Self-referential accumulation flagged unused** — `counter = counter + 1`
  reparses as a redeclaration, which reset the `used` flag *after* inferring the
  right-hand side and wiped the read. The usage entry is now seeded *before*
  inferring the initializer, so the self-referential read counts.
- **Hard keywords broke dot notation** — member names that collide with hard
  keywords (`resp.json()`, `element.text`, `array.list()`, `obj.create()`)
  crashed the parser with "Unexpected token". They are now accepted as member
  names after a dot, disambiguated from a sentence-ending period by token
  adjacency (a real property is written immediately after the dot).
- **Auto-aliased keyword module unusable** — `Use python "json"` binds the module
  to `json`, but `json.dumps(...)` at expression start was a parser error because
  `json` is a hard keyword. A hard keyword immediately followed by an adjacent
  dot-access is now parsed as a variable/module reference.
- **Duck typing destroyed rich Python objects** — `wrap_python_result` collapsed
  *any* non-string object exposing `__iter__` into a list, exhausting and
  stripping objects like a `requests.Response` (losing `.status_code`,
  `.headers`, and consuming the stream). Only genuine pure-iterables (iterators,
  generators, `range`, `frozenset`, dict views) are now materialised; rich
  objects fall through to the attribute-preserving `PythonModule` wrapper.

### Fixed — Python transpiler now preserves EPL runtime semantics

The Python transpiler (`epl export python`) was syntax-faithful but
semantics-incomplete: it mapped EPL syntax to Python syntax without preserving
behaviours the interpreter guarantees, so generated code worked on the happy
path and diverged on common operations. On a fidelity corpus only a minority of
programs produced output matching `epl run`. Every gap below is now closed via a
minimal per-program `_epl_*` prelude (only the helpers a program actually uses
are emitted, so simple programs stay lean):

- **`+` coercion** — text operands auto-stringify and lists concatenate
  (`"n: " + 3` was a Python `TypeError`; now matches EPL). `+=` desugars through
  the same helper.
- **Display form** — `print` and `${}` interpolation render EPL's forms
  (`true`/`false`/`nothing`, bracketed lists, brace maps) instead of Python's
  `True`/`False`/`None`.
- **Int-preserving `/`** — `10 / 2` returns `5`, not `5.0`; `/=` too.
- **Map dot-access** — `user.name` reads a key on a Map from any source
  (literal, `Map with …`, `json_parse`, `db_query`) instead of raising
  `AttributeError`.
- **Inclusive ranges in both directions** — `For i from 10 to 1 step -1` no
  longer drops its last two iterations (the stop is nudged in the direction of
  travel).
- **Builtin/method routing** — the ~900-strong builtin long tail (`file_*`,
  `db_*`, `regex_*`, `http_*`, `crypto_*`, …) and divergent string/list/map
  methods (`.add`, `.has`, `.substring`, `.join`, …) route through EPL's own
  tested runtime — faithful by construction rather than re-implemented.
- **Name collisions** — an EPL variable named `len`, `list`, `sum`, `type`, …
  no longer shadows the Python builtin the transpiler emits (renamed
  consistently).
- **Predicate HOFs** — `.every`/`.some`/`.find` on lists are now implemented on
  the `_EPLList` wrapper (`find` returns `nothing` on no match), instead of
  raising `AttributeError` on a plain Python list.
- **Callable overrides of builtins** — binding a callable to a builtin name
  (`Set to_text to lambda x -> …`) now dispatches to the local callable, matching
  the interpreter, instead of always routing to the builtin.
- **Empty-map mutation** — mutating methods on a freshly-created empty `Map`
  (`m = Map` then `m.set(…)`) now persist, instead of updating a throwaway dict.
- **Lambda parameter renaming** — a lambda parameter that collides with a Python
  builtin (`lambda len -> len + 1`) is now renamed consistently with its uses in
  the body, instead of desyncing (which computed the wrong result).
- **Correct-or-loud** — an unrecognised node now raises `TranspileError` instead
  of emitting a silent `None  # Unsupported` / `# Unsupported: X` that compiled
  fine and computed the wrong answer.

New `tests/test_transpiler_fidelity.py` harness executes every program in
`tests/fidelity_corpus/` through both the interpreter and the transpiled Python
and asserts byte-identical stdout, so a transpiler regression can no longer ship
silently. The harness pins `PYTHONPATH` for spawned scripts (so runtime-routing
programs import `epl` even in a bare checkout) and surfaces subprocess stderr in
failure diagnostics.

### Fixed — JavaScript transpiler now preserves EPL runtime semantics

The JS transpiler (`epl export js` / Node target) had the same class of gaps as
Python, but generated JS can't route back through the interpreter, so each fix is
a minimal native `_epl_*` runtime helper emitted only when a program needs it. On
the same fidelity corpus the JS target went from **7/17 to 17/17** matching
`epl run` byte-for-byte:

- **`+` overload** — `[1, 2] + [3, 4]` now concatenates to a list (was the string
  `"1,23,4"`), and `"row: " + aList`/`+ aMap` render EPL display form instead of
  `[object Object]`. `+=` desugars through the same helper.
- **Display form** — `Print`/`Say` render EPL's forms (`nothing`, `true`/`false`,
  `[a, b]` lists, `{k: v}` maps) instead of Node's `null` / `[ 1, 2 ]` spacing.
- **`type_of`** — returns EPL type names (`integer`/`decimal`/`text`/`list`/`map`/
  `nothing`), not JS `typeof` (`number`/`object`).
- **`reversed`** — preserves input type: `reversed("abc")` → `"cba"` (was a char
  array `['c','b','a']`); `reversed([1,2,3])` stays a list.
- **`to_number`** — now emitted (`Number(...)`); previously a call to an undefined
  function that crashed at runtime.
- **Map iteration** — `For each k in aMap` iterates keys via `_epl_iter` (a plain
  object is not `for..of`-iterable, so this used to throw).
- **Map/string methods & property accessors** — `.has`/`.keys`/`.count`/`.first`/
  … and property-style `.length`/`.uppercase`/`.trim` route through type-dispatched
  helpers (were `[Function: trim]` / `undefined` / crashes), falling back to a real
  method call for user-class instances.
- **`let`-vs-reassignment (TDZ)** — EPL's parser emits a declaration node for both
  first-assignment and reassignment; the transpiler now tracks declared names per
  function scope and emits `let` only once, so the common `sum = sum + n` in a loop
  no longer becomes `let sum = sum + n` (a self-referential `let` that threw
  `ReferenceError: Cannot access 'sum' before initialization`).
- **Interpolation** — `${length(items)}` is transpiled (`items.length`) rather than
  copied raw, and a bare `$name` interpolates only when `name` is a real variable
  (so a literal `$` inside e.g. a password stays literal).

New `tests/test_js_transpiler_fidelity.py` harness runs every corpus program
through the interpreter and through transpiled JS (via `node`) and asserts
byte-identical stdout (skips gracefully where `node` is unavailable).

## [10.1.2] — 2026-07-06

Security-focused patch: the 2026-07 audit fixes plus a second-pass review that
closed a cross-platform gap in the path-traversal jail (the CI-visible failure),
a MySQL identifier-quoting regression, and three more real findings. No API
changes — a safe, recommended upgrade for all users.

### Security — path-traversal jail now cross-platform

`web_send_file`'s jail resolved paths with `os.path`, which on POSIX
(`posixpath`) does not treat `\` as a separator or `C:/…` as absolute. A
request-controlled Windows-style payload (`..\..\..\windows\win.ini`,
`C:/Windows/...`) therefore sailed **past** the jail on a Linux/macOS host and
was only blocked on Windows. The jail now normalises separators and detects
drive-letter/UNC absolute forms before resolving, so traversal is refused
regardless of the deployment OS.

### Security — SQL identifier quoting is dialect-correct + `add_column` hardened

Two gaps in the same DDL-injection class: `add_column` interpolated the table
and column names raw (unlike the already-guarded `create_table`/`drop_table`),
and identifier quoting always emitted ANSI double quotes — which MySQL treats as
**string literals**, not identifiers, in its default SQL mode, so hardened
`CREATE TABLE`s failed there. Identifiers are now validated against a strict
pattern **and** quoted with the character the target engine recognises
(backticks for MySQL, double quotes for SQLite/PostgreSQL), and `add_column`
goes through the same guard.

### Security — ReDoS detector unwraps deeply nested groups

The catastrophic-backtracking detector unwrapped only **one** redundant grouping
layer, so a deeply wrapped pattern such as `(((a+)))+$` slipped past it. It now
unwraps redundant groups until stable, closing the bypass while still accepting
legitimate patterns.

### Fixed — `ffi` basename allowlist worked on POSIX; VM `Exit` type parity

`_has_path_separator` folded `os.altsep` into a membership test, but `os.altsep`
is `None` on POSIX, making `('' in name)` always true — every bare library name
looked path-like and the basename-allowlist shortcut silently never applied on
Linux/macOS. Separately, the bytecode VM swallowed a non-numeric `Exit` value to
status `0`, while the interpreter raised — so `Exit "bad"` looked like success
under the VM path. The VM now raises the same error as the interpreter.

### Changed — parse cache no longer clutters your project

`.eplc` parse-cache files were written next to each `.epl` source, so running a
program made a mystery file appear beside it in the editor. They now live in a
per-user cache directory (`%LOCALAPPDATA%\eplang\cache` on Windows,
`$XDG_CACHE_HOME`/`~/.cache/eplang` elsewhere), keyed by the hash of each
source's absolute path with the readable filename preserved inside. Nothing
appears in your project or VS Code explorer, and there's no risk of committing a
cache file. Set `EPL_CACHE_DIR` to relocate the cache or `EPL_NO_CACHE=1` to
disable it.

### Security — sandbox hardened to deny-by-default

The `--sandbox` (safe mode) enforcement was a **blocklist** naming only 16 of
~740 stdlib functions, so it failed **open**: `file_read`, `net_http_get`,
`http_request`, the `db_*` / `real_db_*` families, and `real_process_run` all
ran with full host access under `--sandbox` (reading `/etc/passwd`, opening
sockets, writing arbitrary files, executing shell commands). Safe mode is now
**deny-by-default**: only an allowlist of pure/computational functions
(string/collection/crypto/encoding/date-math/regex/in-memory concurrency) may
run; everything touching the filesystem, network, database, process,
environment, FFI, GUI, or host is refused with a clear error. Adding a new
dangerous stdlib function is now safe by construction — it stays blocked until
deliberately allowlisted. The VM has no sandbox enforcement, so `--sandbox`
continues to force the enforcing interpreter path.

### Security — ReDoS prevention on all regex functions

CPython's `re` engine holds the GIL for the entire duration of a match, so a
watchdog thread can never interrupt catastrophic backtracking. Instead of trying
to interrupt it, every regex entry point (`regex_match`, `regex_find`,
`regex_find_all`, `regex_replace`, `regex_split`, `regex_test`, `regex_compile`,
plus the inline replace/groups helpers) now **statically rejects** patterns with
nested unbounded quantifiers (the exponential class, e.g. `(a+)+`, `(\d*)*`,
`(a+|b+)+`) before the engine runs. The detector is precise: it does not reject
legitimate patterns like `(\w+\s)*`, `(ab+)+`, or `(\d{3})+`.

### Security — `auth_jwt_decode` no longer silently trusted

`auth_jwt_decode` reads JWT claims **without verifying the signature** — its
payload is forgeable. It now emits a one-time stderr notice steering developers
to `auth_jwt_verify(token, secret)` for authentication (silence with
`EPL_SUPPRESS_JWT_WARNING=1`), and the docs are marked accordingly.

### Security — allowlisted Python auto-install now requires consent

Running an `.epl` file that did `Use python "<allowlisted-pkg>"` would silently
`pip install` into the host environment (a supply-chain footgun). Auto-install
of an allowlisted-but-undeclared package now requires explicit consent:
`EPL_AUTO_INSTALL=1` (for CI/automation) or an interactive yes. Packages declared
in `epl.toml [python-dependencies]` remain an explicit opt-in and still install.

### Fixed — `Exit` crash + real process exit codes

`Exit 1` (and any `Exit <expr>`) crashed the parser with a cryptic
`'int' object is not iterable`. `Exit` now accepts an optional status
expression, and that status **propagates to the process exit code** across both
the bytecode VM and the interpreter — so shells and CI can read `$?`
(`Exit 3` → exit 3, bare `Exit`/`Exit 0` → 0). The parser's error-suggestion
path is also hardened against non-string tokens.

### Fixed — Python bridge chained class methods

Accessing a class attribute on a Python bridge module (e.g.
`alias.datetime.now()`) failed with "Cannot call method on unknown" because the
class was returned unwrapped. Wrapped classes are now callable, so chained
access, instantiation (`alias.Decimal("3.14")`), and store-then-call all work.

### Fixed — database helpers dropped bind parameters

`db_query` / `db_execute` / `db_query_one` read only the first params argument,
silently dropping every parameter after it — turning a multi-placeholder query
into a one-binding call. All trailing arguments are now captured, supporting both
`db_query(conn, sql, [p1, p2])` and `db_query(conn, sql, p1, p2)`.

### Fixed — `--help` swallowed on `epl test` / `epl serve`

`epl test --help` silently ran the whole suite and `epl serve --help` tried to
serve a file literally named `--help`. Both subcommands now print proper usage
for `--help`/`-h`.

## [10.1.1] — 2026-07-02

### Fixed — native export now honors the project's `Import` graph

Both native-export tools used to look only at the **entry file** in isolation
and ignore the `Import` graph — so the honesty and completeness guarantees held
only for single-file programs, which is not how EPL projects are structured.

- **Portability checker (`epl android` / `epl ios` / `epl desktop`)** now follows
  local `Import`s. Previously it walked only the entry file's AST, so a simple
  entry that just calls into an imported module reported `✓ All constructs are
  portable` while the imported module was full of routes, `db_*` calls, and other
  unportable constructs — the exact silent-incomplete-port failure the checker
  exists to prevent. It now parses and analyzes every local `.epl` reached via
  `Import` (source-file-relative, with cycle protection), and each reported issue
  is tagged with the file and line it came from. Non-local imports (stdlib,
  installed packages) are skipped, so analysis stays scoped to your own project
  and never triggers a package install.
- **`epl desktop --webview`** now bundles the entry file's transitive local
  imports. Previously it copied only the single entry `.epl`, so the launcher's
  subprocess died on its first `Import "local/path"` — before the port ever bound
  — and surfaced only a generic "server did not start within 30s" timeout.
  Imported files are copied preserving their path relative to the entry, so
  source-file-relative imports resolve exactly as they did in the source tree.
- **`DependencyScanner`** (shared with `epl build` packaging): its import regex
  was lowercase-only (`import "..."`) and so never matched EPL's capital-`Import`
  keyword, and it resolved every import against the entry file's directory rather
  than the importing file's. Both are fixed — imports are matched
  case-insensitively and resolved source-file-relative, so nested imports are
  found instead of silently dropped.

## [10.1.0] — 2026-06-30

Headline: the default `epl run` engine (the bytecode VM) gains **real closures**
and reaches full counted-loop / control-flow parity with the interpreter, the
native `epl build` backend now **infers types for untyped functions** (so many
previously-refused programs compile correctly), and the CI / release /
supply-chain pipeline is hardened end-to-end. Engine parity is exact across both
runtimes — no silent divergence.

### Changed — CI / release / supply-chain hardening

- **One source of truth for CI.** The three overlapping workflows (`ci.yml`,
  `lint.yml`, `tests.yml`) produced duplicated `lint` / `test (ubuntu-latest, 3.12)`
  checks and, worse, `ci.yml`'s test job ran a *hardcoded list of test files* —
  so a newly-added test file silently never gated. Consolidated into a single
  `ci.yml` that runs the **full `pytest tests/` suite** on every matrix cell;
  removed the duplicate `lint.yml` and `tests.yml`. Required-check names are
  unchanged, so branch protection is unaffected.
- **Enforced coverage floor (honest).** CI previously passed `--cov-fail-under=0`
  while `pyproject.toml` advertised `fail_under = 60` — a floor that was never
  reached *and* never enforced. Whole-suite coverage of `epl/` measures ~48%;
  the floor is now a real, enforced ratchet at **45%** on the required ubuntu/3.12
  job (a coverage regression now fails a required check), and the misleading
  `60` was corrected to match reality.
- **Build validation in CI.** A new `build` job runs `python -m build` +
  `twine check` on every change, so a broken sdist/wheel (bad MANIFEST, metadata,
  or packaging change) is caught in CI instead of at release time.
- **Supply-chain.** All GitHub Actions are pinned to immutable commit SHAs (with
  a version comment); a PR-gated `dependency-review` job blocks newly-introduced
  vulnerable/disallowed dependencies (`fail-on-severity: high`), while the
  existing `pip-audit` stays advisory (a fix-less transitive CVE must not wedge
  every PR); least-privilege `permissions:` and `concurrency` cancellation added.
- **Automated, tokenless releases.** New tag-triggered `release.yml`: build →
  `twine check` → tag/version match guard → publish to PyPI via **trusted
  publishing** (OIDC, no stored API token) → GitHub Release with artifacts.
  Dormant until a `v*` tag is pushed; requires a one-time PyPI trusted-publisher
  registration (documented in the workflow header).

### Fixed — bytecode VM counted-loop / control-flow correctness

**The bytecode VM (the default `epl run` engine) now executes counted loops
correctly.** A deep-research audit of the shipped examples surfaced two real VM
control-flow bugs and a wave of example-file corruption. Both engine bugs are
fixed and covered by VM-vs-interpreter parity tests; the recoverable examples are
restored; and a new runtime test stops broken examples from shipping green again.

### Added — native build (`epl build`) now infers types for untyped functions

- **Conservative monomorphic type inference (`epl/native_infer.py`).** The native
  LLVM backend has no per-expression type inference, so an untyped function
  (`Function add takes a and b` / `Return a + b`) defaulted every parameter to a
  string pointer and miscompiled numeric code — the safety gate therefore refused
  to build it at all. A new whole-program pass now infers each untyped function's
  parameter and return types from its call sites and body. A function is resolved
  only when every parameter and the return collapse to a *single* concrete native
  type across all call sites; the resolved signatures are fed to the compiler so
  the function builds with correct types instead of the miscompiling default.
- **Sound by construction — it can only help, never harm.** Inference runs *only*
  on a program the safety gate would otherwise refuse, and admits it only when the
  **entire** program (top level included) type-checks to concrete native types.
  Anything uncertain or known-divergent falls back to the existing clean refusal:
  conflicting call-site types, int division (native truncates; the interpreter
  yields a float), `**` (native is always float), string/float or string/bool
  concatenation, a user function whose name shadows a native builtin or collides
  with a runtime symbol, or any unmodeled construct. So this turns *refused*
  programs into correct native binaries without introducing a single new
  miscompile or crash (verified: zero new mismatches/segfaults across the example
  suite; previously-refused fully-typed-by-inference programs such as the
  `functions` example now build and match the interpreter exactly).
- **Operator escape hatch.** `EPL_DISABLE_NATIVE_INFER=1` skips inference and
  refuses as the bare gate did, for A/B measurement or as a safety valve.
- Covered by `tests/test_native_infer.py` (analysis: what it resolves and, for
  soundness, everything it refuses) and clang-gated end-to-end builds in
  `tests/test_native_build.py`. `scripts/native_coverage.py` measures native-vs-
  interpreter coverage across the examples.

### Added — the bytecode VM now runs closures (capturing lambdas)
- **Capturing lambdas execute on the default VM instead of forcing an
  interpreter fallback.** A lambda that closes over an enclosing function's
  params or locals — `compose` returning `given x -> f(g(x))`, partial
  application (`given x -> x + n`), captured multipliers used in a loop — now
  compiles to real closures (`MAKE_CLOSURE` / `LOAD_FREE`) and runs on the
  bytecode engine, matching the interpreter exactly. Previously the compiler
  raised on any function-local capture so these programs fell back to the
  tree-walking interpreter.
- **Capture is by value, which is exact for EPL.** Lambda bodies are
  expression-only, so a closure can never reassign a captured name; the only way
  by-value capture could diverge from the interpreter's by-reference semantics is
  the *enclosing* scope reassigning a captured name after the closure is built.
  The compiler detects that one case and refuses it, so `epl run` falls back to
  the interpreter rather than capturing a stale value — output is never wrong.
  Nested (multi-level) capture also falls back. Covered by VM↔interpreter parity
  tests in `tests/test_vm.py`.
- **Closures work through list helpers and across the divergent edge cases.** A
  captured closure passed to `.map`/`.filter`/`.reduce`/`.find`/`.every`/`.some`
  now dispatches correctly (previously returned `nothing`). Capturing a loop
  variable (rebound each iteration) or a variable from a non-immediate enclosing
  function falls back to the interpreter, so output always matches.

### Fixed — bare math/boolean constants diverged between the two engines
- **`pi`, `euler`, `infinity`, `on`, and `off` now resolve identically under
  `epl run` (VM) and `epl run --interpret`.** The VM had a bare-constant table but
  the interpreter did not, so `Say pi` printed `3.141592653589793` on the default
  VM yet `"pi"` (or errored, for `infinity`/`on`/`off`) under the interpreter. Both
  engines now read a single shared `stdlib.BARE_CONSTANTS`, so they can't drift; a
  user `Create pi ...` still shadows the constant. Covered by VM↔interpreter parity
  tests in `tests/test_vm.py`.

### Docs — reconciled platform claims with verified reality
- **iOS/SwiftUI generation and the WASM target are now labeled experimental** in
  the README (not yet validated against a Swift toolchain / Emscripten in CI), and
  the native-build matrix entry notes it covers the type-annotated subset. The
  architecture diagram's native-output note is narrowed to the verified target
  (x86-64). No code behavior changed — this corrects documentation that ran ahead
  of what is currently CI-verified.

### Fixed — VM optimizer skipped function/method bodies; corrected speed claims
- **The bytecode optimizer (constant-fold, peephole, dead-code) now runs on
  every function and class-method body, not just top-level code.** Function and
  method bodies compile into their own instruction streams, so the passes never
  touched them — foldable constants and dead code after `Return` survived inside
  every callable. Bodies are now optimized via a shared `_optimize_code` pipeline
  (with the constructor de-duped by identity against its `Constructor` method).
  VM-vs-interpreter parity is preserved; covered in `tests/test_vm.py`.
- **Removed the inaccurate "10-50x faster than tree-walking" VM claim.** Measured
  with `epl benchmark`, the Python-hosted VM is *not* uniformly faster — on tight
  arithmetic loops the dispatch layer makes it somewhat slower, and on call-heavy
  code the two engines are roughly on par. The large speedups come from native
  compilation (`epl build`, via LLVM), not the VM. The docstring now says so.

### Fixed — transpile commands ignored `-o`/`--output`
- **`epl python`/`js`/`node`/`kotlin`/`micropython` now honor `-o`/`--output`.**
  They previously ignored the flag and always wrote `<basename>.<ext>` into the
  current directory (and `micropython` rejected `-o` outright while `android`
  accepted it). All single-file transpile commands now write to the given path,
  creating parent directories as needed; with no flag the prior CWD behavior is
  unchanged. A bare `-o` (or one followed by another flag) is rejected with a
  clear error instead of silently using the default name, and `-o` is recognized
  in project mode (`epl python -o dist/app.py` against an `epl.toml` entry).
  Coverage in `tests/test_cli_production.py`.

### Added — empty-map literal (`Map`)
- **`Map` with no `with` clause is now the empty-map literal.** EPL previously
  had no way to write an empty map — `Map`, `{}`, and `{...}` all failed to
  parse — which pushed package authors toward the nonexistent `dict()`. Bare
  `Map` now produces `{}`; `Map with k = v ...` is unchanged.

### Added / Fixed — list concatenation, `Add` into nested collections, more usable keywords
- **List concatenation with `+` now works in the interpreter** (e.g.
  `[1] + path`), returning a new list without mutating either operand. The VM
  already supported this; the interpreter raised *"Cannot add list and list"* —
  the two engines now agree.
- **`Add X to <target>` accepts subscript and property targets**, not just bare
  names — `Add 5 to graph[key]`, `Add v to obj.items`. EPL collections are
  reference types, so the referenced list is appended in place. Mirrors the
  lvalues `Set`/`=` already accept.
- **`window` and `constant` are usable as ordinary identifiers** (function
  names, parameters, variables). They are block/declaration keywords (`Window`
  GUI block; `Constant` declaration) but, like the already-soft `Row`/`Column`,
  are common identifiers — `window` is a standard sliding-window helper and
  `constant` is the FP K-combinator. Their statement-level meaning is unchanged.

### Fixed — official-package examples and sources didn't run
- **Restored the shipped official packages to a runnable state.** Many package
  examples and sources used `Set name to ...` for a *first* assignment — but
  EPL's `Set` is reassignment-only by design (it errors on an undeclared name
  to catch typos); declaration is `Create`/`=`. The first-assignment `Set`s are
  rewritten to `=` across the example/source files (real reassignments left
  intact). Also: `epl-auth`/`epl-http` used `dict()` (now `Map`), and
  `epl-string` called `.uppercase` on the integer `0` instead of on the first
  character (`w.char_at(0).uppercase`). Combined with the `python_call` fix
  below, the bulk of the official packages now run end-to-end. (Some remain
  blocked by external setup — `epl-cloud` needs a file, `epl-email` needs SMTP
  credentials — or by backend version drift; tracked separately.)

### Fixed — Python-backed packages were dead (`python_call` unbound)
- **The 13 official packages that reach a Python backend now work.** Packages
  like `epl-array`, `epl-math`, `epl-stats`, `epl-learn`, and `epl-dataframe`
  call their backends through `python_call(module, function, ...args)` — but no
  name was ever bound to that bridge, so every such call raised
  *"Function python_call has not been defined."* `python_call` is now a real
  interpreter builtin (routing to the existing `_python_call` machinery). It is
  **blocked under `--sandbox`** (it executes Python, same policy as
  `Use python`), and the bytecode VM **refuses it at compile time** so `epl run`
  falls back to the interpreter cleanly instead of silently returning null.
- **NumPy results no longer leak as `<python module int64>`.** The Python-bridge
  result wrapper now duck-types NumPy-style scalars/arrays (via `.dtype` +
  `.item()`/`.tolist()`, with no hard dependency on numpy) and converts them to
  native EPL numbers/lists — so numeric packages return `[1, 2, 3]` and `15`
  instead of opaque wrapper objects. Regression coverage in
  `tests/test_python_call_bridge.py`.

### Added — native Android/Kotlin compilation (H1 db bridge + H3 type-correct transpile)
**The transliterating Android/Kotlin target now produces code that actually
compiles**, including database apps. v10.0.0 told the truth about *what* it could
port; this closes the cases it claimed to port but emitted uncompilable Kotlin
for. Every fix below was verified against the real Kotlin compiler (`gradlew
compileDebugKotlin` / `assembleDebug`) on four generated apps — a pure-logic app,
a class-based app, a builtin-name-shadowing app, and the FocusFlow `db_*` app.
Findings **H1** (native `db_*` bridge) and **H3** (scope/type-correct transpile)
from the omniapp audit.

- **H1 — native `db_*` SQLite bridge.** The generated `EPLRuntime.kt` now ships
  database functions, and `db_query`/`db_open`/`db_execute`/`db_close`/`db_count`/
  `db_query_one` (plus their `_params` variants) are rewritten to
  `EPLRuntime.dbQuery`/`dbOpen`/… with correct return types instead of being
  emitted verbatim as unresolved references. Dynamic member/index access on
  maps routes through `EPLRuntime.field(obj,"k")` / `EPLRuntime.at(obj,i)`. The
  `db_*` FocusFlow app now compiles and assembles to an APK, so `epl`'s porting
  report marks `db_*` as portable for the Android target.

### Fixed — Kotlin transliteration emitted uncompilable code (H3)
- **`Set x to …` on a never-declared name emitted a bare `x = …`** — an
  unresolved reference in Kotlin. EPL's `Set` is create-or-update, so the first
  sight of a name now emits a typed `var` declaration; a later `Set` of an
  already-declared name stays a bare reassignment, and class properties still
  assign through `this`.
- **Untyped function parameters became `Any` receivers no operator applied to.**
  Parameters are now typed from body usage: true arithmetic (`-`, `*`, `/`, `%`,
  `//`, `**`), ordering comparisons against a numeric operand, and `+` *only*
  when the other operand is itself numeric. `+` against a string/dynamic operand
  is ignored, since in EPL it doubles as string concatenation — so `greet(name)`
  stays `Any` while `factorial(n)` and `double(x)` resolve to `Int`.
- **Recursive functions couldn't infer a return type** (the self-call resolved to
  nothing). The signature is now seeded from non-recursive (base-case) return
  paths first, then refined with all paths.
- **References to body-local variables broke param/return inference.** Local
  variable types (e.g. a loop counter) are pre-scanned so `i < exp` resolves
  `exp` to `Int` even though `i` isn't emitted yet.
- **Heterogeneous map literals were typed from only the first entry** — e.g.
  `{"name": "Alice", "age": 30}` became `MutableMap<String, String>`. Key and
  value types now collapse to `Any` when the entries disagree.
- **`Any?` on the left of `+` (a dynamic map field) had no `plus` operator.**
  String concatenation now coerces a non-`String` left operand with `.toString()`
  so `field(m, "name") + " is "` compiles.
- **A user function named like a builtin (`power`, `max`, …) was hijacked** by the
  builtin call-rewriting. A defined function of the same name now shadows the
  builtin.

### Fixed
- **`Set list[i] to value` and `Set obj.prop to value` now work.** The `Set`
  parser only accepted bare variable names; subscript and property targets failed
  with "Expected 'to' after variable name". `Set xs[1] to 99` and `Set m.key to
  "val"` now emit the same `IndexSet`/`PropertySet` nodes as the `=` shorthand
  form, so both spellings work identically under the interpreter and the VM.
  Parity coverage added; `test_funcs.epl` (which used this syntax) now runs.
- **`When 1 or 2 or 3` in a Match collapsed to a single boolean `1`.** The
  surface parser consumed each `When` value with `_parse_expression()`, which
  greedily folded `1 or 2 or 3` into one boolean-OR expression — so the match
  only ever tested against `1`. Multi-value `When` now parses each alternative
  at the `_parse_and()` precedence (just below `or`), so the `or` separators stay
  as separators and all alternatives are tested. Parity coverage added.
- **Match accepted only `Default`, not `Otherwise`.** The If statement accepts
  both `Otherwise` and `else` for the catch-all branch, but Match only accepted
  `Default`. All three keywords now work in Match for consistency.
- **`Continue` inside a counted loop (`For … from … to …`, `Repeat … times`)
  hung forever.** The VM pointed the loop's `continue` target at the condition
  check, which runs *before* the counter is advanced — so a `Continue` looped
  back with the counter unchanged and spun the loop infinitely (this hung
  `examples/constants_and_loops.epl`). `Continue` now forward-jumps to the
  increment, matching the tree-walking interpreter. The interpreter was already
  correct; only the VM was affected.
- **Negative-step `For` loops never ran.** The VM always compiled the loop test
  as `var <= end`, so a countdown like `For i from 10 to 1 step -1` exited
  immediately and printed nothing. Counted loops with a compile-time-constant
  negative step now test `var >= end` and count down correctly.
- **`epl build` (native compilation) could not link at all.** `epl/runtime.c`
  had accumulated duplicate definitions of `epl_file_read` / `epl_file_write` /
  `epl_file_append` / `epl_file_exists` / `epl_file_delete` and `epl_time_now`,
  plus a second `epl_sleep_ms` with a conflicting signature. The runtime never
  compiled, so *every* native build failed at link time with `undefined symbol:
  epl_gc_root_depth`. The duplicates are removed (keeping the binary-safe,
  NULL-free file-I/O implementations and the higher-precision `epl_time_now`),
  and `epl_sleep_ms` is resolved to the `int32_t` signature the compiler emits.
  A type-annotated program now builds and runs as a real native executable.
- **`epl build` picked `gcc` when `clang` was absent and then failed
  confusingly.** The native pipeline emits LLVM IR, which gcc cannot compile, so
  the C-compiler probe no longer falls back to gcc; when no LLVM/clang toolchain
  is present it prints a clear, per-OS install hint instead of a link error.
- **Soft-keyword words could not be used as ordinary variables.** `label`,
  `menu`, `grid`, `start`, `row`, `column` and the other GUI/web/style soft
  keywords head a statement only in their statement form, yet the parser
  dispatched them to the widget/layout parsers even when the very next token was
  an assignment operator — so `label = 5` and `grid += 1` failed to parse. The
  statement dispatcher now peeks past a leading soft keyword: an assignment
  operator immediately after it means a plain assignment, never a GUI statement.
  Genuine widget statements (`Label "text"`, `Menu "File"`) are unaffected.
- **Omitted-bound step slices `[::2]` / `[::-1]` / `[1::2]` failed to parse.**
  The lexer emits `::` as a single `DOUBLE_COLON` token, so a slice opening with
  `::` was mis-read as module access (`Module::member`). The subscript parser now
  treats `::` as a slice separator (empty step allowed) when no member name
  follows, and still as module access when one does. Both engines (interpreter
  and VM) match Python slice semantics; explicit `[start:stop:step]` is unchanged.
- **The bytecode VM crashed on `Import` and silently produced wrong results for
  higher-order stdlib code.** Three connected VM gaps are fixed so the default
  `epl run` engine matches the interpreter on module-using programs:
  - *Imports now run on the VM.* `Import "string" as Str` then `Str::capitalize(...)`
    (and the dot form `Str.capitalize(...)`) crashed the VM with an internal
    error; `epl run` only worked by silently falling back to the interpreter.
    The old path compiled the module separately and merged its functions, but
    every function indexes into one shared constant pool, so the merged constant
    indices were meaningless. The compiler now **inlines** an imported module into
    the same compilation unit (one shared pool, no index rebasing); an
    unresolvable module raises before any output so `epl run` still falls back to
    the interpreter's fuller package/auto-install resolver. Imports are resolved
    once (diamond-import safe).
  - *Top-level `Constant`s are visible inside functions.* A module-level
    `Constant` compiled to a main-frame local, so functions (including a module's
    own functions) couldn't read it — diverging from the interpreter. Top-level
    constants are now globals, like every other top-level binding.
  - *First-class function values are callable.* `Call f With x` and `f(...)` where
    `f` is a lambda held in a variable (a parameter or a global) silently returned
    `nothing`, which broke every higher-order stdlib function (`map_list`,
    `reduce_list`, …). The VM now calls function values via a new `CALL_VALUE`
    path. Lambdas that **close over an enclosing function's locals** (e.g.
    `compose`) raise at compile time — the VM has no working capture — so
    `epl run` cleanly falls back to the interpreter instead of computing nonsense.
    VM-vs-interpreter parity is verified across every shipped module example.
- **The bytecode VM crashed on ternary expressions, `Match` statements, and
  file writes/reads/appends.** An empirical VM-vs-interpreter parity sweep over
  every shipped example (forcing `epl vm`, which has no interpreter fallback)
  found the VM compiler reading AST attributes that don't exist on the nodes, so
  `epl vm` raised `AttributeError` and only `epl run` worked — via the silent
  interpreter fallback. Four basic features are now genuinely executable on the
  VM and covered by parity tests:
  - *Ternary* `a if cond otherwise b` read `node.true_value`/`node.false_value`;
    the real fields are `true_expr`/`false_expr`.
  - *`Match`* read `node.value`/`node.cases`/`case.pattern`/`node.default` (none
    of which exist) and ignored multi-value clauses entirely. `_compile_match`
    is rewritten to mirror the interpreter: evaluate the subject once, match a
    clause when the subject equals **any** of its values, then run the first
    matching body or the `Default` body.
  - *File I/O* (`Write`/`Append`/`Read … to/from file`) read `node.path`; the
    real field is `node.filepath`. `Append` now also writes a trailing newline
    and all file ops use `utf-8`, matching the interpreter byte-for-byte (the VM
    previously concatenated appended lines and used the platform default
    encoding).
- **VM float division collapsed whole results to int.** `200.0 / 4` evaluated to
  `50` on the VM but `50.0` in the interpreter, because the VM coerced any
  whole-valued float result to `int`. Division now collapses to `int` only when
  **both** operands are ints that divide evenly (matching the interpreter);
  a float operand always preserves the float. The constant-folding path had the
  same bug and is fixed identically.
- **`Use python` / `Use javascript` failed mid-run on the VM instead of falling
  back.** The foreign-language bridges live only in the interpreter; the VM
  emitted a `__use_python__` builtin call that died later with a cryptic error.
  The VM now declines these at compile time (like the closure-capture guard) so
  `epl run` falls back to the interpreter cleanly, before any output.

### Security
- **`--sandbox` no longer bypassed by the bytecode VM.** Safe mode (file-write /
  append / `exec` / download / dir & env mutation / `Use python` / `Load library`
  blocking) is implemented only by the interpreter; the VM has no safe-mode
  enforcement. `epl run` defaults to the VM, so sandboxed code was executed by an
  engine that ignores the sandbox — previously masked only because the VM
  happened to crash on the file-write op and fall back. Now that VM file I/O
  works, `epl run --sandbox` routes to the interpreter unconditionally, so every
  sandbox restriction is enforced again. (The VM is purely a speed optimization;
  it must not run code it cannot secure.)

### Added — `.env` auto-loading + correct multi-file imports
- **EPL now auto-loads a `.env` file** before a program runs, so API keys and
  other secrets live outside source (the standard Node/Deno/Bun/python-dotenv
  experience). `env_get("OPENAI_API_KEY")` just works with a `.env` next to the
  app — no manual `export`. Zero new dependencies (`epl/dotenv.py`). Semantics:
  real environment variables always win over `.env` (so the same file is safe in
  dev while CI/containers inject prod values); not loaded under `--sandbox`;
  opt out with `EPL_NO_DOTENV=1`. Wired into both `epl run` and `epl serve`.
- **Multi-file programs now run on the bytecode VM regardless of the working
  directory.** The VM (the default `epl run` engine) resolved imports relative
  to the *current working directory* while the interpreter resolved them
  relative to the *importing file* — so `epl run sub/app.epl` that imported a
  sibling silently fell back to the interpreter (losing the VM speed-up), and
  `epl vm sub/app.epl` failed outright with "Cannot find module". The VM now
  resolves relative to the importing file's directory (with correct per-module
  resolution for nested imports), matching the interpreter. Regression coverage
  in `tests/test_dotenv_and_imports.py`.

### Fixed — example taught insecure/incorrect API key usage
- **`examples/apps/chatbot/chatbot_app.epl`** hardcoded the Groq API key as a
  source-literal placeholder and built request headers as a list of
  `"Key: Value"` strings — a pattern that crashes, since `http_post` indexes
  headers by key (requires a map). It now reads the key via
  `env_get("GROQ_API_KEY")` and builds headers with `dict_from_lists(...)`.

### Added — enterprise server deployment hardening
- **Every deployable EPL server is now secure-by-default and deploy-anywhere.**
  Previously the package registry bound to `0.0.0.0` (all interfaces) with no
  way to change it, and the web server's host/port/workers were hardcoded —
  production deployment required editing source. Now:
  - **Secure defaults.** The registry and web dev server bind to `127.0.0.1`
    (localhost only); binding publicly is an explicit opt-in that prints a
    stderr warning.
  - **Env-var config (deploy-anywhere).** Host, port, and worker count resolve
    from environment variables, so the same artifact runs unchanged on Cloud
    Run, Heroku, Azure App Service, Kubernetes, or bare metal. Platforms that
    inject `PORT` work with zero config. Web: `EPL_WEB_HOST`/`EPL_WEB_PORT`/
    `EPL_WEB_WORKERS` (and generic `PORT`/`WEB_CONCURRENCY`). Registry:
    `EPL_REGISTRY_HOST`/`EPL_REGISTRY_PORT`. Precedence: explicit `EPL_*` →
    platform `PORT`/`WEB_CONCURRENCY` → source/CLI value.
  - **Generated `gunicorn_conf.py` rebinds at runtime** from `PORT`/`EPL_PORT`
    and `WEB_CONCURRENCY`/`EPL_WORKERS` — a containerized app now honors a
    runtime-injected port without rebuilding the image (previously baked in at
    generation time).
  - **`--host` flag** added to `epl serve` (parity with `epl registry start`).
  - **Health endpoints on every HTTP server** for load-balancer/orchestrator
    probes: web `/_health`, registry `/health`, playground `/health` & `/_health`,
    MCP `/health`.
  - **`DEPLOYMENT.md`** documents every server, env var, and deployment recipe
    (Docker, Cloud Run/Heroku/Azure, Kubernetes) plus a security checklist.
  - Tests: generated gunicorn config is now verified by executing it under
    simulated platform env (`tests/test_deploy.py`).

### Added — native build safety gate
- **`epl build` now refuses to emit a binary it cannot prove type-correct,
  instead of silently producing a segfaulting one.** Because the native backend
  has no type inference, a function with an untyped parameter or an untyped
  value-return defaults to string and miscompiles numeric code (often a crash).
  `compile_file` now scans for these unprovable functions up front and stops
  with an actionable message — naming each function, the reason, an example
  annotation, and the `epl run` fallback that supports full dynamic typing — and
  writes no executable. Measured effect across the shipped examples: native
  segfaults dropped from 4 to 2, with 14 programs now getting a clean,
  explanatory refusal instead of a build failure or crash. (The 2 remaining
  crashes are top-level dynamic type-mixing such as `"len: " + name.length`,
  which a static gate cannot catch without the full inference work; these run
  correctly under `epl run`.)
- Regression tests: `tests/test_native_safety_gate.py` (toolchain-independent —
  the refusal happens before any compiler runs).

### Restored
- **7 example programs that an automated "AUTO-FIX" pass (v7.4.0) had silently
  gutted** — it deleted variable declarations and other essential lines, leaving
  files that *parsed* but crashed at runtime. Restored from their last-good
  revision and verified to run clean: `variables`, `varargs_test`,
  `error_handling`, `data_pipeline`, `data_tool`, `task_manager`, `text_analyzer`.
- **The 7 per-folder starter examples the same AUTO-FIX pass corrupted** —
  `calculator/`, `hello_web/`, `todo_app/`, `todo_api/`, and
  `official_starters/{auth_api,chatbot,creative_frontend}`. These had no clean
  revision to restore from, so each was **rewritten** to correct, idiomatic,
  verified-working EPL on the maintained web dialect (`Create webapp` +
  `Route … responds with`/`shows`, `Send json`/`Send text`, parameterized `db_*`
  queries). Every one now boots, serves, or runs to completion cleanly:
  `calculator` is a run-to-completion arithmetic showcase (it had been a stdin
  REPL that could not run unattended); `auth_api` hashes passwords with
  `auth_hash_password` / `auth_verify_password` and issues `auth_generate_token`
  sessions; `chatbot` is a self-contained rule-based bot (the old
  `Import "epl.ai"` has no working in-program import) with a documented hook for a
  real model.

### Added
- **`epl build -o/--output PATH`** — the native-build command now accepts an
  output path for the compiled binary (the same `-o` every transpile command
  already had). `epl build main.epl -o dist/myapp` writes the executable to
  `dist/myapp.exe` (Windows) or `dist/myapp` (Unix), auto-creating any
  directories and auto-appending the platform extension when omitted. Without
  `-o` the artifact still lands beside the cwd as `<basename><.exe>` (the
  historical behavior). Parity coverage added.
- **`tests/test_examples_run.py`** — actually *runs* every run-to-completion
  example (not just parses it) and asserts a clean exit, so corruption like the
  above cannot ship green again. Servers, interactive, Node-bridge, test-DSL and
  blocking desktop-GUI examples are excluded by category; `_KNOWN_BROKEN` is now
  empty — `lambdas`, `slicing` and `database_app` are enforced run-to-completion
  (the parser fixes above closed the first two; `database_app` was rewritten to
  the injection-safe map form of `db_create_table` and valid `UPDATE … SET` SQL,
  the example having been wrong). `text_editor` parses now and moved to the new
  `_GUI_APPS` category because it spins a blocking window event loop.
- VM regression tests for counted-loop `Continue`, negative steps, and
  `Break`, including a VM-vs-interpreter parity check; plus slice tests for the
  omitted-bound `::` forms and soft-keyword-as-variable tests, both engines.
- **`tests/test_native_build.py`** — the first end-to-end native test: it
  compiles EPL programs through `compile_file` (the `epl build` path), links
  against `runtime.c`, *runs* the resulting binary, and asserts its output.
  No prior test ever compiled the runtime or ran a binary, which is why the
  duplicate-symbol breakage shipped unnoticed. Skipped when no clang/LLVM
  toolchain is available.
- **`tests/test_starter_examples.py`** — a runtime gate for the per-folder
  starters (`examples/<name>/main.epl`), which fell through *both* the top-level
  glob in `test_examples_run.py` and the `apps/` glob in `test_examples_parse.py`
  — the exact blind spot that let the corruption above ship green. Run-to-completion
  starters must exit 0; web servers must bind their port and serve their body-less
  GET routes with no EPL error in the response *body* (a failed route handler
  returns HTTP 200 with an error body, so a status-code check is not enough).
  `discord_agent` is excluded (it needs the external `DISCORD_TOKEN` secret).
  `test_examples_parse.py` additionally gained a recursive guard that parse-checks
  every `examples/**/*.epl`, with documented exclusions for the Test-DSL and
  JS-bridge files.

### Known issues (documented, not yet fixed)
- **Native compilation (`epl build`) is correct only for type-annotated /
  numerically-typed programs.** Now that linking works, a measurement of the
  shipped run-to-completion examples found roughly 1 in 5 produce a correct
  native binary; the rest fail to build, mismatch the interpreter, or crash.
  The root cause is a single architectural gap: the native backend defaults
  untyped values to `i8*` (string) and has no type inference, so idiomatic
  dynamic code (`Function add takes a and b` used with both numbers and text)
  generates wrong code. Making fully-dynamic EPL compile natively needs a
  uniform tagged-value representation or whole-program type inference — a
  dedicated backend effort tracked separately. The default `epl run`
  (interpreter/VM) path is unaffected and runs this code correctly.

---

## [10.0.0] — 2026-06-25

**The "one codebase → web + Android + iOS + desktop" claim is now genuinely
true — and honest about *how*.** EPL web apps rely on HTTP routing, a server-side
backend, and the web escape hatches `Raw HTML` / `Script` / `Stylesheet`, none
of which have a native-widget equivalent. The transliterating native targets
used to drop all of that silently, exit `0`, and print "✓ generated" — so an app
whose UI is built from `Raw HTML` (the omniapp stress test, finding H2) looked
fully ported when ~90 % of it had been discarded. This release does two things:
it **tells the truth** about what transliteration can carry, and it adds a
**WebView target** that ships the real web app with nothing dropped.

### Added
- **WebView target (`--webview`)** for `android` / `ios` / `desktop` — ships the
  **real** EPL web app instead of transliterating it:
  - **android** — a native `WebView` shell (`epl/webview_gen.py`) that loads the
    running EPL web server; default URL targets the emulator-to-host loopback
    (`10.0.2.2`) on the app's declared port, overridable with `--url`.
  - **ios** — a SwiftUI `WKWebView` shell (sources + `Info.plist` with local
    networking enabled).
  - **desktop** — a Python `pywebview` launcher that starts the EPL app and opens
    it in a native window. Because EPL is itself Python, this runs the **whole**
    app — UI *and* backend — with zero transliteration.
  - Nothing is dropped: routes, `Raw HTML`, `Script`, `Stylesheet`, and the
    `db_*` backend are exactly what you built for the web.
- **Portability analysis** (`epl/native_portability.py`): a single AST walk that
  produces an honest `PortabilityReport` of every construct that cannot be ported
  by the **transliterating** target — web routing/serving (`Route`, `WebApp`,
  `Start ... on port`, `Send ...`), web-only markup (`Raw HTML`, `Script`,
  `Stylesheet`), server-side storage (`Store`/`Fetch`), and web/`db_*` builtins —
  each with its line number and the reason it was dropped.
- **Loud reporting on every transliterating build**: `epl android|ios|desktop`
  prints a summary of unportable constructs to stderr and writes a full
  `PORTING_REPORT.md` into the output directory, including what *did* port and how
  to ship the real app via `--webview`.
- **`--strict` flag** for `android`/`ios`/`desktop`: exit non-zero (code `2`)
  when any construct could not be ported, so CI no longer treats a lossy
  transliteration as success.

### Notes
- The transliterating path changes **no codegen output** — it only reports the
  truth about coverage. Pure-logic EPL (functions, math, data) still ports
  cleanly with an empty report; for a real web app, use `--webview`.
- `db_*` calls are reported as unportable by the transliterating target until the
  native db bridge ships (H1); the WebView target runs them unchanged.
- Major version bump: native-export CLIs gain new behavior (loud reporting,
  `--strict` exit codes, `--webview`/`--url`), so this is **10.0.0**.

---

## [9.9.2] — 2026-06-25

**`For each` and `If` now work inside the Page DSL.** Previously, control-flow
keywords inside a `Page` hit the parser's "unknown element" branch and were
**silently dropped** — so a dynamic list (`For each item in items ...`) rendered
nothing, forcing authors into `Raw HTML`. This was the omniapp finding B1.

### Added
- Control flow inside Page/Div/layout/Component/Responsive elements: `For each`,
  `For i from a to b [step s]`, and `If ... Otherwise ... End` are parsed with
  element bodies and **expanded into markup per request** against the route's
  data. The loop variable is in scope for every (possibly nested) child element;
  an empty iterable renders nothing.
  - Parser: an element-context depth flag (`_element_ctx_depth`) makes
    control-flow bodies parse as elements; `_parse_html_element` now handles
    `For`/`If` instead of skipping them (`epl/parser.py`).
  - Runtime: `epl/web.py` `_resolve_page_element` expands `ForEachLoop` /
    `ForRange` / `IfStatement` nodes via the interpreter in a child env,
    flattening results into the parent element list.

### Tests
- New `tests/test_web_page_control_flow.py`: parser keeps the nodes (top-level
  and nested in a `Div`); served pages render one element per item, only the
  true `If` branch, and nothing for an empty list.
- Full suite: **1937 passed, 5 skipped** (zero regressions).

---

## [9.9.1] — 2026-06-25

**Web framework correctness — shipped-broken examples and route bugs fixed.** A
standalone cross-platform stress test (`epl-omniapp/`) built one app against the
9.9.0 web generator and logged a full audit. This release fixes every web-layer
finding, so the flagship example apps parse, run, and serve correctly.

### Fixed
- **Brace-style path params silently 404'd.** `Route "/x/{id}"` was never
  compiled as a parameterized route (only `:id` was), so every `{id}` route fell
  through to a 404. Both `:name` and `{name}` are now supported and equivalent
  (`epl/web.py` `_compile_param_route` / `add_route`).
- **Captured params were not bound as bare variables.** A route body could only
  read a param via `request_params.name` / `web_request_param("name")`, not the
  bare `name` used throughout the examples and docs. Each identifier-safe param
  is now also exposed as a bare variable (reserved `request_*` names are never
  overwritten).
- **`Send redirect "/path"` was unsupported.** Only the standalone `Redirect to`
  statement worked; the `Send redirect` alias now parses and issues a real HTTP
  3xx from both the WSGI adapter (`epl/deploy.py`) and the dev HTTP handler.
- **`db_query(...).count` type error.** `db_query` returns a *list* of row maps,
  so scalar/`count(*)` reads via `.count` failed. Shipped `todo_app.epl` now
  uses `db_query_one` (returns the first row map or null); `db_query_one` is
  documented as the ergonomic scalar read.
- **`spark_board.epl` shipped with invalid SQL** (`UPDATE ideas pinned = …` and
  `Otherwise` inside SQL) — corrected to valid `UPDATE … SET … ELSE … END`.
- **"Did you mean X?" suggested the exact token typed.** The diagnostic now
  excludes a candidate equal (case-insensitive) to the input across both parser
  sites and `errors.py` `_did_you_mean`.

### Docs
- `docs/guides/web.md`: documented both path-param syntaxes + bare-variable
  access, `Send redirect` / `Redirect to`, positional `Input`, `Form action`
  (defaults to `POST`), `Stylesheet … End` as a raw-CSS block, and
  `db_query` (list) vs `db_query_one` (row).

### Tests
- New `tests/test_web_route_params.py` (`{id}` + `:id` match and bind a bare
  var; redirect parses and executes), `tests/test_diagnostics_self_suggest.py`
  (no self-suggestion), and `tests/test_examples_parse.py` (every shipped
  example app must parse — guards against shipping broken flagship examples).
- Full suite: **1931 passed, 5 skipped** (1921 baseline + 10 new, zero
  regressions).

---

## [9.9.0] — 2026-06-24

**Core de-bloat — website cosmetics removed from the shared language.** v9.7.0
baked four marketing-site visual effects into the core that ships to every PyPI
user: `WordsPullUp`, `WordsPullUpMultiStyle`, `NoiseOverlay`, `BgNoise` — plus
their default CSS and an unconditional `IntersectionObserver` script emitted on
*every* generated page. These were the flagship website's visual identity, not
the language. They are removed; the website now reproduces them in its own layer
via the `Raw HTML` escape hatch + site-owned CSS/JS, verified byte-identical at
build time.

### ⚠️ Breaking (web DSL)
- Removed page elements: `WordsPullUp`, `WordsPullUpMultiStyle` (+ its `Segment`
  keyword), `NoiseOverlay`, `BgNoise`. Pages using them must switch to
  `Raw HTML "..."` or a userland `Component`. No other syntax is affected.

### Removed
- `epl/html_gen.py`: the four cosmetic render branches; the `.native-pull-up` /
  `.native-words-wrapper` / `.noise-overlay` / `.bg-noise` default CSS; and the
  always-on pull-up scroll observer injected into every page.
- `epl/parser.py`: the v7.0 "Native Animation Components" parse branches and the
  four tokens from `_NESTED_ELEMENT_TOKENS`.
- `epl/tokens.py`: `WORDS_PULL_UP`, `WORDS_PULL_UP_MULTI_STYLE`, `SEGMENT`,
  `NOISE_OVERLAY`, `BG_NOISE` token types and their keyword aliases.

### Kept (deliberately)
- `store_list` (`Say items from "…"`) — a legitimate data-store feature used by
  `examples/todo.epl`, styled with core design tokens. There is no in-page loop
  primitive to replace it, so it stays.

### Tests
- New `tests/test_no_website_cosmetics_in_core.py` guards against the cosmetics
  reappearing and confirms `store_list` still renders.
- Full suite: **1921 passed, 5 skipped**; interpreter↔VM parity: **0 divergences**.

---

## [9.8.0] — 2026-06-23

**Backend parity — the default runner now matches the reference.** EPL has three
execution backends (tree-walking interpreter, bytecode VM, LLVM compiler), and
`epl run` defaults to the bytecode VM. A new interpreter-vs-VM parity harness
(`tests/parity_check.py`) revealed that the VM produced different output from the
interpreter for **22 of 66** example programs — string interpolation, object
fields inside methods, `Try`/`Catch` and cross-call-frame exceptions, slicing
with a step, default parameters, stdlib maps, number/boolean/list formatting,
and more. This release drives that to **0 divergences across all testable
examples**, with ~70 new regression tests. It also stops a silent
double-execution fallback (which masked the drift and duplicated output), makes
the VM error on undeclared variables, gives top-level variables the global scope
functions expect, and relaxes an over-strict inferred-type lock. Plus the web
adapter, stdlib, and parser hardening from the prior cycle.

### Security

- **WSGI 500 page no longer leaks exception text:** `epl.wsgi.EPLWSGIApp`
  rendered the raw exception into the 500 response body, exposing internal
  details and allowing reflected HTML if the message contained user-controlled
  text. It now logs the full error server-side and returns a generic page; an
  opt-in `app.debug = True` shows the (HTML-escaped) error for local dev only.
- **`X-Forwarded-For` is no longer trusted by default:** the deploy WSGI adapter
  keyed rate limiting off the first `X-Forwarded-For` hop, which any client can
  spoof to evade limits. It now uses `REMOTE_ADDR` unless constructed with
  `WSGIAdapter(app, trust_proxy=True)` (also threaded through `ASGIAdapter`),
  signalling that a trusted reverse proxy sets the header.

### Fixed

- **Top-level variables are visible inside functions under the bytecode VM:** a
  variable created at module level (e.g. `db = connect(...)`) was stored as a
  local of the implicit main function, but functions looked it up as a global —
  so they couldn't see it (it read as undefined). Top-level variables — including
  `for each` / `for` loop variables — are now globals, matching the interpreter,
  so a loop variable and a later `Create` of the same name share one binding.
- **Unannotated variables are no longer locked to an inferred type:** the
  interpreter inferred a type from the first value (`total = 0` → integer) and
  then rejected accumulating a decimal into it — surprising for a dynamically
  typed language, and stricter than the VM. Only an *explicit* annotation
  (`Create x as integer`) now constrains later assignments.
- **Caught errors carry the right category under the VM:** a caught value now
  reads `EPL Name Error …` / `EPL Type Error …` as appropriate, instead of
  always `EPL Runtime Error …`, matching the interpreter.
- **Reading an undeclared variable is now an error under the bytecode VM:** it
  silently evaluated to `nothing`, so a typo (`score` for `Score`) produced
  wrong output instead of an error. It now raises *"Variable … has not been
  created yet"*, matching the interpreter and catching typos.
- **`to_string` and `random_integer` work on both backends:** the interpreter
  rejected `to_string(x)` and `random_integer(min, max)` (which the bytecode VM
  already accepted), so the same program behaved differently depending on the
  runner. Both are now recognised builtins in the interpreter (`to_string`
  aliases `to_text`; `random_integer` aliases `random`), and the VM gained the
  `random_integer` spelling too.
- **Maps returned by stdlib functions work under the bytecode VM:** functions
  like `csv_read` (and JSON parsing) return the interpreter's map type, which
  the VM didn't recognise — so `row.Salary` returned `nothing` (then crashed in
  `to_integer`) and printing a row showed Python's `repr` (`{'Name': 'Alice'}`).
  Stdlib return values are now normalised to the VM's native maps at the call
  boundary, so attribute access, formatting, and iteration all work.
- **`to_text` / `to_string` format with EPL semantics under the VM:** they used
  Python's `str()`, so `to_text([1, 2])` produced `['1', '2']`-style output and
  booleans rendered as `True`/`False`. They now use the shared formatter
  (`[1, 2]`, `true`/`false`), matching the interpreter.
- **An early `Return` from inside a loop no longer corrupts the caller under the
  bytecode VM:** a function returned without clearing operands it had pushed, so
  a `for each` iterator abandoned by an early `Return` leaked onto the shared
  operand stack — making an *enclosing* loop in the caller iterate the wrong
  collection (e.g. a password analyzer looped over a helper's internal list
  instead of its inputs). `Return` now restores the operand stack to the call
  frame's base, so functions are always stack-neutral apart from their result.
- **A `$word` that isn't a defined variable stays literal under the VM:** the
  VM substituted an undefined `$name` in a string with `nothing` (so a password
  like `aB3$xK9!mN2@` became `aB3nothing!mN2@`). It now leaves an undefined
  `$name` untouched, exactly like the interpreter — a defined variable still
  interpolates.
- **`Try`/`Catch` now binds the caught error and propagates across call frames
  under the bytecode VM:** the catch variable was never populated (the compiler
  checked the wrong AST attribute), so `Catch e … Print e` always printed
  `none`; and an error thrown inside a called function did not reach a
  `Try`/`Catch` in the caller (the handler address was applied to the wrong
  frame). The catch variable now receives the error — formatted identically to
  the interpreter (`EPL Runtime Error on line N: …`) — and exceptions unwind
  nested call frames to the frame that owns the handler.
- **Number and `nothing` formatting match the interpreter under the VM:** whole
  floats printed as integers (`sqrt(16)` → `4` instead of `4.0`) because the
  VM's value formatter collapsed them; it now preserves float form. Division
  still yields an integer for whole results (`8 / 2` → `4`) in both the runtime
  and constant folding. A `nothing` value now prints `nothing` (was `none`).
- **More bytecode-VM parity fixes (vs the interpreter):**
  - `random(min, max)` returned a raw `0..1` float instead of an integer in
    `[min, max]`. It now matches the interpreter (no-arg `random()` still
    returns a `0..1` float).
  - List/string slicing with a step (`items[0:10:2]`) ignored the step and
    returned a contiguous range. The step is now compiled and applied.
  - Default parameter values (`Function greet takes name = "World"`) leaked the
    raw AST node (`<…Literal object…>`) instead of the value. Defaults are now
    reduced to constants (including literal lists/maps) at compile time.
- **Built-in methods and string concatenation now match the interpreter under
  the bytecode VM:** several `epl run` (VM) defects were found via a new
  interpreter-vs-VM parity harness and fixed together:
  - Property-style method access (`text.uppercase`, `list.length`, `map.length`,
    `"…".trim`) returned `none` because the VM treated it as plain attribute
    access. It now dispatches to the built-in method, matching the interpreter.
  - `list.sort()` and `list.reverse()` returned a new list without mutating the
    original, so a subsequent print showed the unsorted list. They now mutate in
    place like the interpreter.
  - String concatenation with `+` stringified booleans, lists, and `none` with
    Python's `repr` (`True`, `['a', 'b']`) instead of EPL formatting
    (`true`, `[a, b]`, `none`). It now uses the shared value formatter.
  - Added missing method aliases so VM and interpreter accept the same names:
    `uppercase`/`lowercase` (method-call form), `find` (string), `to_list`,
    `is_number`, `is_alpha`, `format` (string), and `entries` (map).
- **`epl run` no longer double-executes a program when the VM hits an
  unsupported feature mid-run:** the VM streams output live, then on an internal
  error silently fell back to the interpreter, which re-ran the program from the
  start — duplicating all output already printed (and any side effects). The
  runner now only falls back when the VM has produced no output yet; if output
  was already emitted it surfaces the VM error instead of re-running. Live
  streaming is preserved via a pass-through output counter.
- **Instance fields are accessible inside methods under the bytecode VM
  (implicit `this`):** a method that referenced a bare field name — e.g.
  `Print name` or `Set amount to amount + 1` — compiled the name to a global
  lookup, so reads returned `none` (printing `None says None` instead of
  `Rex says Woof!`) and writes silently went to a global instead of the
  instance. The VM now resolves a bare name inside a method to `this.<field>`
  when it matches a class property and isn't shadowed by a local/parameter,
  matching the interpreter for reads, bare assignments, `Set … to …`, and
  augmented assignments. Found via a new interpreter-vs-VM parity harness.
- **String interpolation now works under the default `epl run` (bytecode VM):**
  EPL's documented `$name` and `${expr}` interpolation was implemented by the
  interpreter and the LLVM compiler but **not** the bytecode VM — and the VM is
  what `epl run` uses by default. The VM keyed off bare `{expr}` (not EPL
  syntax) and only did a naive global load, so `Say "Hello, $name!"` printed
  literally and `${1 + 2}` never evaluated. The VM now uses the same
  `$name`/`${expr}` template grammar, resolves locals before globals, and
  compiles full expressions inside `${…}`. Output is now identical across the
  interpreter, VM, and compiler. Six regression tests added in `tests/test_vm.py`.
- **`epl vm` no longer prints every line twice:** the VM streams output live as
  it executes, but the `vm` CLI command then re-printed the collected
  `output_lines`, duplicating all program output. The redundant re-print was
  removed (the default `run` path was already correct).
- **HEAD requests are handled correctly across the web adapters:** a `HEAD`
  request on a registered `GET` route returned `404` (`epl.wsgi.EPLWSGIApp`,
  `epl.deploy.WSGIAdapter`), and the built-in server wrote a body in violation
  of RFC 9110. `HEAD` now routes as `GET`, keeps identical headers (including
  `Content-Length`), and sends no body.
- **Redis store backend matches Memory/SQLite remove semantics:** an
  out-of-range index passed to `RedisStoreBackend.store_remove()` raised
  (`lset` errors on a bad index) instead of being ignored, breaking backend
  interchangeability and crashing on races. Invalid indexes are now silently
  ignored, and a concurrent shrink between `llen` and `lset` is handled.
- **Static build scripts reject a missing `--out` value:** `build_static.py
  --out` (and the website `build.py`) crashed with `IndexError` when `--out`
  had no argument; they now print a clear error and exit with status `2`.
- **Watch mode on Windows multi-drive setups:** `epl watch` no longer crashes
  with `ValueError: path is on mount 'C:', start on mount 'D:'` when the watched
  file and the current directory live on different drives. The display path now
  degrades gracefully to an absolute path via a new `_safe_relpath()` helper
  (the value is only ever shown to the user, never used for resolution).
- **Bundled stdlib modules are importable again:** every shipped module
  (`json`, `encoding`, `net`, `os`, `regex`, `sql`) failed to parse — and was
  therefore impossible to `Import` — because they use the `Note "…"` comment
  form (now accepted by the lexer alongside `Note:`) and natural wrapper names
  that collide with reserved words. `match`, `fetch`, `delete`, and `where` are
  now usable as function/parameter/member names. (`json` is itself a reserved
  type token, so that module must be imported with an alias: `Import "json" as
  J`.) Regression tests parse all six modules and exercise import + call.
- **`db_create_table` accepts standard column constraints:** the type validator
  split each definition into single words but compared them against multi-word
  phrases (`PRIMARY KEY`, `NOT NULL`), so legitimate types like
  `INTEGER PRIMARY KEY` and `TEXT NOT NULL` were rejected. It now validates
  against the individual constraint words and properly handles parameterized
  types (`VARCHAR(255)`, `DECIMAL(10,2)`), while still blocking SQL injection.
  Also adds `DECIMAL`, `FLOAT`, `DOUBLE`, `CHAR`, and `TIMESTAMP` to the
  allow-list.
- **`Map with` literals can span multiple lines:** map pairs were parsed as a
  single logical line, so breaking `Map with a = 1 and b = 2` across lines was a
  syntax error. Newlines are now tolerated around the `and` separator (both
  trailing `and` and leading `and` styles), without ever swallowing the
  statement terminator of a single-line map.

### Changed

- **Clearer error for `Create WebApp` misuse:** `Create app equal to Create
  WebApp …` previously failed with an opaque `Expected a value or expression`.
  It now explains that `Create WebApp` is a statement, not a value, and points
  to the correct form: `Create WebApp called app`.

---

## [9.7.0] — 2026-06-16

**Native web DSL** — a six-phase effort to make EPL's web layer express
styling, structure, head/SEO, and interactivity as *first-class language
features* instead of raw CSS/JS/meta injected through the `Script` escape hatch.
The flagship site (`landing_page/src/main.epl`) is migrated onto the new
features as proof: it now authors structure, content, styling (page-scoped
`Stylesheet`), and head/SEO natively, leaving only genuinely imperative motion
JS (a canvas particle engine, scroll/tilt) in the sanctioned hatch. Every phase
stays mypy-clean and ruff-clean and ships regression tests; the native event
and CSP layers are additionally **verified in a real browser** (puppeteer),
including under a strict CSP with an enforced negative control.

### Added

- **Structure (Phase 1):** `List`/`Raw HTML`/`Script` and structural/layout tags
  now nest correctly inside `Div`/`Section`/etc. (a parser whitelist bug);
  inline `style "…"`; safe attributes (`aria-*`, `data-*`, `role`, `target`,
  `rel`, `title`, …); `Link`/`Button` accept `class`/`id`/`style`/attrs. Inline
  `on*` handlers are rejected at parse time.
- **Native CSS (Phase 2):** `Style` blocks gain nested rules — `On hover`/`On
  focus-visible` → `:pseudo-class`, `On before`/`after`/… → `::pseudo-element`,
  `On mobile|tablet|desktop` and `On screen below|above "Npx"` → `@media`,
  `Select "sel"` → descendant — plus a first-class `Stylesheet … End` raw-CSS
  block, all server-rendered into `<head>` with a `</style>`/`<script>` breakout
  guard.
- **Semantic head / SEO (Phase 3):** top-level `Head … End` block + per-`Page`
  overrides — `Description`, `Keywords`, `Author`, `ThemeColor`, `Canonical`,
  `Favicon` (auto `type`), `Font "…" weights "…"` (Google Fonts, preconnect
  once), generic `Link`, `OpenGraph`, `Twitter`, `Meta` — server-rendered so
  metadata is visible to crawlers/social scrapers without JS.
- **Native interactivity (Phase 4):** element-level `On click/hover/reveal`
  blocks and inline `on … toggles/adds/navigates/…` sugar compile to
  **generated, CSP-safe JS** (`addEventListener`/`IntersectionObserver`, never
  inline `on*`). Verbs: `Add`/`Remove`/`Toggle class [on "#sel"]`, `Navigate
  to`, `Scroll to`, and a `Run "fn"` bridge to `Script`-defined code.
- **Strict CSP (Phase 5):** opt-in via `epl serve --csp` (or
  `configure_page(csp=True)`) — a per-response nonce is added to every generated
  `<script>` and the `Content-Security-Policy` header becomes `script-src 'self'
  'nonce-…'`, so the generated JS runs under a strict policy with no
  `'unsafe-inline'` for scripts.
- **Page-scoped CSS (Phase 6):** a `Stylesheet`/`Style` block nested inside a
  `Page` renders only on that route (after site-wide CSS), enabling distinct
  per-route stylesheets without shipping every route's CSS on every page.

### Changed

- `landing_page/src/main.epl` — SEO/meta/favicon/fonts migrated from
  `createElement('meta'/'link')` injection to a native `Head` block + per-page
  directives; per-route CSS migrated from `createElement('style')` injection to
  page-scoped `Stylesheet` blocks. Server-rendered, isolated per route, browser-
  verified pixel-identical with KYC content intact.

### Fixed

- Production `epl serve` (`deploy.py` WSGI adapter) was rendering pages with **no
  custom styles/components/animations** — `Style`/`Stylesheet` CSS silently never
  reached served pages in production mode. Now threaded through.
- `web.py` route resolution (`_resolve_page_def`/`_resolve_page_element`) dropped
  newly-added `PageDef`/`HtmlElement` fields (head directives, events, page-scoped
  stylesheets) when cloning nodes for a request, so those features vanished on
  resolved routes. All clone sites now carry every field.

---

## [9.6.0] — 2026-06-13

Language Server Protocol **v2** plus a static-analysis bug-fix batch. EPL's
vision is that anyone can *read, write, and maintain* code in plain English;
this release strengthens the "maintain" leg with editor-grade semantic
highlighting and safe, token-aware refactoring, and hardens the runtime by
running the repo's own toolchain — **mypy** (configured but, until now, never
actually enforced), **ruff** (bugbear/pyflakes rule sets), and `compileall` —
across all ~89K LOC of `epl/` and fixing every verified finding. It also turns
the previously-ignored lint and type-check CI gates into real, ratcheting gates.
Each bug fix ships with a regression test that fails on the old code. Full suite:
**1,719 passed, 5 skipped, 0 failed**.

### Added

- `lsp_server.py` — **Semantic tokens** (`textDocument/semanticTokens/full`).
  The server now publishes a stable 9-type legend (`keyword`, `variable`,
  `function`, `class`, `type`, `number`, `string`, `comment`, `operator`) and
  emits LSP delta-encoded tokens for the whole document. Highlighting is driven
  by the **lexer**, not regex, so an English word like `Print` is colored as a
  keyword only where it is actually a keyword — never inside a string or
  comment. Comments (`# …` and `Note: …`) and string literals are recovered
  from a raw source scan because the lexer discards/unquotes them.
- VS Code extension consumes the legend automatically via
  `vscode-languageclient` 9.x — no client changes required.

### Changed

- `lsp_server.py` — **Find-references and rename are now token-aware.**
  `get_references()` and `get_rename_edits()` match only `IDENTIFIER` tokens, so
  occurrences inside string literals, comments, and keywords are no longer
  returned. This makes workspace-wide rename safe (renaming `count` no longer
  rewrites the word `count` inside a printed string). A word-boundary text scan
  is retained as a fallback for documents that fail to lex.
- LSP server version reported in `initialize` bumped to **2.1.0**.

### Fixed

- `stdlib.py` — **`thread_run` raised `NameError` on every call.** It did
  `return tid` with `tid` undefined; now returns the started `Thread` object so
  callers can `join()` it.
- `vm.py` — **`random` and `random_int` builtins crashed at runtime.** A local
  `def _random(...)` shadowed `import random as _random`, so `random` recursed
  into itself and `random_int` called `.randint` on a function object
  (`AttributeError`). The module import is now aliased `_random_mod`.
- `vm.py` — removed duplicate dict keys `is_none` (defined at two sites) and
  `sorted`; hardened `_sort` with an empty-args guard so the surviving `sort`/
  `sorted` entries behave identically.
- `type_system.py` / `type_checker.py` — **the type checker was silently inert on
  `If`, ternary, and `Match` nodes.** It referenced AST attributes that do not
  exist (`true_body`/`false_body` → `then_body`/`else_body`; `clauses` →
  `when_clauses`; `true_value`/`false_value` → `true_expr`/`false_expr`;
  `node.object` → `node.obj`), raising `AttributeError` that the diagnostics path
  swallowed via a broad `except`. The checker now actually walks these nodes;
  ternary type inference works (e.g. `1 if c otherwise 2` → `integer`). Match
  `default_body` is now type-checked too.
- `parser.py` — parameter-ordering error called non-existent `self._error(...)`
  (`AttributeError`); now raises `ParserError` with a line number like every
  other parser error.
- `interpreter.py` — `EPLClass` now initializes `static_methods` and
  `type_params` in `__init__` so every construction path exposes them (no more
  `AttributeError` on lookup before the class-def executor runs).
- `doc_linter.py` — fixed a loop-variable closure-capture bug (B023): the
  synthesized match object now binds `fname`/`norm_params` by value.
- `official_packages/epl-http` — removed a dead, buggy `get()` that made **two**
  HTTP requests and returned a malformed response, shadowed by the correct one.
- `official_packages/epl-science` — `hasattr(x, "__call__")` → `callable(x)`.
- `ios_gen.py`, `publisher.py` — removed two useless `if/else` branches whose
  arms were identical (RUF034).
- `interpreter.py` — removed a dead `results` accumulator in parallel for-each.
- `packager.py` — native packaging called `compiler.emit_object(path)` which does
  not exist (`AttributeError`); now writes the bytes returned by
  `compile_to_object()` to the `.o` file.
- `type_checker.py` / `type_system.py` — **the type checker crashed on every
  variadic function.** `node.params` can contain a `RestParameter` node, but the
  checker did `p[0]`/`len(p)` on it (`TypeError`, swallowed) in three passes
  (declaration collection, class-method scan, body check). A `_param_name_type()`
  helper now centralizes the guard; `type_system` no longer mis-registers a rest
  param under its `repr`.
- Made return/parameter annotations honest across `lexer.py`, `parser.py`,
  `errors.py`, `environment.py`, `type_checker.py`, `type_system.py` (`Optional`
  where `None` is actually returned) — clears the way for the strict type gate.

### Hardening & CI

- **The lint and type-check CI gates were theater — now they're real.** `mypy epl/`
  exited 1 (191 errors) and `ruff format --check` flagged 48 files, so both gates
  had been effectively red-and-ignored.
- `ruff` (pyproject) — un-ignored **B004, B023, F601, F811** and enforce **RUF034**.
  Each caught a real bug in this release and is now held at **zero violations**, so
  the bug class cannot silently regrow. Configured `ruff check` is fully green.
- `ci.yml` + `pyproject.toml` — **whole-tree `mypy epl/` is now BLOCKING with an
  empty debt ledger.** Type errors were driven from **191 → 0**: *all 75 modules*
  under `epl/` (excluding `official_packages`) type-check clean, with full
  import-following. The work was done as a ratchet — a `[[tool.mypy.overrides]]`
  exemption list that only ever shrank — and that list is now empty, so there are
  no per-module exemptions left. A new type error fails CI.
- Cleaning the tree to zero surfaced honest fixes and several **real latent bugs**:
  the REPL `.vars`/`.type` commands referenced a non-existent Environment API
  (`.env`/`.values`/`.set` vs the real `.global_env`/`.variables`/`define_variable`)
  and would have crashed in production; `_exec_use`/`_exec_use_js` could bind a
  variable literally named `None`; `parallel_each` re-raised a possibly-`None`
  `future.exception()`; networking socket ops on a closed connection raised raw
  `AttributeError` instead of a clear `ConnectionError` (new `_require_socket()`
  guard); `send()` returned `sendall() or len(data)` though `sendall` returns
  `None`. Plus container annotations, honest `Optional`/union signatures, and two
  file-handle/loop-variable shadows in `packager`.
- **34 broad silent `except` swallows** instrumented with
  `_debug_log.suppressed(site)` — failures are now observable under `EPL_DEBUG`
  with zero behavior change by default.
- **Exception chaining (B904) enforced tree-wide** and removed from the ignore
  list. All 116 re-raise sites now chain explicitly: `from e` where the cause is
  bound and useful (42 + infra sites), `from None` for the 51 EPL-domain
  translations in `interpreter`/`stdlib` (so Python internals like `int()`'s
  `ValueError` don't leak into plain-English EPL errors).
- Applied `ruff format` repo-wide (canonical single-quote style); 48 files brought
  into conformance so the format gate passes.

### Tests

- New `tests/test_lsp_semantic_tokens.py` (12 cases): legend stability, capability
  advertisement, delta-encoding validity, per-kind classification, the
  keyword-inside-string guarantee, token-aware references/rename, and graceful
  degradation on unlexable source.
- New `tests/test_static_analysis_fixes.py` (13 cases), including anti-regression
  guards that assert the type checker **actually visits** If/ternary/Match bodies
  and survives variadic params — so a future swallowed-exception regression can't
  hide — plus a guard that `_debug_log.suppressed()` stays silent unless `EPL_DEBUG`
  is set.
- De-brittled `tests/test_phase4_security.py::test_mcp_cors_default` to be
  quote-style-agnostic (the formatter's single-quote canonicalization must not mask
  the real check: CORS default is `null`, never `*`).
- Updated `tests/test_phase5_tooling.py` to assert the corrected token-aware
  reference semantics and the new server version.

Full suite: **1,719 passed, 5 skipped, 0 failed.**

---

## [9.5.0] — 2026-06-13

Post-release stabilization of the v9.4.0 line. A community bug report (12 issues,
46 failing tests on a fresh checkout) was triaged, fixed end-to-end, and locked in
with a dedicated verification suite. The full test suite now reports **1,693 passed,
5 skipped, 0 failed**.

### Security

- `web.py` — **BUG-01 / BUG-02: web servers no longer bind to `0.0.0.0` by default.**
  `start_server()` and `AsyncEPLServer` now accept a `host` parameter that defaults to
  `127.0.0.1` (localhost only) and print an explicit warning when a caller opts into
  `0.0.0.0`. Previously every `epl serve` web app was reachable from the entire network
  regardless of the documented `--host` default. The dedicated deployment entry point
  `start_production_server()` continues to default to `0.0.0.0` by design.
- `web.py` — **BUG-06: open-redirect hardening.** `_validate_redirect()` is now applied
  to *every* `REDIRECT:` URL construction path (`_execute_action` and `_build_page_sync`),
  closing a bypass where unvalidated redirect targets could reach the response.
- `web.py` — **BUG-12: ETag generation moved from MD5 to SHA-256** (truncated to 32 chars),
  bringing it in line with the v9.4.0 hardening that deprecated MD5 elsewhere in the stack.

### Fixed

- `main.py` — **BUG-04: restored the root `main.py` CLI re-exporter.** It re-exports
  `compile_file`, `CROSS_TARGETS`, and the other CLI symbols, fixing 15+ import-time test
  failures across `test_phase1_native.py`, `test_phase6.py`, `test_tier4.py`, and `test_phase7.py`.
- `stdlib.py` — **BUG-05: web route argument validation now runs *before* Flask instantiation**,
  so invalid route definitions raise a clear error instead of failing deep inside Flask.
- `web.py` — **BUG-07: fixed a race condition on the active-connection counter** in
  `AsyncEPLServer` by guarding `_active_connections` with an `asyncio.Lock`.
- `web.py` — **BUG-09 / BUG-10: removed deprecated `datetime.utcnow()` /
  `datetime.utcfromtimestamp()`** in favor of timezone-aware `datetime.now(timezone.utc)` /
  `datetime.fromtimestamp(ts, timezone.utc)`. Prevents breakage on Python 3.15 where the
  legacy APIs are removed.
- `web.py` — **BUG-11: instrumented 6 remaining silent `except` blocks** with
  `_debug_suppressed()` so swallowed exceptions are observable under debug logging.
- `test_phase1_native.py` — **BUG-03: forced `encoding='utf-8'`** on `runtime.c` reads,
  fixing `cp1252` decode crashes on Windows.
- `test_webapp.py` — **BUG-08: raised the test server startup timeout** (15s → 30s, poll
  0.1s → 0.3s) to remove a flaky timeout on slower machines.
- Resolved backwards-compatibility regressions introduced while fixing the above, restoring
  the v9.4.0 public API surface.

### Tests

- Added `tests/test_bug_fixes.py` — a **51-test verification suite** covering BUG-01 through
  BUG-12 with independent assertions plus cross-cutting integration checks.
- Full suite green on a clean checkout: **1,693 passed, 5 skipped, 0 failed** (previously
  1,594 passed / 46 failed / 7 skipped in the community report).

---

## [9.4.0] — 2026-06-05

Multi-phase enterprise-grade remediation against the v9.3.0 audit findings.
All 6 phases ship in this release.

### Phase 6 — Error Explainer v2.0 (Enterprise-Grade Diagnostics)

**Fixed**
- `error_explainer.py` — No longer calls cloud AI API by default. The `_offer_ai_explanation` and `epl fix` functions previously passed `ai=True` unconditionally, causing "Groq API error (401): Invalid API Key" for every user without a configured key. Now runs 100% offline with zero API calls. AI analysis is opt-in via `--ai-errors` flag.
- `error_explainer.py` — `_get_ai_explanation` now filters raw API error strings (401, 403, "Invalid API Key") so they never leak to the terminal even if AI is enabled.

**Enhanced**
- `error_explainer.py` — Upgraded from v1.0 (27 patterns) to v2.0 with 55+ offline patterns covering: type assignment mismatches, overflow, file I/O, method not found, missing `Then`/`Takes`, iterator exhaustion, read-only properties, map key types, `=` vs `==` in conditions, missing quotes, curly braces, semicolons, C++/Java/Ruby output syntax, parentheses in conditions, unterminated strings, unexpected EOF, and more.
- `error_explainer.py` — **Context window**: shows 2 lines above and below the error with line numbers and Rust-style `>` pointer arrows highlighting the exact error line.
- `error_explainer.py` — **"Did you mean?"** fuzzy matching now covers EPL keywords (not just variables/functions). Catches typos like `Funtion` → `Function`, `Whille` → `While`.
- `error_explainer.py` — **Error code documentation links**: each explanation now includes a `https://epl-lang.org/errors/EXXXX` link in the footer.
- `error_explainer.py` — **Category badges**: output header shows `[E0400] [TYPE]` or `[E0500] [NAME]` for quick identification.
- `cli.py` — **Auto-fix**: `epl fix <file.epl> --fix` automatically writes the corrected code back to the file, preserving indentation. Shows old/new diff in the terminal.
- `vscode-extension/package.json` — Renamed "EPL: Fix Errors with AI" to "EPL: Fix Errors" with `$(zap)` icon. No misleading AI branding for an offline tool.


### Phase 5 — CI/CD hardening + dependency fixes

**Fixed**
- `pyproject.toml` — Added `[project.dependencies]` with `flask>=3.0,<4.0` and `requests>=2.31,<3.0`. Both were previously undeclared: `flask` is imported unconditionally in `mcp_http_server.py`; `requests` is a hard requirement of the bundled `epl-http` package. Consumers who `pip install eplang` now receive both transitively without needing extras.
- `pyproject.toml` — Added upper-bound version caps to all optional dependencies. Open-ended `>=X.Y` specifiers previously risked silent breakage if a major-version bump introduced breaking changes. All entries in `llvm`, `ai`, `secure`, `server`, `redis`, `repl`, `cloud`, `all` extras now carry `<NEXT_MAJOR` caps.
- `pyproject.toml` — Added `mypy>=1.8,<2.0` to the `[dev]` optional extra, so `pip install eplang[dev]` installs the type checker alongside pytest/ruff/coverage.
- `.github/workflows/ci.yml` — Test matrix widened from `['3.11', '3.12']` to `['3.9', '3.10', '3.11', '3.12']`, matching the `requires-python = ">=3.9"` claim. macOS excludes 3.9/3.10 to keep runner costs reasonable.
- `.github/workflows/ci.yml` — Added `typecheck` job: installs `.[dev]` and runs `mypy epl/ --ignore-missing-imports --exclude epl/official_packages`. mypy was configured in `pyproject.toml` but had no CI step to enforce it.
- `.github/workflows/ci.yml` — Added `test_phase3_reliability.py`, `test_phase4_security.py`, and `test_security_hardening.py` to the stable test suite whitelist and the coverage step. These files existed but were omitted from the explicit pytest invocation, meaning security and reliability tests never ran in CI.

**Tests**
- 52 new tests in `tests/test_phase5_cicd.py` — static analysis of `pyproject.toml` and `ci.yml` covering: runtime dep declaration, lower/upper bounds on all extras, mypy in dev extra, Python 3.9/3.10/3.11/3.12 matrix, typecheck job wiring, and security test file inclusion.

### Phase 4 — Official package security

**Security**
- `epl-crypto` — Removed insecure XOR-based fallback from `aes_encrypt` / `aes_decrypt`. When the `cryptography` package is absent, both functions now raise a clear `ImportError` with an install hint instead of silently falling back to a trivially-broken XOR cipher. Added `_require_cryptography(fn_name)` helper used by both functions.
- `epl-validator` — `sanitize_sql()` previously escaped only `'` and `"`. Extended to a full 12-character-class sanitizer: `\`, `'`, `"`, `` ` ``, `;`, `--`, `#`, `%`, `_`, NUL, `\n`, `\r`. Backslash is processed first to prevent double-escaping. Includes `WARNING` docstring reminding callers to prefer parameterised queries.
- `epl-validator` — `matches_pattern()` and `validate()` schema pattern fields previously used bare `re.match()`, allowing a crafted pattern to hang the process via catastrophic backtracking (ReDoS). Both now route through `_safe_match()`, which executes the match in a daemon thread and raises `ValueError` if it does not complete within 1 second.
- `epl-auth` — `md5()` now emits a `DeprecationWarning` on every call, steering users toward `sha256()` or `hash_password()`. The digest return value is unchanged for checksum / legacy compatibility.
- `epl-auth` — Session dict (`_sessions`) previously grew without bound. Added a background daemon thread (`_evict_expired`) that sweeps expired sessions every 5 minutes. All session and rate-limit dict mutations are now protected by `_sessions_lock` / `_rate_limits_lock` (thread-safety gap closed). `check_rate_limit` uses a local `bucket` copy to avoid holding the lock during list comprehension iteration.
- `mcp_http_server.py` — `CORS_ORIGIN` default changed from `"*"` (allows any origin) to `"null"` (blocks all cross-origin browser requests). Operators set `EPL_MCP_CORS_ORIGIN=https://their-app.example.com` to allow a specific origin. Module docstring updated with guidance and a NEVER-use-`*`-for-authenticated-endpoints warning.

**Tests**
- 75 new tests in `tests/test_phase4_security.py` covering: XOR removal (simulate absent lib, verify `ImportError`), AES round-trip + fresh-nonce, SQL escaping for all 12 character classes + backslash-first ordering, ReDoS timeout, `_safe_match` invalid-regex handling, schema pattern integration, MD5 `DeprecationWarning` presence + content, session eviction on `validate_session` and via background timer, 50-thread concurrent session creation, 20-thread rate-limit fairness (exactly 10 allowed / 10 blocked), JWT round-trip + bad-secret + expiry, CORS default string + env-override.

### Phase 1 — Critical language pipeline fixes

**Fixed**
- `vm.py` — Float zero (`0.0`) is now caught by the division guard alongside integer zero; previously `10.0 / 0.0` silently produced `inf` instead of a runtime error.
- `vm.py` — List index-set (`obj[i] = val`) now raises a clean `VMError` on out-of-range indices instead of propagating a raw Python `IndexError`.
- `lexer.py` — Triple-quote boundary check corrected (off-by-one that could read one byte past the source buffer on a 2-char source ending in `"`).
- `lexer.py` — Hex (`\xNN`) and Unicode (`\uXXXX`) escape sequences now guard against reading past end-of-source before slicing, raising a clean `LexerError` instead of silently accepting a truncated escape.
- `parser.py` — Rest-parameter error path now raises `ParserError(msg, line)` directly instead of calling the non-existent `self._error()` method, which previously caused an `AttributeError` crash on malformed rest parameters.
- `python_transpiler.py` — Range loops (`for x from A to B`) were emitting one extra iteration when no step was specified. The `end + 1` expression is now correctly parenthesised for both step and no-step paths.
- `type_checker.py` — `_check_call` now reads `node.arguments` (the correct AST attribute) instead of `node.args`, so type inference for function calls no longer silently receives an empty argument list.
- `type_system.py` — `TypeScope.resolve_type_name` accepts a `_seen` guard set and breaks circular alias chains (`type A = B; type B = A`) by returning `EPLType(PRIMITIVE, 'any')` instead of recursing infinitely.

### Phase 2 — Security

**Security**
- `web.py` — Open redirect at 7 locations: all redirect targets now pass through `_validate_redirect()`, which allows only relative paths and rejects absolute URLs and protocol-relative `//host` forms. Attackers can no longer craft `?next=https://evil.com` payloads that redirect users off-site after login/logout.
- `web.py` — Static file path traversal: changed from `os.path.normpath` + bare `startswith` to `os.path.realpath` + `startswith(root + os.sep)`, so symlinks pointing outside the static root are also blocked.
- `web.py` — CSP header tightened: removed `script-src 'unsafe-inline'`; added `object-src 'none'` and `base-uri 'self'` to close dangling-markup and base-tag injection vectors.
- `html_gen.py` — Button `onclick` regex replaced: `[^)]*` (accepted arbitrary JS) with an explicit allowlist `[a-zA-Z0-9_,\s\'\".\-]*` that only allows safe argument characters.
- `html_gen.py` — `$items{collection}` store template now HTML-escapes every item value via `html.escape()` before rendering, closing the stored-XSS vector where attacker-controlled collection values were injected verbatim.

### Phase 3 — Concurrency, resource leaks, and atomicity

**Fixed**
- `bytecode_cache.py` — `save()` now writes to a `.eplc.tmp` sibling and renames it into place atomically. A crash or OOM mid-write previously left a truncated `.eplc` that caused a silent full re-parse on every subsequent run. The temp file is cleaned up on any exception before re-raising.
- `async_io.py` — `EPLInterval.stop()` now cancels the underlying asyncio `Future` immediately via `task.cancel()` in addition to setting `_running = False`. Previously, a sleeping interval task would not wake until the current sleep elapsed, leaving a thread alive for up to `interval` seconds after `stop()`.
- `concurrency.py` — `EPLRWLock` rewritten to eliminate a deadlock window. The previous implementation exited the `Condition` context (releasing `_lock`) and then immediately called `self._lock.acquire()` bare — another thread could win that acquire in the gap, breaking write exclusion. The new design uses three separate primitives: `_write_lock` (serialises writers and gates new readers), `_drain_event` (signals when active reader count hits zero), and `_state_lock` (guards the reader/writer counters).
- `hot_reload.py` — `_restart_pending` plain `bool` replaced with `threading.Event` (`_restart_event`). A plain bool has no memory-barrier guarantee outside CPython's GIL and is not safe to set from one thread and read from another in general. `Event.set()` / `Event.wait()` / `Event.is_set()` are explicitly thread-safe.
- `hot_reload.py` — New `_kill_process(proc, timeout)` helper escalates SIGTERM → SIGKILL after `timeout` seconds. The previous `proc.terminate(); proc.wait(timeout=5)` could hang indefinitely if the child ignored SIGTERM. All termination paths (`run_with_reload`, `stop`, `KeyboardInterrupt`) now use this helper.

**Tests**
- 30 new tests in `tests/test_phase3_reliability.py` covering: atomic write crash safety (mid-write OSError simulation), interval stop cancellation and idempotency, RWLock concurrent readers (peak count), writer exclusion, no-deadlock under mixed contention, `_kill_process` SIGTERM→SIGKILL escalation, and `HotReloader` event thread-visibility.

---

## [9.3.0] — 2026-06-01

Multi-phase enterprise-grade enhancement program. All phases bundled into a single release. Sections below correspond to phases completed before publish.

### Phase 2 — Exception hygiene

**Added**
- `epl/_debug_log.py` — `suppressed(where)` helper. Records swallowed exceptions to stderr when `EPL_DEBUG=1` is set, silent otherwise. Set `EPL_DEBUG_TRACE=1` for full tracebacks. Zero dependencies on the rest of the package — safe to import from any module.

**Changed**
- 34 previously-silent `except Exception: pass` / `return None` blocks now instrumented across `epl/stdlib.py` (15), `epl/web.py` (10), `epl/runtime_support.py` (4), `epl/cli.py` (3), `epl/interpreter.py` (2). Production behaviour is unchanged (still swallows by default); diagnostic visibility is one env var away.

**Tests**
- 12 new tests in `tests/test_debug_log.py` covering env-var parsing, truthy/falsy values, silent-by-default behaviour, and the "called outside an except block" safety case.

### Phase 3 — Raw HTML escape hatch

**Added**
- `Raw HTML "<...>"` keyword for emitting arbitrary HTML inside `Page` blocks. Unblocks every tag the EPL parser does not natively support (`<table>`, `<video>`, `<audio>`, `<details>`, `<select>`, `<textarea>`, `<dialog>`, etc.) without forcing a parser change for each new element. The author is responsible for safety; never pass user input here without sanitisation.
- `examples/raw_html_demo.epl` showcasing the new keyword.

**Tests**
- 7 new tests in `tests/test_raw_html.py` covering verbatim emission, attribute preservation, coexistence with built-in elements, and the regression case (`html`/`raw` still usable as identifiers).

### Phase 4 — Theme system (light / dark / auto)

**Added**
- `configure_page(theme=...)` accepts `'light'`, `'dark'`, or `'auto'` (default). The previous behaviour hardcoded `<meta name="color-scheme" content="dark">` + a Darkreader lock on every page, ignoring user OS preference and breaking light-mode embeds.
- Built-in CSS variable palette injected into the rendered `<head>`: `--bg`, `--fg`, `--muted`, `--accent`, `--surface`, `--border`, `--danger`. Apps that reference these tokens (the parser/StyledElement layer already does) get a coherent palette per theme for free.
- `'auto'` emits both palettes and switches via `@media (prefers-color-scheme: dark)` so the OS picks.

**Changed**
- Page `<head>` no longer hardcodes dark mode. Default is `'auto'` — apps that want the v9.2.0 always-dark behaviour call `configure_page(theme='dark')`.

**Tests**
- 7 new tests in `tests/test_theme.py` covering each theme value, palette completeness, the media-query branch in `auto`, invalid values, and reset semantics.

### Phase 5 — SQL injection hardening

**Security fix.** `real_db_update` and `real_db_delete` previously interpolated dict-WHERE column names directly into SQL without validation, and accepted bare string WHERE clauses with no params. A caller passing `{"id = 1 OR 1=1 --": x}` as a WHERE map could rewrite or delete every row in a table. Both vectors are now closed.

**Added**
- Module-level `_SQL_IDENT_RE` and `_assert_sql_identifier(name, kind)` helper in `epl/stdlib.py` — a single source of truth replacing seven copy-pasted in-function regex compilations. New SQL-emitting endpoints now have one obvious thing to call.

**Changed (breaking only for previously-exploitable code paths)**
- `real_db_update(db, table, set_map, where_map)` — every key in `where_map` is now validated as a SQL identifier before interpolation.
- `real_db_delete(db, table, where_map)` — same validation applied.
- `real_db_update` / `real_db_delete` with a **string** WHERE clause now require an explicit `params` tuple. The string-only form (which executed user input verbatim) raises with a fix hint.

**Tests**
- 24 new tests in `tests/test_sql_injection.py`:
  - 17 unit tests for `_assert_sql_identifier` covering valid identifiers, nine injection patterns (statement breakage, predicate injection, quote breaks, etc.), non-string inputs, and `kind` reporting.
  - 7 integration tests through the public `call_stdlib('real_db_update'|'real_db_delete', ...)` dispatcher proving each historical exploit attempt now raises **and that no rows were mutated**, plus regression tests that the legitimate dict-WHERE and parameterised string-WHERE paths still work.

### Phase 6 — Command injection hardening (pip/npm flag-injection)

**Security fix.** Although `shell=True` was already eliminated in 9.2.0, the package-manager and interpreter still passed manifest/lockfile values into `pip install` and `npm install` as positional argv. `pip` and `npm` both parse flags from positional arguments — so a malicious manifest entry like `evil = "--extra-index-url https://evil.com/pypi"` or `version = "* --before-script=evil.sh"` would, before this release, silently install from an attacker-controlled source or run an attacker-chosen script. All four call sites are now closed.

**Added**
- `_normalize_python_requirement` (existing helper) now refuses any requirement that **starts with `-` or contains a whitespace-separated flag token**, and refuses `pkg @ url`-style URL/path install specs. Power users wanting URL installs call pip directly.
- New `_validate_npm_version_spec(version)` in `epl/package_manager.py` — same flag-injection check for npm version specs read from `[js-dependencies]`.
- **Defense in depth:** every `pip install`/`npm install` invocation now uses the `--` end-of-options separator so that even if validation were bypassed, the package manager would treat the requirement as positional rather than a flag.

**Changed (breaking only for previously-exploitable code paths)**
- `install_python_package`, `install_python_dependencies`, the lockfile install loop, **and the auto-install path in `epl/interpreter.py`** all now route through `_normalize_python_requirement` and emit `pip install --  <req>`.
- `install_js_package` and `install_js_dependencies` now validate both the package name (already protected) and the version spec, and emit `npm install --  <target>`.

**Tests**
- 26 new tests in `tests/test_command_injection.py`:
  - 12 unit tests for `_normalize_python_requirement` covering clean specifiers, six flag-injection payloads, and three URL/path-spec payloads.
  - 12 unit tests for `_validate_npm_version_spec` covering valid semvers, five flag-injection payloads, and the non-string case.
  - 2 end-to-end tests proving that a poisoned `epl.toml` is refused at the boundary and **the `subprocess` is never invoked**.
- 3 existing tests updated to assert the new `--`-separated argv shape.

### Phase 7 — `epl watch` no longer kills long-running programs

**Bug fix.** The dev-mode watcher hard-capped every re-run at **60 seconds**, killing servers, bots, REPLs and any genuinely long-running EPL program the moment they crossed the minute mark. The cap is now removed by default and the watcher exposes a `--timeout=` flag for the rare case where a hard cap is wanted.

**Changed**
- `epl.watcher._execute(...)` `timeout` parameter now defaults to **`None`** (no cap). The previous 60-second default is gone.
- `epl watch` accepts a new `--timeout=SECS` flag. Accepted values: a positive number (seconds), or one of `none`/`off`/`0`/`disable` to explicitly disable the cap.
- Help text for `epl watch` now documents the flag.

**Tests**
- 8 new tests in `tests/test_watcher.py`:
  - 3 `TestWatcherTimeout` cases verifying `_execute` forwards `timeout` to `subprocess.run` verbatim, defaults to `None`, and handles `TimeoutExpired` cleanly without raising.
  - 5 `TestWatcherCliTimeoutParsing` cases verifying CLI flag parsing — integer, decimal, the four disable-sentinels, default (no flag), and the invalid-value error path.

---

## [9.2.0] — 2026-06-01

Phase 1 of the enterprise-grade enhancement program: privacy & secrets hygiene. No breaking changes — every behaviour shift is the safer default, with the old behaviour available behind an opt-in.

### Added
- **OS keyring storage for cloud AI API keys.** Keys configured via `configure_cloud(...)` now go into the OS keychain (Windows Credential Manager, macOS Keychain, Secret Service / KWallet on Linux) under service `epl-lang`, user `cloud_api_key`. The on-disk `ai_config.json` no longer contains plaintext secrets when a keyring backend is available. Requires the optional `keyring` package — install via `pip install eplang[secure]` or it ships with `eplang[all]`.
- **Automatic migration of legacy plaintext API keys.** Pre-9.2.0 configs with `api_key` in `ai_config.json` are moved into the keyring on first read, and the field is scrubbed from the JSON file. No user action required.
- **`html_gen.configure_page(footer=..., fonts=...)`.** Page-level rendering controls for the web framework.
- **System-font default for web pages.** New pages render with the platform's native font stack — no third-party CDN fetch, faster first paint, works offline. The legacy Inter-from-Google-Fonts behaviour is one setting away: `configure_page(fonts='cdn')`.

### Changed
- **Hardcoded `Powered by EPL v1.0` footer is gone.** Pages now omit `<footer>` entirely by default. Apps wanting branding set it explicitly: `configure_page(footer='© 2026 ACME Corp')`. Footer text is HTML-escaped to prevent XSS via injected content.
- **JSON-fallback path retained.** When no keyring backend is available (e.g. headless Linux CI without `libsecret`), `configure_cloud` falls back to writing the key into `ai_config.json` with `chmod 0600` — same as pre-9.2.0. Behaviour is logged in the saved file (no `api_key` field == keyring used).

### Security
- **Plaintext API keys no longer touch disk on systems with a working keyring backend.** Closes the gap flagged in the prior security audit where Gemini/Groq keys lived in cleartext JSON.
- **Footer XSS hardening.** User-provided footer text is HTML-entity-escaped (previously the hardcoded string had no escape path because there was no user input — the new control plane needs it).

### Tests
- 14 new tests across `tests/test_ai_keyring.py` and `tests/test_html_gen_config.py` covering: keyring present, keyring absent, legacy migration, keyring read failure, `clear_cloud` wipe, footer XSS, font opt-in, invalid font value rejection. Full suite remains green: 1518 passed, 5 skipped.

### Packaging
- `pyproject.toml` declares `keyring>=24.0.0` as the new `[secure]` optional dep and includes it in `[all]`.

### Migration notes
- **No code change required for existing users.** Re-run any command that reads cloud config (`epl ai status`, etc.) and the migration happens transparently.
- Apps that relied on the visible `Powered by EPL v1.0` footer must opt back in: `from epl import html_gen; html_gen.configure_page(footer='Powered by EPL v9.2')`.

---

## VS Code Extension [2.2.0] — 2026-06-01

Brings the VS Code extension up to v9.x parity with the language runtime. No breaking changes.

### Added
- **`EPL: Run Current File with Bytecode VM` command.** Executes the active file via `epl vm`, the bytecode VM that reached full interpreter parity in EPL v9.1.0. Surfaced alongside the existing `EPL: Run Current File` command in the command palette.
- **`epl.watch.timeout` setting.** Plumbs the v9.0.0 `--timeout=<seconds|none>` flag into the `EPL: Watch Current File` command. Empty (default) preserves the new uncapped-by-default behaviour; set a number for a per-run cap, or `none` to be explicit.

### Changed
- **README updated for v9.x.** Feature matrix now shows the correct stdlib function count (725+ — was 90+), advertises the bytecode VM backend, and documents the previously-hidden `epl.serve.port`, `epl.serve.observability`, and new `epl.watch.timeout` settings.
- **Stale internal version refs corrected.** Header comment dropped the hard-coded `v2.1.0` tag. PyPI update-checker code comment example bumped from `v7.6.0` → `v9.1.0` so future readers don't mistake it for a current claim.

### Migration notes
- No user action required. Existing keybindings, settings, and the LSP wire format are unchanged.

---

## [9.1.0] — 2026-06-01

VM parity release. The bytecode VM (`epl run --vm`) now matches the tree-walking interpreter on every documented divergence, and the source distribution ships the runtime assets the wheel already includes.

### Fixed
- **Recursive function calls now produce correct results in the VM.** The compiler pre-registers a function's own name before compiling its body, so a recursive call resolves to `Op.CALL` instead of falling through to `Op.CALL_BUILTIN`. `factorial(5)` now returns `120` (was `24`) and `fib(10)` returns `55` (was `6`).
- **`JUMP_IF_FALSE` / `JUMP_IF_TRUE` always pop their condition.** Previously the truthy branch left the value on the stack, corrupting subsequent operations. This single bug was the root cause behind four documented divergences: `continue` inside loops, FizzBuzz chained `Otherwise If`, list-comprehension-style mutation, and (via stack corruption inside recursive frames) Fibonacci/factorial.
- **`Try` / `Catch` now intercepts VM-level runtime errors.** `VMError` (e.g. division by zero, unknown class) routes through the active `try_stack` and lands the error message in the catch binding, matching interpreter semantics. Previously only Python-native exceptions were caught and any runtime error escaped the handler.
- **Class construction now works end-to-end.** `Op.NEW_INSTANCE` unpacks the `(class_name, arg_count)` tuple emitted by the compiler, looks up the class by string name (was failing with `Unknown class: ('Dog', 0)`), and delegates to `_call_constructor` so constructor arguments are passed correctly.
- **Class property defaults are now preserved in the VM.** `VarDeclaration` defaults inside a class body (e.g. `name = "Rex"`) are evaluated at compile time from the AST `Literal` value instead of being silently stored as `None`.
- **`epl/models/Modelfile` is now included in the source distribution.** A `global-exclude Modelfile` rule in `MANIFEST.in` was overriding the package-data inclusion in `pyproject.toml`, so `pip install` from sdist was shipping an incomplete `epl.models` package. Top-level `main.py` is also now explicitly included.

### Changed
- **`tests/test_consistency.py` reorganised.** The five `KNOWN_DIVERGENCE_CASES` and two `KNOWN_BACKEND_GAP_CASES` previously documenting VM divergences have all been promoted to `PARITY_CASES`; both buckets are now empty/removed. The full parity suite — 52 cases — runs against both backends with no expected failures.
- **`tests/test_release_packaging.py` no longer requires a top-level `bundle.py`.** The file was moved to `scripts/bundle.py` in an earlier refactor and `scripts/` is not shipped to end users; the test contract has been updated to reflect that.

### Migration notes
- No source changes required. Programs that previously produced incorrect output under `epl run --vm` (recursion, `continue`, `try`/`catch`, classes) will now match interpreter output. If you had workarounds in place that relied on the buggy VM behaviour, remove them.

---

## [9.0.0] — 2026-05-30

Enterprise hardening release. A focused security & robustness sweep across the interpreter, standard library, database layer, AI cloud integration, file watcher, and CLI. No new language features — every change makes existing surface area safer, more predictable, or easier to operate.

### Security
- **SQL injection — defense-in-depth across all database surfaces.** Stdlib `db_update`, `db_delete`, `db_count`, and `db_table_info` now reject table and column names that are not valid SQL identifiers (`^[A-Za-z_][A-Za-z0-9_]*$`) before any query is built. The same validation extends to `QueryBuilder` (`select`, `where_eq`, `where_like`, `where_in`, `where_gt`, `where_lt`, `where_between`, `where_null`, `where_not_null`, `order_by`, `group_by`, `join`, `left_join`) in `epl/database.py` and to `insert`, `insert_many`, `update`, `delete`, `find_by_id`, and `count` in `epl/database_real.py`. Numeric `LIMIT`/`OFFSET` values are coerced through `int()` so non-numeric strings fail loudly instead of being spliced into SQL. `ORDER BY` direction is restricted to `ASC`/`DESC`. Identifiers are now consistently double-quoted in emitted SQL.
- **Command injection — `exec_async` no longer uses `shell=True`.** Accepts either a list of argv tokens or a single command string that is parsed with `shlex.split` (POSIX rules on Unix, Windows rules on NT). `kill_process` and `env_delete` have been added to the interpreter sandbox alongside the existing `exec`/`file_*`/`env_set` denylist so untrusted scripts cannot escape it.
- **`epl doctor` no longer spawns subprocesses through the shell on Windows.** Commands run as explicit argv with `shell=False`; `shutil.which` resolves `.cmd`/`.bat` shims (npm, etc.) safely.
- **AI cloud config moved out of the package directory.** API keys are now stored in a per-user XDG-aware location — `%APPDATA%\epl\ai_config.json` on Windows, `$XDG_CONFIG_HOME/epl/ai_config.json` (default `~/.config/epl/ai_config.json`) on POSIX — and chmod'd to `0600` on POSIX. Existing `epl/.ai_config.json` files are migrated automatically on first read. Gemini requests now send the API key via the `x-goog-api-key` header instead of as a URL query parameter, keeping it out of proxy logs and shell history.

### Fixed
- **Generators no longer return stale values on timeout.** `EPLGenerator` previously waited 30s for the next yielded value and silently returned the previous value if the body was wedged. It now raises `EPLRuntimeError` with the generator name, the timeout it hit, and guidance to set `EPL_GENERATOR_TIMEOUT`. The timeout is configurable via `EPL_GENERATOR_TIMEOUT=<seconds|none|off>` for long-running computations.
- **`epl watch` no longer kills long-running programs at 60s.** The hard-coded subprocess cap is gone; runs are uncapped by default. Pass `--timeout=<seconds>` (or `--timeout=none`) to opt back into a cap. The watch dispatcher now also warns when an unknown `--flag` is passed instead of silently ignoring it.
- **CLI error reporting is now consistent across `main.py`.** All command dispatchers route through `_cli_error_report` / `_cli_error_exit` helpers, which print a one-line summary by default and a full traceback when `EPL_DEBUG=1` is set or `--debug` is passed anywhere on the command line. ~25 ad-hoc `except Exception:` blocks were collapsed into this single path.

### Changed
- **AI config loading is now cached.** `_load_config()` no longer hits disk on every prompt; `configure_cloud()` / `clear_cloud()` invalidate the cache as expected.
- **`requirements.txt` rewritten for clarity.** Required runtime dependencies (`gunicorn`, `flask`) are separated from optional extras (encryption, PostgreSQL, MySQL, LLVM, Redis, mobile, ML, dev tooling), each commented with its purpose. Pure-standard-library features are no longer listed as commented-out requirements.

### Added
- **`tests/test_security_hardening.py`** — covers stdlib SQL identifier validation, sandbox additions, shell-less `exec_async`, AI config path & permissions, and Gemini header auth.
- **`tests/test_correctness_hardening.py`** — covers generator yield-timeout behavior and watcher `--timeout` plumbing.
- **`tests/test_database_hardening.py`** (16 tests) — covers `QueryBuilder` and `database_real` identifier quoting, rejection of injection attempts in every column/table/order-by/limit slot, and the `IN ()` degenerate-case shortcut.

### Migration notes
- **AI config:** First run of `epl ai …` after upgrade migrates `epl/.ai_config.json` to the per-user location automatically. If you have keys checked into a fork, rotate them — file location change does not remediate prior exposure.
- **`exec_async`:** Scripts that relied on shell features (pipes, redirects, `&&`) in `exec_async` need to either pass an argv list, switch to `exec`/`exec_output` (which retain their previous semantics), or explicitly invoke a shell (`exec_async(["bash", "-c", "..."])`).
- **`epl watch`:** Workflows that depended on the implicit 60s kill should now pass `--timeout=60` explicitly.
- **Generators:** Code that swallowed the previous silent-timeout behavior must now catch `EPLRuntimeError` or extend the timeout via `EPL_GENERATOR_TIMEOUT`.

---

## [8.0.0] — 2026-05-26

### Added
- **`epl watch`** — File watcher with auto-reload for development (PR #47 by @imkoushal)
  - Watches `.epl` files for changes and auto-reruns the program
  - Zero external dependencies (polling-based using `os.stat`)
  - `--test` flag to re-run tests instead of the program
  - `--clear` flag to clear screen before each re-run
  - `--debounce=MS` to customize debounce interval (default: 300ms)
  - 19 unit tests (all passing)
- **`epl doctor`** — Environment health checker (PR #48 by @imkoushal)
  - 11 diagnostic checks: Python version, EPL installation, Node.js/npm, Git, pip, platform, disk space, terminal encoding, project structure, dependencies
  - Color-coded output with actionable fix hints
  - `--json` flag for CI/automation integration
  - 27 unit tests (all passing)
- **Enterprise Discord AI Agent Enhancements** (`examples/discord_agent/`)
  - FAQ auto-reply engine — instant responses without LLM for common questions
  - XP / Leveling system — users earn XP per message, level up through 7 ranks (Newcomer → EPL Legend)
  - Support ticket system — `!ticket` command with automated tracking and founder alerts
  - Anti-raid protection — detects mass joins (10+ in 60s) and alerts `#bot-control`
  - Auto-moderation — instant deletion of invite links, mass mentions, and spam
  - Auto-welcome — rich embed welcome messages with EPL code examples for new members
  - Server milestone celebrations — automated announcements at 10, 25, 50, 100, 250, 500, 1000 members
  - Corrected EPL code knowledge — bot now generates syntactically correct EPL with proper string quoting
  - Concise responses — short questions get short answers, no more walls of text

### Changed
- **VS Code Extension v2.1.0** — Added `epl.watch` and `epl.doctor` commands, enhanced TextMate grammar with missing keywords from lexer/parser (Generic, Where, Yields, Spawn, Parallel, Lambda, Breakpoint, Declare, Let), improved method call highlighting, and new `has` keyword support for class properties
- Version bump to `8.0.0` for PyPI distribution

---

## [7.8.2] — 2026-05-24

### Added
- **Enterprise Discord Agent** — Added a 100% EPL native AI Community Manager for Discord (`examples/discord_agent/`) with advanced spam defense, server-aware routing, and terminal-free background execution scripts.

---

## [7.8.1] — 2026-05-23
- **TaskFlow Pro Max** — Completely overhauled the `taskflow_saas` example with a high-energy, unapologetic Neo-Brutalist UI architecture.
  - Implemented solid box-shadow physics and mechanical hover/active states.
  - Migrated from generic glassmorphism to strict geometric brutalism (0px border radius, sharp contrast, Acid Green accents).

### Fixed
- **Form Parsing Robustness** — Resolved parsing issues in EPL's web backend where empty optional form fields caused exceptions, by enforcing the safe `web_request_param()` pattern.
- **Avatar Letter Fix** — Fixed standard library `uppercase` usage for avatar initialization in session cookies.

---

## [7.6.0] — 2026-05-19

### Added
- **Enterprise Documentation Overhaul** — All project documentation updated to enterprise-grade quality with consistent branding, comprehensive contributor guides, and professional formatting
- **Formal Grammar Specification v7.6** — Updated EBNF grammar to cover JS/TS bridge syntax, Generic types, 3D/Canvas blocks, and all v7.x additions

### Changed
- **CI/CD Pipeline Stabilization** — Achieved 100% green build across the full test matrix (Ubuntu, macOS, Windows × Python 3.11, 3.12)
  - Replaced unstable `import main` with `importlib.util` dynamic path loading
  - Added `pytest.importorskip` guards for optional dependencies (`llvmlite`)
  - Fixed `memory_usage` stdlib test for Windows CI compatibility (`>= 0` vs `> 0`)
  - Switched to explicit stable test file list (61 files) with `shell: bash` for cross-platform line continuation
  - Added `pytest-cov` to CI dependencies for coverage reporting
- **Test Harness Hardening** — Decoupled CI tests from local-only development files (`main.py`) using `@skipUnless` decorators and conditional imports

### Infrastructure
- Version bump to `7.6.0` for PyPI distribution
- Coverage threshold override (`--cov-fail-under=0`) for CI subset runs

## [7.5.2] — 2026-05-12

### Added
- **JavaScript/TypeScript Bridge** — New `Use javascript "library"` / `Use typescript "library"` syntax for accessing the NPM ecosystem from EPL
  - `epl/js_bridge/` — Persistent Node.js subprocess bridge with JSON-RPC protocol over stdin/stdout
  - `JSModule` wrapper class in `interpreter.py` — enables `module.method()` and `module.property` access
  - NPM auto-install for allowlisted packages via `package_manager.py` integration
  - `epl jsinstall <pkg>` / `epl jsremove <pkg>` / `epl jsdeps` — CLI commands for npm dependency management
  - JS transpiler support — `UseJSStatement` emits proper ESM `import` or CommonJS `require`
  - Error explainer patterns for Node.js-not-installed, missing modules, and bridge crashes
  - 34 unit tests covering parser, AST, serialization, transpiler, and Node.js integration
- **Observability Module** (`epl/observability.py`) — Production-grade health checks (`/_health`), readiness probes (`/_ready`), Prometheus-format metrics (`/_metrics`), and structured JSON logging with thread-safe request tracking
- **Kubernetes Manifest Generator** (`epl/k8s_gen.py`) — Generate Namespace, ConfigMap, Deployment, Service, Ingress, and HorizontalPodAutoscaler YAML from CLI with strict input validation
- **Cloud Deploy** (`epl/cloud_deploy.py`) — One-command deployment config generation for AWS ECS/ECR, GCP Cloud Run, and Azure Container Apps with Docker image handling
- **Style/Layout Generation** — CSS style blocks, responsive layout containers, and cross-platform styling with XSS-hardened output
- **3D/Canvas Support** — `Scene` blocks for WebGL 3D rendering and `Canvas` draw commands (rect, circle, line, text, path) with batched rendering
- **Cross-Platform Generation** — iOS (SwiftUI), Desktop (Compose Multiplatform), and Web/WASM target generators
- **Cloudflare Workers Configuration** — Edge deployment support via `wrangler.jsonc`

### Security
- **Input Validation** — Strict regex validation for all user inputs (app_name, image, region, account_id, port, service_type, hostname) in `k8s_gen.py` and `cloud_deploy.py` to prevent shell/YAML injection
- **Thread Safety** — Added `_readiness_lock` for concurrent readiness access in observability module
- **XSS Hardening** — HTML sanitization in style/layout and canvas output generation
- **CSS Injection Prevention** — Strict validation of CSS property values in style blocks

## [7.5.1] — 2026-05-11

### Added (PR Integrations)
- **AI Error Explainer** (PR #3 by @imkoushal) — `epl fix <file>` command with 27-pattern error analysis, "Did you mean?" suggestions, Python/JS foreign keyword detection, and optional AI-powered deep analysis via Ollama/cloud backends.
- **`--ai-errors` CLI flag** — Enable error explainer diagnostics during normal `epl run` execution.
- **`to_context_dict()`** on `EPLError` — Structured error context with surrounding source lines for AI consumption.
- **AWS Cloud Backend** (PR #4 by @D1v3shh) — `cloud_*` stdlib functions for S3 (upload/download/list/read/write/delete/exists/buckets), Lambda (invoke), and SQS (send/receive/delete) with lazy-loaded boto3, thread-safe client caching, and `pip install "eplang[cloud]"` optional dependency.
- **`epl-cloud` Official Package** — Registry entry, EPL source, examples, and `epl.toml` manifest.
- **44 new tests** covering error explainer patterns and cloud backend operations.

### Fixed
- **VS Code Terminal Command Injection** — Replaced unsafe string interpolation in `extension.js` with a safe `buildEplCommand()` builder that properly quotes file paths for both PowerShell and Unix shells.
- **Syntax Reference Ternary Example** — Corrected `Set label = "big" if ...` to the canonical parser form `Set result to "big" if x > 10 otherwise "small"`.
- **Playground Thinking-Block Rendering** — AI "Thinking Process" blocks are now extracted before markdown escaping and re-injected as styled HTML, preventing display corruption.

### Changed
- **Test Modernization** — Migrated CLI dispatcher tests from `main.py` file reads to direct `epl.cli.cli_main` source introspection, aligning with the authoritative CLI architecture.
- **Landing Page Version** — Updated `docs/index.html` badge to `EPL v7.5.1 IS LIVE!`.
- **Extension Version Logging** — `extension.js` now reads version dynamically from `package.json` instead of a hardcoded string.

## [7.5.0] — 2026-04-28

### Added
- **Scientific Packages** — Merged PR #2 adding `epl-science`, `epl-plot`, `epl-learn`, `epl-dataframe`, and `epl-array` official packages with Python bridge backends.
- **`Use` Syntax** — `Use python "json" as json_mod` for importing Python modules directly into EPL scope.
- **Official `.epl` File Icon** — VS Code extension now contributes a dedicated file icon for `.epl` files in the explorer.
- **Lint, Profile, and Build Commands** — `epl.lintFile`, `epl.profileFile`, and `epl.compileFile` commands added to the VS Code extension with editor title bar integration.
- **`.vscodeignore`** — Marketplace package now excludes `node_modules`, `.vsix` artifacts, and large PDFs.

### Fixed
- **`epl.run` Not Found** — Commands are now registered before the LSP client starts, preventing the "command not found" error when the Language Server fails.
- **Duplicate Dict Keys** — Removed duplicate keys in `epl/errors.py`.
- **Deprecated `asyncio` Calls** — Updated to modern `asyncio` API patterns.

### Changed
- **AI Provider Hardening** — Strengthened cloud AI provider configuration and error handling.
- **Extension Icon** — Updated to the new premium `epl_logo_minimal.png` design.

## [7.4.3] — 2026-04-17

### Added
- **Browser AST-Aware Copilot** — The web playground now features a live AST analysis engine powered by Pyodide, securely linked to an Edge AI backend for syntax-specific debugging.
- **Dynamic AI Thinking Mode** — Copilot natively evaluates complex architectural requests using a multi-step semantic logic sequence.
- **Strict Grammar SSOT** — Single Source of Truth enforced across CLI and Edge workers to accurately identify Enums, Ternaries, Error Handling, and File I/O naturally.
- **Root Repository Restructuring** — Purged thousands of lines of dev scratchpads and leaked release artifacts to enforce an industry-standard project structure.
- **Kubernetes Manifest Generator** — `epl deploy k8s` generates production-ready
  Kubernetes manifests: Namespace, ConfigMap, Deployment (with liveness/readiness
  probes, non-root security context, resource limits), Service, Ingress (with
  optional TLS), and HorizontalPodAutoscaler.
  - CLI: `epl deploy k8s --image myapp:1.0 --host myapp.example.com --tls`
  - All manifests written to `./k8s/` by default
- **Bug fix** — Fixed `tests/test_llvm.py` crashing on Python 3.13 when
  `llvmlite` is not installed.

## [7.3.2] — 2026-04-06

### Fixed
- **REPL Python 3.9–11 Compatibility** — Fixed f-string syntax error (`{'━' * 55}` nested quotes) in `epl/repl.py` that crashed on Python 3.9, 3.10, and 3.11. Now uses a pre-computed variable compatible with all supported Python versions.

## [7.3.1] — 2026-04-06

### Added
- **REPL Modernization** — Replaced basic interactive shell with a rich `prompt_toolkit` interface providing real-time syntax highlighting, ghost-text auto-suggestions from history, and robust multi-line continuation tracking.
- **Stdlib Domain Modules** — Architected safe, lazy-loaded domain modules (`epl/stdlib_modules/web.py`, `.db.py`, `.concurrency.py`, `.math.py`, `.collections.py`) as clean import facades directly on top of the `stdlib` monolithic core. Allows `Import "web" from stdlib` with full API isolation.
- **New Examples** — Added high-quality demo applications: `examples/todo_app/` (SQLite ORM + REST API), `examples/cli_calculator.epl` (CLI parsing and functions), and `examples/guessing_game.epl` (Randomness, loops, and IO).
- **First-party Modularization** — Scaffolded the `epl-auth` boilerplate to test dependencies and package repository concepts.

## [7.2.0] — 2026-04-06

### Added
- **Documentation Website** — Full MkDocs Material docs at [abneeshsingh21.github.io/EPL](https://abneeshsingh21.github.io/EPL)
  - Getting started guide, language reference, stdlib reference
  - Web, Database, and Android development guides
  - Examples gallery with real-world projects
  - Online playground integration
- **LSP Autocomplete Expansion** — 90+ new stdlib function signatures for IDE autocomplete, hover docs, and signature help (database, web, crypto, concurrency, GUI, game dev, ML)
- **Project Templates** — `epl new --template android` and `epl new --template fullstack` (7 templates total)
- **Error Diagnostics** — 19 new error hint patterns for common mistakes (type coercion, database, web server, block matching)
- **CI/CD** — GitHub Actions for automated testing (3 OSes × 3 Python versions) and docs auto-deploy

## [7.1.0] — 2026-04-06

### Added
- **Production Server Defaults** — `epl serve` now defaults to waitress/gunicorn/uvicorn
  - `--dev` flag for development mode with hot-reload
  - `--engine` flag for manual server selection
  - Auto-install of waitress if no production server found
- **Android Build Pipeline** — `epl android --build` compiles APKs via Gradle
  - Auto-detection of ANDROID_HOME across Windows/Linux/macOS
  - `--name` flag for custom app display name
- **Stdlib Modularization** — Domain registry mapping 725 functions to 33 domains
  - `epl/stdlib_modules/` package with lookup utilities
  - 100% coverage of all stdlib functions
- **Example Projects** — `examples/hello_web`, `examples/todo_api`, `examples/calculator`

## [7.0.1] — 2026-04-05

### Added
- LLVM compiler backend with native executable output
- Bytecode VM for faster interpretation
- Package manager with `epl.toml` manifest
- Web framework with WSGI/ASGI adapters
- ORM with models, migrations, relationships
- Concurrency primitives (threads, channels, mutexes, barriers)
- Desktop GUI via tkinter
- Game development via Pygame
- Data science via Pandas/NumPy
- Machine Learning via scikit-learn/PyTorch
- Android project generation via Kotlin transpilation
- iOS project generation via Swift transpilation

## [1.0.0] — 2024

### Initial Release
- EPL language interpreter with tree-walking evaluation
- English-like syntax for variables, functions, classes, modules
- 725 standard library functions
- VS Code extension with LSP support
- Interactive REPL
- Code formatter and type checker
