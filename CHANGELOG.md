# Changelog

All notable changes to EPL are documented in this file.

## [Unreleased]

### Added
- **JavaScript/TypeScript Bridge** — New `Use javascript "library"` / `Use typescript "library"` syntax for accessing the NPM ecosystem from EPL
  - `epl/js_bridge/` — Persistent Node.js subprocess bridge with JSON-RPC protocol over stdin/stdout
  - `JSModule` wrapper class in `interpreter.py` — enables `module.method()` and `module.property` access
  - NPM auto-install for allowlisted packages via `package_manager.py` integration
  - `epl jsinstall <pkg>` / `epl jsremove <pkg>` / `epl jsdeps` — CLI commands for npm dependency management
  - JS transpiler support — `UseJSStatement` emits proper ESM `import` or CommonJS `require`
  - Error explainer patterns for Node.js-not-installed, missing modules, and bridge crashes
  - 34 unit tests covering parser, AST, serialization, transpiler, and Node.js integration

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
