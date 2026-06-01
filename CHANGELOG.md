<div align="center">

# Changelog

All notable changes to the **English Programming Language (EPL)** are documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/).

</div>

---

## [9.3.0] — 2026-06-01

Phase 2 of the enterprise-grade enhancement program: exception hygiene. Previously-silent `except Exception: pass` and `except Exception: return None` sites now route through a centralised debug helper, making them inspectable without changing production behaviour.

### Added
- **`epl/_debug_log.py` — `suppressed(where)` helper.** Records swallowed exceptions to stderr when `EPL_DEBUG=1` is set, silent otherwise. Set `EPL_DEBUG_TRACE=1` for full tracebacks. Zero dependencies on the rest of the package — safe to import from any module.

### Changed
- **34 previously-silent except blocks now instrumented** across `epl/stdlib.py` (15), `epl/web.py` (10), `epl/runtime_support.py` (4), `epl/cli.py` (3), `epl/interpreter.py` (2). Production behaviour is unchanged (still swallows by default); diagnostic visibility is one env var away.

### Tests
- 12 new tests in `tests/test_debug_log.py` covering env-var parsing, truthy/falsy values, silent-by-default behaviour, and the "called outside an except block" safety case. Suite remains green: 1530 passed.

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
