# Changelog

All notable changes to EPL (English Programming Language) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

> **Author:** Abneesh Singh -- singhabneesh250@gmail.com
> **Copyright:** 2024-2026 Abneesh Singh -- All Rights Reserved

---

## [7.0.0] -- 2026-04-04 -- First Public Release

### Milestone
- Published to PyPI: `pip install eplang` -- EPL is now publicly installable worldwide
- VS Code Extension built and packaged for the Marketplace

### Security Fixes
- Pickle RCE: Replaced `pickle.loads()` with `_SafeUnpickler` (allowlist-only deserialization)
- Recursion bomb: `MAX_CALL_DEPTH = 500` in both Interpreter and VM engines
- FFI sandbox: `EPL_FFI_SANDBOX=1` blocks all FFI; `EPL_FFI_ALLOWLIST` for per-library allowlist
- Scope chain depth limited to 500 (via `EPL_MAX_SCOPE_DEPTH`)

### Added
- `epl check` -- project-wide static type checking (E001-E003 diagnostic codes)
- `epl fmt` -- source code formatter
- `epl upgrade` -- self-update command
- Type checker v2.0: unused variable detection (W002), fuzzy suggestions
- VM constant folding, EPLCoverageTracker, GitHub issue templates
- Showcase apps: todo_app.epl, rest_api_jwt.epl, discord_bot.epl, blog_engine.epl
- Dockerfile, MANIFEST.in, NOTICE, CONTRIBUTORS.md

### Fixed
- AssertionError class name corrected
- Thread-safe source context in errors.py
- Duplicate EPLChannel/EPLTimer classes removed from async_io.py
- Async event loop shutdown() drains pending tasks before stopping

### Copyright
- Official copyright: Abneesh Singh -- singhabneesh250@gmail.com
- "EPL" and "English Programming Language" are trademarks of Abneesh Singh

---
# Changelog

All notable changes to EPL are documented here.

## [7.0.0] — 2026

### Changed
- Unified production tooling around `epl.toml` while keeping `epl.json` as a legacy fallback.
- Fixed the module CLI so manifest-based builds, strict type checking, and sandboxed execution work correctly.
- Hardened pytest collection to exclude legacy script-style runners from structured pytest runs.
- Updated release metadata and docs to align with EPL v7.0.

### Packaging
- Renamed the standalone CLI bundler script from `build.py` to `bundle.py` so `python -m build` works with the standard Python packaging frontend.
- Added wheel/sdist package data for native `.epl` stdlib modules, `registry.json`, `runtime.c`, and the AI `Modelfile`.
- Expanded PyInstaller bundling assets so packaged EPL binaries include the same runtime files expected by source installs.

## [4.2.0] — 2025

### Added

#### Native EPL Standard Library Modules
- 9 native `.epl` modules written in EPL itself (not Python):
  - `math` — factorial, fibonacci, is_prime, gcd, lcm, statistics (mean, median, variance, std_dev)
  - `string` — capitalize, slug, pad_left/pad_right, truncate, word_count, char_count, repeat_string
  - `collections` — flatten, chunk, unique, zip_pair, take/drop, stack (push/pop/peek), queue
  - `functional` — map_list, filter_list, reduce_list, compose, pipe, curry, memoize, once
  - `datetime` — format_duration, time_ago, is_weekend, days_until, format_date
  - `crypto` — md5, sha256, base64_enc/base64_dec, hex_enc, uuid, random_string
  - `http` — http_fetch, http_send, parse_json, to_json, encode_url
  - `io` — read_whole_file, write_whole_file, file_lines, file_head, file_tail
  - `testing` — test, expect_equal, expect_true, expect_false, expect_contains, test_summary
- `epl/stdlib/registry.json` — Module registry with descriptions and file paths
- `epl modules` CLI command — Lists all available standard library modules

#### Import System Improvements
- AST caching (`_ast_cache`) — Parsed files are cached by absolute path, eliminating redundant lex/parse on re-import
- `_parse_file()` method — Centralised file reading, lexing, and parsing with caching
- Module function recursion — Functions accessed via `Module.method()` or `Module::method()` can call other module functions

#### REPL Enhancements
- `.vars` command now works correctly (shows variables + defined functions with parameter names)
- Persistent REPL history across sessions (`~/.epl_history`)
- Windows readline support via `pyreadline3` fallback

#### CLI
- `epl modules` command — Discover available standard library modules
- Python 3.9+ version guard with friendly error message (both `main.py` and `epl/cli.py`)

### Changed
- `_import_and_exec()` and `_import_as_module()` refactored to use shared `_parse_file()` method
- REPL `.vars` handler uses `interpreter.global_env` (was incorrectly using `interpreter.env`)

### Fixed
- **Security: Removed `shell=True`** from `_exec()` and `_exec_output()` in `epl/stdlib.py` — Eliminates command injection vulnerability. Now raises `EPLRuntimeError` on invalid commands.
- REPL `.vars` crash — was accessing non-existent `interpreter.env` attribute
- `median()` in native math module — was using float division result as list index (now uses `floor()`)
- Module constants accessible via both `Module::CONST` and `Module.CONST` syntax
- F-string syntax compatibility (Python < 3.12) in `_list_modules()`

---

## [4.1.0] — 2025

### Added

#### Pluggable Store & Session Backends
- `epl/store_backends.py` — Abstract `StoreBackend` and `SessionBackend` interfaces
- `MemoryStoreBackend` / `MemorySessionBackend` — In-process (default, fast)
- `SQLiteStoreBackend` / `SQLiteSessionBackend` — File-based, survives restarts
- `RedisStoreBackend` / `RedisSessionBackend` — Shared across workers + restarts
- `configure_backends(store='memory', session='memory', **kwargs)` API
- CLI flags: `--store memory|sqlite|redis`, `--session memory|sqlite|redis`

#### Production Server (`serve` command)
- `python main.py serve <file.epl>` — Cross-platform production server
- Waitress on Windows, Gunicorn on Linux/macOS, wsgiref fallback
- `--port`, `--workers`, `--reload` flags
- `serve()` function in `epl/deploy.py`

#### Hot Reload
- `epl/hot_reload.py` — File watcher + auto-restart for development
- `--reload` flag on `serve` command
- Polling-based (no external dependencies)

#### ASGI WebSocket Support
- `ASGIAdapter` now handles `websocket` scope type
- `_ASGIWebSocket` class with accept/send/receive/close
- Dict-based and simple handler patterns

#### Python Callable Route Handlers
- Routes can return `'callable'` type with a Python function
- Works across `EPLHandler`, `AsyncEPLServer`, `WSGIAdapter`

#### Advanced Template Engine
- 30 template filters: upper, lower, title, capitalize, strip, length, reverse, first, last, sort, join, truncate, default, replace, date, url_encode, nl2br, json, abs, int, float, round, safe, wordcount, striptags, batch, slice, unique, shuffle, dictsort
- Filter chaining: `{{ name|upper|truncate:10 }}`
- `{% set var = expr %}` tag
- Ternary expressions: `{{ x if condition else y }}`

### Changed
- Health check now returns dynamic version from `epl/__init__.py`
- `_data_store` proxy properly delegates `clear()`, `pop()`, `items()` to backends
- VS Code extension updated to v4.1.0 with EPL web/English keyword highlighting
- `startWebServer` command now uses `python main.py serve`
- `requirements.txt` and `pyproject.toml` list `waitress` and `redis` as optional deps

### Fixed
- `_StoreProxy.clear()` and `pop()` were no-ops (inherited from `dict`)
- `_StoreProxy.items()` always returned empty list (missing `all_collections()`)
- Gunicorn multi-worker mode: `_gunicorn_app` was `None` in forked workers

---

## [4.0.0] — 2025

### Added

#### LLVM Native Compiler
- Compile EPL programs to native executables via `python main.py compile <file.epl>`
- Support for integers, floats, strings, print, conditionals, loops, functions
- LLVM IR inspection via `python main.py ir <file.epl>`
- 26 compiler tests

#### Kotlin/Android Transpiler
- Transpile EPL to Kotlin via `python main.py kotlin <file.epl>`
- Full Android project generation via `python main.py android <file.epl>`
- Jetpack Compose UI mapping for GUI and web nodes
- Type inference via SymbolTable across scopes
- Sealed classes for enums, data classes, generics
- 30 transpiler tests

#### Bytecode Virtual Machine
- Stack-based bytecode VM with 68 opcodes
- 10-50x faster than tree-walking interpretation
- Peephole optimizer with instruction reindexing
- Dead code elimination
- Comparison constant folding
- Dict-based builtin dispatch (O(1) lookup)
- 43 VM tests

#### Package Manager v3.0
- SemVer class with full parsing, comparison, caret/tilde compatibility
- Version range parsing: exact, ^, ~, >=, <=, >, <, !=, compound, wildcard
- Transitive dependency resolution via BFS
- Dependency conflict detection with clear error messages
- Lockfile v2 with integrity hashes and required_by tracking
- Frozen install from lockfile
- Package validation (name format, semver, description, entry point)
- Pack command (zip + SHA256 checksum)
- Publish workflow (validate → pack → install → register)
- Update and update-all commands
- 91 package manager tests

#### Stability Improvements
- Short-circuit evaluation for `and`/`or` operators
- Clean error for `max()`/`min()` on empty lists
- Type checking for `sum()`, `sorted()`, `round()`, `sqrt()`, `log()`
- Overflow protection for `**` with exponent > 10000
- Negative repeat count protection
- `reduce()` on empty list without initial value raises clean error
- 42 stability tests

#### Documentation
- `docs/language-reference.md` — Complete syntax and built-in reference
- `docs/tutorials.md` — 11 step-by-step tutorials
- `docs/architecture.md` — Technical system overview
- `docs/package-manager.md` — Package management guide

#### Adoption Infrastructure
- `CONTRIBUTING.md` — Contributor guide
- `CHANGELOG.md` — Version history
- `CODE_OF_CONDUCT.md` — Community guidelines
- `.github/ISSUE_TEMPLATE/` — Bug report and feature request templates

### Changed
- Test count: 299 → 547+ (7 test suites)
- README updated with documentation links and current statistics

---

## [3.0.0] — 2024

### Added
- Web framework with routing, sessions, WebSocket support
- GUI toolkit (tkinter-based): windows, widgets, canvas, events, menus
- Package manager with init, install, uninstall, list
- Database ORM with Store/Fetch/Delete
- Debugger with breakpoints, stepping, watch expressions
- LSP server for editor integration
- Testing framework (Assert, AssertEqual, AssertThrows)
- AI assistant for code generation and explanation
- Static type system with optional annotations
- WSGI/ASGI server support
- Profiler with DAP debugging
- Async I/O support
- JavaScript transpiler (browser + Node.js targets)
- Standard library: 311 functions across 20+ modules
- 36 built-in packages

### Added (Language Features)
- Augmented assignment (`+=`, `-=`, `*=`, `/=`)
- Ternary expressions (`x If condition Otherwise y`)
- Enums and enum access
- Match/When pattern matching
- Super calls in class inheritance
- Try/Catch/Finally
- Module definitions and exports
- Interfaces and implements clauses
- Generics, abstract methods, static methods
- Yield, destructuring, spread expressions
- Chained comparisons
- Lambda expressions and higher-order functions

---

## [2.0.0] — 2024

### Added
- Classes and inheritance
- File I/O (read, write, append)
- Error handling (Try/Catch/Throw)
- Imports and module system
- Break/Continue in loops
- ForRange loops with step
- Maps/dictionaries
- Index access and assignment
- Slice access for lists and strings

---

## [1.0.0] — 2024

### Added
- Core language: variables, functions, conditionals, loops
- Data types: integers, decimals, text, booleans, nothing, lists
- Print/Input (Say/Ask)
- Repeat/While/ForEach loops
- User-defined functions with parameters and return values
- Binary and unary operators
- String concatenation and interpolation
- Comments via `Note:`

